from playwright.sync_api import sync_playwright
import time, os

out_dir = r"C:\Users\Admin\Desktop\San (Don't Use)\popupdoc\kppp_platform\data\screenshots"
os.makedirs(out_dir, exist_ok=True)

chrome_path = r"C:\Users\Admin\AppData\Local\ms-playwright\chromium-1248\chrome-win64\chrome.exe"

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome_path, headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    
    # 1. Dashboard
    page.goto("http://127.0.0.1:8000", wait_until="networkidle")
    time.sleep(1.5)
    page.screenshot(path=os.path.join(out_dir, "1_dashboard.png"))
    print("Saved: 1_dashboard.png")
    
    # 2. IND Search
    page.click("button[data-tab='tab-search']")
    time.sleep(0.5)
    page.fill("#indSearchQuery", "IND2012")
    page.click("button:has-text('Search')")
    time.sleep(1.5)
    page.screenshot(path=os.path.join(out_dir, "2_ind_search.png"))
    print("Saved: 2_ind_search.png")
    
    # 3. Company Page
    page.click("button[data-tab='tab-company']")
    time.sleep(1.5)
    page.screenshot(path=os.path.join(out_dir, "3_company_kk_allianze.png"))
    print("Saved: 3_company_kk_allianze.png")
    
    # 4. Tender Details Modal with document viewer
    page.click("button[data-tab='tab-dashboard']")
    time.sleep(0.5)
    page.click("#dashTenderTable button.action-btn")
    time.sleep(1.5)
    page.screenshot(path=os.path.join(out_dir, "4_tender_modal_documents.png"))
    print("Saved: 4_tender_modal_documents.png")
    
    browser.close()

print("ALL 4 SCREENSHOTS CAPTURED PERFECTLY!")
