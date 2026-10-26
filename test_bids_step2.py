import urllib.request
import ssl
import json

BASE_API = 'https://kppp.karnataka.gov.in/supplier-registration-service/v1/api'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
    'Content-Type': 'application/json'
}

def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return 0, str(e)

nit_id = 60793
cat = "GOODS"

# Step 1: get bid-groups-details
st1, r1 = get_json(f'{BASE_API}/portal-service/bids/{nit_id}/tender-category/{cat}/bid-groups-details')
print(f'1. bid-groups-details: status {st1}')
if st1 == 200 and r1:
    group = r1[0]
    group_id = group.get('id')
    tender_group_id = group.get('tenderGroupId')
    print(f'   Group ID: {group_id}, Tender Group ID: {tender_group_id}')
    
    # Try with tender_group_id and group_id
    for gid in [tender_group_id, group_id]:
        url2 = f'{BASE_API}/portal-service/bids/{nit_id}/tender-category/{cat}/bid-item-group/{gid}/bid-items/get-selected-bid-item'
        st2, r2 = get_json(url2)
        print(f'2. get-selected-bid-item (gid={gid}): status {st2}')
        if st2 == 200:
            print(f'   Success! Returned {len(r2)} items')
            if r2:
                item0 = r2[0]
                print(f'   First item: {item0}')
                item_id = item0.get('id') or item0.get('itemId') or item0.get('tenderItemId')
                print(f'   Item ID: {item_id}')
                
                # Step 3: itemwise bids
                url3 = f'{BASE_API}/portal-service/bids/{nit_id}/tender-category/{cat}/bidItem/{item_id}/get-selected-bid-for-itemwise'
                st3, r3 = get_json(url3)
                print(f'3. get-selected-bid-for-itemwise (itemId={item_id}): status {st3}')
                if st3 == 200:
                    print(f'   Itemwise bids data: {json.dumps(r3, indent=2)[:500]}')
            break
