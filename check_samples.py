import os, glob
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

print(f"{'TENDER NUMBER':<30} {'CLAIMED VAL':<15} {'FOUND':<8} {'CALCULATED / ECV':<20} {'NOTES'}")
print("-" * 95)

raw_files = glob.glob(r"C:\Users\Admin\Desktop\kppp_probe\kk_extraction\raw\*.xlsx")

for t_num, claimed_val in sample_tenders:
    safe_t = t_num.replace("/", "_")
    matched_f = [f for f in raw_files if safe_t in f]
    if matched_f:
        fpath = matched_f[0]
        meta, bidders, items, bids = parse_comparative_statement(fpath)
        # Check kk allianze
        kk_bids = [b for b in bids if "ALLIANZE" in (b.get("supplier_name") or "").upper() or "KAMAL" in (b.get("supplier_name") or "").upper()]
        tot = sum(float(b.get("total") or 0) for b in kk_bids)
        print(f"{t_num:<30} {claimed_val:<15} {'YES':<8} {tot:<20} Bids found: {len(kk_bids)}, File: {os.path.basename(fpath)}")
    else:
        print(f"{t_num:<30} {claimed_val:<15} {'NO':<8} {'-':<20} Not in kk_extraction folder")
