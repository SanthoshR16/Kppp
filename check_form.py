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

# Search for form controls in searchTender
pos = 0
found = 0
while found < 5:
    idx = js.find('searchTender=', pos)
    if idx == -1:
        idx = js.find('searchTender =', pos)
    if idx == -1:
        break
    print(f'Match at {idx}:')
    print(js[max(0, idx - 50):min(len(js), idx + 250)])
    print('='*50)
    pos = idx + 20
    found += 1
