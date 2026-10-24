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

# Search for the services
for service_name in ['goodsTenderService', 'worksTenderService', 'serviceTenderService']:
    print(f'=== {service_name} ===')
    pos = 0
    while True:
        idx = js.find(service_name, pos)
        if idx == -1:
            break
        print(js[max(0, idx - 100):min(len(js), idx + 250)])
        print('-'*30)
        pos = idx + len(service_name) + 200

# Search for classes with getTenderFullView
print('=== getTenderFullView implementations ===')
pos = 0
while True:
    idx = js.find('getTenderFullView(', pos)
    if idx == -1:
        break
    print(js[max(0, idx - 50):min(len(js), idx + 250)])
    print('='*50)
    pos = idx + 20
