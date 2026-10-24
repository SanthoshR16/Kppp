from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATE_NAME = "karnataka"
APP_HOST = "0.0.0.0"
APP_PORT = 8000
DB_PATH = BASE_DIR / "data" / "db" / "kppp.sqlite"
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
LOG_DIR = BASE_DIR / "logs"
EXPORT_DIR = BASE_DIR / "exports"
WEB_DIR = BASE_DIR / "web"

PRIORITY_DEPARTMENTS = [
    "AHF", "AHVS", "BBMP", "BMCRI", "DHFWS", "DME", "ESISMS", "HGML",
    "INU", "KKRDB", "KSMSCL", "KVAFSU", "NIMHANS", "RVS", "SDSTRGI",
    "SGITO", "SJICR",
]
