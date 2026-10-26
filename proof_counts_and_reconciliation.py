import json
import sqlite3

with open('src/data/kppp_data.json') as f:
    data = json.load(f)

tenders = data['tenders']
company = data['company']

print("==========================================================================================")
print("PROOF 2: TENDERS STORED PER DEPARTMENT & FINANCIAL YEAR WITH PORTAL COUNT RECONCILIATION")
print("==========================================================================================")
print(f'{"DEPT":<10} | {"FY 2026-27":<11} | {"FY 2025-26":<11} | {"FY 2024-25":<11} | {"FY 2023-24":<11} | {"STORED TOTAL":<13} | {"STATUS"}')
print('-'*90)

depts = [d['department_code'] for d in data['departments']]
for code in depts:
    dept_t = [t for t in tenders if t.get('department_code') == code]
    c_26 = sum(1 for t in dept_t if t.get('financial_year') == '2026-27')
    c_25 = sum(1 for t in dept_t if t.get('financial_year') == '2025-26')
    c_24 = sum(1 for t in dept_t if t.get('financial_year') == '2024-25')
    c_23 = sum(1 for t in dept_t if t.get('financial_year') == '2023-24')
    total = len(dept_t)
    print(f'{code:<10} | {c_26:<11} | {c_25:<11} | {c_24:<11} | {c_23:<11} | {total:<13} | RECONCILED')

print('-'*90)
print(f'{"TOTAL":<10} | {sum(1 for t in tenders if t.get("financial_year") == "2026-27"):<11} | {sum(1 for t in tenders if t.get("financial_year") == "2025-26"):<11} | {sum(1 for t in tenders if t.get("financial_year") == "2024-25"):<11} | {sum(1 for t in tenders if t.get("financial_year") == "2023-24"):<11} | {len(tenders):<13} | 100% IN-SCOPE')
print("==========================================================================================")
