import urllib.request
import ssl
import json

BASE_API = 'https://kppp.karnataka.gov.in/supplier-registration-service/v1/api'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Content-Type': 'application/json'}

SCOPE_DEPTS = {
    "DME": 3640, "DHFWS": 39, "KSMSCL": 3357, "SGITO": 9146, "INU": 6179
}

def find_paths(obj, target, path=''):
    paths = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}" if path else k
            if target == v:
                paths.append((new_path, v))
            elif isinstance(v, (dict, list)):
                paths.extend(find_paths(v, target, new_path))
    elif isinstance(obj, list):
        for i, it in enumerate(obj):
            new_path = f"{path}[{i}]"
            paths.extend(find_paths(it, target, new_path))
    return paths

print("====================================================================================================")
print("PROOF C: RECURSIVE SEARCH FOR EXPECTED TENDER NUMBER IN FULL-VIEW JSON (5 IN-SCOPE TENDERS)")
print("====================================================================================================")

# 1. DME/2026-27/IND2454
targets = [
    {"tenderNumber": "DME/2026-27/IND2454", "id": 59501, "nitId": 59610, "dept": "DME"}
]

# Find 4 more in-scope tenders from DME, DHFWS, KSMSCL, SGITO
for dept_code, did in SCOPE_DEPTS.items():
    if len(targets) >= 5:
        break
    url = f"{BASE_API}/portal-service/search-eproc-tenders?page=0&size=10"
    payload = json.dumps({"category": "GOODS", "status": "PUBLISHED", "tenderType": "OPEN", "deptId": did}).encode()
    try:
        req = urllib.request.Request(url, data=payload, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            items = json.loads(r.read().decode())
            for it in items:
                t_num = it.get('tenderNumber')
                t_id = it.get('id')
                t_nit = it.get('nitId')
                if t_id and t_nit and t_id != t_nit and t_num not in [x['tenderNumber'] for x in targets]:
                    targets.append({"tenderNumber": t_num, "id": t_id, "nitId": t_nit, "dept": dept_code})
                    if len(targets) >= 5:
                        break
    except Exception:
        pass

for i, t in enumerate(targets, 1):
    t_num = t["tenderNumber"]
    t_id = t["id"]
    t_nit = t["nitId"]
    dept = t["dept"]
    
    url = f"{BASE_API}/portal-service/{t_nit}/goods-tender-full-view"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
            data = json.loads(resp.read().decode())
            matches = find_paths(data, t_num)
            print(f"\n[{i}] Tender: {t_num} (Dept: {dept})")
            print(f"    Record ID:     {t_id}")
            print(f"    Record NIT ID: {t_nit}")
            print(f"    ID != NIT ID?: {t_id != t_nit}")
            print(f"    Full-View Call: GET /portal-service/{t_nit}/goods-tender-full-view -> HTTP {resp.status}")
            if matches:
                for path, val in matches:
                    print(f"    -> FOUND MATCH at path: '{path}' === '{val}'")
            else:
                print(f"    -> Match in tenderSchedule.tenderNumber: {data.get('tenderSchedule', {}).get('tenderNumber')}")
    except Exception as e:
        print(f"[{i}] {t_num} Error: {e}")

print("\n====================================================================================================")
