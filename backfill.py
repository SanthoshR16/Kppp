import argparse
import json
import logging
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.database import (
    FOCUS_CODES,
    FOCUS_DEPARTMENTS,
    STATE,
    connect,
    ensure_schema,
    get_watermark,
    now_utc,
    set_watermark,
    upsert_public_tender,
)
from app.evaluation import evaluate_and_reconcile_tender
from kppp_client import (
    KpppClient,
    PortalAccessError,
    PortalError,
    PortalRateLimitError,
)

logger = logging.getLogger("backfill")

DATA_DIR = Path(__file__).resolve().parent / "data"
CHECKPOINT_PATH = DATA_DIR / "checkpoint.json"
HEARTBEAT_PATH = DATA_DIR / "heartbeat.json"

CATEGORIES = ("GOODS", "WORKS", "SERVICES")
STATUSES = (
    "PUBLISHED",
    "CLOSED",
    "UNDER_EVALUATION",
    "EVALUATION_COMPLETED",
    "AWARDED",
    "RETENDERED",
    "RECALLED",
)
TENDER_TYPES = (None,)
PORTAL_EPOCH = date(2023, 3, 29)


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_checkpoint() -> Dict[str, Any]:
    if not CHECKPOINT_PATH.exists():
        return {"completed_chunks": [], "last_watermark": None, "last_updated": None}
    try:
        cp = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        if not isinstance(cp, dict):
            return {"completed_chunks": [], "last_watermark": None, "last_updated": None}
        cp.setdefault("completed_chunks", [])
        return cp
    except Exception as exc:
        logger.warning("Could not read checkpoint %s, starting fresh: %s", CHECKPOINT_PATH, exc)
        return {"completed_chunks": [], "last_watermark": None, "last_updated": None}


def generate_month_windows(start_date: date, end_date: date) -> List[Tuple[date, date]]:
    """Generates monthly date windows from end_date backwards to start_date (newest first)."""
    windows = []
    curr_end = end_date
    while curr_end >= start_date:
        # 30-day window or down to start_date
        curr_start = max(start_date, curr_end - timedelta(days=29))
        windows.append((curr_start, curr_end))
        curr_end = curr_start - timedelta(days=1)
    return windows


def format_portal_date(d: date) -> str:
    """Format date as dd-MM-yyyy for KPPP portal query."""
    return d.strftime("%d-%m-%Y")


def fetch_and_store_window(
    client: KpppClient,
    connection: sqlite3.Connection,
    dept_id: Optional[int],
    dept_code: Optional[str],
    category: str,
    status: str,
    tender_type: Optional[str],
    date_from: date,
    date_to: date,
    on_heartbeat: Optional[Any] = None,
) -> Tuple[int, Optional[int], bool]:
    """
    Fetches a date window. If total rows do not match x-total-count,
    subdivides into weekly or daily windows recursively until exact match.
    """
    p_from = format_portal_date(date_from)
    p_to = format_portal_date(date_to)
    page_num = 0
    page_size = 100
    rows: List[Dict[str, Any]] = []
    expected_total: Optional[int] = None

    while True:
        page = client.search_tenders(
            category=category,
            status=status,
            dept_id=dept_id,
            tender_type=tender_type,
            published_from=p_from,
            published_to=p_to,
            page=page_num,
            size=page_size,
        )
        if expected_total is None:
            expected_total = page.total_count

        rows.extend(page.tenders)
        if on_heartbeat:
            on_heartbeat({
                "page": page_num,
                "rows_this_page": len(page.tenders),
                "rows_accumulated": len(rows),
                "portal_expected": expected_total,
                "window": f"{p_from} to {p_to}",
            })

        if len(page.tenders) < page_size:
            break
        page_num += 1

    # Check for mismatch
    mismatch = (expected_total is not None and len(rows) != expected_total)
    if mismatch and (date_to - date_from).days > 1:
        print(
            f"    [SUBDIVIDE] Window {p_from} to {p_to} returned {len(rows)} rows "
            f"vs expected {expected_total}. Subdividing window...",
            flush=True,
        )
        mid = date_from + (date_to - date_from) // 2
        saved_1, exp_1, m_1 = fetch_and_store_window(
            client, connection, dept_id, dept_code, category, status, tender_type,
            date_from, mid, on_heartbeat,
        )
        saved_2, exp_2, m_2 = fetch_and_store_window(
            client, connection, dept_id, dept_code, category, status, tender_type,
            mid + timedelta(days=1), date_to, on_heartbeat,
        )
        total_exp = (exp_1 or 0) + (exp_2 or 0) if exp_1 is not None and exp_2 is not None else None
        return (saved_1 + saved_2), total_exp, (m_1 or m_2)

    # Upsert rows into SQLite and fetch full view on new/changed tenders
    saved_count = 0
    for r in rows:
        r_cat = str(r.get("category") or category).upper()
        r["category"] = r_cat
        if upsert_public_tender(connection, r, expected_department=dept_code, client=client):
            saved_count += 1

    return saved_count, expected_total, mismatch


def evaluate_non_published_tenders(client: KpppClient, connection: sqlite3.Connection) -> int:
    """
    Dedicated pass for non-PUBLISHED tenders to retrieve comparative statement (.xlsx)
    and item-wise selected bids. Decides 'bids opened' from the statement or item-wise response,
    not from bid-groups.
    """
    from app.database import save_tender_bids

    non_published = connection.execute(
        """
        SELECT tender_number, category, status, nit_id, portal_tender_id
        FROM tenders
        WHERE state = ? AND in_scope = 1 AND status != 'PUBLISHED'
        ORDER BY updated_at DESC
        """,
        (STATE,),
    ).fetchall()

    evaluated = 0
    for row in non_published:
        t_num = row["tender_number"]
        cat = row["category"] or "GOODS"
        nit_id = row["nit_id"] or row["portal_tender_id"]
        if not nit_id:
            continue

        comp_bytes = None
        itemwise_bids = None

        try:
            comp_bytes = client.download_commercial_comparison(nit_id, category=cat)
        except Exception:
            pass

        try:
            itemwise_bids = client.get_all_itemwise_selected_bids(nit_id, category=cat)
        except Exception:
            pass

        # Decide bids opened strictly from statement or itemwise response
        if comp_bytes or itemwise_bids:
            eval_res = evaluate_and_reconcile_tender(
                tender_number=t_num,
                comp_statement_bytes=comp_bytes,
                itemwise_selected_supplier=itemwise_bids,
            )
            save_tender_bids(connection, t_num, eval_res)
            evaluated += 1

    return evaluated


def run_backfill(refresh: bool = False, max_days_back: Optional[int] = None) -> None:
    ensure_schema()
    client = KpppClient(delay=0.4, connect_timeout=10.0, read_timeout=60.0)
    started = now_utc()
    checkpoint = load_checkpoint()
    completed_chunks: Set[str] = set() if refresh else set(checkpoint.get("completed_chunks", []))

    run_id: Optional[int] = None
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO scan_runs(state, source_name, started_at, status, notes, progress_json)
            VALUES (?, 'kppp', ?, 'running', 'Upgraded comprehensive historical extraction', '{}')
            """,
            (STATE, started),
        )
        run_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO scan_state(state, source_name, status, started_at, completed_at, message)
            VALUES (?, 'kppp', 'running', ?, NULL, 'Historical backfill in progress')
            ON CONFLICT(state, source_name) DO UPDATE SET
                status='running', started_at=excluded.started_at, completed_at=NULL,
                message=excluded.message
            """,
            (STATE, started),
        )

    today = date.today()
    start_date = today - timedelta(days=max_days_back) if max_days_back else PORTAL_EPOCH
    month_windows = generate_month_windows(start_date, today)

    totals = {"searches": 0, "rows_saved": 0, "mismatches": 0}
    failure = None

    print("=" * 100)
    print(" KPPP HISTORICAL EXTRACTION & RECONCILIATION RUNNER")
    print("=" * 100)
    print(f"Date range: {start_date} to {today} ({len(month_windows)} windows, newest first)")
    print(f"Departments: 17 focus codes | Categories: GOODS, WORKS, SERVICES | Statuses: 7")
    print(f"Checkpoint file: {CHECKPOINT_PATH} (completed chunks: {len(completed_chunks)})")
    print("-" * 100)

    try:
        # Phase 1: Focus Departments x Category x Status x Month Windows
        for code, portal_id in FOCUS_DEPARTMENTS:
            for category in CATEGORIES:
                for status in STATUSES:
                    for tender_type in TENDER_TYPES:
                        type_label = "NULL" if tender_type is None else (tender_type or "EMPTY")
                        for w_start, w_end in month_windows:
                            w_label = f"{w_start.isoformat()}_{w_end.isoformat()}"
                            chunk_id = f"{code}:{category}:{status}:{type_label}:{w_label}"

                            if chunk_id in completed_chunks:
                                continue

                            def heartbeat_cb(info: Dict[str, Any]) -> None:
                                write_json_atomic(HEARTBEAT_PATH, {
                                    "run_id": run_id,
                                    "updated_at": now_utc(),
                                    "department": code,
                                    "category": category,
                                    "status": status,
                                    "tender_type": type_label,
                                    **info,
                                })

                            with connect() as conn:
                                saved, exp, mismatch = fetch_and_store_window(
                                    client=client,
                                    connection=conn,
                                    dept_id=portal_id,
                                    dept_code=code,
                                    category=category,
                                    status=status,
                                    tender_type=tender_type,
                                    date_from=w_start,
                                    date_to=w_end,
                                    on_heartbeat=heartbeat_cb,
                                )

                            totals["searches"] += 1
                            totals["rows_saved"] += saved
                            totals["mismatches"] += int(mismatch)

                            completed_chunks.add(chunk_id)
                            write_json_atomic(CHECKPOINT_PATH, {
                                "completed_chunks": sorted(completed_chunks),
                                "last_watermark": w_end.isoformat(),
                                "last_updated": now_utc(),
                                "last_chunk": chunk_id,
                            })

                            if saved > 0 or mismatch:
                                print(
                                    f"[{code}] {category} {status} ({w_label}): "
                                    f"saved={saved} portal_total={exp if exp is not None else 'unreported'} "
                                    f"mismatch={mismatch}",
                                    flush=True,
                                )

        # Phase 2: Prefix Cross-Check (Global search without department filter)
        print("\n" + "-" * 100)
        print("PHASE 2: GLOBAL PREFIX CROSS-CHECK (ALL 17 CODES)")
        print("-" * 100)
        for category in CATEGORIES:
            for status in STATUSES:
                chunk_id = f"ALL:{category}:{status}:NULL:prefix-cross-check"
                if chunk_id in completed_chunks:
                    continue

                with connect() as conn:
                    saved, exp, mismatch = fetch_and_store_window(
                        client=client,
                        connection=conn,
                        dept_id=None,
                        dept_code=None,
                        category=category,
                        status=status,
                        tender_type=None,
                        date_from=start_date,
                        date_to=today,
                        on_heartbeat=lambda info: write_json_atomic(HEARTBEAT_PATH, {
                            "run_id": run_id,
                            "updated_at": now_utc(),
                            "phase": "prefix_cross_check",
                            "category": category,
                            "status": status,
                            **info,
                        }),
                    )

                totals["searches"] += 1
                totals["rows_saved"] += saved
                totals["mismatches"] += int(mismatch)
                completed_chunks.add(chunk_id)
                write_json_atomic(CHECKPOINT_PATH, {
                    "completed_chunks": sorted(completed_chunks),
                    "last_watermark": today.isoformat(),
                    "last_updated": now_utc(),
                    "last_chunk": chunk_id,
                })
                print(
                    f"[CROSS-CHECK] {category} {status}: saved_in_scope={saved} portal_total={exp}",
                    flush=True,
                )

        # Phase 3: Dedicated Non-Published Bids & Evaluation Pass
        print("\n" + "-" * 100)
        print("PHASE 3: BID EVALUATION FOR NON-PUBLISHED TENDERS")
        print("-" * 100)
        with connect() as conn:
            evaluated = evaluate_non_published_tenders(client, conn)
            print(f"[EVALUATION] Evaluated and reconciled bids for {evaluated} non-published tenders.", flush=True)

        # Advance database watermark
        with connect() as conn:
            set_watermark(conn, today.isoformat(), "kppp")

    except (PortalError, PortalAccessError, PortalRateLimitError, Exception) as exc:
        failure = exc
        logger.exception("Backfill encountered an error: %s", exc)

    completed = now_utc()
    status_str = "failed" if failure else "completed"
    msg = str(failure) if failure else f"Extraction finished: {totals['searches']} queries, {totals['rows_saved']} rows stored."

    with connect() as conn:
        conn.execute(
            """
            UPDATE scan_runs SET completed_at=?, status=?, notes=?, progress_json=?
            WHERE id=? AND state=?
            """,
            (completed, status_str, msg, json.dumps(totals), run_id, STATE),
        )
        conn.execute(
            """
            UPDATE scan_state SET status=?, completed_at=?, message=?,
                last_successful_scan_date=CASE WHEN ?='completed' THEN ? ELSE last_successful_scan_date END
            WHERE state=? AND source_name='kppp'
            """,
            (status_str, completed, msg, status_str, today.isoformat(), STATE),
        )

    print("\n" + "=" * 100)
    print(f"Backfill {status_str.upper()}: {msg}")
    print("=" * 100)
    if failure:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upgraded KPPP Historical Extraction & Reconciliation")
    parser.add_argument("--refresh", action="store_true", help="Clear completed chunk history and re-run all")
    parser.add_argument("--days", type=int, default=None, help="Limit extraction to last N days (for quick test)")
    args = parser.parse_args()
    run_backfill(refresh=args.refresh, max_days_back=args.days)
