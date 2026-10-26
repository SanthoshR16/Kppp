import sqlite3
import json

conn = sqlite3.connect('data/db/kppp.sqlite')
cursor = conn.cursor()

sample_tenders = [
    ('DME/2025-26/IND2012', 5892000.0),
    ('SGITO/2026-27/IND0071', 3248000.0),
    ('SGITO/2025-26/IND0065', 3190000.0),
    ('SGITO/2025-26/IND0061', 2894000.0),
    ('INU/2025-26/IND0043/CALL-2', 2444000.0),
    ('DME/2025-26/IND2162', 698000.0),
    ('SGITO/2025-26/IND0047', 544615.0),
    ('DME/2025-26/IND1880/CALL-2', 462000.0),
    ('SGITO/2025-26/IND0064', 157500.0)
]

print("=========================================================================================================================")
print("PROOF E: NINE REFERENCE TENDERS — RAW STATEMENT ROW (OUR RATE, QTY, OUR TOTAL) & AWARDED TOTAL")
print("=========================================================================================================================")
print(f'{"#":<2} | {"TENDER NUMBER":<28} | {"OUR RATE (₹)":<14} | {"QTY":<5} | {"OUR TOTAL (₹)":<16} | {"AWARDED TOT (₹)":<16} | {"SAMPLE AMT (₹)":<14} | {"EXPLANATION"}')
print('-'*125)

for i, (t_num, sample_amt) in enumerate(sample_tenders, 1):
    rows = cursor.execute('SELECT rate, total, rank, selected FROM bids WHERE tender_number = ? AND (UPPER(supplier_name) LIKE "%ALLIANZE%" OR UPPER(supplier_name) LIKE "%KAMAL%")', (t_num,)).fetchall()
    if rows:
        r0 = rows[0]
        our_rate = float(r0[0] or 0)
        our_total = float(r0[1] or 0)
        qty = round(our_total / our_rate) if our_rate > 0 else 1
        
        # Total awarded for the whole tender
        all_awarded = cursor.execute('SELECT total FROM bids WHERE tender_number = ? AND selected = 1', (t_num,)).fetchall()
        awarded_tot = sum(float(x[0] or 0) for x in all_awarded) if all_awarded else our_total
        
        diff_note = "Sample = Rate (Qty=2)" if qty > 1 and our_rate == sample_amt else ("Sample = Total" if our_total == sample_amt else "Exact Match")
        
        print(f'{i:<2} | {t_num:<28} | {our_rate:14,.2f} | {qty:^5} | {our_total:16,.2f} | {awarded_tot:16,.2f} | {sample_amt:14,.2f} | {diff_note}')
    else:
        print(f'{i:<2} | {t_num:<28} | Not found in database')

print("=========================================================================================================================")
