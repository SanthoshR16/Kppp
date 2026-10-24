import urllib.request
import ssl
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    'https://kppp.karnataka.gov.in/main.js',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
)

with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
    js = resp.read().decode('utf-8', errors='ignore')

for method_name in ['workstenderSearch', 'servicestenderSearch', 'goodstenderSearch', 'downloadFile', 'downloadTenderDocument']:
    print(f'=== {method_name} ===')
    pos = 0
    while True:
        idx = js.find(method_name, pos)
        if idx == -1:
            break
        print(js[max(0, idx - 60):min(len(js), idx + 200)])
        print('-'*30)
        pos = idx + len(method_name) + 50
