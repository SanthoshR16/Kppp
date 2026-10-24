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

# Search for download methods for tender documents
patterns = ['download-file', 'downloadDocument', 'download-detailed', 'download-tender', 'tender-document']
for pat in patterns:
    print(f'=== Pattern: {pat} ===')
    pos = 0
    while True:
        idx = js.find(pat, pos)
        if idx == -1:
            break
        print(js[max(0, idx - 80):min(len(js), idx + 180)])
        print('-'*30)
        pos = idx + len(pat) + 30
