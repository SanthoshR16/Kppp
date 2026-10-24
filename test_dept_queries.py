import urllib.request
import ssl
import json
import time

BASE_API = 'https://kppp.karnataka.gov.in/supplier-registration-service/v1/api'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
    'Content-Type': 'application/json'
}

with open('data/verified_depts.json') as f:
    depts = json.load(f)

print('Testing live KPPP query across focus departments...')
for code in ['AHVS', 'BMCRI', 'DHFWS', 'DME', 'ESISMS', 'INU', 'KSMSCL', 'SGITO', 'SJICR']:
    did = depts[code]['id']
    url = f'{BASE_API}/portal-service/search-eproc-tenders?page=0&size=10'
    payload = json.dumps({
        "category": "GOODS",
        "status": "PUBLISHED",
        "tenderType": "OPEN",
        "deptId": did
    }).encode()
    try:
        req = urllib.request.Request(url, data=payload, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            print(f'{code:<10} (ID: {did:<6}): Returned {len(data)} published GOODS tenders')
    except Exception as e:
        print(f'{code:<10}: Error {e}')
    time.sleep(0.3)
