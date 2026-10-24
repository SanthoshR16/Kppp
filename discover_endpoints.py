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

# Search for strings containing "/api/" or "http" or "service"
all_strings = set(re.findall(r'["\']([a-zA-Z0-9_\-\/:\.]*(?:fullview|full-view|tender-view|viewtender|searchtender|download|statement|nitid|tenderid)[\w\-/:\.]*)["\']', js, re.IGNORECASE))
print(f'Matched strings ({len(all_strings)}):')
for s in sorted(all_strings):
    print('  ', s)

# Also search for "tenderGoodsItemsList" or "tenderCriterionDocumentList" in main.js
print('--- Occurrences of tenderGoodsItemsList ---')
for m in re.finditer(r'tenderGoodsItemsList', js):
    start = max(0, m.start() - 200)
    end = min(len(js), m.end() + 200)
    print(js[start:end])
    break

# Also search for works or services equivalent of tenderGoodsItemsList
works_items = set(re.findall(r'tender(?:Works|Services|Work|Service)\w*', js))
print('Works/Services items properties:', works_items)
