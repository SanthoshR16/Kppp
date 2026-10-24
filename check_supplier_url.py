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

pos = 0
found = 0
while found < 5:
    idx = js.find('supplierRegistrationURL', pos)
    if idx == -1:
        break
    print(f'Match at {idx}:')
    print(js[max(0, idx - 100):min(len(js), idx + 150)])
    print('-'*50)
    pos = idx + 25
    found += 1
