import requests
import json

base_url = "https://kppp.karnataka.gov.in/supplier-registration-service/v1/api/portal-service"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json"
}

r1 = requests.get(f"{base_url}/departments/activeDepartment", headers=headers)
print("activeDepartment status:", r1.status_code)
d1 = r1.json()
print("activeDepartment type:", type(d1))
if isinstance(d1, dict):
    print("activeDepartment keys:", list(d1.keys()))
    # print sample
    for k in list(d1.keys())[:3]:
        print(f"Key {k}:", str(d1[k])[:200])

# Now check timings.jsonl from earlier for the exact payload of search-eproc-tenders!
# Earlier we saw request_body_keys: ['category', 'deptId', 'location', 'publishedFromDate', 'publishedToDate', 'status', 'tenderClosureFromDate', 'tenderClosureToDate', 'tenderNumber', 'tenderType', 'title']
payload = {
    "category": "GOODS",
    "deptId": 3640,
    "location": "",
    "publishedFromDate": "01-01-2026",
    "publishedToDate": "24-10-2026",
    "status": "",
    "tenderClosureFromDate": "",
    "tenderClosureToDate": "",
    "tenderNumber": "",
    "tenderType": "",
    "title": ""
}
r2 = requests.post(f"{base_url}/search-eproc-tenders?page=0&size=10", headers=headers, json=payload)
print("\nsearch-eproc-tenders status:", r2.status_code)
print("search-eproc-tenders text:", r2.text[:500])
print("search-eproc-tenders headers:", r2.headers)
