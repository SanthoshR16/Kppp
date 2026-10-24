import time

from app.database import FOCUS_DEPARTMENTS, STATE, connect, ensure_schema, now_utc, upsert_public_tender
from sources.kppp_karnataka import CATEGORIES, KpppClient


QUOTE_INTERVAL_SECONDS = 15 * 60
FULL_INTERVAL_SECONDS = 60 * 60


def check_quotes(client):
    with connect() as connection:
        quotes = connection.execute(
            """
            SELECT q.tender_number, t.category
            FROM quoted_tenders q LEFT JOIN tenders t
              ON t.state = q.state AND t.tender_number = q.tender_number
            WHERE q.state = ? ORDER BY q.added_at
            """,
            (STATE,),
        ).fetchall()
    if not quotes:
        print("Quoted-tender check: no tenders are being watched.", flush=True)
        return

    started_at = now_utc()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO scan_state(state, source_name, status, started_at, completed_at, message)
            VALUES (?, 'quote-watch', 'running', ?, NULL, ?)
            ON CONFLICT(state, source_name) DO UPDATE SET
              status='running', started_at=excluded.started_at, completed_at=NULL,
              message=excluded.message
            """,
            (STATE, started_at, f"Checking 0 of {len(quotes)} quoted tenders."),
        )

    department_ids = {code: portal_id for code, portal_id in FOCUS_DEPARTMENTS}
    checked = 0
    missing = []
    deadline = time.monotonic() + 20 * 60
    for index, quote in enumerate(quotes, start=1):
        if time.monotonic() >= deadline:
            raise TimeoutError("Quoted-tender checks exceeded the 20-minute cycle timeout.")
        number = quote["tender_number"]
        department_code = number.split("/", 1)[0].upper()
        portal_id = department_ids.get(department_code)
        if portal_id is None:
            raise RuntimeError(f"Refusing out-of-scope quoted tender {number}")
        categories = [quote["category"]] if quote["category"] in CATEGORIES else list(CATEGORIES)
        matching_rows = []
        for category in categories:
            matching_rows = client.search_tender_number(portal_id, category, number)
            if matching_rows:
                break
        if matching_rows:
            with connect() as connection:
                upsert_public_tender(connection, matching_rows[0], expected_department=department_code)
                connection.execute(
                    "UPDATE quoted_tenders SET last_checked_at = ? WHERE state = ? AND tender_number = ?",
                    (now_utc(), STATE, number),
                )
            checked += 1
        else:
            missing.append(number)
            with connect() as connection:
                connection.execute(
                    "UPDATE quoted_tenders SET last_checked_at = ? WHERE state = ? AND tender_number = ?",
                    (now_utc(), STATE, number),
                )
        with connect() as connection:
            connection.execute(
                """
                UPDATE scan_state SET message = ?
                WHERE state = ? AND source_name = 'quote-watch'
                """,
                (f"Checked {index} of {len(quotes)} quoted tenders.", STATE),
            )

    checked_at = now_utc()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO scan_state(state, source_name, status, started_at, completed_at, message)
            VALUES (?, 'quote-watch', 'completed', ?, ?, ?)
            ON CONFLICT(state, source_name) DO UPDATE SET
              status='completed', started_at=excluded.started_at,
              completed_at=excluded.completed_at, message=excluded.message
            """,
            (STATE, checked_at, checked_at, f"Public search checked {checked} of {len(quotes)} quoted tenders."),
        )
    print(
        f"Quoted-tender check: {checked} public matches, {len(missing)} not found, "
        f"of {len(quotes)} watched tenders at {checked_at}. "
        "Bidder/evaluation endpoint checks are not yet implemented.",
        flush=True,
    )
    if missing:
        print("No exact public search result: " + ", ".join(missing), flush=True)


def main():
    ensure_schema()
    client = KpppClient()
    next_full = 0.0
    while True:
        now = time.monotonic()
        try:
            check_quotes(client)
            if now >= next_full:
                next_full = now + FULL_INTERVAL_SECONDS
                print("Full status/category backfill starting; it may take several minutes.", flush=True)
                import subprocess
                import sys

                subprocess.run(
                    [sys.executable, "backfill.py", "--refresh"],
                    check=True,
                    timeout=1200,
                )
        except Exception as exc:
            failed_at = now_utc()
            message = f"{type(exc).__name__}: {exc}"
            with connect() as connection:
                connection.execute(
                    """
                    INSERT INTO scan_state(state, source_name, status, started_at, completed_at, message)
                    VALUES (?, 'quote-watch', 'failed', ?, ?, ?)
                    ON CONFLICT(state, source_name) DO UPDATE SET
                      status='failed', completed_at=excluded.completed_at, message=excluded.message
                    """,
                    (STATE, failed_at, failed_at, message),
                )
            print(f"Daily update cycle failed: {message}", flush=True)
        time.sleep(QUOTE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
