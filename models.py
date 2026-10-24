from __future__ import annotations

import json, os, glob
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from config import STATE_NAME
from database import get_connection

BASE_DIR = Path(__file__).resolve().parent

SCOPE_DEPTS = [
    "AHF", "AHVS", "BBMP", "BMCRI", "DHFWS", "DME", "ESISMS", "HGML",
    "INU", "KKRDB", "KSMSCL", "KVAFSU", "NIMHANS", "RVS", "SDSTRGI",
    "SGITO", "SJICR"
]

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def get_dashboard_stats() -> Dict[str, Any]:
    with get_connection() as conn:
        tender_count = conn.execute("SELECT COUNT(*) as count FROM tenders WHERE state = ? AND in_scope = 1", (STATE_NAME,)).fetchone()["count"]
        dept_count = len(SCOPE_DEPTS)
        latest_run = conn.execute("SELECT id, started_at, status FROM scan_runs WHERE state = ? ORDER BY id DESC LIMIT 1", (STATE_NAME,)).fetchone()
        last_watermark = conn.execute("SELECT last_successful_scan_date FROM watermarks WHERE state = ? ORDER BY updated_at DESC LIMIT 1", (STATE_NAME,)).fetchone()
        
        # KK Allianze summary
        my_tenders_count = conn.execute("SELECT COUNT(*) as count FROM tenders WHERE state = ? AND in_scope = 1 AND found_automatically = 1", (STATE_NAME,)).fetchone()["count"]
        unknown_count = conn.execute("SELECT COUNT(*) as count FROM tenders WHERE state = ? AND in_scope = 1 AND unknown_to_us = 1", (STATE_NAME,)).fetchone()["count"]
        
        # Bids won value
        won_row = conn.execute("""
            SELECT SUM(total) as won_val FROM bids
            WHERE state = ? AND selected = 1 AND (supplier_name LIKE '%ALLIANZE%' OR supplier_name LIKE '%KAMAL%')
        """, (STATE_NAME,)).fetchone()
        won_val = won_row["won_val"] if won_row and won_row["won_val"] else 0.0

    return {
        "tender_count": tender_count,
        "department_count": dept_count,
        "my_tenders_count": my_tenders_count,
        "unknown_count": unknown_count,
        "total_won_val": round(won_val, 2),
        "last_run": dict(latest_run) if latest_run else None,
        "last_successful_scan_date": last_watermark["last_successful_scan_date"] if last_watermark else None,
    }

def list_departments() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        placeholders = ','.join('?' * len(SCOPE_DEPTS))
        rows = conn.execute(f"""
            SELECT d.department_code, d.department_name, d.status, COUNT(t.id) as tender_count
            FROM departments d
            LEFT JOIN tenders t ON (t.department_code = d.department_code OR t.department_code = CAST(d.id AS TEXT)) AND t.in_scope = 1
            WHERE d.state = ? AND d.department_code IN ({placeholders})
            GROUP BY d.department_code
            ORDER BY d.department_name
        """, [STATE_NAME] + SCOPE_DEPTS).fetchall()
    return [dict(row) for row in rows]

def list_tenders(
    limit: int = 100,
    department_code: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    my_tenders_only: bool = False,
    unknown_only: bool = False
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM tenders WHERE state = ? AND in_scope = 1"
    params: List[Any] = [STATE_NAME]

    if department_code:
        query += " AND (department_code = ? OR department_name LIKE ?)"
        params.extend([department_code, f"%{department_code}%"])
    if status:
        query += " AND status = ?"
        params.append(status)
    if search:
        query += " AND tender_number LIKE ?"
        params.append(f"%{search}%")
    if my_tenders_only:
        query += " AND found_automatically = 1"
    if unknown_only:
        query += " AND unknown_to_us = 1"

    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]

def get_tender_by_number(tender_number: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tenders WHERE state = ? AND tender_number = ? AND in_scope = 1",
            (STATE_NAME, tender_number),
        ).fetchone()
        if not row:
            # Fallback search without in_scope check
            row = conn.execute(
                "SELECT * FROM tenders WHERE state = ? AND tender_number = ?",
                (STATE_NAME, tender_number),
            ).fetchone()
            if not row:
                return None
        t_data = dict(row)
        
        # Bids
        bids = [dict(b) for b in conn.execute(
            "SELECT * FROM bids WHERE state = ? AND tender_number = ? ORDER BY item_name, rank ASC",
            (STATE_NAME, tender_number)
        ).fetchall()]
        t_data["bids"] = bids
        
        # Flags
        flags = [dict(f) for f in conn.execute(
            "SELECT * FROM flags WHERE state = ? AND tender_number = ?",
            (STATE_NAME, tender_number)
        ).fetchall()]
        t_data["flags"] = flags

    # Look for files on disk in raw/
    safe_num = tender_number.replace("/", "_")
    matched_dirs = glob.glob(str(BASE_DIR / "data" / "raw" / "**" / safe_num), recursive=True)
    if not matched_dirs:
        matched_dirs = glob.glob(str(BASE_DIR / "data" / "raw" / safe_num))
    
    docs = []
    if matched_dirs:
        tdir = Path(matched_dirs[0])
        docs_dir = tdir / "docs"
        if docs_dir.exists():
            mf = docs_dir / "manifest.json"
            if mf.exists():
                try:
                    docs = json.loads(mf.read_text())
                except Exception:
                    pass
            if not docs:
                for f in docs_dir.iterdir():
                    if f.name != "manifest.json":
                        docs.append({"file_name": f.name, "size": f.stat().st_size})
        # Check comparative statement
        cs = tdir / "comparative_statement.xlsx"
        if cs.exists():
            docs.append({"file_name": "comparative_statement.xlsx", "size": cs.stat().st_size, "is_comp": True})

    t_data["documents"] = docs
    return t_data

def get_tender_history(tender_number: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tender_status_history WHERE state = ? AND tender_number = ? ORDER BY changed_at ASC",
            (STATE_NAME, tender_number),
        ).fetchall()
    return [dict(row) for row in rows]

def get_company_analysis() -> Dict[str, Any]:
    with get_connection() as conn:
        # All tenders where KK participated
        cur = conn.cursor()
        tenders = [dict(r) for r in cur.execute("""
            SELECT DISTINCT t.tender_number, t.department_code, t.department_name, t.category, t.status, t.published_date, t.unknown_to_us
            FROM tenders t
            JOIN bids b ON t.tender_number = b.tender_number
            WHERE (b.supplier_name LIKE '%ALLIANZE%' OR b.supplier_name LIKE '%KAMAL%')
            ORDER BY t.tender_number DESC
        """).fetchall()]

        # All bids by KK
        kk_bids = [dict(r) for r in cur.execute("""
            SELECT b.*, t.department_code
            FROM bids b
            JOIN tenders t ON b.tender_number = t.tender_number
            WHERE (b.supplier_name LIKE '%ALLIANZE%' OR b.supplier_name LIKE '%KAMAL%')
        """).fetchall()]

        # Winning bids by competitors in tenders KK lost
        lost_items = [dict(r) for r in cur.execute("""
            SELECT b1.tender_number, b1.item_name, b1.rate as our_rate, b1.total as our_total, b1.rank as our_rank,
                   b2.supplier_name as winner_name, b2.rate as winner_rate, b2.total as winner_total
            FROM bids b1
            JOIN bids b2 ON b1.tender_number = b2.tender_number AND b1.item_name = b2.item_name
            WHERE (b1.supplier_name LIKE '%ALLIANZE%' OR b1.supplier_name LIKE '%KAMAL%')
              AND b1.selected = 0
              AND b2.selected = 1
              AND b2.supplier_name NOT LIKE '%ALLIANZE%' AND b2.supplier_name NOT LIKE '%KAMAL%'
            ORDER BY b1.tender_number, b1.item_name
        """).fetchall()]

        # Won items
        won_items = [dict(r) for r in cur.execute("""
            SELECT b.tender_number, b.item_name, b.rate, b.total, b.rank
            FROM bids b
            WHERE (b.supplier_name LIKE '%ALLIANZE%' OR b.supplier_name LIKE '%KAMAL%')
              AND b.selected = 1
            ORDER BY b.tender_number
        """).fetchall()]

    # Aggregates
    won_tenders = set(w["tender_number"] for w in won_items)
    all_tenders = set(t["tender_number"] for t in tenders)
    lost_tenders = all_tenders - won_tenders
    total_won_val = sum(float(w["total"] or 0) for w in won_items)

    # Competitors who beat us
    competitors = {}
    for li in lost_items:
        w = li["winner_name"]
        competitors[w] = competitors.get(w, 0) + 1

    return {
        "total_participated": len(all_tenders),
        "total_won_tenders": len(won_tenders),
        "total_lost_tenders": len(lost_tenders),
        "total_won_value": round(total_won_val, 2),
        "tenders": tenders,
        "won_items": won_items,
        "lost_items": lost_items,
        "competitors_who_beat_us": sorted([{"name": k, "times_beat_us": v} for k, v in competitors.items()], key=lambda x: x["times_beat_us"], reverse=True)
    }

def get_scan_runs(limit: int = 15) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM scan_runs WHERE state = ? ORDER BY started_at DESC LIMIT ?",
            (STATE_NAME, limit),
        ).fetchall()
    return [dict(row) for row in rows]

def set_watermark(source_name: str, date_value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO watermarks (state, source_name, last_successful_scan_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(state, source_name)
            DO UPDATE SET last_successful_scan_date=excluded.last_successful_scan_date, updated_at=excluded.updated_at
            """,
            (STATE_NAME, source_name, date_value, utc_now(), utc_now()),
        )
        conn.commit()
