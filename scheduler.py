from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, Thread
from typing import Any, Dict

from extractor import KPPPExtractor
from models import add_scan_run, finish_scan_run, set_watermark


class BackgroundScheduler:
    def __init__(self, interval_seconds: int = 900, reconcile_seconds: int = 3600):
        self.interval_seconds = interval_seconds
        self.reconcile_seconds = reconcile_seconds
        self.stop_event = Event()
        self.thread = None
        self.status = {"state": "idle", "last_tick": None}

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            self.status = {"state": "scanning", "last_tick": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            run_id = add_scan_run("kppp_karnataka", "running", notes="background scan cycle")
            try:
                extractor = KPPPExtractor()
                metadata = extractor.fetch_public_snapshot()
                coverage = extractor.reconcile_coverage()
                set_watermark("kppp_karnataka", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
                finish_scan_run(run_id, "completed", notes=json_dump_safe({"metadata": metadata, "coverage": coverage}))
            except Exception as exc:
                finish_scan_run(run_id, "failed", notes=str(exc))
            self.status = {"state": "idle", "last_tick": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            self.stop_event.wait(self.interval_seconds)


def json_dump_safe(data: Dict[str, Any]) -> str:
    import json
    return json.dumps(data, ensure_ascii=False, sort_keys=True)
