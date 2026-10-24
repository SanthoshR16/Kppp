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

# Search for getExportDocumentDetailed
print('--- getExportDocumentDetailed ---')
for m in re.finditer(r'getExportDocumentDetailed', js):
    start = max(0, m.start() - 100)
    end = min(len(js), m.end() + 250)
    print(js[start:end])
    print('='*50)

# Search for how tendersService gets tender full view or details
print('--- viewTender / fullView methods ---')
matches = set(re.findall(r'(\w*(?:fullView|tenderDetails|viewTender|getDocument|exportDoc|getTender)\w*\([^\)]*\)\s*\{[^}]+\})', js, re.IGNORECASE))
for m in list(matches)[:15]:
    print(m)
    print('-'*40)
