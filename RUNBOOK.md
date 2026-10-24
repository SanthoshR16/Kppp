# KPPP Platform — Local Runbook & Operations Guide

## 1. First-Time Setup

1. In VS Code, open the repository root folder (`File > Open Folder`).
2. Open the integrated terminal (PowerShell / Command Prompt) and set up the virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   npm install
   npm run build
   ```

## 2. VS Code Tasks Execution Order

Run tasks from the VS Code top menu: **Terminal > Run Task...**

| Task Name | Script / Command | Purpose |
|---|---|---|
| **KPPP 0: Diagnose** | `python diagnose.py` | Run this first. Checks DNS, TCP/TLS handshake, active departments, search endpoint, and full-view latency. |
| **KPPP 1: Backfill all history** | `python backfill.py` | Performs full historical extraction across all 17 departments, 3 categories, and 7 statuses using monthly windows and prefix cross-checking. Resumes from `data/checkpoint.json`. |
| **KPPP 2: Daily update loop** | `python daily_update.py` | Continuous background process: checks watched quoted tenders every 15 minutes, downloads comparative statements, detects L1 changes and bid openings, and runs an hourly backfill pass. |
| **KPPP 3: Start website** | `uvicorn app.main:app --host 127.0.0.1 --port 8000` | Serves the full-stack FastAPI monitor and React frontend at `http://127.0.0.1:8000`. |
| **KPPP 4: Verify** | `pytest tests`, `verify_all.py`, `npm run build` | Runs the full verification suite: offline unit tests, 9-section verification report, and web build audit. |

Alternatively, run `run_all.bat` from the project folder to start the daily updater and website server in background processes (logs written under `logs/`).

---

## 3. When the PC Was Off for Some Days

When your PC has been powered off or offline for multiple days, run this exact sequence:

1. **Step 1: Check Connectivity**
   ```powershell
   .\.venv\Scripts\python.exe diagnose.py
   ```
   Ensures the live portal is reachable and responsive.

2. **Step 2: Fill the Missed-Days Gap**
   ```powershell
   .\.venv\Scripts\python.exe backfill.py
   ```
   The engine reads the persisted watermark date from SQLite and automatically fills the gap from the last successful scan date to today in chronological order. The watermark advances only after each date succeeds.

3. **Step 3: Resume Daily Watcher & Website**
   Run **KPPP 2: Daily update loop** and **KPPP 3: Start website** (or run `run_all.bat`).

4. **Step 4: Reconcile and Verify**
   ```powershell
   .\.venv\Scripts\python.exe reconcile.py
   .\.venv\Scripts\python.exe verify_all.py
   ```

---

## 4. Operational Scripts Guide

### A. Live Department Verification
```powershell
.\.venv\Scripts\python.exe verify_departments.py
```
Queries `GET /portal-service/departments/activeDepartment`, checks the 17 focus department IDs, updates SQLite `focus_departments`, and flags any mismatch.

### B. Portal Endpoint & Chunk Discovery
```powershell
.\.venv\Scripts\python.exe discover_endpoints.py
```
Downloads `main.js` and discovered chunks from the live portal to inspect exact bidder, evaluation, and reserved tender route declarations.

### C. Import Quoted Tenders from Excel
```powershell
.\.venv\Scripts\python.exe import_excel_quotes.py <path_to_excel.xlsx>
```
Reads Excel sheets, detects the submitted/quoted column, normalizes tender numbers, imports them into the watch list, and prints a 10-matched vs 10-unmatched side-by-side audit table.

### D. Offline Unit Tests
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```
Runs offline tests with in-memory fixtures (won, lost, winner mismatch check, item sum check, look-alikes).

---

## 5. Security & Rate-Limiting Policy

- **Unauthenticated Public Endpoints Only**: Never pass tokens, passwords, cookies, or Authorization headers.
- **Polite Pacing**: Default delay of 0.35–0.5s per request.
- **Circuit Breaker**: Stops immediately on HTTP 429 (Rate Limit) or HTTP 401/403.
- **Scope Restriction**: Only the 17 focus departments are saved to `tenders`. All other tender prefixes are rejected or marked out of scope.
