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
    "category": "WORKS",
    "tenderstatusdropdown": "PUBLISHED",
    "departmentstatus": None,
    "district": None,
    "ecvRange": None,
    "innertendername": None,
    "innertendertype": None,
    "subCategory": None,
    "tenderclosureFromDate": None,
    "tenderclosureTOdate": None,
    "tendernumber": None,
    "tenderpublishedTodate": None,
    "tenderpublishedfromdate": None
}

url = f'{BASE_API}/portal-service/works/search-eproc-tenders?page=0&size=5&order-by-tender-publish=true'
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=HEADERS)

try:
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        print('Status:', resp.status)
        data = json.loads(resp.read().decode('utf-8'))
        print('Success! Data keys:', list(data.keys()) if isinstance(data, dict) else len(data))
        if isinstance(data, dict):
            content = data.get('content') or data.get('list') or []
            print(f'Items returned: {len(content)}')
            if content:
                print('First work tender:', content[0].get('tenderNumber'), 'NIT:', content[0].get('nitId'), 'Status:', content[0].get('status'))
except Exception as e:
    print('Failed with error:', type(e), e)
