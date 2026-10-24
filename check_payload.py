import urllib.request
import ssl
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    'https://kppp.karnataka.gov.in/main.js',
    headers={'User-Agent': 'Mozilla/5.0'}
)
with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
    js = resp.read().decode('utf-8', errors='ignore')

# Search for calls to goodstenderSearch or workstenderSearch or servicestenderSearch
print('--- Search caller context ---')
for search_fn in ['goodstenderSearch(', 'workstenderSearch(', 'servicestenderSearch(']:
    pos = 0
    while True:
        idx = js.find(search_fn, pos)
        if idx == -1:
            break
        print(f'=== {search_fn} at {idx} ===')
        print(js[max(0, idx - 250):min(len(js), idx + 200)])
        pos = idx + len(search_fn) + 50
