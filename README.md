# KPPP Platform (17 Focus Departments & K.K. Allianze Intelligence)

A high-performance, deterministic public procurement extraction and intelligence platform for the Karnataka Public Procurement Portal (KPPP).

Designed specifically for monitoring tenders across 17 focus health and government departments, tracking competitor commercial evaluation bids, and managing company intelligence for **K.K. Allianze** (Supplier ID: 5086).

---

## 🌟 Key Features

1. **Scoped 17-Department Intelligence**:
   - Strictly isolated to 17 target departments: `AHF`, `AHVS`, `BBMP`, `BMCRI`, `DHFWS`, `DME`, `ESISMS`, `HGML`, `INU`, `KKRDB`, `KSMSCL`, `KVAFSU`, `NIMHANS`, `RVS`, `SDSTRGI`, `SGITO`, `SJICR`.
   - Verified department IDs against live portal directory.
   - Comprehensive extraction across `GOODS`, `WORKS`, and `SERVICES` categories from 2023 to present.

2. **K.K. Allianze & Proprietor Commercial Tracking**:
   - Automated detection of supplier ID `5086` and aliases (`KAMAL KUMAR PARASMAL JAIN`, `KAMAL KUMAR P JAIN`).
   - Comparative statement parser extracting item-by-item competitor rates, evaluated totals, rankings, and L1 selections.
   - Categorization into `WON_ALL`, `WON_PART`, `LOST`, `RETENDERED`, and `RESULT_NOT_PUBLIC`.
   - Baseline reconciliation against existing Excel workbooks with `unknown_to_us` flagging for newly discovered tenders.

3. **Deterministic & Headless REST Extraction**:
   - Completely headless API communication with KPPP REST services without requiring browser automation or CAPTCHAs.
   - Resumable month-by-month chunk extraction with minute-by-minute heartbeat and persistent checkpoints.
   - Watermark tracking with gap-fill capabilities.

4. **Modern Multi-Tab Web Interface**:
   - **Dashboard**: Real-time stats, recent in-scope tenders, department overview.
   - **Tenders Directory**: Full listing with department and status filters.
   - **Instant IND Search**: Search by partial or full IND numbers across all departments.
   - **Company Page (K.K. Allianze)**: Participated tenders, win/loss stats, competitor intelligence ("Who Beat Us"), and item-level price comparisons.
   - **My Tenders**: Filter by automatically detected tenders and un-reconciled items.
   - **Tender Modal & Document Viewer**: View metadata, attached tender documents (PDF/XLSX), commercial bid comparisons, and timeline.

---

## 📁 Repository Structure

```
kppp_platform/
├── app/
│   ├── main.py                 # FastAPI web application routes and SSE events
│   └── __init__.py
├── web/
│   ├── index.html              # Modern responsive multi-tab UI
│   ├── styles.css              # Custom clean CSS design system
│   └── app.js                  # Frontend state management & interactive controllers
├── sources/
│   ├── kppp_karnataka.py       # Karnataka KPPP state adapter
│   └── __init__.py
├── models.py                   # Data models, analytics, and SQLite queries
├── database.py                 # SQLite WAL connection management
├── comp_parser.py              # Comparative statement Excel parser
├── extract_scoped.py           # 17-department background extraction engine
├── scoped_watcher.py           # Watermark gap-fill & live status change watcher
├── config.py                   # System configuration & file paths
├── data/
│   ├── db/                     # SQLite database (kppp.sqlite)
│   ├── raw/                    # Downloaded documents, manifests, and full views
│   └── screenshots/            # Automated UI verification captures
└── tests/                      # Automated test suite
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- Dependencies: `fastapi`, `uvicorn`, `requests`, `openpyxl`, `playwright`

```bash
pip install -r requirements.txt # or install standard requirements
```

### 2. Configuration (`.env`)
```dotenv
DEPARTMENTS=AHF,AHVS,BBMP,BMCRI,DHFWS,DME,ESISMS,HGML,INU,KKRDB,KSMSCL,KVAFSU,NIMHANS,RVS,SDSTRGI,SGITO,SJICR
COMPANY_SUPPLIER_IDS=5086
COMPANY_NAMES=K K ALLIANZE;KAMAL KUMAR PARASMAL JAIN;KAMAL KUMAR P JAIN
```

### 3. Launch the Web Platform
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Visit `http://127.0.0.1:8000` in any web browser.

### 4. Run the Background Scoped Extractor
```bash
python -u extract_scoped.py
```
Tracks live status in `data/scoped_checkpoint.json` and `data/scoped_heartbeat.json`.

---

## 📊 Summary of Current Platform Data

- **In-Scope Departments**: 17
- **Total In-Scope Tenders**: 405+
- **K.K. Allianze Participated**: 46 tenders
- **Evaluated Value Won**: ₹34.98 Crore
- **Item-level Bids Stored**: 561+
