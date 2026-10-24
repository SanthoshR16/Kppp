import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BASE_DIR / "data" / "db" / "kppp.sqlite"
STATE = "karnataka"

FOCUS_DEPARTMENTS = (
    ("AHF", 26),
    ("AHVS", 6820),
    ("BBMP", 671),
    ("BMCRI", 8191),
    ("DHFWS", 39),
    ("DME", 3640),
    ("ESISMS", 6289),
    ("HGML", 2617),
    ("INU", 6179),
    ("KKRDB", 5981),
    ("KSMSCL", 3357),
    ("KVAFSU", 8296),
    ("NIMHANS", 3562),
    ("RVS", 10552),
    ("SDSTRGI", 8559),
    ("SGITO", 9146),
    ("SJICR", 7200),
)
FOCUS_DEPARTMENT_NAMES = {
    "AHF": "Animal Husbandry And Fisheries Department",
    "AHVS": "Animal Husbandry and Veterinary Services",
    "BBMP": "Bruhat Bengaluru Mahanagara Palike",
    "BMCRI": "Bangalore Medical College and Research Institute",
    "DHFWS": "Department of Health and Family Welfare Services",
    "DME": "Department of Medical Education",
    "ESISMS": "Employees State Insurance Scheme Medical Service",
    "HGML": "Hutti Gold Mines Company Limited",
    "INU": "Institute of Nephro Urology",
    "KKRDB": "Kalyana Karnataka Region Development Board",
    "KSMSCL": "Karnataka State Medical Supplies Corporation Limited",
    "KVAFSU": "Karnataka Veterinary Animal and Fisheries Sciences University",
    "NIMHANS": "National Institute of Mental Health and Neuro Sciences",
    "RVS": "Rajya Vokkaligara Sangha",
    "SDSTRGI": "SDS Tuberculosis and Rajiv Gandhi Institute of Chest Diseases",
    "SGITO": "Sanjay Gandhi Institute of Trauma and Orthopaedics",
    "SJICR": "Sri Jayadeva Institute of Cardiovascular Sciences and Research",
}
FOCUS_CODES = tuple(code for code, _ in FOCUS_DEPARTMENTS)
ID_TO_CODE = {str(department_id): code for code, department_id in FOCUS_DEPARTMENTS}


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exception_type, exception_value, traceback):
        try:
            return super().__exit__(exception_type, exception_value, traceback)
        finally:
            self.close()


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def database_path():
    return Path(os.environ.get("KPPP_DB_PATH", DEFAULT_DB_PATH))


def connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def ensure_column(connection, table, column, definition):
    columns = {row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")')}
    if column not in columns:
        connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}')


def ensure_schema():
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS focus_departments (
                state TEXT NOT NULL,
                department_code TEXT NOT NULL,
                portal_id INTEGER NOT NULL,
                department_name TEXT,
                name_verified INTEGER NOT NULL DEFAULT 0,
                name_source TEXT NOT NULL DEFAULT 'local snapshot',
                PRIMARY KEY (state, department_code),
                UNIQUE (state, portal_id)
            );
            CREATE TABLE IF NOT EXISTS quoted_tenders (
                state TEXT NOT NULL,
                tender_number TEXT NOT NULL,
                source TEXT NOT NULL,
                added_at TEXT NOT NULL,
                last_checked_at TEXT,
                bids_opened_at TEXT,
                PRIMARY KEY (state, tender_number)
            );
            CREATE TABLE IF NOT EXISTS change_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                tender_number TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_change_events_state_time
                ON change_events(state, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_quoted_tenders_state
                ON quoted_tenders(state, added_at DESC);
            CREATE TABLE IF NOT EXISTS scan_state (
                state TEXT NOT NULL,
                source_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                message TEXT,
                last_successful_scan_date TEXT,
                PRIMARY KEY (state, source_name)
            );
            CREATE TABLE IF NOT EXISTS tenders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                tender_number TEXT NOT NULL,
                department_code TEXT,
                department_name TEXT,
                category TEXT,
                status TEXT,
                title TEXT,
                published_date TEXT,
                closing_date TEXT,
                estimated_value TEXT,
                emd_amount TEXT,
                raw_data_json TEXT,
                in_scope INTEGER NOT NULL DEFAULT 1,
                out_of_scope INTEGER NOT NULL DEFAULT 0,
                bids_opened_at TEXT,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE (state, tender_number)
            );
            CREATE TABLE IF NOT EXISTS tender_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                tender_number TEXT NOT NULL,
                item_code TEXT,
                item_name TEXT,
                quantity TEXT,
                unit TEXT,
                rate TEXT,
                total TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS bids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                tender_number TEXT NOT NULL,
                item_name TEXT,
                supplier_id TEXT,
                supplier_name TEXT,
                rate TEXT,
                total TEXT,
                rank INTEGER,
                selected INTEGER,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS tender_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                tender_number TEXT NOT NULL,
                previous_status TEXT,
                new_status TEXT,
                changed_at TEXT NOT NULL,
                note TEXT
            );
            CREATE TABLE IF NOT EXISTS scan_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                source_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                progress_json TEXT
            );
            CREATE TABLE IF NOT EXISTS scan_watermarks (
                state TEXT NOT NULL,
                source_name TEXT NOT NULL,
                watermark_date TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (state, source_name)
            );
            """
        )
        ensure_column(connection, "focus_departments", "name_verified", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(connection, "focus_departments", "name_source", "TEXT NOT NULL DEFAULT 'local snapshot'")
        ensure_column(connection, "tenders", "title", "TEXT")
        ensure_column(connection, "tenders", "department_name", "TEXT")
        ensure_column(connection, "tenders", "tender_fee", "TEXT")
        ensure_column(connection, "tenders", "officer_details", "TEXT")
        ensure_column(connection, "tenders", "out_of_scope", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(connection, "tenders", "bids_opened_at", "TEXT")
        ensure_column(connection, "tenders", "nit_id", "TEXT")
        ensure_column(connection, "tenders", "portal_tender_id", "TEXT")
        ensure_column(connection, "tenders", "tender_type", "TEXT")
        ensure_column(connection, "tenders", "check_reason", "TEXT")
        ensure_column(connection, "bids", "check_reason", "TEXT")

        for code, portal_id in FOCUS_DEPARTMENTS:
            connection.execute(
                """
                INSERT INTO focus_departments(
                    state, department_code, portal_id, department_name, name_verified, name_source
                ) VALUES (?, ?, ?, ?, 0, 'local snapshot')
                ON CONFLICT(state, department_code) DO UPDATE SET
                  portal_id = excluded.portal_id,
                  department_name = coalesce(focus_departments.department_name, excluded.department_name)
                """,
                (STATE, code, portal_id, FOCUS_DEPARTMENT_NAMES[code]),
            )

        for legacy_id, code in ID_TO_CODE.items():
            connection.execute(
                """
                UPDATE tenders
                SET department_code = ?
                WHERE state = ? AND (department_code = ? OR upper(tender_number) LIKE ?)
                """,
                (code, STATE, legacy_id, f"{code}/%"),
            )

        valid_codes = ",".join("?" for _ in FOCUS_CODES)
        connection.execute(
            f"""
            UPDATE tenders
            SET in_scope = CASE
                    WHEN upper(coalesce(department_code, '')) IN ({valid_codes}) THEN 1
                    ELSE 0
                END,
                out_of_scope = CASE
                    WHEN upper(coalesce(department_code, '')) IN ({valid_codes}) THEN 0
                    ELSE 1
                END
            WHERE state = ?
            """,
            (*FOCUS_CODES, *FOCUS_CODES, STATE),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO quoted_tenders(state, tender_number, source, added_at)
            SELECT DISTINCT state, tender_number, 'public_bid_match', ?
            FROM bids
            WHERE state = ? AND (
                supplier_id = '5086'
                OR upper(trim(supplier_name)) IN (
                    'K K ALLIANZE',
                    'KAMAL KUMAR PARASMAL JAIN',
                    'KAMAL KUMAR P JAIN'
                )
            )
            """,
            (now_utc(), STATE),
        )
        connection.execute(
            """
            UPDATE tenders
            SET bids_opened_at = (
                SELECT min(b.created_at) FROM bids b
                WHERE b.state = tenders.state AND b.tender_number = tenders.tender_number
                  AND b.created_at IS NOT NULL
            )
            WHERE state = ? AND bids_opened_at IS NULL
              AND EXISTS (
                SELECT 1 FROM bids b
                WHERE b.state = tenders.state AND b.tender_number = tenders.tender_number
              )
            """,
            (STATE,),
        )


def json_object(value):
    if not value:
        return {}
    try:
        result = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Stored tender payload is not valid JSON.") from exc
    if not isinstance(result, dict):
        raise ValueError("Stored tender payload must be a JSON object.")
    return result


def fetch_and_store_tender_full_view(
    client,
    connection,
    tender_number: str,
    tender_id=None,
    nit_id=None,
    category: str = "GOODS",
) -> bool:
    """
    Fetches the tender full view once per new or changed tender and stores
    the real estimated value, EMD amount, tender fee, officer details, and item details.
    """
    if client is None:
        return False
    try:
        data = client.get_tender_full_view(
            expected_tender_number=tender_number,
            tender_id=tender_id,
            nit_id=nit_id,
            category=category or "GOODS",
        )
    except Exception:
        return False

    now = now_utc()
    estimated = (
        data.get("estimatedValue")
        or data.get("ecv")
        or data.get("tenderValue")
        or data.get("approximateCost")
    )
    emd = data.get("emdAmount") or data.get("emd") or data.get("earnestMoneyDeposit")
    fee = data.get("tenderFee") or data.get("costOfTenderForm") or data.get("tenderFormFee")
    officer = (
        data.get("officerName")
        or data.get("tenderInvitingOfficer")
        or data.get("officerDesignation")
        or data.get("officer")
        or data.get("contactPerson")
    )
    items = data.get("items") or data.get("tenderItems") or data.get("bidItems") or []

    connection.execute(
        """
        UPDATE tenders SET
            estimated_value = coalesce(?, estimated_value),
            emd_amount = coalesce(?, emd_amount),
            tender_fee = coalesce(?, tender_fee),
            officer_details = coalesce(?, officer_details),
            updated_at = ?
        WHERE state = ? AND tender_number = ?
        """,
        (
            str(estimated) if estimated is not None else None,
            str(emd) if emd is not None else None,
            str(fee) if fee is not None else None,
            str(officer) if officer is not None else None,
            now,
            STATE,
            tender_number,
        ),
    )

    if isinstance(items, list) and items:
        connection.execute("DELETE FROM tender_items WHERE state = ? AND tender_number = ?", (STATE, tender_number))
        for item in items:
            if isinstance(item, dict):
                connection.execute(
                    """
                    INSERT INTO tender_items(state, tender_number, item_code, item_name, quantity, unit, rate, total, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        STATE,
                        tender_number,
                        str(item.get("itemCode") or item.get("code") or "") or None,
                        str(item.get("itemName") or item.get("name") or item.get("description") or "Item"),
                        str(item.get("quantity") or item.get("qty") or "") or None,
                        str(item.get("unit") or "") or None,
                        str(item.get("rate") or item.get("estimatedRate") or "") or None,
                        str(item.get("total") or "") or None,
                        now,
                    ),
                )
    return True


def upsert_public_tender(connection, source_row, expected_department=None, client=None):
    if not isinstance(source_row, dict):
        return False
    tender_number = " ".join(
        str(source_row.get("tenderNumber") or source_row.get("tender_number") or "")
        .strip()
        .upper()
        .split()
    ).replace(" /", "/").replace("/ ", "/")
    if "/" not in tender_number:
        return False
    prefix = tender_number.split("/", 1)[0]
    if prefix not in FOCUS_CODES:
        return False
    if expected_department and prefix != expected_department:
        return False

    timestamp = now_utc()
    category = str(source_row.get("category") or source_row.get("tenderCategory") or "").upper() or None
    status = str(source_row.get("status") or "").upper() or None
    title = source_row.get("title") or source_row.get("tenderName") or source_row.get("tenderTitle")
    published = source_row.get("publishedDate") or source_row.get("publishDate")
    # Correct KPPP listing field is tenderClosureDate, with closingDate/bidSubmissionEndDate fallback
    closing = source_row.get("tenderClosureDate") or source_row.get("closingDate") or source_row.get("bidSubmissionEndDate")
    # Correct KPPP listing field is ecv, with estimatedValue/tenderValue fallback
    estimated = source_row.get("ecv") or source_row.get("estimatedValue") or source_row.get("tenderValue")
    emd = source_row.get("emdAmount") or source_row.get("emd")
    # Store deptName, id, nitId, and tenderType
    dept_name = source_row.get("deptName") or source_row.get("departmentName") or source_row.get("dept_name")
    portal_tender_id = source_row.get("id") or source_row.get("portal_tender_id") or source_row.get("portalTenderId")
    nit_id = source_row.get("nitId") or source_row.get("nit_id")
    tender_type = source_row.get("tenderType") or source_row.get("tender_type")
    raw = json.dumps(source_row, ensure_ascii=False, separators=(",", ":"))

    previous = connection.execute(
        """
        SELECT status, closing_date, portal_tender_id, nit_id, officer_details, estimated_value FROM tenders
        WHERE state = ? AND tender_number = ?
        """,
        (STATE, tender_number),
    ).fetchone()

    is_new = (previous is None)
    is_changed = False

    if previous:
        if status and previous["status"] != status:
            is_changed = True
            connection.execute(
                """
                INSERT INTO tender_status_history(
                    state, tender_number, previous_status, new_status, changed_at, note
                ) VALUES (?, ?, ?, ?, ?, 'Public portal status update')
                """,
                (STATE, tender_number, previous["status"], status, timestamp),
            )
            connection.execute(
                """
                INSERT INTO change_events(state, tender_number, change_type, old_value, new_value, created_at)
                VALUES (?, ?, 'status', ?, ?, ?)
                """,
                (STATE, tender_number, previous["status"], status, timestamp),
            )
        if closing and previous["closing_date"] != str(closing):
            is_changed = True
            connection.execute(
                """
                INSERT INTO change_events(state, tender_number, change_type, old_value, new_value, created_at)
                VALUES (?, ?, 'closing_date', ?, ?, ?)
                """,
                (STATE, tender_number, previous["closing_date"], str(closing), timestamp),
            )
        if portal_tender_id and previous["portal_tender_id"] != str(portal_tender_id):
            is_changed = True
        if nit_id and previous["nit_id"] != str(nit_id):
            is_changed = True

    connection.execute(
        """
        INSERT INTO tenders(
            state, tender_number, department_code, department_name, category, status, title,
            published_date, closing_date, estimated_value, emd_amount,
            portal_tender_id, nit_id, tender_type,
            raw_data_json, in_scope, out_of_scope, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)
        ON CONFLICT(state, tender_number) DO UPDATE SET
            department_code=excluded.department_code,
            department_name=coalesce(excluded.department_name, tenders.department_name),
            category=coalesce(excluded.category, tenders.category),
            status=coalesce(excluded.status, tenders.status),
            title=coalesce(excluded.title, tenders.title),
            published_date=coalesce(excluded.published_date, tenders.published_date),
            closing_date=coalesce(excluded.closing_date, tenders.closing_date),
            estimated_value=coalesce(excluded.estimated_value, tenders.estimated_value),
            emd_amount=coalesce(excluded.emd_amount, tenders.emd_amount),
            portal_tender_id=coalesce(excluded.portal_tender_id, tenders.portal_tender_id),
            nit_id=coalesce(excluded.nit_id, tenders.nit_id),
            tender_type=coalesce(excluded.tender_type, tenders.tender_type),
            raw_data_json=excluded.raw_data_json,
            in_scope=1,
            out_of_scope=0,
            updated_at=excluded.updated_at
        """,
        (
            STATE,
            tender_number,
            prefix,
            str(dept_name) if dept_name is not None else None,
            category,
            status,
            str(title) if title is not None else None,
            str(published) if published is not None else None,
            str(closing) if closing is not None else None,
            str(estimated) if estimated is not None else None,
            str(emd) if emd is not None else None,
            str(portal_tender_id) if portal_tender_id is not None else None,
            str(nit_id) if nit_id is not None else None,
            str(tender_type) if tender_type is not None else None,
            raw,
            timestamp,
            timestamp,
        ),
    )

    # Fetch full view once per new or changed tender if client is available
    has_full_view = bool(previous and previous["officer_details"] and previous["estimated_value"])
    if client is not None and (is_new or is_changed or not has_full_view):
        fetch_and_store_tender_full_view(
            client=client,
            connection=connection,
            tender_number=tender_number,
            tender_id=portal_tender_id,
            nit_id=nit_id,
            category=category or "GOODS",
        )

    bid_timestamp = connection.execute(
        """
        SELECT min(created_at) FROM bids
        WHERE state = ? AND tender_number = ? AND created_at IS NOT NULL
        """,
        (STATE, tender_number),
    ).fetchone()[0]
    if bid_timestamp:
        opened = connection.execute(
            "SELECT bids_opened_at FROM tenders WHERE state = ? AND tender_number = ?",
            (STATE, tender_number),
        ).fetchone()
        if opened and not opened["bids_opened_at"]:
            connection.execute(
                "UPDATE tenders SET bids_opened_at = ? WHERE state = ? AND tender_number = ?",
                (bid_timestamp, STATE, tender_number),
            )
            connection.execute(
                """
                INSERT INTO change_events(state, tender_number, change_type, old_value, new_value, created_at)
                VALUES (?, ?, 'bids_opened', NULL, ?, ?)
                """,
                (STATE, tender_number, bid_timestamp, timestamp),
            )
    connection.execute(
        """
        INSERT INTO quoted_tenders(state, tender_number, source, added_at)
        SELECT ?, ?, 'public_bid_match', ?
        WHERE EXISTS (
            SELECT 1 FROM bids WHERE state = ? AND tender_number = ?
              AND (supplier_id = '5086' OR upper(trim(supplier_name)) IN (
                'K K ALLIANZE', 'KAMAL KUMAR PARASMAL JAIN', 'KAMAL KUMAR P JAIN'
              ))
        )
        ON CONFLICT(state, tender_number) DO NOTHING
        """,
        (STATE, tender_number, timestamp, STATE, tender_number),
    )
    return True


def save_tender_bids(connection, tender_number: str, evaluation_result: dict):
    bids = evaluation_result.get("bids", [])
    items = evaluation_result.get("items", [])
    discrepancy = evaluation_result.get("check_status")
    now = now_utc()

    # Track previous L1 to detect L1 change events
    prev_l1_row = connection.execute(
        """
        SELECT supplier_name, total FROM bids
        WHERE state = ? AND tender_number = ? AND (rank = 1 OR selected IN (1, '1', 'true', 'TRUE'))
        ORDER BY rank ASC LIMIT 1
        """,
        (STATE, tender_number),
    ).fetchone()
    prev_l1_name = prev_l1_row["supplier_name"] if prev_l1_row else None

    # Replace bids for this tender with latest parsed results
    connection.execute("DELETE FROM bids WHERE state = ? AND tender_number = ?", (STATE, tender_number))
    for bid in bids:
        connection.execute(
            """
            INSERT INTO bids(
                state, tender_number, item_name, supplier_id, supplier_name,
                rate, total, rank, selected, check_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                STATE,
                tender_number,
                bid.get("item_name") or "Main Bid",
                str(bid.get("supplier_id") or "") or None,
                bid.get("supplier_name"),
                str(bid.get("rate")) if bid.get("rate") is not None else None,
                str(bid.get("total")) if bid.get("total") is not None else None,
                bid.get("rank"),
                1 if bid.get("selected") else 0,
                discrepancy,
                now,
            ),
        )

    # Save item breakdowns
    if items:
        connection.execute("DELETE FROM tender_items WHERE state = ? AND tender_number = ?", (STATE, tender_number))
        for item in items:
            connection.execute(
                """
                INSERT INTO tender_items(state, tender_number, item_name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (STATE, tender_number, item.get("item_name"), now),
            )

    # Check if tender already had bids opened
    t_row = connection.execute(
        "SELECT bids_opened_at FROM tenders WHERE state = ? AND tender_number = ?",
        (STATE, tender_number),
    ).fetchone()
    if t_row and not t_row["bids_opened_at"] and bids:
        connection.execute(
            "UPDATE tenders SET bids_opened_at = ?, updated_at = ? WHERE state = ? AND tender_number = ?",
            (now, now, STATE, tender_number),
        )
        connection.execute(
            """
            INSERT INTO change_events(state, tender_number, change_type, old_value, new_value, created_at)
            VALUES (?, ?, 'bids_opened', NULL, ?, ?)
            """,
            (STATE, tender_number, now, now),
        )

    # Detect L1 change
    new_l1 = evaluation_result.get("l1_name")
    if prev_l1_name and new_l1 and prev_l1_name != new_l1:
        connection.execute(
            """
            INSERT INTO change_events(state, tender_number, change_type, old_value, new_value, created_at)
            VALUES (?, ?, 'l1_changed', ?, ?, ?)
            """,
            (STATE, tender_number, prev_l1_name, new_l1, now),
        )

    # If discrepancy, record on tender
    if discrepancy:
        connection.execute(
            "UPDATE tenders SET check_reason = ? WHERE state = ? AND tender_number = ?",
            (discrepancy, STATE, tender_number),
        )

    # Auto-link quoted tender if our company is present
    if evaluation_result.get("we_bid"):
        connection.execute(
            """
            INSERT INTO quoted_tenders(state, tender_number, source, added_at, bids_opened_at)
            VALUES (?, ?, 'public_bid_match', ?, ?)
            ON CONFLICT(state, tender_number) DO UPDATE SET
                bids_opened_at = coalesce(quoted_tenders.bids_opened_at, excluded.bids_opened_at)
            """,
            (STATE, tender_number, now, now),
        )


def get_watermark(connection, source_name="kppp") -> str | None:
    row = connection.execute(
        "SELECT watermark_date FROM scan_watermarks WHERE state = ? AND source_name = ?",
        (STATE, source_name),
    ).fetchone()
    return row["watermark_date"] if row else None


def set_watermark(connection, watermark_date: str, source_name="kppp") -> None:
    connection.execute(
        """
        INSERT INTO scan_watermarks(state, source_name, watermark_date, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(state, source_name) DO UPDATE SET
            watermark_date = excluded.watermark_date,
            updated_at = excluded.updated_at
        """,
        (STATE, source_name, watermark_date, now_utc()),
    )

