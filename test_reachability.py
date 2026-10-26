import socket
import time
import ssl
import urllib.request
import json
import sys

print("======================================================================")
print("ACTION 1: REACHABILITY TEST TO kppp.karnataka.gov.in")
print("======================================================================")

HOST = "kppp.karnataka.gov.in"
PORT = 443
API_URL = "https://kppp.karnataka.gov.in/supplier-registration-service/v1/api/portal-service/search-eproc-tenders?page=0&size=1"

# 1. DNS Resolution
t0 = time.perf_counter()
try:
    ip = socket.gethostbyname(HOST)
    dns_time_ms = (time.perf_counter() - t0) * 1000
    print(f"1. DNS Resolution: SUCCESS | IP: {ip} | Time: {dns_time_ms:.2f} ms")
except Exception as e:
    dns_time_ms = (time.perf_counter() - t0) * 1000
    print(f"1. DNS Resolution: FAILED | Error: {e} | Time: {dns_time_ms:.2f} ms")
    print("BLOCKED FROM THIS RUNTIME")
    sys.exit(0)

# 2. TCP 443 Handshake
t0 = time.perf_counter()
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect((ip, PORT))
    tcp_time_ms = (time.perf_counter() - t0) * 1000
    s.close()
    print(f"2. TCP 443 Connection: SUCCESS | Time: {tcp_time_ms:.2f} ms")
except Exception as e:
    tcp_time_ms = (time.perf_counter() - t0) * 1000
    print(f"2. TCP 443 Connection: FAILED / TIMED OUT | Error: {e} | Time: {tcp_time_ms:.2f} ms")
    print("BLOCKED FROM THIS RUNTIME")
    sys.exit(0)

# 3. HTTP Search Call
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
    'Content-Type': 'application/json'
}
payload = json.dumps({
    "category": "GOODS",
    "status": "PUBLISHED",
    "tenderType": "OPEN"
}).encode('utf-8')

t0 = time.perf_counter()
try:
    req = urllib.request.Request(API_URL, data=payload, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=10.0) as resp:
        http_time_ms = (time.perf_counter() - t0) * 1000
        body = resp.read()
        status_code = resp.status
        try:
            data = json.loads(body.decode('utf-8'))
            count = len(data) if isinstance(data, list) else len(data.get('content', []))
            print(f"3. HTTPS API Search Call: SUCCESS | HTTP Status: {status_code} | Rows Returned: {count} | Latency: {http_time_ms:.2f} ms")
            print("STATUS: REACHABLE DIRECTLY FROM THIS RUNTIME")
        except Exception:
            print(f"3. HTTPS API Search Call: SUCCESS (Non-JSON) | HTTP Status: {status_code} | Bytes: {len(body)} | Latency: {http_time_ms:.2f} ms")
            print("STATUS: REACHABLE DIRECTLY FROM THIS RUNTIME")
except urllib.error.HTTPError as e:
    http_time_ms = (time.perf_counter() - t0) * 1000
    print(f"3. HTTPS API Search Call: HTTP ERROR {e.code} | Latency: {http_time_ms:.2f} ms")
    if e.code in [403, 429]:
        print("BLOCKED FROM THIS RUNTIME")
    else:
        print(f"Portal returned status {e.code}")
except Exception as e:
    http_time_ms = (time.perf_counter() - t0) * 1000
    print(f"3. HTTPS API Search Call: FAILED / TIMED OUT | Error: {e} | Latency: {http_time_ms:.2f} ms")
    print("BLOCKED FROM THIS RUNTIME")

print("======================================================================")
