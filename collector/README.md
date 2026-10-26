# KPPP Karnataka Standalone Collector

This standalone collector can be run on any local PC or remote VPS in India where `kppp.karnataka.gov.in` is directly reachable without network restrictions.

## Requirements
- Python 3.8 or later.
- Standard library modules only (no extra pip packages required).

## Running Manually
```bash
python run_collector.py
```
This generates `kppp_data.json` in the current folder.

---

## Automated Hourly Schedule Setup

### 1. Windows Task Scheduler (`schtasks`)
Open Command Prompt (as Administrator) and run:
```cmd
schtasks /create /tn "KPPP_Collector_Hourly" /tr "python C:\path\to\collector\run_collector.py" /sc hourly /mo 1
```
To verify the scheduled task:
```cmd
schtasks /query /tn "KPPP_Collector_Hourly"
```
To run it immediately on demand:
```cmd
schtasks /run /tn "KPPP_Collector_Hourly"
```

---

### 2. Linux / macOS Cron (`crontab`)
Open crontab:
```bash
crontab -e
```
Add the following line to run at the top of every hour:
```cron
0 * * * * cd /path/to/collector && /usr/bin/python3 run_collector.py >> collector.log 2>&1
```

---

## Importing into the Website
1. After `run_collector.py` finishes, locate `kppp_data.json`.
2. Open the KPPP Platform website in your browser.
3. Click the **"Import Collected Data"** button in the header / status bar.
4. Select `kppp_data.json`. The web app immediately parses and loads the latest dataset.
