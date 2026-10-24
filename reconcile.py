import argparse
import sys
from typing import Dict, Optional, Tuple

from app.database import FOCUS_DEPARTMENTS, STATE, connect, ensure_schema
from kppp_client import KpppClient, PortalError

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


def get_stored_counts() -> Dict[Tuple[str, str, str], int]:
    ensure_schema()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT department_code, upper(category) as category, upper(status) as status, count(*) as cnt
            FROM tenders
            WHERE state = ? AND coalesce(out_of_scope, 0) = 0
            GROUP BY department_code, upper(category), upper(status)
            """,
            (STATE,),
        ).fetchall()
        return {
            (str(r["department_code"]).upper(), str(r["category"]).upper(), str(r["status"]).upper()): r["cnt"]
            for r in rows
        }


def reconcile(offline: bool = False, dept_filter: Optional[str] = None) -> None:
    print("=" * 115)
    print(" KPPP RECONCILIATION AUDIT: PORTAL vs LOCAL DATABASE")
    print("=" * 115)

    stored_counts = get_stored_counts()
    client = KpppClient(delay=0.35) if not offline else None

    print(f"{'DEPT':<9} | {'CATEGORY':<9} | {'STATUS':<22} | {'PORTAL':<8} | {'STORED':<8} | {'GAP':<8} | {'STATE'}")
    print("-" * 115)

    total_portal = 0
    total_stored = 0
    total_gap = 0
    mismatch_rows = []

    for code, portal_id in FOCUS_DEPARTMENTS:
        if dept_filter and code.upper() != dept_filter.upper():
            continue

        for cat in CATEGORIES:
            for st in STATUSES:
                stored = stored_counts.get((code, cat, st), 0)
                total_stored += stored

                if offline:
                    portal_cnt = "-"
                    gap = "-"
                    match_str = "OFFLINE"
                else:
                    try:
                        page = client.search_tenders(category=cat, status=st, dept_id=portal_id, size=1)
                        p_total = page.total_count if page.total_count is not None else 0
                        portal_cnt = str(p_total)
                        total_portal += p_total
                        diff = p_total - stored
                        gap = str(diff) if diff != 0 else "0"
                        if diff == 0:
                            match_str = "MATCH [OK]"
                        elif diff > 0:
                            match_str = f"MISSING ({diff})"
                            total_gap += diff
                            mismatch_rows.append((code, cat, st, p_total, stored, diff))
                        else:
                            match_str = f"EXTRA ({-diff})"
                    except PortalError as exc:
                        portal_cnt = "ERR"
                        gap = "ERR"
                        match_str = f"API FAIL ({exc})"

                # Only print non-zero rows or if mismatch
                if stored > 0 or portal_cnt not in ("0", "-", "ERR") or match_str != "MATCH [OK]":
                    print(
                        f"{code:<9} | {cat:<9} | {st:<22} | {str(portal_cnt):<8} | "
                        f"{stored:<8} | {str(gap):<8} | {match_str}"
                    )

    print("=" * 115)
    print(f"Summary: Local Stored Tenders = {total_stored}")
    if not offline:
        print(f"         Live Portal Total    = {total_portal}")
        print(f"         Total Gap (Missing)  = {total_gap}")
        if total_gap > 0:
            print(f"\n[ATTENTION] Found {len(mismatch_rows)} category/status groups with missing tenders.")
            print("Run `python backfill.py` to fill missing records.")
        else:
            print("\n>>> RECONCILIATION PERFECT: 100% of portal tenders are present in local database.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconcile KPPP Portal vs SQLite tenders")
    parser.add_argument("--offline", action="store_true", help="Print stored database breakdown without querying portal")
    parser.add_argument("--dept", type=str, default=None, help="Reconcile specific department code (e.g. DME)")
    args = parser.parse_args()
    reconcile(offline=args.offline, dept_filter=args.dept)
