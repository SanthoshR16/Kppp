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

def post_json(endpoint, payload):
    url = f'{BASE_API}{endpoint}'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return 0, str(e)

def get_json(endpoint):
    url = f'{BASE_API}{endpoint}'
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return 0, str(e)

print("=== 1. TESTING /contract/awarded-tender-list ===")
st, r = post_json('/contract/awarded-tender-list?page=0&size=10', {"supplierId": 5086})
print(f"POST /contract/awarded-tender-list (with supplierId=5086): status {st}")
if st != 200:
    st2, r2 = post_json('/contract/awarded-tender-list?page=0&size=10', {})
    print(f"POST /contract/awarded-tender-list (empty payload): status {st2}")
    if st2 == 200 and isinstance(r2, (list, dict)):
        print(f"  Got response: {type(r2)}")

print("\n=== 2. TESTING DEBARRED LIST ===")
st_deb, r_deb = get_json('/portal/view-debarred-documents')
if st_deb == 0 or st_deb >= 400:
    st_deb2, r_deb2 = post_json('/portal-service/debarred-suppliers?page=0&size=10', {})
    print(f"Debarred suppliers endpoint candidate 2: status {st_deb2}")
    st_deb3, r_deb3 = get_json('/portal-service/debarred-suppliers')
    print(f"Debarred suppliers endpoint candidate 3: status {st_deb3}")

print("\n=== 3. TESTING BIDS ENDPOINTS ON KNOWN TENDER WITH NIT ID 60793 ===")
# NitId 60793 (DME/2026-27/IND2602)
nit_id = 60793
cat = "GOODS"
st_bg, r_bg = get_json(f'/portal-service/bids/{nit_id}/tender-category/{cat}/bid-groups-details')
print(f"GET /portal-service/bids/{nit_id}/tender-category/{cat}/bid-groups-details: status {st_bg}")
if st_bg == 200:
    print(f"  bid-groups-details response: {r_bg}")
