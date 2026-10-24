import glob, json
from comp_parser import parse_comparative_statement

sample_tenders = [
    ("DME/2025-26/IND2012", 5892000),
    ("SGITO/2026-27/IND0071", 3248000),
    ("SGITO/2025-26/IND0065", 3190000),
    ("SGITO/2025-26/IND0061", 2894000),
    ("INU/2025-26/IND0043/CALL-2", 2444000),
    ("DME/2025-26/IND2162", 698000),
    ("SGITO/2025-26/IND0047", 544615),
    ("DME/2025-26/IND1880/CALL-2", 462000),
    ("SGITO/2025-26/IND0064", 157500)
]

raw_files = glob.glob(r"C:\Users\Admin\Desktop\kppp_probe\kk_extraction\raw\*.xlsx")

print("=== DETAILED BREAKDOWN OF 9 SAMPLE TENDERS ===")
for t_num, claimed_val in sample_tenders:
    safe_t = t_num.replace("/", "_")
    matched_f = [f for f in raw_files if safe_t in f]
    print(f"\n--- {t_num} (Claimed: {claimed_val:,}) ---")
    if not matched_f:
        print("  Not found in raw files")
        continue
    meta, bidders, items, bids = parse_comparative_statement(matched_f[0])
    kk_bids = [b for b in bids if "ALLIANZE" in (b.get("supplier_name") or "").upper() or "KAMAL" in (b.get("supplier_name") or "").upper()]
    for b in kk_bids:
        print(f"  Item: {b.get('item_name')} | Rate: {b.get('rate')} | Qty: {b.get('qty')} | Total: {b.get('total')} | Rank: {b.get('rank')} | Selected: {b.get('selected')}")
