import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.database import STATE, connect, ensure_schema, json_object, upsert_public_tender
from app.main import app
from sources.kppp_karnataka import (
    KpppClient,
    PortalAccessError,
    PortalError,
    PortalRateLimitError,
)


class PlatformApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {"KPPP_DB_PATH": os.path.join(self.temp_dir.name, "test.sqlite")},
        )
        self.env.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.env.stop()
        self.temp_dir.cleanup()

    def test_dashboard_seeds_all_focus_departments_and_empty_counts(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["departments"]), 17)
        self.assertFalse(payload["departments"][0]["name_verified"])
        self.assertEqual(payload["stats"]["tenders"], 0)
        self.assertEqual(payload["scan"]["status"], "not_started")

    def test_quotes_are_normalised_and_visible_on_dashboard(self):
        response = self.client.post(
            "/api/quotes",
            json={"tender_numbers": [" dme / 2026-27 / ind0123 ", "SGITO/2026-27/IND0099"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["added"],
            ["DME/2026-27/IND0123", "SGITO/2026-27/IND0099"],
        )
        dashboard = self.client.get("/api/dashboard").json()
        self.assertEqual(dashboard["stats"]["quoted"], 2)
        self.assertEqual(dashboard["stats"]["not_public"], 2)

    def test_out_of_scope_tender_numbers_are_rejected(self):
        response = self.client.post(
            "/api/quotes",
            json={"tender_numbers": ["OUTSIDE/2026-27/IND0001"]},
        )
        self.assertEqual(response.status_code, 422)

    def test_tender_search_excludes_out_of_scope_rows(self):
        ensure_schema()
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO tenders(
                    state, tender_number, department_code, status, title,
                    in_scope, out_of_scope, created_at
                ) VALUES (?, ?, ?, ?, ?, 1, 0, ?)
                """,
                (STATE, "DME/2026-27/IND0001", "DME", "PUBLISHED", "In scope", "2026-10-24"),
            )
            connection.execute(
                """
                INSERT INTO tenders(
                    state, tender_number, department_code, status, title,
                    in_scope, out_of_scope, created_at
                ) VALUES (?, ?, ?, ?, ?, 0, 1, ?)
                """,
                (STATE, "OTHER/2026-27/IND0002", "OTHER", "PUBLISHED", "Out of scope", "2026-10-24"),
            )
        payload = self.client.get("/api/tenders?q=scope").json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["department_code"], "DME")

    def test_public_upsert_tracks_status_changes_without_documents(self):
        ensure_schema()
        first = {
            "tenderNumber": "DME/2026-27/IND0001",
            "category": "GOODS",
            "status": "PUBLISHED",
            "title": "Test tender",
        }
        second = {**first, "status": "UNDER_EVALUATION"}
        with connect() as connection:
            self.assertTrue(upsert_public_tender(connection, first, "DME"))
            self.assertTrue(upsert_public_tender(connection, second, "DME"))
            self.assertFalse(
                upsert_public_tender(
                    connection,
                    {**first, "tenderNumber": "OTHER/2026-27/IND0003"},
                    "DME",
                )
            )
        detail = self.client.get(
            "/api/tender", params={"number": "DME/2026-27/IND0001"}
        ).json()
        self.assertEqual(detail["status"], "UNDER_EVALUATION")
        self.assertEqual(detail["timeline"][0]["previous_status"], "PUBLISHED")
        self.assertEqual(detail["items"], [])
        self.assertEqual(detail["bids"], [])

    def test_schema_migration_normalises_legacy_department_ids(self):
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO tenders(
                    state, tender_number, department_code, status, in_scope, out_of_scope
                ) VALUES (?, ?, '3640', 'PUBLISHED', 1, 0)
                """,
                (STATE, "DME/2026-27/IND0098"),
            )
        ensure_schema()
        with connect() as connection:
            row = connection.execute(
                """
                SELECT department_code, in_scope, out_of_scope FROM tenders
                WHERE state = ? AND tender_number = ?
                """,
                (STATE, "DME/2026-27/IND0098"),
            ).fetchone()
        self.assertEqual(tuple(row), ("DME", 1, 0))

    def test_invalid_stored_tender_json_is_not_silently_hidden(self):
        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            json_object("{invalid")


class PublicClientTests(unittest.TestCase):
    def test_client_sends_no_auth_or_cookie_headers(self):
        client = KpppClient(delay=0)
        self.assertIsNone(client.session.auth)
        self.assertEqual(dict(client.session.cookies), {})
        self.assertNotIn("Authorization", client.session.headers)
        self.assertNotIn("Cookie", client.session.headers)
        self.assertFalse(client.session.trust_env)

    def test_401_and_403_are_explicit_access_errors(self):
        for status in (401, 403):
            response = type("Response", (), {"status_code": status})()
            client = KpppClient(delay=0)
            with patch.object(client.session, "post", return_value=response):
                with self.assertRaises(PortalAccessError):
                    client._request(0, "GOODS", "PUBLISHED", 3640)

    def test_429_stops_the_request_cycle(self):
        response = type("Response", (), {"status_code": 429})()
        client = KpppClient(delay=0)
        with patch.object(client.session, "post", return_value=response):
            with self.assertRaises(PortalRateLimitError):
                client._request(0, "GOODS", "PUBLISHED", 3640)

    def test_search_variants_send_null_and_empty_tender_type(self):
        response = type(
            "Response",
            (),
            {
                "status_code": 200,
                "headers": {},
                "json": lambda self: [],
                "raise_for_status": lambda self: None,
            },
        )()
        client = KpppClient(delay=0)
        with patch.object(client.session, "post", return_value=response) as post:
            client._request(0, "GOODS", "PUBLISHED", 3640, tender_type=None)
            self.assertIsNone(post.call_args.kwargs["json"]["tenderType"])
            client._request(0, "GOODS", "PUBLISHED", 3640, tender_type="")
            self.assertEqual(post.call_args.kwargs["json"]["tenderType"], "")

    def test_invalid_portal_total_is_an_explicit_error(self):
        response = type(
            "Response",
            (),
            {
                "status_code": 200,
                "headers": {"x-total-count": "unknown"},
                "json": lambda self: [],
                "raise_for_status": lambda self: None,
            },
        )()
        client = KpppClient(delay=0)
        with patch.object(client.session, "post", return_value=response):
            with self.assertRaisesRegex(PortalError, "invalid x-total-count"):
                client._request(0, "GOODS", "PUBLISHED", 3640)


if __name__ == "__main__":
    unittest.main()
