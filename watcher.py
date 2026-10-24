from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from extractor import KPPPExtractor
from models import get_dashboard_stats, get_scan_runs, set_watermark


class KPPPWatcher:
    """Light-weight watcher for a 15-minute scan and hourly reconciliation cycle."""

    def __init__(self):
        self.extractor = KPPPExtractor()
        self.last_status: Dict[str, Any] = {"status": "idle", "last_check": None}

    def run_cycle(self) -> Dict[str, Any]:
        snapshot = self.extractor.fetch_public_snapshot()
        coverage = self.extractor.reconcile_coverage()
        self.last_status = {
            "status": "ok" if snapshot.get("status") == "online" else "degraded",
            "last_check": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshot": snapshot,
            "coverage": coverage,
        }
        set_watermark("kppp_karnataka", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        dashboard = get_dashboard_stats()
        return {"watcher": self.last_status, "dashboard": dashboard, "scan_runs": get_scan_runs()}
