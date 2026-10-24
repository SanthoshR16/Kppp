import urllib.request
import ssl
import json

BASE_API = 'https://kppp.karnataka.gov.in/supplier-registration-service/v1/api'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*'
}

payload = {
    "tenderNumber": None,
    "category": "WORKS",
    "status": "PUBLISHED",
    "deptId": None,
    "publishedFromDate": None,
    "publishedToDate": None,
    "tenderType": "OPEN",
    "title": None,
    "ecv": None,
    "location": None,
    "tenderClosureFromDate": None,
    "tenderClosureToDate": None
}

url = f'{BASE_API}/portal-service/works/search-eproc-tenders?page=0&size=5&order-by-tender-publish=true'
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=HEADERS)

try:
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        print('Status:', resp.status)
        data = json.loads(resp.read().decode('utf-8'))
        print('Success! Data type:', type(data))
        if isinstance(data, list):
            print(f'Items returned: {len(data)}')
            if data:
                print('First work tender:', json.dumps(data[0], indent=2)[:400])
        elif isinstance(data, dict):
            print('Data keys:', list(data.keys()))
            c = data.get('content', [])
            print(f'Content count: {len(c)}')
            if c:
                print('First work tender:', json.dumps(c[0], indent=2)[:400])
except Exception as e:
    print('Failed with error:', type(e), e)
