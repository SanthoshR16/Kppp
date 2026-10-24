import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app
from database import init_db
from sources.kppp_karnataka import KarnatakaKPPPAdapter


def test_database_schema_initializes():
    db_path = PROJECT_ROOT / "data" / "db" / "test_kppp.sqlite"
    init_db(db_path)
    assert db_path.exists()
    assert db_path.stat().st_size > 0


def test_karnataka_adapter_metadata_is_consistent():
    metadata = KarnatakaKPPPAdapter.metadata()
    assert metadata["state"] == "karnataka"
    assert "kppp_karnataka" in metadata["source_name"]
    assert "AHF" in metadata["priority_departments"]


def test_app_health_and_metadata_endpoints():
    client = TestClient(app)
    health = client.get("/health")
    metadata = client.get("/metadata")

    assert health.status_code == 200
    assert health.json()["state"] == "karnataka"
    assert metadata.status_code == 200
    assert metadata.json()["state"] == "karnataka"
