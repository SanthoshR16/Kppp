import json
import socket
import ssl
import sys
import time
from typing import Optional

from kppp_client import KpppClient, PortalAccessError, PortalError, PortalRateLimitError

TARGET_HOST = "kppp.karnataka.gov.in"
TARGET_PORT = 443


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(f" {title.upper()}")
    print("=" * 80)


def step_dns() -> Optional[str]:
    print("\n[Step 1/5] Testing DNS Resolution for", TARGET_HOST)
    start = time.perf_counter()
    try:
        addrinfo = socket.getaddrinfo(TARGET_HOST, TARGET_PORT, socket.AF_INET, socket.SOCK_STREAM)
        duration_ms = (time.perf_counter() - start) * 1000
        ip = addrinfo[0][4][0]
        print(f"  --> SUCCESS: Resolved to {ip} in {duration_ms:.1f}ms")
        return ip
    except socket.gaierror as exc:
        print(f"  --> FAILED: DNS lookup failed for {TARGET_HOST}: {exc}")
        print("  --> FIX: Check your internet connection or try changing DNS (e.g. 8.8.8.8).")
        return None


def step_tcp_tls(ip: str) -> bool:
    print(f"\n[Step 2/5] Testing TCP connection & TLS handshake ({TARGET_HOST}:443)")
    start = time.perf_counter()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        sock.connect((ip, TARGET_PORT))
        tcp_duration_ms = (time.perf_counter() - start) * 1000
        print(f"  --> TCP Connected to {ip}:{TARGET_PORT} in {tcp_duration_ms:.1f}ms")

        tls_start = time.perf_counter()
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(sock, server_hostname=TARGET_HOST) as ssock:
            tls_duration_ms = (time.perf_counter() - tls_start) * 1000
            print(f"  --> TLS Handshake ({ssock.version()}, cipher: {ssock.cipher()[0]}) in {tls_duration_ms:.1f}ms")
        return True
    except (socket.timeout, TimeoutError):
        print("  --> TIMED OUT: Port 443 is unreachable or blocked by your network/firewall/ISP.")
        return False
    except Exception as exc:
        print(f"  --> FAILED: {exc}")
        return False


def step_active_departments(client: KpppClient) -> bool:
    print("\n[Step 3/5] Testing HTTP GET /portal-service/departments/activeDepartment")
    start = time.perf_counter()
    try:
        depts = client.get_active_departments()
        duration_ms = (time.perf_counter() - start) * 1000
        print(f"  --> SUCCESS: Received {len(depts)} active departments in {duration_ms:.1f}ms")
        if depts:
            sample = depts[0]
            print(f"      Sample: ID={sample.get('id') or sample.get('deptId')}, Name={sample.get('deptName') or sample.get('name')}")
        return True
    except PortalAccessError as exc:
        print(f"  --> ACCESS DENIED (HTTP 401/403): {exc}")
        return False
    except PortalRateLimitError as exc:
        print(f"  --> RATE LIMITED (HTTP 429): {exc}")
        return False
    except PortalError as exc:
        print(f"  --> PORTAL ERROR: {exc}")
        return False
    except Exception as exc:
        print(f"  --> UNEXPECTED ERROR: {exc}")
        return False


def step_search(client: KpppClient) -> Optional[dict]:
    print("\n[Step 4/5] Testing HTTP POST /portal-service/search-eproc-tenders (page=0, size=1)")
    start = time.perf_counter()
    try:
        # Search DME (deptId 3640)
        page = client.search_tenders(category="GOODS", status="PUBLISHED", dept_id=3640, size=1)
        duration_ms = (time.perf_counter() - start) * 1000
        print(f"  --> SUCCESS: Returned {len(page.tenders)} rows (portal total: {page.total_count}) in {duration_ms:.1f}ms")
        if page.tenders:
            t = page.tenders[0]
            print(f"      Found tender: {t.get('tenderNumber')} (id={t.get('id')}, nitId={t.get('nitId')})")
            return t
        else:
            # Try searching all without department
            page_all = client.search_tenders(category="GOODS", status="PUBLISHED", size=1)
            if page_all.tenders:
                t = page_all.tenders[0]
                print(f"      Found global tender: {t.get('tenderNumber')} (id={t.get('id')}, nitId={t.get('nitId')})")
                return t
        return None
    except Exception as exc:
        print(f"  --> SEARCH CALL FAILED: {exc}")
        return None


def step_full_view(client: KpppClient, tender: Optional[dict]) -> bool:
    print("\n[Step 5/5] Testing HTTP GET goods-tender-full-view")
    tender_id = tender.get("id") if tender else 63253
    print(f"  --> Requesting full-view for tender id: {tender_id}")
    start = time.perf_counter()
    try:
        full = client.get_tender_full_view(tender_id, category="GOODS")
        duration_ms = (time.perf_counter() - start) * 1000
        ecv = full.get("estimatedCost") or full.get("tenderValue") or full.get("ecv")
        print(f"  --> SUCCESS: Full-view loaded in {duration_ms:.1f}ms. ECV: {ecv}")
        return True
    except Exception as exc:
        print(f"  --> FULL VIEW FAILED for id {tender_id}: {exc}")
        return False


def main() -> None:
    print_header("KPPP Portal Connectivity Diagnostics")
    print(f"Target: {TARGET_HOST}")
    print(f"Local time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    ip = step_dns()
    if not ip:
        print("\nDiagnostic result: DNS failure. Cannot reach portal.")
        sys.exit(1)

    tcp_ok = step_tcp_tls(ip)
    if not tcp_ok:
        print("\nDiagnostic result: TCP/TLS connection timeout. The portal may be down, or your IP is being blocked.")
        sys.exit(1)

    client = KpppClient(delay=0.4, connect_timeout=10.0, read_timeout=60.0)

    dept_ok = step_active_departments(client)
    sample_tender = step_search(client)
    full_view_ok = step_full_view(client, sample_tender)

    print_header("Diagnostic Summary")
    print(f"  DNS Resolution:         {'[OK]' if ip else '[FAILED]'}")
    print(f"  TCP/TLS Handshake:      {'[OK]' if tcp_ok else '[FAILED]'}")
    print(f"  Active Departments API: {'[OK]' if dept_ok else '[FAILED]'}")
    print(f"  Tender Search API:      {'[OK]' if sample_tender is not None else '[FAILED]'}")
    print(f"  Full View API:          {'[OK]' if full_view_ok else '[FAILED]'}")

    if dept_ok and sample_tender and full_view_ok:
        print("\n>>> ALL TESTS PASSED! The live portal is responsive and ready for backfill.")
    else:
        print("\n>>> ONE OR MORE TESTS FAILED. Please review the output above and copy into your prompt.")


if __name__ == "__main__":
    main()
