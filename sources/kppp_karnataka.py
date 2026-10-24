import time
from dataclasses import dataclass

import requests

from app.database import FOCUS_DEPARTMENTS


BASE_API = "https://kppp.karnataka.gov.in/supplier-registration-service/v1/api"
STATUSES = (
    "PUBLISHED",
    "CLOSED",
    "UNDER_EVALUATION",
    "EVALUATION_COMPLETED",
    "AWARDED",
    "RETENDERED",
    "RECALLED",
)
CATEGORIES = ("GOODS", "WORKS", "SERVICES")
PAGE_SIZE = 100


class PortalError(RuntimeError):
    pass


class PortalAccessError(PortalError):
    pass


class PortalRateLimitError(PortalError):
    pass


@dataclass
class TenderPage:
    tenders: list
    total_count: int | None


class KpppClient:
    def __init__(self, session=None, delay=0.4, timeout=15):
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.auth = None
        self.session.cookies.clear()
        self.session.headers.clear()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "KPPP-Local-Procurement-Monitor/1.0",
        })
        self.delay = delay
        self.timeout = timeout
        self._last_request = 0.0

    def _request(self, page, category, status, department_id, tender_type=None, tender_number=None):
        route = {
            "GOODS": "/portal-service/search-eproc-tenders",
            "WORKS": "/portal-service/works/search-eproc-tenders",
            "SERVICES": "/portal-service/services/search-eproc-tenders",
        }[category]
        now = time.monotonic()
        wait = self.delay - (now - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

        payload = {
            "category": category,
            "status": status,
            "deptId": department_id,
            "tenderType": tender_type,
        }
        if tender_number is not None:
            payload["tenderNumber"] = tender_number
        self.session.cookies.clear()
        try:
            response = self.session.post(
                f"{BASE_API}{route}",
                params={"page": page, "size": PAGE_SIZE, "order-by-tender-publish": "true"},
                json=payload,
                timeout=self.timeout,
            )
        finally:
            self.session.cookies.clear()
        if response.status_code in (401, 403):
            raise PortalAccessError(
                f"Unauthenticated public KPPP endpoint rejected the request: HTTP {response.status_code}"
            )
        if response.status_code == 429:
            raise PortalRateLimitError("KPPP returned HTTP 429; stopped the scan immediately")
        response.raise_for_status()

        try:
            body = response.json()
        except ValueError as exc:
            raise PortalError("KPPP returned a non-JSON tender-search response") from exc
        if isinstance(body, list):
            rows = body
        elif isinstance(body, dict):
            rows = None
            for key in ("content", "list", "data"):
                if key in body:
                    rows = body[key]
                    break
            if not isinstance(rows, list):
                raise PortalError("KPPP tender-search response has an unknown list shape")
        else:
            raise PortalError("KPPP tender-search response has an unknown shape")
        total_header = response.headers.get("x-total-count")
        if total_header is None:
            total_count = None
        else:
            try:
                total_count = int(total_header)
            except (TypeError, ValueError) as exc:
                raise PortalError("KPPP returned an invalid x-total-count header") from exc
            if total_count < 0:
                raise PortalError("KPPP returned a negative x-total-count header")
        return TenderPage(rows, total_count)

    def search_department(self, department_id, category, status, tender_type=None, tender_number=None, on_page=None):
        results = []
        expected_total = None
        page_number = 0
        while True:
            page = self._request(
                page_number, category, status, department_id, tender_type, tender_number
            )
            if expected_total is None:
                expected_total = page.total_count
            results.extend(page.tenders)
            if on_page:
                on_page({
                    "page": page_number,
                    "rows": len(page.tenders),
                    "rows_seen": len(results),
                    "portal_total": expected_total,
                })
            if len(page.tenders) < PAGE_SIZE:
                break
            page_number += 1
        mismatch = expected_total is not None and len(results) != expected_total
        return results, expected_total, mismatch

    def search_tender_number(self, department_id, category, tender_number):
        page = self._request(
            0,
            category,
            None,
            department_id,
            tender_type=None,
            tender_number=tender_number,
        )
        return [
            row for row in page.tenders
            if str(row.get("tenderNumber") or row.get("tender_number") or "").strip().upper()
            == tender_number.strip().upper()
        ]


def focus_department_rows():
    return tuple({"department_code": code, "portal_id": portal_id} for code, portal_id in FOCUS_DEPARTMENTS)
