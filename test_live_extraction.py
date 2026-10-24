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

def post_json(path, payload):
    url = BASE_API + path
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=HEADERS, method='POST')
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return 0, str(e)

def get_json(path):
    url = BASE_API + path
    req = urllib.request.Request(url, headers=HEADERS, method='GET')
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return 0, str(e)

print('=== 1. SEARCHING 1 REAL TENDER FOR GOODS ===')
status, res = post_json('/portal-service/search-eproc-tenders?page=0&size=5&order-by-tender-publish=true', {'category': 'GOODS'})
print(f'GOODS search status: {status}')
goods_sample = None
if status == 200 and isinstance(res, dict):
    content = res.get('content') or res.get('list') or []
    print(f'Goods count: {len(content)}')
    if content:
        goods_sample = content[0]
        print('Goods sample:', goods_sample.get('tenderNumber'), 'NIT:', goods_sample.get('nitId'), 'ID:', goods_sample.get('id'), 'Status:', goods_sample.get('status'))

print('\n=== 2. SEARCHING 1 REAL TENDER FOR WORKS ===')
status, res = post_json('/portal-service/works/search-eproc-tenders?page=0&size=5&order-by-tender-publish=true', {'category': 'WORKS'})
print(f'WORKS search status: {status}')
works_sample = None
if status == 200 and isinstance(res, dict):
    content = res.get('content') or res.get('list') or []
    print(f'Works count: {len(content)}')
    if content:
        works_sample = content[0]
        print('Works sample:', works_sample.get('tenderNumber'), 'NIT:', works_sample.get('nitId'), 'ID:', works_sample.get('id'), 'Status:', works_sample.get('status'))

print('\n=== 3. SEARCHING 1 REAL TENDER FOR SERVICES ===')
status, res = post_json('/portal-service/services/search-eproc-tenders?page=0&size=5&order-by-tender-publish=true', {'category': 'SERVICES'})
print(f'SERVICES search status: {status}')
services_sample = None
if status == 200 and isinstance(res, dict):
    content = res.get('content') or res.get('list') or []
    print(f'Services count: {len(content)}')
    if content:
        services_sample = content[0]
        print('Services sample:', services_sample.get('tenderNumber'), 'NIT:', services_sample.get('nitId'), 'ID:', services_sample.get('id'), 'Status:', services_sample.get('status'))

# Full view tests
if goods_sample and goods_sample.get('nitId'):
    nit = goods_sample['nitId']
    st, g_fv = get_json(f'/portal-service/{nit}/goods-tender-full-view')
    print(f'\nGOODS full-view ({nit}): status {st}, keys: {list(g_fv.keys()) if isinstance(g_fv, dict) else g_fv}')

if works_sample and works_sample.get('nitId'):
    nit = works_sample['nitId']
    st, w_fv = get_json(f'/portal-service/{nit}/works-tender-full-view')
    print(f'\nWORKS full-view ({nit}): status {st}, keys: {list(w_fv.keys()) if isinstance(w_fv, dict) else w_fv}')

if services_sample and services_sample.get('nitId'):
    nit = services_sample['nitId']
    st, s_fv = get_json(f'/portal-service/{nit}/service-tender-full-view')
    print(f'\nSERVICES full-view ({nit}): status {st}, keys: {list(s_fv.keys()) if isinstance(s_fv, dict) else s_fv}')
