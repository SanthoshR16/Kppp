import urllib.request
import ssl
import re

with open('check_criteria.py') as f:
    pass

# search in main.js
req = urllib.request.Request('https://kppp.karnataka.gov.in/main.js', headers={'User-Agent': 'Mozilla/5.0'})
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
with urllib.request.urlopen(req, context=ctx) as r:
    js = r.read().decode('utf-8', errors='ignore')

matches = set(re.findall(r'["\'](/[\w\-/]+department[\w\-/]*)["\']', js, re.IGNORECASE))
print('Department paths in main.js:')
for m in sorted(matches):
    print('  ', m)
