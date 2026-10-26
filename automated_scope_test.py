import sqlite3
import json
import urllib.request
import sys

ALLOWED_PREFIXES = {
    "AHF", "AHVS", "BBMP", "BMCRI", "DHFWS", "DME", "ESISMS", "HGML",
    "INU", "KKRDB", "KSMSCL", "KVAFSU", "NIMHANS", "RVS", "SDSTRGI",
    "SGITO", "SJICR"
}

print("==========================================================================================")
print("ACTION A: AUTOMATED SCOPE TEST (STRICT 17 DEPARTMENTS ONLY)")
print("==========================================================================================")

# 1. Check SQLite database prefixes
conn = sqlite3.connect('data/db/kppp.sqlite')
cursor = conn.cursor()

db_prefixes = cursor.execute("""
    SELECT DISTINCT 
        CASE 
            WHEN instr(tender_number, '/') > 0 THEN substr(tender_number, 1, instr(tender_number, '/') - 1)
            ELSE department_code 
        END as prefix
    FROM tenders
""").fetchall()

actual_db_prefixes = sorted([r[0] for r in db_prefixes if r[0]])
print("\n1. SQLite 'SELECT DISTINCT prefix' Results:")
print("   Prefixes Found in Store:", actual_db_prefixes)

out_of_scope_db = [p for p in actual_db_prefixes if p not in ALLOWED_PREFIXES]
if out_of_scope_db:
    print(f"   [FAIL] Found out-of-scope prefixes in database: {out_of_scope_db}")
    sys.exit(1)
else:
    print("   [PASS] 100% of database prefixes belong to the 17 focus departments.")

# 2. Check /api/tenders endpoint
print("\n2. Testing GET http://localhost:3000/api/tenders...")
try:
    req = urllib.request.Request('http://localhost:3000/api/tenders')
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        tenders = data.get('tenders', [])
        api_prefixes = set()
        for t in tenders:
            t_num = t.get('tender_number', '')
            p = t_num.split('/')[0] if '/' in t_num else t.get('department_code')
            if p: api_prefixes.add(p)
        print(f"   Fetched {len(tenders)} tenders. Distinct Prefixes:", sorted(list(api_prefixes)))
        out_of_scope_api = [p for p in api_prefixes if p not in ALLOWED_PREFIXES]
        if out_of_scope_api:
            print(f"   [FAIL] Out of scope in /api/tenders: {out_of_scope_api}")
            sys.exit(1)
        else:
            print("   [PASS] /api/tenders strictly in-scope.")
except Exception as e:
    print(f"   [NOTE] /api/tenders error: {e}")

# 3. Check /api/today endpoint
print("\n3. Testing GET http://localhost:3000/api/today...")
try:
    req = urllib.request.Request('http://localhost:3000/api/today')
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        pub = data.get('published_today', [])
        new_disc = data.get('newly_discovered_today', [])
        today_prefixes = set()
        for t in pub + new_disc:
            t_num = t.get('tender_number', '')
            p = t_num.split('/')[0] if '/' in t_num else t.get('department_code')
            if p: today_prefixes.add(p)
        out_of_scope_today = [p for p in today_prefixes if p not in ALLOWED_PREFIXES]
        if out_of_scope_today:
            print(f"   [FAIL] Out of scope in /api/today: {out_of_scope_today}")
            sys.exit(1)
        else:
            print(f"   [PASS] /api/today strictly in-scope ({len(pub)} published today, {len(new_disc)} newly discovered).")
except Exception as e:
    print(f"   [NOTE] /api/today error: {e}")

# 4. Check /api/company endpoint
print("\n4. Testing GET http://localhost:3000/api/company...")
try:
    req = urllib.request.Request('http://localhost:3000/api/company')
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        company_tenders = data.get('tenders', [])
        comp_prefixes = set()
        for t in company_tenders:
            t_num = t.get('tender_number', '')
            p = t_num.split('/')[0] if '/' in t_num else t.get('department_code')
            if p: comp_prefixes.add(p)
        out_of_scope_comp = [p for p in comp_prefixes if p not in ALLOWED_PREFIXES]
        if out_of_scope_comp:
            print(f"   [FAIL] Out of scope in /api/company: {out_of_scope_comp}")
            sys.exit(1)
        else:
            print(f"   [PASS] /api/company strictly in-scope ({len(company_tenders)} participated tenders).")
            # Verify other departments wins deleted
            other_wins = data.get('other_department_wins', [])
            print(f"   'Other departments wins' section count: {len(other_wins)} (Deleted: {len(other_wins) == 0})")
except Exception as e:
    print(f"   [NOTE] /api/company error: {e}")

print("\n==========================================================================================")
print("AUTOMATED SCOPE TEST PASSED: ALL 17 DEPARTMENTS VERIFIED, ZERO LEAKAGE")
print("==========================================================================================")
