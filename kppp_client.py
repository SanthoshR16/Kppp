import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import requests

BASE_API = "https://kppp.karnataka.gov.in/supplier-registration-service/v1/api"
PORTAL_ORIGIN = "https://kppp.karnataka.gov.in"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

logger = logging.getLogger("kppp_client")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class PortalError(RuntimeError):
    """Base exception for portal communication or schema issues."""
    pass


class PortalAccessError(PortalError):
    """Raised when the public portal returns 401 or 403."""
    pass


class PortalRateLimitError(PortalError):
    """Raised when the public portal returns 429."""
    pass


@dataclass
class TenderPage:
    tenders: List[Dict[str, Any]]
    total_count: Optional[int]


class KpppClient:
    """
    Polite, unauthenticated client for the Karnataka Public Procurement Portal.
    Uses a single shared session, exponential backoff for transient issues,
    strict rate limits, and stops immediately on HTTP 429 or 401/403.
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        delay: float = 0.4,
        connect_timeout: float = 10.0,
        read_timeout: float = 60.0,
        max_retries: int = 3,
    ):
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.auth = None
        self.session.cookies.clear()
        self.session.headers.clear()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": PORTAL_ORIGIN,
            "Referer": f"{PORTAL_ORIGIN}/",
            "User-Agent": DEFAULT_USER_AGENT,
        })
        self.delay = delay
        self.timeout = (connect_timeout, read_timeout)
        self.max_retries = max_retries
        self._last_request_time = 0.0

    def _wait_for_rate_limit(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_time
        remaining = self.delay - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_time = time.monotonic()

    def _execute_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        stream: bool = False,
        raw_response: bool = False,
    ) -> requests.Response:
        url = f"{BASE_API}{path}" if path.startswith("/") else f"{BASE_API}/{path}"
        retries = 0
        backoff = 1.0

        while True:
            self._wait_for_rate_limit()
            # Ensure stateless, unauthenticated execution
            self.session.cookies.clear()
            start_t = time.monotonic()

            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=self.timeout,
                    stream=stream,
                )
                duration = time.monotonic() - start_t
                logger.info(
                    "%s %s -> HTTP %d (%.2fs)",
                    method,
                    path,
                    response.status_code,
                    duration,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                duration = time.monotonic() - start_t
                retries += 1
                logger.warning(
                    "%s %s failed (attempt %d/%d, %.2fs): %s",
                    method,
                    path,
                    retries,
                    self.max_retries,
                    duration,
                    exc,
                )
                if retries > self.max_retries:
                    raise PortalError(
                        f"KPPP endpoint {path} timed out after {retries} attempts: {exc}"
                    ) from exc
                time.sleep(backoff)
                backoff *= 2.0
                continue
            finally:
                self.session.cookies.clear()

            if response.status_code in (401, 403):
                raise PortalAccessError(
                    f"Public KPPP endpoint rejected request with HTTP {response.status_code}. "
                    "Ensure no stale cookies or auth tokens are being sent."
                )

            if response.status_code == 429:
                raise PortalRateLimitError(
                    "KPPP returned HTTP 429 (Rate Limit). Scanning stopped immediately."
                )

            if response.status_code in (502, 503, 504) and retries < self.max_retries:
                retries += 1
                logger.warning(
                    "Transient server error HTTP %d for %s. Retrying in %.1fs...",
                    response.status_code,
                    path,
                    backoff,
                )
                time.sleep(backoff)
                backoff *= 2.0
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                raise PortalError(f"KPPP request failed: {exc}") from exc

            return response

    def search_tenders(
        self,
        category: str = "GOODS",
        status: Optional[str] = None,
        dept_id: Optional[int] = None,
        tender_type: Optional[str] = None,
        published_from: Optional[str] = None,
        published_to: Optional[str] = None,
        closing_from: Optional[str] = None,
        closing_to: Optional[str] = None,
        tender_number: Optional[str] = None,
        title: Optional[str] = None,
        ecv: Optional[Union[str, float]] = None,
        location: Optional[str] = None,
        page: int = 0,
        size: int = 100,
        order_by: bool = True,
    ) -> TenderPage:
        cat_upper = category.upper()
        if cat_upper == "WORKS":
            route = "/portal-service/works/search-eproc-tenders"
        elif cat_upper == "SERVICES":
            route = "/portal-service/services/search-eproc-tenders"
        else:
            route = "/portal-service/search-eproc-tenders"

        params: Dict[str, Any] = {"page": page, "size": size}
        if order_by:
            params["order-by-tender-publish"] = "true"

        payload: Dict[str, Any] = {
            "category": cat_upper,
            "status": status,
            "deptId": dept_id,
            "tenderType": tender_type,
        }
        if published_from:
            payload["publishedFromDate"] = published_from
        if published_to:
            payload["publishedToDate"] = published_to
        if closing_from:
            payload["tenderClosureFromDate"] = closing_from
        if closing_to:
            payload["tenderClosureToDate"] = closing_to
        if tender_number:
            payload["tenderNumber"] = tender_number
        if title:
            payload["title"] = title
        if ecv is not None:
            payload["ecv"] = ecv
        if location:
            payload["location"] = location

        response = self._execute_request("POST", route, params=params, json_data=payload)

        try:
            body = response.json()
        except ValueError as exc:
            raise PortalError("KPPP tender-search returned non-JSON response") from exc

        if isinstance(body, list):
            rows = body
        elif isinstance(body, dict):
            rows = []
            for key in ("content", "list", "data"):
                if key in body and isinstance(body[key], list):
                    rows = body[key]
                    break
            else:
                rows = []
        else:
            rows = []

        total_header = response.headers.get("x-total-count")
        total_count: Optional[int] = None
        if total_header is not None:
            try:
                total_count = int(total_header)
            except (ValueError, TypeError) as exc:
                raise PortalError(f"KPPP returned invalid x-total-count: {total_header}") from exc
            if total_count < 0:
                raise PortalError("KPPP returned negative x-total-count")

        return TenderPage(tenders=rows, total_count=total_count)

    def _get_full_view_raw(self, tender_id: Union[int, str], category: str = "GOODS") -> Dict[str, Any]:
        cat_upper = category.upper()
        if cat_upper == "WORKS":
            route = f"/portal-service/{tender_id}/works-tender-full-view"
        elif cat_upper == "SERVICES":
            route = f"/portal-service/{tender_id}/service-tender-full-view"
        else:
            route = f"/portal-service/{tender_id}/goods-tender-full-view"

        response = self._execute_request("GET", route)
        try:
            return response.json()
        except ValueError as exc:
            raise PortalError(f"Non-JSON full view response for tender id {tender_id}") from exc

    def get_tender_full_view(
        self,
        expected_tender_number: str,
        tender_id: Optional[Union[int, str]] = None,
        nit_id: Optional[Union[int, str]] = None,
        category: str = "GOODS",
    ) -> Dict[str, Any]:
        norm_expected = " ".join(str(expected_tender_number).strip().upper().split()).replace(" /", "/").replace("/ ", "/")
        candidate_ids = [cid for cid in (tender_id, nit_id) if cid is not None]
        if not candidate_ids:
            raise ValueError(f"Neither tender_id nor nit_id provided for {norm_expected}")

        last_error = None
        for cid in candidate_ids:
            try:
                data = self._get_full_view_raw(cid, category=category)
                resp_num = str(data.get("tenderNumber") or data.get("tender_number") or "").strip().upper()
                resp_norm = " ".join(resp_num.split()).replace(" /", "/").replace("/ ", "/")
                if resp_norm == norm_expected:
                    return data
                logger.warning(
                    "Tender number mismatch for ID %s: expected %s, got %s",
                    cid,
                    norm_expected,
                    resp_norm,
                )
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error
        raise PortalError(f"Tender number verification failed in full-view for {norm_expected} with IDs {candidate_ids}")

    def download_commercial_comparison(self, nit_id: Union[int, str], category: str = "GOODS") -> bytes:
        cat_upper = category.upper()
        route = (
            f"/portal-service/tender-eval/{nit_id}/commercial-evaluation/"
            f"tender-category/{cat_upper}/commercial-comparison/download-detailed"
        )
        response = self._execute_request("GET", route)
        return response.content

    def get_bid_groups_details(self, nit_id: Union[int, str], category: str = "GOODS") -> List[Dict[str, Any]]:
        cat_upper = category.upper()
        route = f"/portal-service/bids/{nit_id}/tender-category/{cat_upper}/bid-groups-details"
        response = self._execute_request("GET", route)
        try:
            res = response.json()
            return res if isinstance(res, list) else []
        except ValueError:
            return []

    def get_selected_bid_item(
        self,
        nit_id: Union[int, str],
        category: str,
        group_id: Union[int, str],
    ) -> List[Dict[str, Any]]:
        cat_upper = category.upper()
        route = (
            f"/portal-service/bids/{nit_id}/tender-category/{cat_upper}/"
            f"bid-item-group/{group_id}/bid-items/get-selected-bid-item"
        )
        response = self._execute_request("GET", route)
        try:
            res = response.json()
            return res if isinstance(res, list) else []
        except ValueError:
            return []

    def get_selected_bid_for_itemwise(
        self,
        nit_id: Union[int, str],
        category: str,
        item_id: Union[int, str],
    ) -> Dict[str, Any]:
        cat_upper = category.upper()
        route = (
            f"/portal-service/bids/{nit_id}/tender-category/{cat_upper}/"
            f"bidItem/{item_id}/get-selected-bid-for-itemwise"
        )
        response = self._execute_request("GET", route)
        try:
            res = response.json()
            return res if isinstance(res, dict) else {}
        except ValueError:
            return {}

    def get_all_itemwise_selected_bids(
        self,
        nit_id: Union[int, str],
        category: str = "GOODS",
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the itemwise selected bid for EVERY item across all bid groups.
        """
        cat_upper = category.upper()
        selected_bids: List[Dict[str, Any]] = []
        groups = self.get_bid_groups_details(nit_id, category=cat_upper)

        for group in groups:
            group_id = group.get("id") or group.get("groupId")
            if not group_id:
                continue
            items = self.get_selected_bid_item(nit_id, cat_upper, group_id)
            for item in items:
                item_id = item.get("id") or item.get("itemId") or item.get("bidItemId")
                if not item_id:
                    continue
                item_bid = self.get_selected_bid_for_itemwise(nit_id, cat_upper, item_id)
                if item_bid:
                    item_bid["item_id"] = item_id
                    item_bid["item_name"] = item.get("itemName") or item.get("item_name")
                    selected_bids.append(item_bid)

        return selected_bids

    def get_active_departments(self) -> List[Dict[str, Any]]:
        route = "/portal-service/departments/activeDepartment"
        response = self._execute_request("GET", route)
        try:
            body = response.json()
            return body if isinstance(body, list) else []
        except ValueError as exc:
            raise PortalError("Failed to parse activeDepartment JSON") from exc

    def get_metrics_count(self) -> Dict[str, Any]:
        route = "/portal-service/metrics/get-count"
        response = self._execute_request("GET", route)
        try:
            return response.json()
        except ValueError as exc:
            raise PortalError("Failed to parse metrics count JSON") from exc

    def get_awarded_tender_list(self, payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        route = "/contract/awarded-tender-list"
        response = self._execute_request("POST", route, json_data=payload or {})
        try:
            res = response.json()
            return res if isinstance(res, list) else []
        except ValueError as exc:
            raise PortalError("Failed to parse awarded-tender-list JSON") from exc
