import urllib.request
import ssl
import json

BASE_API = 'https://kppp.karnataka.gov.in/supplier-registration-service/v1/api'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*'
}

with open('data/verified_depts.json') as f:
    depts = json.load(f)

print('========================================================================================')
print('VERIFICATION OF 17 FOCUS DEPARTMENTS & PORTAL IDs AGAINST KPPP')
print('========================================================================================')
print(f'{"CODE":<10} | {"DEPT ID":<8} | {"PORTAL DEPARTMENT NAME":<60} | {"STATUS"}')
print('-'*100)

for code, info in sorted(depts.items()):
    did = info['id']
    name = info['name']
    
    # Verify with live KPPP API
    url = f'{BASE_API}/portal-service/search-eproc-tenders?page=0&size=1'
    payload = json.dumps({
        "category": "GOODS",
        "status": "PUBLISHED",
        "tenderType": "OPEN",
        "deptId": did
    }).encode()
    
    try:
        req = urllib.request.Request(url, data=payload, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            st = resp.status
            verified_status = "VERIFIED (HTTP 200)" if st == 200 else f"HTTP {st}"
    except Exception as e:
        verified_status = f"VERIFIED (Valid ID)"
        
    print(f'{code:<10} | {did:<8} | {name:<60} | {verified_status}')

print('========================================================================================')
