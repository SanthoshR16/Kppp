import sqlite3
import json
import re

conn = sqlite3.connect('data/db/kppp.sqlite')
cursor = conn.cursor()

# 1. Load dataset
with open('src/data/kppp_data.json') as f:
    dataset = json.load(f)

# 2. Get all 46 participated tenders
tenders = cursor.execute('''
    SELECT t.tender_number, t.department_code, t.status, t.published_date, b.supplier_name, b.rate, b.total, b.rank, b.selected
    FROM tenders t
    JOIN bids b ON t.tender_number = b.tender_number
    WHERE UPPER(b.supplier_name) LIKE '%ALLIANZE%' OR UPPER(b.supplier_name) LIKE '%KAMAL%'
''').fetchall()

by_t = {}
for r in tenders:
    by_t.setdefault(r[0], []).append(r)

results_by_fy = {}
for fy in ['2026-27', '2025-26', '2024-25', '2023-24']:
    results_by_fy[fy] = {'fy': fy, 'participated': 0, 'won': 0, 'lost': 0, 'pending': 0, 'total_won_value': 0.0}

for t_num, rows in by_t.items():
    m_fy = re.search(r'/(\d{4}-\d{2})/', t_num)
    fy = m_fy.group(1) if m_fy and m_fy.group(1) in results_by_fy else '2025-26'
    
    any_won = any(r[8] == 1 for r in rows)
    all_won = all(r[8] == 1 for r in rows)
    status = rows[0][2]
    
    if any_won:
        outcome = 'WON_ALL' if all_won else 'WON_PART'
        won_amt = sum(float(r[6] or 0) for r in rows if r[8] == 1)
        results_by_fy[fy]['won'] += 1
        results_by_fy[fy]['total_won_value'] += won_amt
    elif status in ['EVALUATION_COMPLETED', 'AWARDED', 'CLOSED']:
        outcome = 'LOST'
        results_by_fy[fy]['lost'] += 1
    else:
        outcome = 'PENDING'
        results_by_fy[fy]['pending'] += 1
        
    results_by_fy[fy]['participated'] += 1

fy_summaries = [results_by_fy[fy] for fy in ['2026-27', '2025-26', '2024-25', '2023-24']]
total_won = sum(f['total_won_value'] for f in fy_summaries)

# Update dataset
dataset['company']['fy_summaries'] = fy_summaries
dataset['company']['total_won_value'] = total_won
dataset['company']['total_won_tenders'] = sum(f['won'] for f in fy_summaries)
dataset['company']['total_lost_tenders'] = sum(f['lost'] for f in fy_summaries)
dataset['company']['total_pending_tenders'] = sum(f['pending'] for f in fy_summaries)
dataset['stats']['total_won_val'] = total_won

# Remove any hardcoded other_department_wins
dataset['company']['other_department_wins'] = []

with open('src/data/kppp_data.json', 'w') as f:
    json.dump(dataset, f)

print(f"Updated src/data/kppp_data.json with true computed values: Total Won: ₹{total_won:,.2f}")
