# KPPP Platform Progress

## M1. Foundation

### Evidence
- Created an isolated project folder under the repository: `kppp_platform/`.
- Legacy baseline check from the existing project: `pytest popupdoc/tests/test_scan_model_v2.py -q` returned `11 passed in 0.33s`.
- Repository isolation check: `git status --short` is limited to the new `kppp_platform/` directory and does not modify any tracked legacy file outside this project.
- Added schema, state adapter, minimal FastAPI service, and a startup script in the isolated folder.

### Scope delivered
- `config.py`: base paths and KPPP state configuration.
- `database.py`: SQLite WAL database with the required states/departments/tenders/status history tables.
- `sources/kppp_karnataka.py`: source adapter for Karnataka with public endpoints and priority departments.
- `app/main.py`: minimal live system with health and SSE stream endpoints.
- `start.bat`: one-click local start script for the isolated service.

### Validation
- `python -m pytest kppp_platform/tests/test_foundation.py -q` is the smoke test used for the foundation layer.

## M2. Historical extraction and resumable ingestion

### Evidence
- Added `extractor.py` with a state-specific adapter runner and a resumable backfill cycle.
- Added `models.py` for persistent database writes including departments, tenders, status snapshots, and watermark updates.
- `reconcile_coverage` confirms a coverage model and missing-department checks against the KPPP adapter’s catalog.

### Scope delivered
- `extractor.py`: public snapshot fetcher, background archival pattern, and department reconciliation.
- `database.py`: SQLite tables for status history, scan runs, and watermark tracking.
- `models.py`: insert/update helpers for provider data and tender records.

## M3. Daily routine, watermark, and gap fill

### Evidence
- `watermarks` and `scan_runs` are persisted in the database model.
- `set_watermark()` records the last successful scan day, and scheduler logic advances status while keeping the platform live.
- `BackgroundScheduler` is implemented in `scheduler.py`, with a runtime-safe loop for incremental updates.

### Scope delivered
- `scheduler.py`: background scan loop with scheduled wake-ups and status logging.
- `models.py`: `add_scan_run()`, `finish_scan_run()`, and `set_watermark()` functions for daily gap handling.

## M4. Live watcher and trigger mechanism

### Evidence
- Added `watcher.py` to perform light checks and publish current state snapshots.
- Added `/events` SSE to stream status updates to the UI without reloading the page.
- The app exposes `/dashboard`, `/tenders`, `/reconcile`, and `/companies` endpoints for live monitoring.

### Scope delivered
- `watcher.py`: watcher for portal health and status snapshots.
- `app/main.py`: live data endpoints and SSE stream.

## M5. Our own tenders and automatic detection state

### Evidence
- Database schema includes `found_automatically` and `unknown_to_us` fields for tender-level ownership detection.
- `models.py` supports updates to tender status and extraction attributes, ready for supplier-ID matching against our company record.
- The adapter is structured for future supplier mapping, company aliases, and winners/reconciliation tracking.

### Scope delivered
- `database.py`: tender ownership and company-tracking fields.
- `models.py`: helper methods to record tender findings and status changes.

## M6. Website shell and dashboard

### Evidence
- Built a live, React-like single-page shell in the `web/` directory.
- A dashboard renders state, counts, recent tenders, and department coverage without page reload.
- The app serves `/` and static assets from the isolated project directory.

### Scope delivered
- `web/index.html`: dashboard shell.
- `web/styles.css`: K.K. Allianze-inspired styling with red/blue tones.
- `web/app.js`: fetches live data and listens to server-sent events.

### Final validation
- `cd "C:\Users\Admin\Desktop\San (Don't Use)\popupdoc\kppp_platform"; .\.venv\Scripts\python.exe -m pytest -q`
- Result: `5 passed in 0.64s`

## Real extraction audit (live proof, status-blocked)

### Evidence collected
- Live portal navigation to `https://kppp.karnataka.gov.in/#/portal/searchTender/live` loads successfully.
- The page body contains `Security Check*` and `Please Enter Captcha:`; there is no live tender table or `search-eproc-tenders` call before captcha completion.
- Browser network capture shows only the base portal JS and `departments/activeDepartment` calls, with no `search-eproc-tenders` request, so the portal is still gated before search execution.
- Under the isolated platform: `data/db/kppp.sqlite` exists but contains 0 tenders and only the schema/state rows; `data/raw` exists with 0 files and 0 bytes.

### Honest status
- M1 Foundation: DONE (project scaffolding exists and the app tests pass).
- M2 Historical extraction: PARTIAL (database schema exists; no live or parsed records were saved).
- M3 Daily routine / watermark: PARTIAL (schema and helper methods exist; no successful live scan has run).
- M4 Live watcher: PARTIAL (watcher code exists; no real portal-status changes have been observed because the site is blocked by CAPTCHA).
- M5 Own tenders / auto-detection: NOT IMPLEMENTED (no supplier matching, no statement parsing, no company ownership detection has been run against a live dataset).
- M6 Website shell: PARTIAL (dashboard shell exists, but no real stored data is displayed from KPPP yet).
- M7 Model training: NOT IMPLEMENTED (no real training data persisted or model comparison performed).

### Blocking conclusion
The isolated platform is not complete for a real KPPP extraction because the live KPPP portal gate is a captcha challenge before the tender search request is allowed. This means any real extraction, document download, statement parsing, and reconciliation work remains blocked until a valid captcha-handling path or a trusted source-of-truth artifact is available. The project is therefore marked as `not complete` and `not implemented` for the real extraction milestone.
