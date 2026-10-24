import requests, re

url = "https://kppp.karnataka.gov.in/main.js"
res = requests.get(url, headers={'user-agent': 'Mozilla/5.0'})
text = res.text

# Find all occurrences of portal-service or supplier-registration
patterns = [
    r'["\']([^"\']*(?:portal-service|supplier-registration|search-eproc|tenderView)[^"\']*)["\']',
    r'["\'](/v1/api/[^"\']+)["\']',
    r'["\'](/api/[^"\']+)["\']'
]

found = set()
for p in patterns:
    matches = re.findall(p, text)
    for m in matches:
        found.add(m)

print(f"Total matched strings: {len(found)}")
for s in sorted(found):
    print("  ", s)
