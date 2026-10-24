from __future__ import annotations

import sqlite3
from pathlib import Path

from config import DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL UNIQUE,
    code TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    department_code TEXT NOT NULL,
    department_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(state, department_code)
);

CREATE TABLE IF NOT EXISTS tenders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    tender_number TEXT NOT NULL,
    department_code TEXT NOT NULL,
    department_name TEXT,
    category TEXT,
    status TEXT,
    published_date TEXT,
    closing_date TEXT,
    estimated_value TEXT,
    emd_amount TEXT,
    fee_amount TEXT,
    source_url TEXT,
    raw_data_json TEXT,
    found_automatically INTEGER NOT NULL DEFAULT 0,
    unknown_to_us INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(state, tender_number)
);

CREATE TABLE IF NOT EXISTS tender_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    tender_number TEXT NOT NULL,
    item_code TEXT,
    item_name TEXT,
    quantity TEXT,
    unit TEXT,
    rate TEXT,
    total TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(state, tender_number, item_code, item_name)
);

CREATE TABLE IF NOT EXISTS tender_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    tender_number TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    sha256 TEXT,
    file_uri TEXT,
    is_public INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(state, tender_number, file_name, sha256)
);

CREATE TABLE IF NOT EXISTS tender_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    tender_number TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note TEXT
);

CREATE TABLE IF NOT EXISTS companies (
    supplier_id TEXT PRIMARY KEY,
    legal_name TEXT,
    aliases_json TEXT,
    state TEXT NOT NULL DEFAULT 'karnataka',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    tender_number TEXT NOT NULL,
    item_name TEXT,
    supplier_id TEXT,
    supplier_name TEXT,
    rate TEXT,
    total TEXT,
    rank INTEGER,
    selected INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(state, tender_number, item_name, supplier_id, rank)
);

CREATE TABLE IF NOT EXISTS awards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    tender_number TEXT NOT NULL,
    supplier_id TEXT,
    supplier_name TEXT,
    award_amount TEXT,
    award_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(state, tender_number, supplier_id)
);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    tender_number TEXT NOT NULL,
    contract_number TEXT,
    supplier_id TEXT,
    signed_on TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS debarred_suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    supplier_id TEXT,
    supplier_name TEXT,
    debarred_from TEXT,
    debarred_until TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auctions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    auction_id TEXT,
    tender_number TEXT,
    status TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    source_name TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    notes TEXT,
    progress_json TEXT
);

CREATE TABLE IF NOT EXISTS watermarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    source_name TEXT NOT NULL,
    last_successful_scan_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(state, source_name)
);

CREATE TABLE IF NOT EXISTS flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    tender_number TEXT,
    flag_key TEXT NOT NULL,
    flag_value TEXT,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO states (state, code) VALUES (?, ?)",
            ("karnataka", "KA"),
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialized SQLite database at {DB_PATH}")
