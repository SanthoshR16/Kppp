import urllib.request
import ssl
import json

BASE_API = 'https://kppp.karnataka.gov.in/supplier-registration-service/v1/api'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Content-Type': 'application/json'}

def api_post(endpoint, payload):
    url = f"{BASE_API}{endpoint}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return 0, str(e)

def api_get_raw(endpoint):
    url = f"{BASE_API}{endpoint}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()

print("====================================================================================================")
print("ACTION D: DEBUGGING 5 EVALUATION_COMPLETED TENDERS AND BIDS ENDPOINTS")
print("====================================================================================================\n")

# Find 5 EVALUATION_COMPLETED tenders from DME (deptId 3640)
st, items = api_post('/portal-service/search-eproc-tenders?page=0&size=5', {
    "category": "GOODS",
    "status": "EVALUATION_COMPLETED",
    "tenderType": "OPEN",
    "deptId": 3640
})

if not isinstance(items, list):
    print("Failed to fetch evaluation completed tenders")
    exit(0)

for idx, it in enumerate(items[:5], 1):
    t_num = it.get('tenderNumber')
    nit_id = it.get('nitId')
    t_id = it.get('id')
    cat = "GOODS"
    
    print(f"\n====================================================================================================")
    print(f"[{idx}] TENDER: {t_num} | Record ID: {t_id} | NIT ID: {nit_id}")
    print(f"====================================================================================================")

    # 1. Download-detailed (Comparative Statement)
    ep1 = f"/portal-service/tender-eval/{nit_id}/commercial-evaluation/tender-category/{cat}/commercial-comparison/download-detailed"
    st1, raw1 = api_get_raw(ep1)
    print(f"1. Endpoint: GET {ep1}")
    print(f"   Status Code: {st1} | Bytes Returned: {len(raw1)}")
    if st1 == 200:
        print(f"   First 150 bytes (hex/repr): {repr(raw1[:150])}")
        is_zip = raw1.startswith(b'PK\x03\x04')
        print(f"   Is valid XLSX/ZIP?: {is_zip}")
    else:
        print(f"   Raw response (first 300 chars): {raw1.decode('utf-8', errors='ignore')[:300]}")

    # 2. bid-groups-details
    ep2 = f"/portal-service/bids/{nit_id}/tender-category/{cat}/bid-groups-details"
    st2, raw2 = api_get_raw(ep2)
    print(f"\n2. Endpoint: GET {ep2}")
    print(f"   Status Code: {st2} | Bytes Returned: {len(raw2)}")
    text2 = raw2.decode('utf-8', errors='ignore')
    print(f"   First 1500 chars of response:\n{text2[:1500]}")

    # Parse groups if 200
    if st2 == 200:
        try:
            groups = json.loads(text2)
            if isinstance(groups, list) and groups:
                g0 = groups[0]
                gid = g0.get('tenderGroupId') or g0.get('id')
                
                # 3. get-selected-bid-item
                ep3 = f"/portal-service/bids/{nit_id}/tender-category/{cat}/bid-item-group/{gid}/bid-items/get-selected-bid-item"
                st3, raw3 = api_get_raw(ep3)
                print(f"\n3. Endpoint: GET {ep3}")
                print(f"   Status Code: {st3} | Bytes: {len(raw3)}")
                text3 = raw3.decode('utf-8', errors='ignore')
                print(f"   Response:\n{text3[:500]}")
        except Exception as e:
            print("   Parse group error:", e)

    print("\n----------------------------------------------------------------------------------------------------")
