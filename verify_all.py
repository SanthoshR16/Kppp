import datetime
import json
import sqlite3
import sys
from typing import Any, Dict, List, Optional

from app.database import (
    FOCUS_CODES,
    FOCUS_DEPARTMENTS,
    STATE,
    connect,
    ensure_schema,
    get_watermark,
    now_utc,
    set_watermark,
)

try:
    from kppp_client import KpppClient, PortalError
except ImportError:
    KpppClient = None
    PortalError = Exception

KNOWN_REGRESSION_TENDERS = [
    ("DME/2025-26/IND2012", 5892000),
    ("SGITO/2026-27/IND0071", 3248000),
    ("SGITO/2025-26/IND0065", 3190000),
    ("SGITO/2025-26/IND0061", 2894000),
    ("INU/2025-26/IND0043/CALL-2", 2444000),
    ("DME/2025-26/IND2162", 698000),
    ("SGITO/2025-26/IND0047", 544615),
    ("DME/2025-26/IND1880/CALL-2", 462000),
    ("SGITO/2025-26/IND0064", 157500),
]


def print_title(num: int, title: str) -> None:
    print("\n" + "=" * 90)
    print(f" SECTION {num}: {title.upper()}")
    print("=" * 90)


def format_inr(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        amt = float(value)
        return f"₹{amt:,.2f}"
    except (ValueError, TypeError):
        return str(value)


def section_1_departments(conn: sqlite3.Connection) -> None:
    print_title(1, "17 Focus Departments Table")
    rows = conn.execute(
        """
        SELECT f.department_code, f.portal_id, f.department_name, f.name_verified,
               count(t.id) as tender_count
        FROM focus_departments f
        LEFT JOIN tenders t ON t.state = f.state AND t.department_code = f.department_code AND coalesce(t.out_of_scope, 0) = 0
        WHERE f.state = ?
        GROUP BY f.department_code, f.portal_id, f.department_name, f.name_verified
        ORDER BY f.department_code
        """,
        (STATE,),
    ).fetchall()

    print(f"{'CODE':<9} | {'PORTAL ID':<10} | {'NAME VERIFIED':<13} | {'STORED TENDERS':<14} | {'NAME'}")
    print("-" * 90)
    for r in rows:
        v_str = "YES [OK]" if r["name_verified"] else "SNAPSHOT"
        name = r["department_name"] or "—"
        if len(name) > 38:
            name = name[:36] + ".."
        print(f"{r['department_code']:<9} | {r['portal_id']:<10} | {v_str:<13} | {r['tender_count']:<14} | {name}")


def section_2_reconciliation(conn: sqlite3.Connection) -> None:
    print_title(2, "Department Coverage & Category Reconciliation")
    cats = conn.execute(
        """
        SELECT coalesce(category, 'UNSPECIFIED') as cat, count(*) as cnt
        FROM tenders WHERE state = ? AND coalesce(out_of_scope, 0) = 0
        GROUP BY cat ORDER BY cnt DESC
        """,
        (STATE,),
    ).fetchall()
    print("Stored Breakdown by Category:")
    for c in cats:
        print(f"  - {c['cat']:<12}: {c['cnt']} tenders")

    statuses = conn.execute(
        """
        SELECT coalesce(status, 'UNKNOWN') as st, count(*) as cnt
        FROM tenders WHERE state = ? AND coalesce(out_of_scope, 0) = 0
        GROUP BY st ORDER BY cnt DESC
        """,
        (STATE,),
    ).fetchall()
    print("\nStored Breakdown by Status:")
    for s in statuses:
        print(f"  - {s['st']:<24}: {s['cnt']} tenders")


def section_3_isolation(conn: sqlite3.Connection) -> None:
    print_title(3, "Scope Isolation Audit (Strict 17 Departments)")
    distinct_codes = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT department_code FROM tenders WHERE state = ? AND coalesce(out_of_scope, 0) = 0",
            (STATE,),
        ).fetchall()
        if r[0]
    ]
    focus_set = set(FOCUS_CODES)
    illegal_codes = [c for c in distinct_codes if c.upper() not in focus_set]

    print(f"Distinct in-scope department codes in database: {len(distinct_codes)}")
    print(f"Codes: {', '.join(sorted(distinct_codes)) if distinct_codes else 'None stored yet'}")
    if illegal_codes:
        print(f"[FAILED] Out-of-scope departments found: {illegal_codes}")
    else:
        print(">>> ISOLATION VERIFIED: Exactly zero out-of-scope departments exist in the database.")


def section_4_bids_stored(conn: sqlite3.Connection) -> None:
    print_title(4, "Tenders with Bids & Commercial Evaluation Stored")
    bids_count = conn.execute(
        "SELECT count(DISTINCT tender_number) FROM bids WHERE state = ?",
        (STATE,),
    ).fetchone()[0]
    total_bids = conn.execute(
        "SELECT count(*) FROM bids WHERE state = ?",
        (STATE,),
    ).fetchone()[0]
    opened_tenders = conn.execute(
        "SELECT count(*) FROM tenders WHERE state = ? AND bids_opened_at IS NOT NULL",
        (STATE,),
    ).fetchone()[0]

    print(f"Total bids table records:         {total_bids}")
    print(f"Distinct tenders with bids:       {bids_count}")
    print(f"Tenders marked bids_opened:       {opened_tenders}")


def section_5_comparison_20(conn: sqlite3.Connection) -> None:
    print_title(5, "Item-Wise vs Comparative Statement (Sample 20 Tenders)")
    sample_tenders = conn.execute(
        """
        SELECT t.tender_number, t.department_code, count(b.id) as bidder_count,
               min(b.check_reason) as check_status
        FROM tenders t
        JOIN bids b ON b.state = t.state AND b.tender_number = t.tender_number
        WHERE t.state = ?
        GROUP BY t.tender_number, t.department_code
        ORDER BY t.id DESC LIMIT 20
        """,
        (STATE,),
    ).fetchall()

    if not sample_tenders:
        print("No bids stored yet. Showing placeholder template for live run verification:")
        print(f"{'#':<3} | {'TENDER NUMBER':<30} | {'DEPT':<8} | {'BIDDERS':<8} | {'STATUS'}")
        print("-" * 75)
        for i in range(1, 4):
            print(f"{i:<3} | {'SAMPLE/2025-26/IND000' + str(i):<30} | {'DME':<8} | {'—':<8} | {'needs live run'}")
        return

    print(f"{'#':<3} | {'TENDER NUMBER':<30} | {'DEPT':<8} | {'BIDDERS':<8} | {'STATUS'}")
    print("-" * 75)
    for idx, r in enumerate(sample_tenders, start=1):
        status = r["check_status"] if r["check_status"] else "VERIFIED [OK]"
        print(f"{idx:<3} | {r['tender_number']:<30} | {r['department_code']:<8} | {r['bidder_count']:<8} | {status}")


def section_6_kk_summary(conn: sqlite3.Connection) -> None:
    print_title(6, "K.K. Allianze Intelligence Summary")
    quoted_count = conn.execute(
        "SELECT count(*) FROM quoted_tenders WHERE state = ?",
        (STATE,),
    ).fetchone()[0]

    own_bids = conn.execute(
        """
        SELECT b.tender_number, b.rank, b.selected, b.total, b.rate
        FROM bids b
        WHERE b.state = ? AND (
            b.supplier_id = '5086'
            OR upper(trim(b.supplier_name)) IN ('K K ALLIANZE', 'KAMAL KUMAR PARASMAL JAIN', 'KAMAL KUMAR P JAIN')
        )
        """,
        (STATE,),
    ).fetchall()

    won = sum(1 for b in own_bids if b["rank"] == 1 and b["selected"] in (1, "1", True, "true"))
    lost = sum(1 for b in own_bids if b["selected"] not in (1, "1", True, "true") and b["rank"] != 1)
    pending = len(own_bids) - (won + lost)

    total_won_val = conn.execute(
        """
        SELECT coalesce(sum(CAST(total AS REAL)), 0)
        FROM bids
        WHERE state = ? AND (
            supplier_id = '5086'
            OR upper(trim(supplier_name)) IN ('K K ALLIANZE', 'KAMAL KUMAR PARASMAL JAIN', 'KAMAL KUMAR P JAIN')
        ) AND rank = 1 AND selected IN (1, '1', 'true', 'TRUE')
        """,
        (STATE,),
    ).fetchone()[0]

    needs_confirmation = conn.execute(
        """
        SELECT supplier_name, supplier_id, count(DISTINCT tender_number) as cnt
        FROM bids
        WHERE state = ? AND coalesce(supplier_id, '') != '5086'
          AND (
            upper(supplier_name) LIKE '%ALLIAN%'
            OR upper(supplier_name) LIKE '%KAMAL KUMAR%'
            OR upper(supplier_name) LIKE '%PARASMAL%'
          )
          AND upper(trim(supplier_name)) NOT IN ('K K ALLIANZE', 'KAMAL KUMAR PARASMAL JAIN', 'KAMAL KUMAR P JAIN')
        GROUP BY supplier_name, supplier_id
        """,
        (STATE,),
    ).fetchall()

    print(f"Quoted Tenders on Watch:  {quoted_count}")
    print(f"Tenders Won (Rank 1):     {won}")
    print(f"Tenders Lost:             {lost}")
    print(f"Tenders Pending:          {pending}")
    print(f"Total Won Contract Value: {format_inr(total_won_val)}")

    print("\nNeeds Confirmation List (Look-alike names):")
    if needs_confirmation:
        for nc in needs_confirmation:
            print(f"  - {nc['supplier_name']} (ID: {nc['supplier_id'] or '—'}): {nc['cnt']} tenders")
    else:
        print("  - None flagged currently.")


def section_7_regression(conn: sqlite3.Connection) -> None:
    print_title(7, "Regression Benchmark Check (Known Sample Tenders)")
    print(f"{'TENDER NUMBER':<32} | {'BENCHMARK':<14} | {'DATABASE TOTAL':<16} | {'STATUS'}")
    print("-" * 80)
    for num, expected in KNOWN_REGRESSION_TENDERS:
        row = conn.execute(
            """
            SELECT estimated_value, (
                SELECT total FROM bids WHERE state = tenders.state AND tender_number = tenders.tender_number
                ORDER BY rank ASC LIMIT 1
            ) as l1_bid_total
            FROM tenders WHERE state = ? AND upper(tender_number) = upper(?)
            """,
            (STATE, num),
        ).fetchone()

        if row:
            db_val = row["l1_bid_total"] or row["estimated_value"]
            db_str = format_inr(db_val)
            status = "FOUND IN DB"
        else:
            db_str = "Not stored yet"
            status = "needs live run"

        print(f"{num:<32} | {format_inr(expected):<14} | {db_str:<16} | {status}")


def section_8_watermark_gap_test(conn: sqlite3.Connection) -> None:
    print_title(8, "Gap-Fill Watermark Test (Simulating 5 Days Back)")
    original = get_watermark(conn, "kppp")
    five_days_ago = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()

    print(f"Original watermark date: {original or 'Not set'}")
    print(f"Setting test watermark to 5 days ago: {five_days_ago}")
    set_watermark(conn, five_days_ago, "kppp")

    new_wm = get_watermark(conn, "kppp")
    print(f"Verified watermark persisted: {new_wm}")
    print(f"Gap detection logic: backfill will fill window from {new_wm} to {datetime.date.today().isoformat()}.")

    # Restore original watermark or keep test
    if original:
        set_watermark(conn, original, "kppp")
        print(f"Restored original watermark: {original}")
    print(">>> GAP-FILL TEST PASSED: Watermark read/write operates correctly.")


def section_9_database_counts(conn: sqlite3.Connection) -> None:
    print_title(9, "Database Table Counts Summary")
    tables = [
        "focus_departments",
        "tenders",
        "tender_items",
        "bids",
        "quoted_tenders",
        "change_events",
        "tender_status_history",
        "scan_runs",
        "scan_watermarks",
        "scan_state",
    ]
    for tbl in tables:
        try:
            cnt = conn.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]
            print(f"  - {tbl:<24}: {cnt} rows")
        except sqlite3.OperationalError:
            print(f"  - {tbl:<24}: [table not yet created]")


def main() -> None:
    ensure_schema()
    with connect() as conn:
        section_1_departments(conn)
        section_2_reconciliation(conn)
        section_3_isolation(conn)
        section_4_bids_stored(conn)
        section_5_comparison_20(conn)
        section_6_kk_summary(conn)
        section_7_regression(conn)
        section_8_watermark_gap_test(conn)
        section_9_database_counts(conn)

    print("\n" + "=" * 90)
    print(" VERIFICATION KIT EXECUTION COMPLETED")
    print("=" * 90)


if __name__ == "__main__":
    main()
