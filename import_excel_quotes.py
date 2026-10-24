import argparse
import glob
import io
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from app.database import FOCUS_CODES, STATE, connect, ensure_schema, now_utc
from app.evaluation import parse_xlsx_rows


def normalise_tender_number(value: Any) -> str:
    if value is None:
        return ""
    s = " ".join(str(value).strip().upper().split())
    s = s.replace(" /", "/").replace("/ ", "/")
    return s


def extract_ind_token(tender_str: str) -> str:
    match = re.search(r"(IND\d+(?:/CALL-\d+)?)", tender_str, re.IGNORECASE)
    return match.group(1).upper() if match else ""


def find_default_excel() -> Optional[str]:
    candidates = (
        glob.glob("data/*.xlsx")
        + glob.glob("data/**/*.xlsx", recursive=True)
        + glob.glob("*.xlsx")
    )
    for c in candidates:
        if not os.path.basename(c).startswith("~$"):
            return c
    return None


def read_sheet_names_and_rows(file_path: str) -> Tuple[List[str], List[List[Any]]]:
    content = Path(file_path).read_bytes()
    # Try openpyxl
    try:
        import openpyxl  # type: ignore

        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheet_names = wb.sheetnames
        sheet = wb.active
        rows = [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
        return sheet_names, rows
    except Exception:
        pass

    # Built-in fallback
    rows = parse_xlsx_rows(content)
    return ["Sheet1"], rows


def import_quotes(file_path: Optional[str] = None) -> None:
    path = file_path or find_default_excel()
    if not path or not os.path.isfile(path):
        print("\n[ERROR] No Excel file found to import.")
        print("Usage: python import_excel_quotes.py <path_to_excel_file.xlsx>")
        sys.exit(1)

    print("=" * 100)
    print(f" READ-ONLY EXCEL QUOTE IMPORT: {path}")
    print("=" * 100)

    sheet_names, rows = read_sheet_names_and_rows(path)
    print(f"Sheet names in workbook: {sheet_names}")
    if not rows:
        print("[ERROR] Workbook contains no data.")
        sys.exit(1)

    # Inspect first few rows to locate column headers
    header_idx = 0
    header_row = rows[0]
    for idx, r in enumerate(rows[:5]):
        text = " ".join(str(c).upper() for c in r if c)
        if any(term in text for term in ("TENDER", "IND", "SUBMITTED", "QUOTED", "NIT")):
            header_idx = idx
            header_row = r
            break

    print(f"\nHeader row (row {header_idx + 1}):")
    target_col_idx = -1
    for col_idx, col_val in enumerate(header_row):
        col_name = str(col_val).strip() if col_val else f"Column {col_idx}"
        print(f"  Col {col_idx}: {col_name}")
        val_upper = col_name.upper()
        if target_col_idx == -1 and any(k in val_upper for k in ("TENDER", "IND", "QUOTED", "SUBMITTED")):
            target_col_idx = col_idx

    if target_col_idx == -1:
        # Default to first non-empty column
        target_col_idx = 0

    print(f"\nTargeting Column {target_col_idx}: '{header_row[target_col_idx]}' for tender numbers.")

    raw_candidates = []
    for r in rows[header_idx + 1:]:
        if target_col_idx < len(r) and r[target_col_idx]:
            raw_candidates.append(r[target_col_idx])

    print(f"Total tender values read from column: {len(raw_candidates)}")

    ensure_schema()
    timestamp = now_utc()
    matched_examples: List[Tuple[str, str]] = []
    unmatched_examples: List[Tuple[str, str]] = []
    imported_count = 0

    with connect() as conn:
        # Load all existing tenders from database
        db_rows = conn.execute(
            "SELECT tender_number, department_code FROM tenders WHERE state = ? AND out_of_scope = 0",
            (STATE,),
        ).fetchall()
        db_tenders = {r["tender_number"].upper(): r["tender_number"] for r in db_rows}
        db_inds = {extract_ind_token(r["tender_number"]): r["tender_number"] for r in db_rows if extract_ind_token(r["tender_number"])}

        for raw in raw_candidates:
            norm = normalise_tender_number(raw)
            if not norm:
                continue

            # Prefix validation
            prefix = norm.split("/", 1)[0]
            ind_token = extract_ind_token(norm)

            db_match = db_tenders.get(norm) or (db_inds.get(ind_token) if ind_token else None)
            final_number = db_match if db_match else norm

            if prefix in FOCUS_CODES or (db_match and db_match.split("/", 1)[0] in FOCUS_CODES):
                # Valid in-scope tender number: add to quoted_tenders
                conn.execute(
                    """
                    INSERT INTO quoted_tenders(state, tender_number, source, added_at)
                    VALUES (?, ?, 'excel_import', ?)
                    ON CONFLICT(state, tender_number) DO NOTHING
                    """,
                    (STATE, final_number, timestamp),
                )
                imported_count += 1

                if db_match:
                    matched_examples.append((norm, db_match))
                else:
                    unmatched_examples.append((norm, "Not yet in local DB (will be fetched in backfill)"))
            else:
                unmatched_examples.append((norm, f"Prefix '{prefix}' not in 17 focus departments"))

    print("\n" + "=" * 100)
    print("IMPORT & MATCHING AUDIT SUMMARY")
    print("=" * 100)
    print(f"Total Quoted Tenders Ingested to Watch List: {imported_count}")
    print(f"Matched with existing database tenders:     {len(matched_examples)}")
    print(f"Unmatched (New/Pending discovery on KPPP):   {len(unmatched_examples)}")

    print("\n" + "=" * 100)
    print(f"{'#':<3} | {'MATCHED EXAMPLES (ALREADY IN DB)':<44} | {'UNMATCHED EXAMPLES (NEW TO FETCH)':<44}")
    print("-" * 100)
    for i in range(10):
        m_txt = f"{matched_examples[i][0]} -> {matched_examples[i][1]}" if i < len(matched_examples) else "—"
        u_txt = unmatched_examples[i][0] if i < len(unmatched_examples) else "—"
        if len(m_txt) > 42:
            m_txt = m_txt[:40] + ".."
        if len(u_txt) > 42:
            u_txt = u_txt[:40] + ".."
        print(f"{i+1:<3} | {m_txt:<44} | {u_txt:<44}")

    print("=" * 100)
    print("Import complete. All quoted tenders are now active in the 15-minute watcher.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read-only Excel Quote Importer")
    parser.add_argument("path", nargs="?", default=None, help="Path to Excel (.xlsx) file")
    args = parser.parse_args()
    import_quotes(args.path)
