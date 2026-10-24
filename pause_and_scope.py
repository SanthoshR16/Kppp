"""
pause_and_scope.py
- Marks out-of-scope tenders in DB as `in_scope=0`
- Moves raw folders for out-of-scope depts to data/paused_full_extract/
- Prints before/after counts
Run once. Safe to re-run (idempotent).
"""
import sqlite3, shutil, os, json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "db" / "kppp.sqlite"
RAW_DIR = BASE_DIR / "data" / "raw"
PAUSED_DIR = BASE_DIR / "data" / "paused_full_extract"
PAUSED_DIR.mkdir(parents=True, exist_ok=True)

SCOPE_CODES = {
    "AHF", "AHVS", "BBMP", "BMCRI", "DHFWS", "DME", "ESISMS",
    "HGML", "INU", "KKRDB", "KSMSCL", "KVAFSU", "NIMHANS",
    "RVS", "SDSTRGI", "SGITO", "SJICR"
}

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
cur = conn.cursor()

# Add in_scope column if missing
cols = [r[1] for r in cur.execute("PRAGMA table_info(tenders)").fetchall()]
if "in_scope" not in cols:
    cur.execute("ALTER TABLE tenders ADD COLUMN in_scope INTEGER DEFAULT 1")
    conn.commit()
    print("Added in_scope column to tenders table")

# Mark in-scope
cur.execute("UPDATE tenders SET in_scope = 1 WHERE department_code IN ({})".format(
    ",".join("?" * len(SCOPE_CODES))), list(SCOPE_CODES))
in_scope_count = cur.rowcount

# Mark out-of-scope
cur.execute("UPDATE tenders SET in_scope = 0 WHERE department_code NOT IN ({})".format(
    ",".join("?" * len(SCOPE_CODES))), list(SCOPE_CODES))
out_scope_count = cur.rowcount

conn.commit()

cur.execute("SELECT COUNT(*) FROM tenders WHERE in_scope=1")
total_in = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM tenders WHERE in_scope=0")
total_out = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM tenders")
total_all = cur.fetchone()[0]
conn.close()

print(f"\nDB Scope Update:")
print(f"  Total tenders: {total_all}")
print(f"  In-scope (17 depts): {total_in}")
print(f"  Out-of-scope: {total_out}")

# Move raw folders for out-of-scope depts
# Raw folder layout: data/raw/<tender_number_safe>/
# We identify out-of-scope by loading full_view.json or checking dept
moved_dirs = []
kept_dirs = []

if RAW_DIR.exists():
    for tender_dir in RAW_DIR.iterdir():
        if not tender_dir.is_dir():
            continue
        # Try to identify dept from full_view.json
        fv = tender_dir / "full_view.json"
        dept_code = None
        if fv.exists():
            try:
                data = json.load(open(fv))
                dept_code = (
                    data.get("deptCode") or
                    data.get("departmentCode") or
                    (data.get("department") or {}).get("deptCode")
                )
            except Exception:
                pass
        
        if dept_code and dept_code.upper() not in SCOPE_CODES:
            dest = PAUSED_DIR / tender_dir.name
            if not dest.exists():
                shutil.move(str(tender_dir), str(dest))
                moved_dirs.append(tender_dir.name)
            else:
                moved_dirs.append(f"{tender_dir.name} (already moved)")
        else:
            kept_dirs.append(tender_dir.name)

print(f"\nRaw folder audit:")
print(f"  Kept (in-scope or unidentifiable): {len(kept_dirs)}")
print(f"  Moved to paused_full_extract: {len(moved_dirs)}")
if moved_dirs:
    for d in moved_dirs:
        print(f"    MOVED: {d}")

print("\nPause complete. Nothing deleted. Checkpoint and all data preserved.")
