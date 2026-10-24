import json
import sqlite3
import argparse
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.database import FOCUS_DEPARTMENTS, STATE, connect, ensure_schema, now_utc, upsert_public_tender
from sources.kppp_karnataka import CATEGORIES, STATUSES, KpppClient, PortalError


DATA_DIR = Path(__file__).resolve().parent / "data"
CHECKPOINT_PATH = DATA_DIR / "checkpoint.json"
HEARTBEAT_PATH = DATA_DIR / "heartbeat.json"
TENDER_TYPES = (None, "", "OPEN")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_checkpoint():
    if not CHECKPOINT_PATH.exists():
        return {"completed_chunks": [], "last_updated": None}
    try:
        checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid checkpoint file {CHECKPOINT_PATH}: {exc}") from exc
    if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("completed_chunks", []), list):
        raise RuntimeError(f"Invalid checkpoint structure in {CHECKPOINT_PATH}")
    checkpoint.setdefault("completed_chunks", [])
    return checkpoint


def main(refresh=False):
    ensure_schema()
    client = KpppClient()
    started = now_utc()
    checkpoint = load_checkpoint()
    completed_chunks = set() if refresh else set(checkpoint["completed_chunks"])
    run_id = None
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO scan_runs(state, source_name, started_at, status, notes, progress_json)
            VALUES (?, 'kppp', ?, 'running', 'Public, unauthenticated historical backfill', '{}')
            """,
            (STATE, started),
        )
        run_id = cursor.lastrowid
        connection.execute(
            """
            INSERT INTO scan_state(state, source_name, status, started_at, completed_at, message)
            VALUES (?, 'kppp', 'running', ?, NULL, 'Historical backfill in progress')
            ON CONFLICT(state, source_name) DO UPDATE SET
              status='running', started_at=excluded.started_at, completed_at=NULL,
              message=excluded.message
            """,
            (STATE, started),
        )

    totals = {"requests": 0, "rows": 0, "mismatches": 0}
    failure = None
    try:
        for code, portal_id in FOCUS_DEPARTMENTS:
            for category in CATEGORIES:
                for status in STATUSES:
                    for tender_type in TENDER_TYPES:
                        type_label = "NULL" if tender_type is None else tender_type or "EMPTY"
                        chunk = f"{code}:{category}:{status}:{type_label}:all"
                        if chunk in completed_chunks:
                            print(f"Resume: already completed {chunk}", flush=True)
                            continue

                        def heartbeat(page_state):
                            write_json(HEARTBEAT_PATH, {
                                "run_id": run_id,
                                "updated_at": now_utc(),
                                "department": code,
                                "category": category,
                                "status": status,
                                "tender_type": type_label,
                                **page_state,
                            })

                        rows, expected, mismatch = client.search_department(
                            portal_id,
                            category,
                            status,
                            tender_type=tender_type,
                            on_page=heartbeat,
                        )
                        totals["requests"] += 1
                        with connect() as connection:
                            saved = sum(
                                upsert_public_tender(connection, row, expected_department=code)
                                for row in rows
                            )
                        totals["rows"] += saved
                        totals["mismatches"] += int(mismatch)
                        progress = {
                            "department": code,
                            "category": category,
                            "status": status,
                            "tender_type": type_label,
                            "rows": len(rows),
                            "saved_in_scope": saved,
                            "portal_total": expected,
                            **totals,
                        }
                        with connect() as connection:
                            connection.execute(
                                "UPDATE scan_runs SET progress_json = ? WHERE id = ? AND state = ?",
                                (json.dumps(progress), run_id, STATE),
                            )
                        print(
                            f"{chunk}: rows={len(rows)} saved_in_scope={saved} "
                            f"portal_total={expected if expected is not None else 'unreported'} "
                            f"count_mismatch={mismatch}",
                            flush=True,
                        )
                        if mismatch:
                            raise RuntimeError(
                                f"Portal total does not match page rows for {chunk}; "
                                "split the date range and reconcile before marking complete."
                            )
                        completed_chunks.add(chunk)
                        checkpoint = {
                            "completed_chunks": sorted(completed_chunks),
                            "last_updated": now_utc(),
                            "last_chunk": chunk,
                        }
                        write_json(CHECKPOINT_PATH, checkpoint)

        for category in CATEGORIES:
            for status in STATUSES:
                chunk = f"ALL:{category}:{status}:NULL:prefix-cross-check"
                if chunk in completed_chunks:
                    continue
                rows, expected, mismatch = client.search_department(
                    None, category, status, tender_type=None,
                    on_page=lambda state: write_json(HEARTBEAT_PATH, {
                        "run_id": run_id, "updated_at": now_utc(),
                        "department": "ALL", "category": category, "status": status,
                        **state,
                    }),
                )
                with connect() as connection:
                    saved = sum(upsert_public_tender(connection, row) for row in rows)
                totals["requests"] += 1
                totals["rows"] += saved
                totals["mismatches"] += int(mismatch)
                print(
                    f"{chunk}: rows={len(rows)} saved_in_scope_prefixes={saved} "
                    f"portal_total={expected if expected is not None else 'unreported'} "
                    f"count_mismatch={mismatch}",
                    flush=True,
                )
                if mismatch:
                    raise RuntimeError(f"Portal total does not match page rows for {chunk}.")
                completed_chunks.add(chunk)
                write_json(CHECKPOINT_PATH, {
                    "completed_chunks": sorted(completed_chunks),
                    "last_updated": now_utc(),
                    "last_chunk": chunk,
                })
    except (PortalError, requests.RequestException, sqlite3.Error, RuntimeError) as exc:
        failure = exc

    completed = now_utc()
    status = "failed" if failure else "completed"
    message = str(failure) if failure else f"Completed {totals['requests']} searches; {totals['rows']} rows."
    with connect() as connection:
        connection.execute(
            """
            UPDATE scan_runs SET completed_at=?, status=?, notes=?, progress_json=?
            WHERE id=? AND state=?
            """,
            (completed, status, message, json.dumps(totals), run_id, STATE),
        )
        connection.execute(
            """
            UPDATE scan_state SET status=?, completed_at=?, message=?,
              last_successful_scan_date=CASE WHEN ?='completed' THEN ? ELSE last_successful_scan_date END
            WHERE state=? AND source_name='kppp'
            """,
            (status, completed, message, status, datetime.now(timezone.utc).date().isoformat(), STATE),
        )
    print(f"Backfill {status}: {message}", flush=True)
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume a polite KPPP public-data backfill.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Repeat completed searches for an hourly reconciliation cycle.",
    )
    main(refresh=parser.parse_args().refresh)
