import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.database import (
    FOCUS_DEPARTMENTS,
    STATE,
    connect,
    ensure_schema,
    now_utc,
    save_tender_bids,
    upsert_public_tender,
)
from app.evaluation import evaluate_and_reconcile_tender
from kppp_client import (
    KpppClient,
    PortalAccessError,
    PortalError,
    PortalRateLimitError,
)

logger = logging.getLogger("daily_update")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)

QUOTE_INTERVAL_SECONDS = 15 * 60  # 15 minutes
FULL_INTERVAL_SECONDS = 60 * 60   # 1 hour
CATEGORIES = ("GOODS", "WORKS", "SERVICES")


def check_quotes(client: KpppClient) -> None:
    ensure_schema()
    with connect() as conn:
        quotes = conn.execute(
            """
            SELECT q.tender_number, t.category, t.status, t.closing_date, t.nit_id, t.portal_tender_id
            FROM quoted_tenders q
            LEFT JOIN tenders t ON t.state = q.state AND t.tender_number = q.tender_number
            WHERE q.state = ?
            ORDER BY q.added_at DESC
            """,
            (STATE,),
        ).fetchall()

    if not quotes:
        logger.info("Quoted-tender check: no tenders are currently being watched.")
        return

    started_at = now_utc()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO scan_state(state, source_name, status, started_at, completed_at, message)
            VALUES (?, 'quote-watch', 'running', ?, NULL, ?)
            ON CONFLICT(state, source_name) DO UPDATE SET
                status='running', started_at=excluded.started_at, completed_at=NULL,
                message=excluded.message
            """,
            (STATE, started_at, f"Checking {len(quotes)} quoted tenders..."),
        )

    dept_ids = {code: portal_id for code, portal_id in FOCUS_DEPARTMENTS}
    checked = 0
    missing = []
    deadline = time.monotonic() + 20 * 60  # Max 20 min per cycle

    for idx, quote in enumerate(quotes, start=1):
        if time.monotonic() >= deadline:
            raise TimeoutError("Quoted-tender checks exceeded the 20-minute cycle safety deadline.")

        number = quote["tender_number"]
        dept_code = number.split("/", 1)[0].upper()
        portal_id = dept_ids.get(dept_code)
        if portal_id is None:
            continue

        cats = [quote["category"]] if quote["category"] in CATEGORIES else list(CATEGORIES)
        matched_row = None

        for cat in cats:
            try:
                page = client.search_tenders(
                    category=cat,
                    dept_id=portal_id,
                    tender_number=number,
                    size=10,
                )
                for r in page.tenders:
                    r_num = str(r.get("tenderNumber") or r.get("tender_number") or "").strip().upper()
                    if r_num == number.upper():
                        matched_row = r
                        matched_row["category"] = cat
                        break
                if matched_row:
                    break
            except Exception as exc:
                logger.warning("Search failed for %s (%s): %s", number, cat, exc)

        check_time = now_utc()
        if matched_row:
            checked += 1
            with connect() as conn:
                upsert_public_tender(conn, matched_row, expected_department=dept_code, client=client)
                conn.execute(
                    "UPDATE quoted_tenders SET last_checked_at = ? WHERE state = ? AND tender_number = ?",
                    (check_time, STATE, number),
                )

                # Fetch and evaluate comparative statement / bids if tender is non-published
                current_status = str(matched_row.get("status") or "").upper()
                nit_id = matched_row.get("nitId") or quote["nit_id"]
                category = matched_row.get("category") or "GOODS"

                if current_status != "PUBLISHED" and nit_id:
                    comp_bytes = None
                    itemwise_bids = None

                    # 1. Download comparative statement
                    try:
                        comp_bytes = client.download_commercial_comparison(nit_id, category=category)
                    except Exception:
                        pass

                    # 2. Get all itemwise selected bids
                    try:
                        itemwise_bids = client.get_all_itemwise_selected_bids(nit_id, category=category)
                    except Exception:
                        pass

                    if comp_bytes or itemwise_bids:
                        eval_res = evaluate_and_reconcile_tender(
                            tender_number=number,
                            comp_statement_bytes=comp_bytes,
                            itemwise_selected_supplier=itemwise_bids,
                        )
                        save_tender_bids(conn, number, eval_res)
        else:
            missing.append(number)
            with connect() as conn:
                conn.execute(
                    "UPDATE quoted_tenders SET last_checked_at = ? WHERE state = ? AND tender_number = ?",
                    (check_time, STATE, number),
                )

        if idx % 5 == 0 or idx == len(quotes):
            with connect() as conn:
                conn.execute(
                    "UPDATE scan_state SET message = ? WHERE state = ? AND source_name = 'quote-watch'",
                    (f"Checked {idx} of {len(quotes)} quoted tenders.", STATE),
                )

    completed_at = now_utc()
    summary_msg = f"Watch checked {checked} found, {len(missing)} not yet found, out of {len(quotes)} quoted tenders."
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO scan_state(state, source_name, status, started_at, completed_at, message)
            VALUES (?, 'quote-watch', 'completed', ?, ?, ?)
            ON CONFLICT(state, source_name) DO UPDATE SET
                status='completed', started_at=excluded.started_at,
                completed_at=excluded.completed_at, message=excluded.message
            """,
            (STATE, started_at, completed_at, summary_msg),
        )
    logger.info(summary_msg)


def recheck_non_final_tenders(client: KpppClient) -> int:
    """
    Rechecks active non-final tenders:
    status NOT IN ('AWARDED', 'RECALLED', 'RETENDERED')
    Updates statuses, closing dates, full view, and bids for changing tenders.
    """
    ensure_schema()
    with connect() as conn:
        tenders = conn.execute(
            """
            SELECT tender_number, category, status, department_code, nit_id, portal_tender_id
            FROM tenders
            WHERE state = ? AND in_scope = 1
              AND (status IS NULL OR status NOT IN ('AWARDED', 'RECALLED', 'RETENDERED'))
            ORDER BY updated_at ASC
            LIMIT 200
            """,
            (STATE,),
        ).fetchall()

    if not tenders:
        logger.info("Non-final tender recheck: all focus department tenders are in final state.")
        return 0

    logger.info("Rechecking %d active non-final tenders...", len(tenders))
    dept_ids = {code: portal_id for code, portal_id in FOCUS_DEPARTMENTS}
    updated = 0

    for t in tenders:
        num = t["tender_number"]
        dept_code = t["department_code"] or num.split("/", 1)[0].upper()
        portal_id = dept_ids.get(dept_code)
        if portal_id is None:
            continue
        category = t["category"] or "GOODS"

        try:
            page = client.search_tenders(
                category=category,
                dept_id=portal_id,
                tender_number=num,
                size=5,
            )
            matched = None
            for r in page.tenders:
                r_num = str(r.get("tenderNumber") or r.get("tender_number") or "").strip().upper()
                if r_num == num.upper():
                    matched = r
                    matched["category"] = category
                    break

            if matched:
                with connect() as conn:
                    upsert_public_tender(conn, matched, expected_department=dept_code, client=client)
                    updated += 1

                    cur_status = str(matched.get("status") or "").upper()
                    nit_id = matched.get("nitId") or t["nit_id"] or matched.get("id")
                    if cur_status != "PUBLISHED" and nit_id:
                        comp_bytes = None
                        itemwise_bids = None
                        try:
                            comp_bytes = client.download_commercial_comparison(nit_id, category=category)
                        except Exception:
                            pass
                        try:
                            itemwise_bids = client.get_all_itemwise_selected_bids(nit_id, category=category)
                        except Exception:
                            pass
                        if comp_bytes or itemwise_bids:
                            eval_res = evaluate_and_reconcile_tender(
                                tender_number=num,
                                comp_statement_bytes=comp_bytes,
                                itemwise_selected_supplier=itemwise_bids,
                            )
                            save_tender_bids(conn, num, eval_res)
        except Exception as exc:
            logger.debug("Active recheck error for %s: %s", num, exc)

    logger.info("Non-final tender recheck finished: %d tenders refreshed.", updated)
    return updated


def main() -> None:
    ensure_schema()
    client = KpppClient(delay=0.4, connect_timeout=10.0, read_timeout=60.0)
    next_full_check = 0.0

    logger.info("Starting KPPP Daily Update Loop (Quoted every 15m, 7-day delta hourly)...")
    while True:
        now = time.monotonic()
        try:
            logger.info("Executing 15-minute quoted-tender watch check...")
            check_quotes(client)

            if now >= next_full_check:
                next_full_check = now + FULL_INTERVAL_SECONDS
                logger.info("Starting hourly 7-day delta update (no --refresh)...")
                try:
                    # Run 7-day delta without refresh so multi-year history is not restarted
                    subprocess.run(
                        [sys.executable, "backfill.py", "--days", "7"],
                        check=True,
                        timeout=1800,
                    )
                except Exception as exc:
                    logger.error("Hourly 7-day delta backfill run failed: %s", exc)

                logger.info("Starting recheck of non-final active tenders...")
                try:
                    recheck_non_final_tenders(client)
                except Exception as exc:
                    logger.error("Non-final tender recheck failed: %s", exc)

        except (PortalRateLimitError, PortalAccessError) as exc:
            logger.critical("Portal access error in daily loop: %s. Sleeping 30m before retry.", exc)
            time.sleep(1800)
        except Exception as exc:
            logger.exception("Error in update loop: %s", exc)
            failed_at = now_utc()
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO scan_state(state, source_name, status, started_at, completed_at, message)
                    VALUES (?, 'quote-watch', 'failed', ?, ?, ?)
                    ON CONFLICT(state, source_name) DO UPDATE SET
                        status='failed', completed_at=excluded.completed_at, message=excluded.message
                    """,
                    (STATE, failed_at, failed_at, str(exc)),
                )

        logger.info("Sleeping %d seconds until next quote-watch check...", QUOTE_INTERVAL_SECONDS)
        time.sleep(QUOTE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
