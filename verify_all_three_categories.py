import urllib.request
import ssl
import json
import hashlib

BASE_API = 'https://kppp.karnataka.gov.in/supplier-registration-service/v1/api'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*'
}

def api_post(endpoint, payload):
    url = f'{BASE_API}{endpoint}'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=HEADERS)
    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

def api_get_json(endpoint):
    url = f'{BASE_API}{endpoint}'
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

def api_get_bytes(endpoint):
    url = f'{BASE_API}{endpoint}'
    req = urllib.request.Request(url, headers={'User-Agent': HEADERS['User-Agent']})
    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
        return resp.status, resp.read(), resp.headers.get('Content-Type')

print('======================================================================')
print('PROOF 1: COMPLETE ENDPOINT VERIFICATION FOR GOODS, WORKS, AND SERVICES')
print('======================================================================\n')

# 1. GOODS
print('>>> 1. GOODS CATEGORY')
goods_search_payload = {
    "tenderNumber": None,
    "category": "GOODS",
    "status": "PUBLISHED",
    "tenderType": "OPEN"
}
st, goods_list = api_post('/portal-service/search-eproc-tenders?page=0&size=2&order-by-tender-publish=true', goods_search_payload)
g_tender = goods_list[0]
g_nit = g_tender['nitId']
print(f'Search Endpoint: POST /portal-service/search-eproc-tenders (Status: {st})')
print(f'Sample Tender: {g_tender["tenderNumber"]} | NIT ID: {g_nit} | Title: {g_tender.get("title")}')

st, g_full = api_get_json(f'/portal-service/{g_nit}/goods-tender-full-view')
print(f'Full-View Endpoint: GET /portal-service/{g_nit}/goods-tender-full-view (Status: {st})')
print(f'Full-View Keys: {list(g_full.keys())}')

st, g_files = api_get_json(f'/portal-service/{g_nit}/get-goods-tender-files')
print(f'File-List Endpoint: GET /portal-service/{g_nit}/get-goods-tender-files (Status: {st}, Found {len(g_files)} files)')
if g_files:
    f0 = g_files[0]
    fid = f0.get('id') or f0.get('uuid')
    fname = f0.get('fileName')
    st, f_bytes, ct = api_get_bytes(f'/portal-service/{g_nit}/goods-tender-file/{fid}/download-file')
    print(f'File-Download: GET /portal-service/{g_nit}/goods-tender-file/{fid}/download-file -> Status: {st}, Size: {len(f_bytes)} bytes, SHA256: {hashlib.sha256(f_bytes).hexdigest()[:16]}...')

# 2. WORKS
print('\n>>> 2. WORKS CATEGORY')
works_search_payload = {
    "tenderNumber": None,
    "category": "WORKS",
    "status": "PUBLISHED",
    "tenderType": "OPEN"
}
st, works_list = api_post('/portal-service/works/search-eproc-tenders?page=0&size=2&order-by-tender-publish=true', works_search_payload)
w_tender = works_list[0]
w_nit = w_tender['nitId']
print(f'Search Endpoint: POST /portal-service/works/search-eproc-tenders (Status: {st})')
print(f'Sample Tender: {w_tender["tenderNumber"]} | NIT ID: {w_nit} | Title: {w_tender.get("title")}')

st, w_full = api_get_json(f'/portal-service/{w_nit}/works-tender-full-view')
print(f'Full-View Endpoint: GET /portal-service/{w_nit}/works-tender-full-view (Status: {st})')
print(f'Full-View Keys: {list(w_full.keys())}')

st, w_files = api_get_json(f'/portal-service/{w_nit}/get-works-tender-files')
print(f'File-List Endpoint: GET /portal-service/{w_nit}/get-works-tender-files (Status: {st}, Found {len(w_files)} files)')
if w_files:
    f0 = w_files[0]
    fid = f0.get('id') or f0.get('uuid')
    fname = f0.get('fileName')
    st, f_bytes, ct = api_get_bytes(f'/portal-service/{w_nit}/works-tender-file/{fid}/download-file')
    print(f'File-Download: GET /portal-service/{w_nit}/works-tender-file/{fid}/download-file -> Status: {st}, Size: {len(f_bytes)} bytes, SHA256: {hashlib.sha256(f_bytes).hexdigest()[:16]}...')

# 3. SERVICES
print('\n>>> 3. SERVICES CATEGORY')
services_search_payload = {
    "tenderNumber": None,
    "category": "SERVICES",
    "status": "PUBLISHED",
    "tenderType": "OPEN"
}
st, services_list = api_post('/portal-service/services/search-eproc-tenders?page=0&size=2&order-by-tender-publish=true', services_search_payload)
s_tender = services_list[0]
s_nit = s_tender['nitId']
print(f'Search Endpoint: POST /portal-service/services/search-eproc-tenders (Status: {st})')
print(f'Sample Tender: {s_tender["tenderNumber"]} | NIT ID: {s_nit} | Title: {s_tender.get("title")}')

st, s_full = api_get_json(f'/portal-service/{s_nit}/service-tender-full-view')
print(f'Full-View Endpoint: GET /portal-service/{s_nit}/service-tender-full-view (Status: {st})')
print(f'Full-View Keys: {list(s_full.keys())}')

st, s_files = api_get_json(f'/portal-service/{s_nit}/get-services-tender-files')
print(f'File-List Endpoint: GET /portal-service/{s_nit}/get-services-tender-files (Status: {st}, Found {len(s_files)} files)')
if s_files:
    f0 = s_files[0]
    fid = f0.get('id') or f0.get('uuid')
    fname = f0.get('fileName')
    st, f_bytes, ct = api_get_bytes(f'/portal-service/{s_nit}/services-tender-file/{fid}/download-file')
    print(f'File-Download: GET /portal-service/{s_nit}/services-tender-file/{fid}/download-file -> Status: {st}, Size: {len(f_bytes)} bytes, SHA256: {hashlib.sha256(f_bytes).hexdigest()[:16]}...')

print('\n======================================================================')
print('EXTRACTION PROOF COMPLETE: GOODS, WORKS, SERVICES TESTED SUCCESSFULLY!')
print('======================================================================')
