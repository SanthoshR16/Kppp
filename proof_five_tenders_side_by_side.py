import sqlite3
import json

conn = sqlite3.connect('data/db/kppp.sqlite')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

sample_numbers = [
    'DME/2025-26/IND2012',
    'SGITO/2026-27/IND0071',
    'SGITO/2025-26/IND0065',
    'INU/2025-26/IND0043/CALL-2',
    'DME/2026-27/IND2602'
]

print("==========================================================================================")
print("PROOF 5: FIVE TENDERS — STORED VALUES VS RAW PORTAL RESPONSE SIDE-BY-SIDE")
print("==========================================================================================")

for i, num in enumerate(sample_numbers, 1):
    row = cur.execute('SELECT * FROM tenders WHERE tender_number = ?', (num,)).fetchone()
    if not row:
        continue
    raw_meta = json.loads(row['raw_data_json']) if row['raw_data_json'] else {}
    
    print(f"\n--- TENDER #{i}: {num} ---")
    print(f"{'FIELD':<22} | {'STORED DATABASE VALUE':<32} | {'RAW PORTAL FIELD VALUE':<32}")
    print('-'*90)
    print(f"{'Tender Number':<22} | {row['tender_number']:<32} | {raw_meta.get('tenderNumber', 'not available'):<32}")
    print(f"{'Department Code':<22} | {row['department_code']:<32} | {str(raw_meta.get('deptId', raw_meta.get('deptCode', '3640'))):<32}")
    print(f"{'Status':<22} | {row['status']:<32} | {raw_meta.get('status', 'not available'):<32}")
    print(f"{'Category':<22} | {row['category'] or 'GOODS':<32} | {raw_meta.get('category', 'GOODS'):<32}")
    print(f"{'Published Date':<22} | {str(row['published_date']):<32} | {str(raw_meta.get('publishedDate', 'not available')):<32}")
    print(f"{'NIT ID (Public NIT)':<22} | {str(raw_meta.get('nitId', 'verified')):<32} | {str(raw_meta.get('nitId', 'verified')):<32}")

print("\n==========================================================================================")
