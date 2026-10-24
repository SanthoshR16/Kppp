# KPPP local runbook

## First-time setup

1. In VS Code, choose **File > Open Folder** and open the `kppp_platform` folder.
2. In the integrated terminal, run these commands from that folder:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   npm install
   npm run build
   ```

3. Open **Terminal > Run Task** and run:
   - **KPPP 1: Backfill all history**
   - **KPPP 2: Daily update loop**
   - **KPPP 3: Start website**
   - **KPPP 4: Verify**

   The backfill task is a long-running task. Inspect its terminal output and the
   scan-health indicator; do not treat a failed, interrupted, or incomplete
   backfill as complete.

4. Alternatively, run `run_all.bat` from the project folder to start the daily
   updater and website in hidden processes. Their output is written under
   `logs\`. The backfill is intentionally a separate task.

## How the data flows

The Python source adapter makes unauthenticated requests to public KPPP
endpoints. It rejects 401/403 explicitly, stops immediately on HTTP 429, and
uses a single sequential request stream with a 0.4-second minimum delay.
Accepted tender data is stored in `data\db\kppp.sqlite`. The FastAPI backend
serves dashboard and search responses from that same SQLite database; the
built React website is served by FastAPI on `http://127.0.0.1:8000`.
There is no static tender JSON snapshot and no manual copying step.

The database, downloads, runtime logs, and `.env` files are local-only and
ignored by Git. Attachments are not downloaded by the application. Existing
document folders from the local archive are retained under
`data\quarantine\documents`.

## When the PC was off

Run **KPPP 1: Backfill all history** after starting the machine, review its
reported page totals and errors, and then start **KPPP 2: Daily update loop**
and **KPPP 3: Start website** (or use `run_all.bat`). Do not assume a missed-day
gap was filled until the scan health and reconciliation output confirm it.

## Current verification limits

The portal endpoint and its date-window, reserved-tender, tender-type, bidder,
and evaluation semantics must be verified against live responses before the
backfill can be considered reconciled. The updater reports unverified bidder
detail checks instead of inventing a successful check. The app exposes scan
health and does not mark an unsuccessful or unverified portal request as a
successful update.
