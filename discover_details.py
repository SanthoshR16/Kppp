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

# Search for the function or method that calls viewTenderDetails or tender details
print('--- viewTenderDetails context ---')
for m in re.finditer(r'viewTenderDetails', js, re.IGNORECASE):
    start = max(0, m.start() - 250)
    end = min(len(js), m.end() + 250)
    print(js[start:end])
    print('='*50)

# Search for comparativeStatement context
print('--- comparativeStatement context ---')
for m in re.finditer(r'comparativeStatement', js, re.IGNORECASE):
    start = max(0, m.start() - 250)
    end = min(len(js), m.end() + 250)
    print(js[start:end])
    print('='*50)
