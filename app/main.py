import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.database import (
    FOCUS_CODES,
    FOCUS_DEPARTMENTS,
    FOCUS_DEPARTMENT_NAMES,
    STATE,
    connect,
    ensure_schema,
    json_object,
    now_utc,
)


BASE_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = BASE_DIR / "dist"
COMPANY_NAMES = {
    "K K ALLIANZE",
    "KAMAL KUMAR PARASMAL JAIN",
    "KAMAL KUMAR P JAIN",
}


class QuoteRequest(BaseModel):
    tender_numbers: list[str] = Field(min_length=1)


def normalise_tender_number(value):
    return " ".join(value.strip().upper().split()).replace(" /", "/").replace("/ ", "/")


def _iso_day(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _tender(row):
    result = dict(row)
    raw = json_object(result.get("raw_data_json"))
    result["title"] = result.get("title") or raw.get("title") or raw.get("tenderName")
    result["tender_number"] = result.get("tender_number", "")
    result["department_code"] = (result.get("department_code") or "").upper()
    result["department_name"] = (
        result.get("department_name")
        or FOCUS_DEPARTMENT_NAMES.get(result["department_code"])
    )
    result["bids_opened"] = bool(result.get("bids_opened_at"))
    result.pop("raw_data_json", None)
    return result


def _supplier_is_us(row):
    supplier_id = str(row.get("supplier_id") or "").strip()
    name = " ".join(str(row.get("supplier_name") or "").upper().split())
    return supplier_id == "5086" or name in COMPANY_NAMES


def _bid_summary(connection, tender_number):
    rows = connection.execute(
        """
        SELECT item_name, supplier_id, supplier_name, rate, total, rank, selected
        FROM bids WHERE state = ? AND tender_number = ?
        ORDER BY item_name, rank, supplier_name
        """,
        (STATE, tender_number),
    ).fetchall()
    bids = [dict(row) for row in rows]
    own = [row for row in bids if _supplier_is_us(row)]
    selected = [row for row in bids if row.get("selected") in (1, True, "1", "true", "TRUE")]
    l1 = selected[0] if selected else next((row for row in bids if row.get("rank") == 1), None)
    our_rank = min((row["rank"] for row in own if row.get("rank") is not None), default=None)
    our_total = next((row.get("total") for row in own if row.get("total") is not None), None)
    l1_total = l1.get("total") if l1 else None
    try:
        difference = float(our_total) - float(l1_total) if our_total is not None and l1_total is not None else None
    except (TypeError, ValueError):
        difference = None
    return {
        "bids": bids,
        "bids_opened": bool(bids),
        "our_rank": our_rank,
        "our_rate": next((row.get("rate") for row in own if row.get("rate") is not None), None),
        "our_total": our_total,
        "l1_name": l1.get("supplier_name") if l1 else None,
        "l1_rate": l1.get("rate") if l1 else None,
        "l1_total": l1_total,
        "difference": difference,
        "result": (
            "won" if own and any(
                row.get("rank") == 1
                and _supplier_is_us(row)
                and row.get("selected") in (1, True, "1", "true", "TRUE")
                for row in bids
            )
            else "lost" if own and selected
            else "pending" if bids
            else "not_public"
        ),
    }


def _base_tender_query(connection):
    return connection.execute(
        "SELECT t.* FROM tenders t WHERE t.state = ? AND coalesce(t.out_of_scope, 0) = 0",
        (STATE,),
    ).fetchall()


def _recent_changes(connection, limit=20):
    rows = connection.execute(
        """
        SELECT id, tender_number, change_type, old_value, new_value, created_at
        FROM change_events
        WHERE state = ? AND date(created_at, 'localtime') = date('now', 'localtime')
        ORDER BY id DESC LIMIT ?
        """,
        (STATE, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def _departments(connection):
    counts = {
        str(row["department_code"]).upper(): row["count"]
        for row in connection.execute(
            """
            SELECT department_code, count(*) AS count FROM tenders
            WHERE state = ? AND coalesce(out_of_scope, 0) = 0
            GROUP BY department_code
            """,
            (STATE,),
        )
        if row["department_code"]
    }
    names = {
        str(row["department_code"]).upper(): dict(row)
        for row in connection.execute(
            "SELECT department_code, department_name, name_verified, name_source FROM focus_departments WHERE state = ?",
            (STATE,),
        )
    }
    return [
        {
            "code": code,
            "portal_id": portal_id,
            "name": names[code]["department_name"] if names.get(code) else code,
            "count": counts.get(code, 0),
            "name_verified": bool(names.get(code) and names[code]["name_verified"]),
            "name_source": names[code]["name_source"] if names.get(code) else "department code",
        }
        for code, portal_id in FOCUS_DEPARTMENTS
    ]


def _scan_health(connection):
    rows = connection.execute(
        """
        SELECT source_name, status, started_at, completed_at, message, last_successful_scan_date
        FROM scan_state WHERE state = ? AND source_name IN ('kppp', 'quote-watch')
        """,
        (STATE,),
    ).fetchall()
    by_source = {row["source_name"]: dict(row) for row in rows}
    primary = by_source.get("kppp") or {
        "status": "not_started",
        "started_at": None,
        "completed_at": None,
        "message": "No successful public portal scan has been recorded.",
        "last_successful_scan_date": None,
    }
    primary["quote_watch"] = by_source.get("quote-watch", {
        "status": "not_started",
        "started_at": None,
        "completed_at": None,
        "message": "No quoted-tender checks have been recorded.",
    })
    return primary


def _get_tender(connection, tender_number):
    row = connection.execute(
        """
        SELECT t.* FROM tenders t
        WHERE t.state = ? AND upper(t.tender_number) = upper(?)
          AND coalesce(t.out_of_scope, 0) = 0
        """,
        (STATE, tender_number),
    ).fetchone()
    quote = connection.execute(
        """
        SELECT source, added_at, last_checked_at, bids_opened_at
        FROM quoted_tenders WHERE state = ? AND upper(tender_number) = upper(?)
        """,
        (STATE, tender_number),
    ).fetchone()
    if row is None and quote is None:
        return None
    result = _tender(row) if row else {
        "tender_number": normalise_tender_number(tender_number),
        "department_code": normalise_tender_number(tender_number).split("/", 1)[0],
        "status": "NOT_YET_FOUND",
        "title": None,
        "created_at": None,
    }
    items = connection.execute(
        """
        SELECT item_code, item_name, quantity, unit, rate, total
        FROM tender_items WHERE state = ? AND tender_number = ? ORDER BY id
        """,
        (STATE, result["tender_number"]),
    ).fetchall()
    timeline = connection.execute(
        """
        SELECT previous_status, new_status, changed_at, note
        FROM tender_status_history WHERE state = ? AND tender_number = ?
        ORDER BY id DESC
        """,
        (STATE, result["tender_number"]),
    ).fetchall()
    result.update(_bid_summary(connection, result["tender_number"]))
    result["items"] = [dict(item) for item in items]
    result["timeline"] = [dict(item) for item in timeline]
    result["quote"] = dict(quote) if quote else None
    result["quoted"] = quote is not None
    return result


def _record_change(connection, tender_number, change_type, old_value, new_value):
    if old_value == new_value:
        return None
    cursor = connection.execute(
        """
        INSERT INTO change_events(state, tender_number, change_type, old_value, new_value, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (STATE, tender_number, change_type, old_value, new_value, now_utc()),
    )
    return cursor.lastrowid


@asynccontextmanager
async def lifespan(_app):
    ensure_schema()
    yield


app = FastAPI(title="KPPP Local Procurement Monitor", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health():
    try:
        with connect() as connection:
            tender_count = connection.execute(
                "SELECT count(*) FROM tenders WHERE state = ? AND out_of_scope = 0",
                (STATE,),
            ).fetchone()[0]
            return {"status": "ok", "database": "connected", "tenders": tender_count}
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc


@app.get("/api/dashboard")
def dashboard():
    with connect() as connection:
        tenders = [_tender(row) for row in _base_tender_query(connection)]
        quotes = connection.execute(
            "SELECT tender_number FROM quoted_tenders WHERE state = ?",
            (STATE,),
        ).fetchall()
        quote_details = [
            _get_tender(connection, row["tender_number"])
            for row in quotes
        ]
        results = [quote["result"] for quote in quote_details if quote]
        won_value_row = connection.execute(
            """
            SELECT coalesce(sum(CAST(total AS REAL)), 0)
            FROM bids
            WHERE state = ? AND (
                supplier_id = '5086'
                OR upper(trim(supplier_name)) IN (
                    'K K ALLIANZE', 'KAMAL KUMAR PARASMAL JAIN', 'KAMAL KUMAR P JAIN'
                )
            ) AND rank = 1 AND selected IN (1, '1', 'true', 'TRUE')
            """,
            (STATE,),
        ).fetchone()[0]
        needs_confirmation = connection.execute(
            """
            SELECT supplier_id, supplier_name, count(DISTINCT tender_number) AS tenders
            FROM bids
            WHERE state = ? AND coalesce(supplier_id, '') != '5086'
              AND (
                upper(supplier_name) LIKE '%ALLIAN%'
                OR upper(supplier_name) LIKE '%KAMAL KUMAR%'
                OR upper(supplier_name) LIKE '%PARASMAL%'
              )
              AND upper(trim(supplier_name)) NOT IN (
                'K K ALLIANZE', 'KAMAL KUMAR PARASMAL JAIN', 'KAMAL KUMAR P JAIN'
              )
            GROUP BY supplier_id, supplier_name
            ORDER BY tenders DESC, supplier_name
            """,
            (STATE,),
        ).fetchall()
        return {
            "stats": {
                "tenders": len(tenders),
                "quoted": len(quote_details),
                "bids_opened": sum(bool(item and item["bids_opened"]) for item in quote_details),
                "won": results.count("won"),
                "lost": results.count("lost"),
                "pending": results.count("pending"),
                "not_public": results.count("not_public"),
                "total_won_value": won_value_row,
            },
            "quoted_tenders": quote_details,
            "today_updates": _recent_changes(connection),
            "departments": _departments(connection),
            "needs_confirmation": [dict(row) for row in needs_confirmation],
            "scan": _scan_health(connection),
        }


@app.get("/api/departments")
def departments():
    with connect() as connection:
        return {"departments": _departments(connection)}


@app.get("/api/tenders")
def tenders(
    q: str = "",
    department: list[str] | None = Query(default=None),
    category: list[str] | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    date_from: date | None = None,
    date_to: date | None = None,
    closing_soon: bool = False,
    quoted: bool | None = None,
    period: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    with connect() as connection:
        rows = [_tender(row) for row in _base_tender_query(connection)]
        quoted_numbers = {
            row["tender_number"]
            for row in connection.execute(
                "SELECT tender_number FROM quoted_tenders WHERE state = ?",
                (STATE,),
            )
        }
        today = date.today()
        lower = date_from
        upper = date_to
        if period in ("today", "yesterday", "7days"):
            lower = today if period == "today" else today - timedelta(days=1) if period == "yesterday" else today - timedelta(days=6)
            upper = today - timedelta(days=1) if period == "yesterday" else today

        filtered = []
        needle = q.strip().casefold()
        for row in rows:
            number = row["tender_number"]
            is_quoted = number in quoted_numbers
            if department and row.get("department_code", "").upper() not in {x.upper() for x in department}:
                continue
            if category and str(row.get("category") or "").upper() not in {x.upper() for x in category}:
                continue
            if status and str(row.get("status") or "").upper() not in {x.upper() for x in status}:
                continue
            if quoted is not None and is_quoted != quoted:
                continue
            published = _iso_day(row.get("published_date"))
            discovered = _iso_day(row.get("created_at"))
            if lower and not ((published and lower <= published <= (upper or today)) or (discovered and lower <= discovered <= (upper or today))):
                continue
            closing = _iso_day(row.get("closing_date"))
            if closing_soon and not (closing and today <= closing <= today + timedelta(days=7)):
                continue
            if needle:
                item_match = connection.execute(
                    """
                    SELECT 1 FROM tender_items
                    WHERE state = ? AND tender_number = ? AND lower(coalesce(item_name, '')) LIKE ?
                    LIMIT 1
                    """,
                    (STATE, number, f"%{needle}%"),
                ).fetchone()
                searchable = " ".join(
                    str(row.get(key) or "")
                    for key in ("tender_number", "title", "department_code", "department_name")
                ).casefold()
                if needle not in searchable and not item_match:
                    continue
            row["quoted"] = is_quoted
            row.update(_bid_summary(connection, number))
            filtered.append(row)

        start = (page - 1) * page_size
        return {"total": len(filtered), "page": page, "page_size": page_size, "items": filtered[start:start + page_size]}


@app.get("/api/tender")
def tender_detail(number: str):
    with connect() as connection:
        result = _get_tender(connection, normalise_tender_number(number))
        if result is None:
            raise HTTPException(status_code=404, detail="Tender not found in the local database or watch list.")
        return result


@app.post("/api/quotes")
def add_quotes(request: QuoteRequest):
    values = []
    invalid = []
    for raw in request.tender_numbers:
        number = normalise_tender_number(raw)
        if not number or not number.split("/", 1)[0] in FOCUS_CODES or "/" not in number:
            invalid.append(raw)
        else:
            values.append(number)
    if invalid:
        raise HTTPException(
            status_code=422,
            detail={"message": "Only tender numbers with an in-scope department prefix are accepted.", "invalid": invalid},
        )

    timestamp = now_utc()
    with connect() as connection:
        added = []
        for number in dict.fromkeys(values):
            exists = connection.execute(
                "SELECT 1 FROM quoted_tenders WHERE state = ? AND tender_number = ?",
                (STATE, number),
            ).fetchone()
            if exists:
                continue
            connection.execute(
                """
                INSERT INTO quoted_tenders(state, tender_number, source, added_at)
                VALUES (?, ?, 'manual', ?)
                """,
                (STATE, number, timestamp),
            )
            _record_change(connection, number, "quoted", None, "manual")
            added.append(number)
        return {"added": added, "already_watched": len(set(values) - set(added))}


@app.delete("/api/quotes")
def remove_quote(number: str):
    normalised = normalise_tender_number(number)
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM quoted_tenders WHERE state = ? AND tender_number = ?",
            (STATE, normalised),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Quoted tender is not being watched.")
        _record_change(connection, normalised, "quote_removed", "watched", None)
        return {"removed": normalised}


@app.get("/api/today")
def today(period: str = Query(default="today", pattern="^(today|yesterday|7days)$")):
    with connect() as connection:
        entries = tenders(period=period, page=1, page_size=200)
        by_department = {department["code"]: [] for department in _departments(connection)}
        for item in entries["items"]:
            code = item.get("department_code")
            if code in by_department:
                published = _iso_day(item.get("published_date"))
                created = _iso_day(item.get("created_at"))
                item["day_type"] = "published_today" if published == date.today() else "newly_discovered"
                by_department[code].append(item)
        return {
            "period": period,
            "groups": [
                {"department": department, "tenders": by_department[department["code"]]}
                for department in _departments(connection)
            ],
        }


@app.get("/api/events")
async def events():
    async def stream():
        last_id = 0
        while True:
            with connect() as connection:
                rows = connection.execute(
                    """
                    SELECT id, tender_number, change_type, old_value, new_value, created_at
                    FROM change_events WHERE state = ? AND id > ? ORDER BY id LIMIT 100
                    """,
                    (STATE, last_id),
                ).fetchall()
                scan = _scan_health(connection)
            if rows:
                for row in rows:
                    payload = json.dumps(dict(row), ensure_ascii=False)
                    last_id = row["id"]
                    yield f"id: {last_id}\nevent: change\ndata: {payload}\n\n"
            else:
                yield f"event: status\ndata: {json.dumps(scan)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/changes")
def changes(since_id: int = Query(default=0, ge=0)):
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, tender_number, change_type, old_value, new_value, created_at
            FROM change_events WHERE state = ? AND id > ? ORDER BY id
            """,
            (STATE, since_id),
        ).fetchall()
        return {"items": [dict(row) for row in rows]}


@app.get("/")
def home():
    index = DIST_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="Frontend build missing. Run `npm run build` in kppp_platform.")
    return FileResponse(index)


if DIST_DIR.is_dir():
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="frontend")
