import requests, re

text = requests.get('https://kppp.karnataka.gov.in/main.js', headers={'user-agent': 'Mozilla/5.0'}).text

matches = set(re.findall(r'["\']([^"\']*(?:department|dept)[^"\']*)["\']', text, re.IGNORECASE))
for m in sorted(matches):
    if any(k in m.lower() for k in ['service', 'portal', 'list', 'get', 'all', 'dropdown']):
        print(m)
