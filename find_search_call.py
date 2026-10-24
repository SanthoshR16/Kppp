import requests, re

url = "https://kppp.karnataka.gov.in/main.js"
res = requests.get(url, headers={'user-agent': 'Mozilla/5.0'})
text = res.text

# Find where searchTender or search-eproc-tenders is called
idx = 0
while True:
    idx = text.find('search-eproc-tenders', idx)
    if idx == -1:
        break
    snippet = text[max(0, idx - 400): min(len(text), idx + 200)]
    print("\n--- SNIPPET ---")
    print(snippet)
    idx += 20
