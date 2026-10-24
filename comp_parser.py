import openpyxl

def parse_comparative_statement(file_path):
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    
    # 1. Tender metadata from top rows
    metadata = {}
    for r in rows[:7]:
        clean = [c for c in r if c is not None]
        if len(clean) >= 2:
            key = str(clean[0]).strip().rstrip(':')
            val = str(clean[1]).strip()
            metadata[key] = val
            
    # 2. Find bidder row (Row 7, 1-indexed -> index 6)
    # Col 10+ (1-indexed -> index 9+) are bidder names
    bidder_row = rows[6]
    bidders = {}
    for col_idx in range(9, len(bidder_row)):
        name = bidder_row[col_idx]
        if name and str(name).strip():
            bidders[col_idx] = str(name).strip()
            
    # 3. Item rows starting from row 9 (index 8)
    items = []
    bids = []
    for row_idx in range(8, len(rows)):
        r = rows[row_idx]
        if not r or r[0] is None or not str(r[0]).strip():
            continue
        try:
            sl_no = float(r[0])
        except (ValueError, TypeError):
            # Not an item row (maybe footer)
            continue
            
        item_name = str(r[1]).strip() if len(r) > 1 and r[1] is not None else ""
        item_code = str(r[2]).strip() if len(r) > 2 and r[2] is not None else ""
        unit = str(r[3]).strip() if len(r) > 3 and r[3] is not None else ""
        rate = str(r[4]).strip() if len(r) > 4 and r[4] is not None else ""
        qty = str(r[5]).strip() if len(r) > 5 and r[5] is not None else ""
        selected_eval = str(r[6]).strip() if len(r) > 6 and r[6] is not None else ""
        selected_appr = str(r[7]).strip() if len(r) > 7 and r[7] is not None else ""
        
        items.append({
            "sl_no": sl_no,
            "item_name": item_name,
            "item_code": item_code,
            "unit": unit,
            "rate": rate,
            "qty": qty,
            "selected_evaluator": selected_eval,
            "selected_approver": selected_appr
        })
        
        # Read price for each bidder from their own column
        item_bids = []
        for col_idx, bname in bidders.items():
            price = r[col_idx] if col_idx < len(r) else None
            price_str = str(price).strip() if price is not None else None
            if price_str and price_str.lower() != 'none':
                try:
                    price_val = float(price_str)
                except ValueError:
                    price_val = 0.0
                item_bids.append({
                    "supplier_name": bname,
                    "price_str": price_str,
                    "price_val": price_val
                })
        
        # Sort bids by price to get ranks (L1, L2, ...)
        item_bids.sort(key=lambda x: x["price_val"])
        winner_name = selected_appr or selected_eval
        
        for rank, b in enumerate(item_bids, 1):
            is_winner = 1 if (winner_name and b["supplier_name"] in winner_name or winner_name in b["supplier_name"]) else 0
            bids.append({
                "item_name": item_name,
                "item_code": item_code,
                "supplier_name": b["supplier_name"],
                "rate": b["price_str"],
                "total": str(b["price_val"] * (float(qty) if qty else 1.0)),
                "rank": rank,
                "selected": is_winner
            })
            
    return metadata, bidders, items, bids

if __name__ == "__main__":
    for p in ["data/test_comp_59033.xlsx", "data/test_comp_59514.xlsx"]:
        meta, bidders, items, bids = parse_comparative_statement(p)
        print(f"\nFile: {p}")
        print("Metadata:", meta)
        print(f"Bidders ({len(bidders)}):", list(bidders.values()))
        print(f"Items: {len(items)}, Bids: {len(bids)}")
        for b in bids[:4]:
            print("  Bid:", b)
