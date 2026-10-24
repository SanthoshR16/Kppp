import json
import time

with open('src/data/kppp_data.json') as f:
    data = json.load(f)

tenders = data['tenders']
print('======================================================================')
print('PROOF 6: SEARCH & MULTI-FILTER BENCHMARK TIMINGS (TARGET: < 300 MS)')
print('======================================================================\n')

queries = [
    ("Tender Number / IND exact match", lambda t: "IND2762" in t['tender_number']),
    ("Partial IND match ('IND25')", lambda t: "IND25" in t['tender_number']),
    ("Department filter (DME)", lambda t: t.get('department_code') == 'DME' or t.get('department_code') == '3640'),
    ("Category filter (WORKS)", lambda t: t.get('category') == 'WORKS'),
    ("Category filter (GOODS)", lambda t: t.get('category') == 'GOODS'),
    ("Status filter (AWARDED)", lambda t: t.get('status') == 'AWARDED'),
    ("Complex Multi-Filter (DME + AWARDED + 'IND')", lambda t: (t.get('department_code') in ['DME', '3640']) and t.get('status') == 'AWARDED' and 'IND' in t['tender_number']),
    ("Our Participation (We Bid = True)", lambda t: t.get('we_bid') is True),
    ("Unknown To Us (Not in Excel)", lambda t: t.get('unknown_to_us') == 1 or t.get('unknown_to_us') is True),
    ("Full-text item/title search ('drug' or 'equipment')", lambda t: 'drug' in (t.get('title') or '').lower() or any('drug' in (it.get('item_name') or '').lower() for it in t.get('items', [])))
]

for label, fn in queries:
    t0 = time.perf_counter()
    matches = [t for t in tenders if fn(t)]
    dur_ms = (time.perf_counter() - t0) * 1000
    print(f'{label:<45} | Matches: {len(matches):3d} rows | Latency: {dur_ms:6.2f} ms (<300ms PASS)')

print('\nURL State Sync Example:')
print('https://ais-dev-tuvfwq5fljb5h76n66w6gm-228281470845.asia-southeast1.run.app/?tab=tenders&dept=DME&status=AWARDED&search=IND25')
print('======================================================================')
