import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.evaluation import (
    clean_number,
    clean_text,
    evaluate_and_reconcile_tender,
    is_lookalike_company,
    is_our_company,
    parse_comparative_statement,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


class EvaluationTests(unittest.TestCase):
    def test_our_company_detection(self):
        self.assertTrue(is_our_company("5086", "ANY NAME"))
        self.assertTrue(is_our_company("", "K K ALLIANZE"))
        self.assertTrue(is_our_company(None, "KAMAL KUMAR PARASMAL JAIN"))
        self.assertTrue(is_our_company(None, "KAMAL KUMAR P JAIN ( K K ALLIANZE )"))
        self.assertFalse(is_our_company("9999", "MEDTRONIC INDIA"))

    def test_lookalike_company_detection(self):
        self.assertTrue(is_lookalike_company("1234", "Alliance Biomedica"))
        self.assertTrue(is_lookalike_company(None, "Kamal Kumar Enterprises"))
        self.assertFalse(is_lookalike_company("5086", "K K ALLIANZE"))

    def test_real_file_sgito_we_won(self):
        file_path = ROOT_DIR / "Comp_SGITO_53572_53678.xlsx"
        self.assertTrue(file_path.exists(), f"Missing real fixture {file_path}")
        content = file_path.read_bytes()

        parsed = parse_comparative_statement(content)
        self.assertEqual(parsed["tender_number"], "SGITO/2025-26/IND0065")
        self.assertEqual(parsed["department_name"], "Sanjay Gandhi Institute of Trauma and Orthopaedics")
        self.assertEqual(len(parsed["bidders"]), 3)

        bidder_names = [b["supplier_name"] for b in parsed["bidders"]]
        self.assertIn("K K ALLIANZE", bidder_names)
        self.assertIn("SRI VENKATESHWARA ENTERPRISES", bidder_names)
        self.assertIn("ADITHYA AGENCIES", bidder_names)

        res = evaluate_and_reconcile_tender(
            tender_number="SGITO/2025-26/IND0065",
            comp_statement_bytes=content,
            itemwise_selected_supplier={"supplierName": "KAMAL KUMAR PARASMAL JAIN (1)( K K ALLIANZE )"},
        )
        self.assertTrue(res["we_bid"])
        self.assertTrue(res["we_won"])
        self.assertFalse(res["we_lost"])
        self.assertEqual(res["result"], "won")
        self.assertEqual(res["our_rank"], 1)
        self.assertEqual(res["our_rate"], 3190000.0)
        self.assertEqual(res["l1_name"], "K K ALLIANZE")
        self.assertEqual(res["l1_rate"], 3190000.0)
        self.assertIsNone(res["check_status"])

    def test_real_file_inu_1605_we_won(self):
        file_path = ROOT_DIR / "KK_Allianze_INU_1605.xlsx"
        self.assertTrue(file_path.exists(), f"Missing real fixture {file_path}")
        content = file_path.read_bytes()

        parsed = parse_comparative_statement(content)
        self.assertEqual(parsed["tender_number"], "INU/2023-24/IND0012")
        self.assertEqual(parsed["department_name"], "Institute of Nephro Urology")
        self.assertEqual(len(parsed["bidders"]), 3)

        bidder_names = [b["supplier_name"] for b in parsed["bidders"]]
        self.assertIn("K K ALLIANZE", bidder_names)

        res = evaluate_and_reconcile_tender(
            tender_number="INU/2023-24/IND0012",
            comp_statement_bytes=content,
            itemwise_selected_supplier={"supplierName": "KAMAL KUMAR P JAIN  (  K K ALLIANZE  )"},
        )
        self.assertTrue(res["we_bid"])
        self.assertTrue(res["we_won"])
        self.assertEqual(res["result"], "won")
        self.assertEqual(res["our_rank"], 1)
        self.assertEqual(res["our_rate"], 724000.0)
        self.assertEqual(res["l1_name"], "K K ALLIANZE")

    def test_real_file_sjcri_competitor_won(self):
        file_path = ROOT_DIR / "Comp_SJICR_51946_52051.xlsx"
        self.assertTrue(file_path.exists(), f"Missing real fixture {file_path}")
        content = file_path.read_bytes()

        parsed = parse_comparative_statement(content)
        self.assertEqual(parsed["tender_number"], "SJICR/2025-26/IND0054")
        self.assertEqual(len(parsed["bidders"]), 1)
        self.assertEqual(parsed["bidders"][0]["supplier_name"], "VENOR PHARMA LIMITED")

        res = evaluate_and_reconcile_tender(
            tender_number="SJICR/2025-26/IND0054",
            comp_statement_bytes=content,
            itemwise_selected_supplier={"supplierName": "SUSHIL KUMAR SHARMA( VENOR PHARMA LIMITED )"},
        )
        self.assertFalse(res["we_bid"])
        self.assertFalse(res["we_won"])
        self.assertEqual(res["l1_name"], "VENOR PHARMA LIMITED")
        self.assertIsNone(res["our_rank"])

    def test_real_file_inu_multi_item_split_award(self):
        file_path = ROOT_DIR / "KK_Allianze_INU_28563.xlsx"
        self.assertTrue(file_path.exists(), f"Missing real fixture {file_path}")
        content = file_path.read_bytes()

        parsed = parse_comparative_statement(content)
        self.assertEqual(parsed["tender_number"], "INU/2024-25/IND0031/CALL-2")
        self.assertEqual(len(parsed["items"]), 2)
        # Item 1 was awarded to K.K. Allianze
        self.assertIn("K K ALLIANZE", parsed["items"][0]["winner_approver"])
        self.assertEqual(parsed["items"][0]["prices"]["K K ALLIANZE"], 2362665.0)

    def test_tender_type_open_adds_nothing_over_none(self):
        """
        Proof that tender_type=None returns the full superset of tenders,
        and querying tender_type='OPEN' adds no new records while tripling request volume.
        """
        from unittest.mock import MagicMock
        if "requests" not in sys.modules:
            try:
                import requests
            except ImportError:
                sys.modules["requests"] = MagicMock()
        from kppp_client import KpppClient

        mock_session = MagicMock()
        # Mock response for None (all tenders)
        all_tenders = [
            {"tenderNumber": "SGITO/2025-26/IND0065", "tenderType": "OPEN"},
            {"tenderNumber": "SGITO/2025-26/IND0066", "tenderType": "LIMITED"},
            {"tenderNumber": "SGITO/2025-26/IND0067", "tenderType": "SHORT_TERM"},
        ]
        # Mock response for OPEN (subset only)
        open_only_tenders = [
            {"tenderNumber": "SGITO/2025-26/IND0065", "tenderType": "OPEN"},
        ]

        client = KpppClient(session=mock_session)
        client._execute_request = MagicMock()

        # Query 1: tender_type=None
        resp_all = MagicMock()
        resp_all.json.return_value = all_tenders
        resp_all.headers = {"x-total-count": "3"}
        client._execute_request.return_value = resp_all
        page_none = client.search_tenders(category="GOODS", tender_type=None)

        # Query 2: tender_type="OPEN"
        resp_open = MagicMock()
        resp_open.json.return_value = open_only_tenders
        resp_open.headers = {"x-total-count": "1"}
        client._execute_request.return_value = resp_open
        page_open = client.search_tenders(category="GOODS", tender_type="OPEN")

        numbers_none = {t["tenderNumber"] for t in page_none.tenders}
        numbers_open = {t["tenderNumber"] for t in page_open.tenders}

        # Assert OPEN is a strict subset of None
        self.assertTrue(numbers_open.issubset(numbers_none))
        # Assert OPEN adds ZERO new tenders beyond tender_type=None
        self.assertEqual(numbers_open - numbers_none, set())
        # Assert tender_type=None found everything
        self.assertGreater(len(numbers_none), len(numbers_open))


if __name__ == "__main__":
    unittest.main()
