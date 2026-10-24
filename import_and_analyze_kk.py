import os, sys, glob, json, re, sqlite3
from pathlib import Path
from comp_parser import parse_comparative_statement

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "db" / "kppp.sqlite"
RAW_DIR = BASE_DIR / "data" / "raw"
EXCEL_INDS_FILE = BASE_DIR / "data" / "existing_excel_inds.json"

RAW_NAMES = ["K K ALLIANZE", "KAMAL KUMAR PARASMAL JAIN", "KAMAL KUMAR P JAIN"]
COMPANY_IDS = ["5086"]

def is_our_company(name_str):
    if not name_str:
        return False
    n = name_str.upper().replace(".", "").replace("-", " ").replace("(", " ").replace(")", " ")
    n = re.sub(r'\s+', ' ', n).strip()
    for raw in RAW_NAMES:
        clean = raw.upper().replace(".", "").replace("-", " ")
        clean = re.sub(r'\s+', ' ', clean).strip()
        if clean in n or n in clean:
            return True
    if "ALLIANZE" in n or "ALLIANCE" in n:
        return "needs_confirmation"
    return False

# Load existing Excel INDs
existing_inds = set()
if EXCEL_INDS_FILE.exists():
    existing_inds = set(json.loads(EXCEL_INDS_FILE.read_text()))

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")
cur = conn.cursor()

# Find all comparative statement files
probe_raw = glob.glob(r"C:\Users\Admin\Desktop\kppp_probe\kk_extraction\raw\*.xlsx")
platform_raw = glob.glob(str(RAW_DIR / "**" / "comparative_statement.xlsx"), recursive=True)
all_comp_files = list(set(probe_raw + platform_raw))

print(f"Total comparative statement workbooks to analyze: {len(all_comp_files)}")

results = {
    "participated": [],
    "won_all": [],
    "won_part": [],
    "lost": [],
    "retendered": [],
    "result_not_public": [],
    "needs_confirmation": [],
    "unknown_to_us": [],
    "total_value_won": 0.0,
    "check_flags": []
}

for fp in all_comp_files:
    fname = os.path.basename(fp)
    # Extract tender number
    # Probe naming: Comparative_Statement_<nit>_<dept>_<year>_<ind>.xlsx
    m = re.search(r'([A-Z0-9]+_\d{4}-\d{2}_[A-Z0-9_-]+)\.xlsx', fname)
    if m:
        raw_num = m.group(1)
        # convert _ back to /
        parts = raw_num.split("_")
        if len(parts) >= 3:
            dept = parts[0]
            year = parts[1]
            ind = "_".join(parts[2:]).replace("_CALL-", "/CALL-")
            tender_num = f"{dept}/{year}/{ind}"
        else:
            tender_num = raw_num
    else:
        # Platform folder structure: .../<tender_safe>/comparative_statement.xlsx
        parent = os.path.basename(os.path.dirname(fp))
        tender_num = parent.replace("_", "/")

    try:
        meta, bidders, items, bids = parse_comparative_statement(fp)
    except Exception as e:
        continue

    our_bids = []
    other_bids = []
    needs_conf_bidders = []

    for b in bids:
        s_name = b.get("supplier_name", "")
        match = is_our_company(s_name)
        if match is True:
            our_bids.append(b)
        elif match == "needs_confirmation":
            needs_conf_bidders.append((s_name, tender_num))
        else:
            other_bids.append(b)

    if needs_conf_bidders:
        for nc in needs_conf_bidders:
            results["needs_confirmation"].append({"supplier_name": nc[0], "tender_number": nc[1]})

    if not our_bids:
        # We did not participate in this tender
        continue

    # We participated!
    results["participated"].append(tender_num)

    # Check against existing Excel
    # IND number format check
    ind_match = False
    for ind_key in existing_inds:
        if ind_key in tender_num:
            ind_match = True
            break
    if not ind_match:
        results["unknown_to_us"].append(tender_num)
        unknown_val = 1
    else:
        unknown_val = 0

    # Determine WON_ALL, WON_PART, LOST
    our_wins = [b for b in our_bids if b.get("selected")]
    all_selected = [b for b in bids if b.get("selected")]

    tender_won_val = sum(float(b.get("total") or 0) for b in our_wins)
    results["total_value_won"] += tender_won_val

    if len(our_wins) == len(bids) and len(bids) > 0:
        res_code = "WON_ALL"
        results["won_all"].append({"tender": tender_num, "value": tender_won_val})
    elif len(our_wins) > 0:
        res_code = "WON_PART"
        results["won_part"].append({"tender": tender_num, "value": tender_won_val})
    else:
        res_code = "LOST"
        results["lost"].append(tender_num)

    # Save to SQLite bids table
    for b in bids:
        is_sel = 1 if b.get("selected") else 0
        cur.execute("""
            INSERT OR REPLACE INTO bids (
                state, tender_number, item_name, supplier_id, supplier_name,
                rate, total, rank, selected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "karnataka", tender_num, b.get("item_name", ""),
            "5086" if is_our_company(b.get("supplier_name")) is True else "",
            b.get("supplier_name", ""), b.get("rate"), b.get("total"),
            b.get("rank"), is_sel
        ))

    # Upsert tender record if missing or update flags
    dept_code = tender_num.split("/")[0] if "/" in tender_num else "UNKNOWN"
    cur.execute("""
        INSERT INTO tenders (
            state, tender_number, department_code, status, found_automatically, unknown_to_us, in_scope, updated_at
        ) VALUES (?, ?, ?, 'AWARDED', 1, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(state, tender_number) DO UPDATE SET
            found_automatically=1,
            unknown_to_us=excluded.unknown_to_us,
            in_scope=1,
            updated_at=CURRENT_TIMESTAMP
    """, ("karnataka", tender_num, dept_code, unknown_val))

    # Check flags for math integrity
    for b in our_bids:
        r = float(b.get("rate") or 0)
        q = float(b.get("qty") or 0) if b.get("qty") else None
        tot = float(b.get("total") or 0)
        if q and r and tot:
            calc = round(r * q, 2)
            if abs(calc - tot) > 1.0:
                flag_msg = f"{tender_num}: item '{b.get('item_name')}' rate {r} * qty {q} = {calc} != total {tot}"
                results["check_flags"].append(flag_msg)
                cur.execute("""
                    INSERT OR REPLACE INTO flags (state, tender_number, flag_key, flag_value, reason)
                    VALUES (?, ?, 'MATH_MISMATCH', ?, ?)
                """, ("karnataka", tender_num, str(tot), flag_msg))

conn.commit()
conn.close()

with open("data/kk_allianze_analysis.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*60)
print("K.K. ALLIANZE EXTRACTION & PARTICIPATION SUMMARY")
print("="*60)
print(f"Total tenders participated: {len(results['participated'])}")
print(f"  - Won all items:          {len(results['won_all'])}")
print(f"  - Won part of items:      {len(results['won_part'])}")
print(f"  - Lost tenders:           {len(results['lost'])}")
print(f"  - Total value won:        Rs. {results['total_value_won']:,.2f}")
print(f"  - Needs confirmation:     {len(results['needs_confirmation'])}")
print(f"  - Unknown to us (new):    {len(results['unknown_to_us'])}")
print(f"  - CHECK flags:            {len(results['check_flags'])}")
print("="*60)
