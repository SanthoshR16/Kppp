import sys, os
sys.path.insert(0, os.path.abspath(r"..\popupdoc"))
from browser import BrowserManager
import scraper

bm = BrowserManager()
bm.start()
page = bm.page
captured_req = {}
captured_resp = {}

def on_request(request):
    if "search-eproc-tenders" in request.url:
        captured_req["url"] = request.url
        captured_req["method"] = request.method
        captured_req["headers"] = dict(request.headers)
        captured_req["post_data"] = request.post_data

def on_response(response):
    if "search-eproc-tenders" in response.url:
        captured_resp["status"] = response.status
        captured_resp["headers"] = dict(response.headers)
        try:
            captured_resp["body"] = response.text()
        except Exception:
            pass

page.on("request", on_request)
page.on("response", on_response)

page.goto("https://kppp.karnataka.gov.in/#/portal/searchTender/live")
scraper.ensure_english(page)
scraper.handle_captcha(page, bm)

scraper.search_with_verification(page, "DME")
page.wait_for_timeout(2000)

print("\n--- CAPTURED REQUEST ---")
print("URL:", captured_req.get("url"))
print("Method:", captured_req.get("method"))
print("Headers:", captured_req.get("headers"))
print("Post Data:", captured_req.get("post_data"))

print("\n--- CAPTURED RESPONSE ---")
print("Status:", captured_resp.get("status"))
print("Headers:", captured_resp.get("headers"))
print("Body Sample:", (captured_resp.get("body") or "")[:500])

bm.stop()
