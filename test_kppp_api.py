import requests
import json

def test_api():
    base_url = "https://kppp.karnataka.gov.in/supplier-registration-service/v1/api/portal-service"
    
    # Test 1: Active departments list
    dept_url = f"{base_url}/departments/activeDepartment"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json"
    }
    print("Testing active departments endpoint...")
    try:
        r = requests.get(dept_url, headers=headers, timeout=15)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Departments returned: {len(data) if isinstance(data, list) else type(data)}")
            if isinstance(data, list) and len(data) > 0:
                print("Sample dept:", data[0])
                # Find DME deptId
                dme = [d for d in data if "dme" in str(d.get("departmentCode", "")).lower() or "dme" in str(d.get("departmentName", "")).lower() or d.get("id") == 3640]
                print("DME found:", dme)
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: Search tenders endpoint
    search_url = f"{base_url}/search-eproc-tenders"
    payload = {
        "category": "GOODS",
        "deptId": 3640,
        "publishedFromDate": "01-01-2026",
        "publishedToDate": "24-10-2026",
        "status": ""
    }
    params = {
        "page": 0,
        "size": 10
    }
    print("\nTesting search-eproc-tenders endpoint...")
    try:
        r = requests.post(search_url, headers=headers, json=payload, params=params, timeout=15)
        print(f"Status: {r.status_code}")
        print("Response headers:", {k: v for k, v in r.headers.items() if "total" in k.lower() or "count" in k.lower()})
        if r.status_code == 200:
            data = r.json()
            print(f"Results type: {type(data)}")
            if isinstance(data, list):
                print(f"Rows count: {len(data)}")
                if len(data) > 0:
                    print("Sample row keys:", list(data[0].keys()))
                    print("Sample tender:", data[0].get("tenderNumber"), data[0].get("title"))
            elif isinstance(data, dict):
                print("Keys:", list(data.keys()))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
