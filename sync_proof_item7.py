import sqlite3, json, os, glob
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "db" / "kppp.sqlite"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

proof_files = glob.glob(str(BASE_DIR / "data" / "raw" / "proof_item7" / "*" / "full_view.json"))
print(f"Syncing {len(proof_files)} full_view files to SQLite...")

for pf in proof_files:
    fv = json.loads(open(pf, encoding="utf-8").read())
    sched = fv.get("tenderSchedule") or {}
    nit = fv.get("noticeInvitingTenderDTO") or {}
    
    t_num = sched.get("tenderNumber")
    dept_name = sched.get("deptName")
    ecv = str(sched.get("ecv") or "")
    emd = str(nit.get("emd") or "")
    fee = str(nit.get("tenderFee") or "")
    pub = str(nit.get("publishedDate") or "")
    close = str(nit.get("tenderReceiptClose") or "")
    cat = sched.get("category") or "GOODS"
    
    cur.execute("""
        UPDATE tenders SET
            department_name = ?,
            estimated_value = ?,
            emd_amount = ?,
            fee_amount = ?,
            published_date = ?,
            closing_date = ?,
            category = ?,
            in_scope = 1
        WHERE tender_number = ?
    """, (dept_name, ecv, emd, fee, pub, close, cat, t_num))

conn.commit()
conn.close()
print("Synced successfully.")
