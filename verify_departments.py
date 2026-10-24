import json
import sqlite3
import sys
from typing import Dict, List, Optional

from app.database import FOCUS_DEPARTMENTS, STATE, connect, ensure_schema
from kppp_client import KpppClient, PortalError

# The canonical 17 focus departments and their portal IDs
CANONICAL_DEPARTMENTS = dict(FOCUS_DEPARTMENTS)


def normalize_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return " ".join(str(name).strip().upper().split())


def verify_departments() -> None:
    print("=" * 110)
    print(" KPPP LIVE VERIFICATION: 17 FOCUS DEPARTMENTS & PORTAL IDs")
    print("=" * 110)

    client = KpppClient(delay=0.4)
    try:
        active_depts = client.get_active_departments()
    except PortalError as exc:
        print(f"\n[ERROR] Failed to fetch active departments from portal: {exc}")
        print("Run `python diagnose.py` to check network reachability.")
        sys.exit(1)

    print(f"Total active departments reported by portal: {len(active_depts)}")

    # Index by department ID
    portal_by_id: Dict[int, str] = {}
    portal_by_name: Dict[str, int] = {}
    for item in active_depts:
        did = item.get("id") or item.get("deptId")
        name = item.get("deptName") or item.get("name") or item.get("departmentName")
        if did is not None and name:
            try:
                int_id = int(did)
                portal_by_id[int_id] = str(name).strip()
                portal_by_name[normalize_name(name)] = int_id
            except (ValueError, TypeError):
                continue

    ensure_schema()
    mismatches = []
    verified_count = 0

    print(f"\n{'CODE':<9} | {'EXPECTED ID':<11} | {'PORTAL VERIFIED NAME':<55} | {'MATCH STATUS'}")
    print("-" * 110)

    with connect() as conn:
        for code, expected_id in sorted(CANONICAL_DEPARTMENTS.items()):
            actual_name = portal_by_id.get(expected_id)

            if actual_name:
                verified_count += 1
                status = "VERIFIED [OK]"
                # Update SQLite database
                conn.execute(
                    """
                    INSERT INTO focus_departments(state, department_code, portal_id, department_name, name_verified, name_source)
                    VALUES (?, ?, ?, ?, 1, 'live portal activeDepartment')
                    ON CONFLICT(state, department_code) DO UPDATE SET
                        portal_id = excluded.portal_id,
                        department_name = excluded.department_name,
                        name_verified = 1,
                        name_source = 'live portal activeDepartment'
                    """,
                    (STATE, code, expected_id, actual_name),
                )
            else:
                status = "MISMATCH / NOT FOUND"
                mismatches.append((code, expected_id))

            display_name = actual_name if actual_name else "--- NOT FOUND IN PORTAL BY ID ---"
            if len(display_name) > 53:
                display_name = display_name[:50] + "..."
            print(f"{code:<9} | {expected_id:<11} | {display_name:<55} | {status}")

    print("=" * 110)
    print(f"Summary: {verified_count}/{len(CANONICAL_DEPARTMENTS)} focus departments verified against live portal.")

    if mismatches:
        print("\n[WARNING] Following departments had ID mismatches or were missing:")
        for code, expected_id in mismatches:
            print(f"  - {code}: Expected ID {expected_id} not found in active departments list.")
    else:
        print("\nAll 17 focus departments match active portal IDs perfectly. Database updated.")


if __name__ == "__main__":
    verify_departments()
