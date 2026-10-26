import urllib.request
import ssl
import json
import sys

BASE_API = 'https://kppp.karnataka.gov.in/supplier-registration-service/v1/api'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*'
}

def api_get(endpoint):
    url = f"{BASE_API}{endpoint}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, str(e)

def api_post(endpoint, payload):
    url = f"{BASE_API}{endpoint}"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, str(e)

print("====================================================================================================")
print("ACTION 3: PROOF OF id VS nitId HARD CHECKS ON DME/2026-27/IND2454 AND 4 OTHER TENDERS")
print("====================================================================================================\n")

# Target 1: DME/2026-27/IND2454 (id 59501, nitId 59610)
# Targets 2-5: Find 4 more tenders from live search where id != nitId
st, search_results = api_post('/portal-service/search-eproc-tenders?page=0&size=10', {
    "category": "GOODS",
    "status": "PUBLISHED",
    "tenderType": "OPEN"
})

targets = [
    {"tenderNumber": "DME/2026-27/IND2454", "id": 59501, "nitId": 59610, "category": "GOODS"}
]

if isinstance(search_results, list):
    for r in search_results:
        t_num = r.get('tenderNumber')
        t_id = r.get('id')
        t_nit = r.get('nitId')
        if t_id and t_nit and t_id != t_nit and t_num != "DME/2026-27/IND2454":
            targets.append({"tenderNumber": t_num, "id": t_id, "nitId": t_nit, "category": "GOODS"})
            if len(targets) >= 5:
                break

for idx, t in enumerate(targets[:5], 1):
    t_num = t["tenderNumber"]
    t_id = t["id"]
    t_nit = t["nitId"]
    cat = t["category"]
    print(f">>> TEST #{idx}: {t_num}")
    print(f"    Expected Tender Number: {t_num}")
    print(f"    Record ID:              {t_id}")
    print(f"    Record NIT ID:          {t_nit}")
    print(f"    Does ID != NIT ID?:     {t_id != t_nit}")

    # Full view with id
    st_fv_id, fv_id = api_get(f"/portal-service/{t_id}/goods-tender-full-view")
    num_in_fv_id = fv_id.get('noticeInvitingTenderDTO', {}).get('tenderNumber') if isinstance(fv_id, dict) else None
    
    # Full view with nitId
    st_fv_nit, fv_nit = api_get(f"/portal-service/{t_nit}/goods-tender-full-view")
    num_in_fv_nit = fv_nit.get('noticeInvitingTenderDTO', {}).get('tenderNumber') if isinstance(fv_nit, dict) else None

    # File list with id
    st_fl_id, fl_id = api_get(f"/portal-service/{t_id}/get-goods-tender-files")
    # File list with nitId
    st_fl_nit, fl_nit = api_get(f"/portal-service/{t_nit}/get-goods-tender-files")

    print(f"    [Full-View with ID {t_id}]       Status: {st_fv_id:<3} | tenderNumber in response: {num_in_fv_id}")
    print(f"    [Full-View with NITID {t_nit}]    Status: {st_fv_nit:<3} | tenderNumber in response: {num_in_fv_nit}")
    print(f"    [File-List with ID {t_id}]        Status: {st_fl_id:<3} | Files count: {len(fl_id) if isinstance(fl_id, list) else 0}")
    print(f"    [File-List with NITID {t_nit}]     Status: {st_fl_nit:<3} | Files count: {len(fl_nit) if isinstance(fl_nit, list) else 0}")

    # Inspect entityId in file list
    if isinstance(fl_nit, list) and fl_nit:
        f0 = fl_nit[0]
        print(f"    -> NIT File 0: '{f0.get('fileName')}' | entityId: {f0.get('entityId')} (Matches NITID: {f0.get('entityId') == t_nit})")
    
    print("-" * 100)
