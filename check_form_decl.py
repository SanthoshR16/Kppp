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

matches = list(re.finditer(r'createSearchForm\s*\([^\)]*\)\s*\{', js))
for m in matches:
    print('Match at:', m.start())
    print(js[m.start():m.start() + 700])
