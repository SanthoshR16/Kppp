import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app
from extractor import KPPPExtractor


def test_extractor_has_expected_state_adapter():
    extractor = KPPPExtractor()
    payload = extractor.fetch_public_snapshot()
    assert payload["state"] == "karnataka"
    assert payload["source"] == "kppp_karnataka"


def test_dashboard_and_tenders_endpoints_work():
    client = TestClient(app)
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["state"] == "karnataka"

    tenders = client.get("/tenders?limit=5")
    assert tenders.status_code == 200
    assert isinstance(tenders.json(), list)

    reconcile = client.get("/reconcile")
    assert reconcile.status_code == 200
    assert "coverage_percent" in reconcile.json()
