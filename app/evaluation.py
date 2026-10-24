import io
import json
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("evaluation")

COMPANY_SUPPLIER_IDS = {"5086"}
COMPANY_EXACT_NAMES = {
    "K K ALLIANZE",
    "KAMAL KUMAR PARASMAL JAIN",
    "KAMAL KUMAR P JAIN",
    "K.K. ALLIANZE",
    "KK ALLIANZE",
}
LOOKALIKE_KEYWORDS = ("ALLIAN", "KAMAL KUMAR", "PARASMAL")


def clean_text(val: Any) -> str:
    if val is None:
        return ""
    return " ".join(str(val).strip().split())


def clean_number(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).replace(",", "").replace("₹", "").replace("INR", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def is_our_company(supplier_id: Optional[str], supplier_name: Optional[str]) -> bool:
    sid = clean_text(supplier_id)
    if sid in COMPANY_SUPPLIER_IDS:
        return True
    name_norm = clean_text(supplier_name).upper()
    if name_norm in COMPANY_EXACT_NAMES:
        return True
    # Check if any exact company name is in the supplier string
    for exact in COMPANY_EXACT_NAMES:
        if exact in name_norm:
            return True
    return False


def is_lookalike_company(supplier_id: Optional[str], supplier_name: Optional[str]) -> bool:
    if is_our_company(supplier_id, supplier_name):
        return False
    name_norm = clean_text(supplier_name).upper()
    return any(keyword in name_norm for keyword in LOOKALIKE_KEYWORDS)


def col2num(col_str: str) -> int:
    """Convert an Excel column letter (e.g. 'A', 'J', 'AA') to a 0-indexed column integer."""
    num = 0
    for c in col_str.upper():
        if "A" <= c <= "Z":
            num = num * 26 + (ord(c) - ord("A") + 1)
    return max(0, num - 1)


def parse_xlsx_rows(file_content: bytes) -> List[List[Any]]:
    """
    Parses an .xlsx file into a list of row lists with true column coordinates.
    Uses openpyxl if available, with built-in zipfile/xml fallback
    so it works with zero external dependencies.
    """
    try:
        import openpyxl  # type: ignore

        wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
        sheet = wb.active
        return [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
    except Exception:
        pass

    # Built-in XML fallback preserving exact column coordinates
    try:
        with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
            shared_strings: List[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                tree = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for elem in tree.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                    t = elem.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    if t is not None and t.text:
                        shared_strings.append(t.text)
                    else:
                        t_parts = [
                            r_elem.text
                            for r_elem in elem.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                            if r_elem.text
                        ]
                        shared_strings.append("".join(t_parts))

            sheet_xml = zf.read("xl/worksheets/sheet1.xml")
            tree = ET.fromstring(sheet_xml)
            rows: List[List[Any]] = []
            for row_elem in tree.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
                row_map: Dict[int, Any] = {}
                max_c = -1
                for c in row_elem.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                    ref = c.get("r") or ""
                    m = re.match(r"([A-Z]+)(\d+)", ref)
                    col_idx = col2num(m.group(1)) if m else len(row_map)
                    v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    val = v.text if v is not None else ""
                    if c.get("t") == "s" and val.isdigit():
                        idx = int(val)
                        val = shared_strings[idx] if idx < len(shared_strings) else val
                    row_map[col_idx] = val
                    if col_idx > max_c:
                        max_c = col_idx
                current_row = [row_map.get(i, "") for i in range(max_c + 1)] if max_c >= 0 else []
                rows.append(current_row)
            return rows
    except Exception as exc:
        logger.warning("Failed to parse .xlsx file: %s", exc)
        return []


def extract_firm_and_contact(cell_str: str) -> Tuple[str, str]:
    """
    Extracts firm name and contact name from bidder cell format e.g.:
    'KAMAL KUMAR PARASMAL JAIN (1)( K K ALLIANZE )' -> ('K K ALLIANZE', 'KAMAL KUMAR PARASMAL JAIN')
    'THIMMAPPA VENKATESH( SRI VENKATESHWARA ENTERPRISES )' -> ('SRI VENKATESHWARA ENTERPRISES', 'THIMMAPPA VENKATESH')
    'SUSHIL KUMAR SHARMA( VENOR PHARMA LIMITED )' -> ('VENOR PHARMA LIMITED', 'SUSHIL KUMAR SHARMA')
    """
    text = clean_text(cell_str)
    m_firm = re.search(r"\(\s*([^()]+)\s*\)\s*$", text)
    if m_firm:
        firm_name = m_firm.group(1).strip()
        contact_name = re.sub(r"\(.*", "", text).strip()
        return firm_name, contact_name or firm_name
    return text, text


def parse_comparative_statement(file_bytes: bytes) -> Dict[str, Any]:
    """
    Parses real KPPP Comparative Statement Excel sheets (.xlsx).
    Handles real layout:
      - Rows 1-3: Tender Number, Description, Department Name
      - Row 4 (Excel row 5): Bidders in Col J+ (cells like 'NAME (1)( FIRM )')
      - Row 5 (Excel row 6): Headers: Sl. No., Item Name, Item Code, Unit, Item Rate, Quantity,
                             Selected Supplier By Evaluator, Selected Supplier By Approver, All User Comments,
                             followed by 'Item Price' per bidder.
      - Rows 6+: Items, quantities, approved winner, and bidder prices.
    Also supports legacy or fallback formats.
    """
    rows = parse_xlsx_rows(file_bytes)
    if not rows or len(rows) < 2:
        return {"bidders": [], "items": [], "discrepancies": ["Empty or invalid comparative statement"]}

    tender_number = None
    description = None
    department_name = None
    discrepancies: List[str] = []

    # 1. Extract metadata from title rows
    for r in rows[:6]:
        line = [clean_text(c) for c in r if c]
        for idx, cell in enumerate(line):
            cell_u = cell.upper()
            if "TENDER NUMBER" in cell_u:
                # Value is next cell or after colon
                if idx + 1 < len(line):
                    tender_number = line[idx + 1]
                elif ":" in cell:
                    tender_number = clean_text(cell.split(":", 1)[1])
            elif "TENDER DESCRIPTION" in cell_u:
                if idx + 1 < len(line):
                    description = line[idx + 1]
                elif ":" in cell:
                    description = clean_text(cell.split(":", 1)[1])
            elif "DEPARTMENT NAME" in cell_u:
                if idx + 1 < len(line):
                    department_name = line[idx + 1]
                elif ":" in cell:
                    department_name = clean_text(cell.split(":", 1)[1])

    # 2. Identify Bidders Row and Header Row
    bidders_row_idx = -1
    headers_row_idx = -1

    for r_idx, r in enumerate(rows[:10]):
        row_str = " ".join(clean_text(c).upper() for c in r if c)
        if any(term in row_str for term in ("SL. NO.", "SL NO", "ITEM NAME", "ITEM CODE")) and "SELECTED SUPPLIER" in row_str:
            headers_row_idx = r_idx
            break

    # In real files, bidders row is immediately above the headers row
    if headers_row_idx > 0:
        bidders_row_idx = headers_row_idx - 1
    else:
        # Fallback: scan for row with bidder cells
        for r_idx, r in enumerate(rows[:10]):
            for c_idx in range(len(r)):
                cell_txt = clean_text(r[c_idx])
                if "(" in cell_txt and ")" in cell_txt and any(k in cell_txt.upper() for k in ("PHARMA", "ENTERPRISES", "ALLIANZE", "AGENCIES", "LIMITED")):
                    bidders_row_idx = r_idx
                    headers_row_idx = r_idx + 1
                    break
            if bidders_row_idx >= 0:
                break

    bidders_by_col: Dict[int, Dict[str, Any]] = {}
    if bidders_row_idx >= 0 and bidders_row_idx < len(rows):
        bidders_row = rows[bidders_row_idx]
        # Bidders start at column index 9 (Column J) or wherever cells have firm names
        start_col = 9 if len(bidders_row) > 9 and clean_text(bidders_row[9]) else 0
        for col_idx in range(start_col, len(bidders_row)):
            val = clean_text(bidders_row[col_idx])
            if not val:
                continue
            val_u = val.upper()
            if any(val_u == skip for skip in ("SL", "SL. NO.", "ITEM NAME", "ITEM CODE", "UNIT", "ITEM RATE", "QUANTITY", "ALL USER COMMENTS")):
                continue
            firm, contact = extract_firm_and_contact(val)
            # Check for supplier ID in parentheses
            id_match = re.search(r"\((\d{4,})\)", val)
            supplier_id = id_match.group(1) if id_match else None
            bidders_by_col[col_idx] = {
                "supplier_name": firm,
                "contact_person": contact,
                "raw_name": val,
                "supplier_id": supplier_id,
                "items": {},
                "item_details": [],
                "rate": None,
                "total": None,
                "rank": None,
                "selected": False,
            }

    # 3. Parse Item Rows and Approver Selections
    item_rows: List[Dict[str, Any]] = []
    start_item_row = (headers_row_idx + 1) if headers_row_idx >= 0 else 6

    for r_idx in range(start_item_row, len(rows)):
        r = rows[r_idx]
        if not r:
            continue
        # Check if row is metadata, totals, or empty
        row_str = " ".join(clean_text(c).upper() for c in r if c)
        if not row_str or any(k in row_str for k in ("DISCLAIMER", "SIGNATURE", "NOTE:")):
            continue

        # In real statements:
        # Col 0: Sl. No., Col 1: Item Name, Col 2: Item Code, Col 3: Unit, Col 4: Item Rate,
        # Col 5: Quantity, Col 6: Selected Supplier By Evaluator, Col 7: Selected Supplier By Approver
        item_name = clean_text(r[1]) if len(r) > 1 else ""
        if not item_name and len(r) > 0:
            item_name = clean_text(r[0])
        if not item_name:
            continue

        item_code = clean_text(r[2]) if len(r) > 2 else None
        unit = clean_text(r[3]) if len(r) > 3 else None
        item_rate_est = clean_number(r[4]) if len(r) > 4 else None
        quantity = clean_number(r[5]) if len(r) > 5 else 1.0
        evaluator_winner = clean_text(r[6]) if len(r) > 6 else ""
        approver_winner = clean_text(r[7]) if len(r) > 7 else ""
        comments = clean_text(r[8]) if len(r) > 8 else ""

        # Price columns for each bidder
        item_prices: Dict[str, float] = {}
        for col_idx, b_info in bidders_by_col.items():
            if col_idx < len(r):
                quoted_price = clean_number(r[col_idx])
                if quoted_price is not None:
                    b_info["items"][item_name] = quoted_price
                    b_info["item_details"].append({
                        "item_name": item_name,
                        "item_code": item_code,
                        "quantity": quantity,
                        "unit": unit,
                        "rate": quoted_price,
                        "total": quoted_price * (quantity if quantity is not None else 1.0),
                    })
                    item_prices[b_info["supplier_name"]] = quoted_price

        # Check winner selection on this item
        winning_supplier_str = approver_winner or evaluator_winner
        if winning_supplier_str:
            winning_firm, winning_contact = extract_firm_and_contact(winning_supplier_str)
            winning_firm_u = winning_firm.upper()
            winning_contact_u = winning_contact.upper()
            for b_info in bidders_by_col.values():
                b_name_u = b_info["supplier_name"].upper()
                b_contact_u = b_info.get("contact_person", "").upper()
                b_raw_u = b_info.get("raw_name", "").upper()
                if (
                    b_name_u == winning_firm_u
                    or (b_contact_u and b_contact_u == winning_contact_u)
                    or winning_firm_u in b_raw_u
                    or (is_our_company(b_info.get("supplier_id"), b_name_u) and is_our_company(None, winning_supplier_str))
                ):
                    b_info["selected"] = True

        item_rows.append({
            "item_name": item_name,
            "item_code": item_code,
            "unit": unit,
            "estimated_rate": item_rate_est,
            "quantity": quantity,
            "winner_approver": approver_winner,
            "winner_evaluator": evaluator_winner,
            "comments": comments,
            "prices": item_prices,
        })

    # 4. Post-process totals and ranks
    bidders = list(bidders_by_col.values())
    for b in bidders:
        if b["item_details"]:
            total_sum = sum(it["total"] for it in b["item_details"])
            b["total"] = total_sum
            # Rate is first item's rate or unit rate
            b["rate"] = b["item_details"][0]["rate"]
        elif b["items"]:
            b["total"] = sum(b["items"].values())
            b["rate"] = next(iter(b["items"].values()))

    # Calculate ranks based on evaluated totals / rates
    priced_bidders = [b for b in bidders if b.get("total") is not None]
    if priced_bidders:
        sorted_bidders = sorted(priced_bidders, key=lambda x: (x["total"], x.get("rate") or 0))
        for rank_idx, b in enumerate(sorted_bidders, start=1):
            b["rank"] = rank_idx
            # If no approver selected marked yet, lowest bidder is L1
            if rank_idx == 1 and not any(other.get("selected") for other in bidders):
                b["selected"] = True

    return {
        "tender_number": tender_number,
        "description": description,
        "department_name": department_name,
        "bidders": bidders,
        "items": item_rows,
        "discrepancies": discrepancies,
    }


def evaluate_and_reconcile_tender(
    tender_number: str,
    comp_statement_bytes: Optional[bytes] = None,
    itemwise_selected_supplier: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    existing_bids: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Cross-checks comparative statement against itemwise selected bid endpoint,
    validates discrepancies, assigns winner, and determines K.K. Allianze outcome.
    """
    bids: List[Dict[str, Any]] = []
    items: List[Dict[str, Any]] = []
    discrepancies: List[str] = []

    if comp_statement_bytes:
        parsed = parse_comparative_statement(comp_statement_bytes)
        bids = parsed.get("bidders", [])
        items = parsed.get("items", [])
        discrepancies.extend(parsed.get("discrepancies", []))
    elif existing_bids:
        bids = existing_bids

    # Cross-check winner between comparative statement and item-wise endpoint
    comp_winner = next((b for b in bids if b.get("selected") or b.get("rank") == 1), None)
    
    # itemwise_selected_supplier may be a single dict or a list of itemwise selections
    itemwise_winners: List[str] = []
    if isinstance(itemwise_selected_supplier, list):
        for entry in itemwise_selected_supplier:
            w = clean_text(entry.get("supplierName") or entry.get("supplier_name"))
            if w:
                itemwise_winners.append(w)
    elif isinstance(itemwise_selected_supplier, dict):
        w = clean_text(itemwise_selected_supplier.get("supplierName") or itemwise_selected_supplier.get("supplier_name"))
        if w:
            itemwise_winners.append(w)

    if comp_winner and itemwise_winners:
        comp_name_norm = clean_text(comp_winner.get("supplier_name")).upper()
        # Check if comp_winner matches any itemwise winner
        matched = False
        for iw_name in itemwise_winners:
            iw_norm = iw_name.upper()
            if (
                comp_name_norm == iw_norm
                or comp_name_norm in iw_norm
                or iw_norm in comp_name_norm
                or (is_our_company(comp_winner.get("supplier_id"), comp_name_norm) and is_our_company(None, iw_norm))
            ):
                matched = True
                break
        if not matched:
            discrepancies.append(
                f"CHECK: Winner mismatch (comp_statement='{comp_winner.get('supplier_name')}' "
                f"vs item_wise='{', '.join(itemwise_winners)}')"
            )

    # Determine our company presence & outcome
    our_bids = [b for b in bids if is_our_company(b.get("supplier_id"), b.get("supplier_name"))]
    selected_bid = next((b for b in bids if b.get("selected")), None)
    l1_bid = selected_bid or next((b for b in bids if b.get("rank") == 1), None)

    our_bid = our_bids[0] if our_bids else None
    our_rank = our_bid.get("rank") if our_bid else None
    our_rate = our_bid.get("rate") if our_bid else None
    our_total = our_bid.get("total") if our_bid else None

    l1_name = l1_bid.get("supplier_name") if l1_bid else None
    l1_rate = l1_bid.get("rate") if l1_bid else None
    l1_total = l1_bid.get("total") if l1_bid else None

    difference = None
    if our_total is not None and l1_total is not None:
        try:
            difference = float(our_total) - float(l1_total)
        except (ValueError, TypeError):
            difference = None

    we_won = bool(our_bid and (our_bid.get("selected") or our_bid.get("rank") == 1))
    we_lost = bool(our_bid and not we_won and l1_bid)
    we_bid = bool(our_bid)

    if we_won:
        result = "won"
    elif we_lost:
        result = "lost"
    elif bids:
        result = "pending"
    else:
        result = "not_public"

    # Identify lookalikes
    needs_confirmation = [
        b.get("supplier_name")
        for b in bids
        if is_lookalike_company(b.get("supplier_id"), b.get("supplier_name"))
    ]

    return {
        "tender_number": tender_number,
        "bids": bids,
        "items": items,
        "bids_opened": bool(bids),
        "we_bid": we_bid,
        "we_won": we_won,
        "we_lost": we_lost,
        "our_rank": our_rank,
        "our_rate": our_rate,
        "our_total": our_total,
        "l1_name": l1_name,
        "l1_rate": l1_rate,
        "l1_total": l1_total,
        "difference": difference,
        "result": result,
        "needs_confirmation": needs_confirmation,
        "discrepancies": discrepancies,
        "check_status": discrepancies[0] if discrepancies else None,
    }
