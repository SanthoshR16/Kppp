import re
import sys
import time
import urllib.request
from typing import Set

BASE_PORTAL = "https://kppp.karnataka.gov.in"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def fetch_text(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Referer": f"{BASE_PORTAL}/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def discover_endpoints() -> None:
    print("=" * 100)
    print(" KPPP LIVE PORTAL ENDPOINT & CHUNK DISCOVERY")
    print("=" * 100)
    print(f"Fetching main bundle: {BASE_PORTAL}/main.js ...")

    try:
        main_js = fetch_text(f"{BASE_PORTAL}/main.js")
    except Exception as exc:
        print(f"[ERROR] Could not fetch main.js: {exc}")
        sys.exit(1)

    print(f"Downloaded main.js ({len(main_js)} bytes). Scanning for lazy-loaded chunk files...")

    # Find chunk files e.g., chunk-vendors.js, 123.chunk.js, runtime.js, etc.
    chunk_matches = set(re.findall(r'["\']([a-zA-Z0-9_\-\.]+\.chunk\.js|[0-9]+\.[a-f0-9]+\.js|chunk-[a-zA-Z0-9_\-\.]+\.js)[\'"]', main_js))
    # Also find webpack chunks if present e.g. u(e)+".js"
    additional_chunks = set(re.findall(r'["\']([a-zA-Z0-9_\-]+\.js)[\'"]', main_js))
    candidate_chunks = [c for c in chunk_matches | additional_chunks if "chunk" in c or c.endswith(".js") and len(c) < 50][:15]

    print(f"Identified {len(candidate_chunks)} candidate script chunks.")

    scripts = {"main.js": main_js}
    for chunk in candidate_chunks:
        chunk_url = f"{BASE_PORTAL}/{chunk}"
        try:
            time.sleep(0.3)
            print(f"  Downloading chunk: {chunk} ...")
            content = fetch_text(chunk_url, timeout=15.0)
            scripts[chunk] = content
        except Exception:
            # Chunk may not be directly at root
            pass

    print("\n" + "-" * 100)
    print("1. EVALUATION & BIDDER ENDPOINTS (GOODS, WORKS, SERVICES)")
    print("-" * 100)

    eval_patterns = [
        r'["\']([\/a-zA-Z0-9_\-:]*(?:commercial-evaluation|commercial-comparison|bid-groups|selected-bid|itemwise|tender-eval|bids)[\/a-zA-Z0-9_\-:]*)["\']',
        r'["\']([\/a-zA-Z0-9_\-:]*(?:works-tender|service-tender|goods-tender)[\/a-zA-Z0-9_\-:]*)["\']',
        r'["\']([\/a-zA-Z0-9_\-:]*(?:search-eproc-tenders|awarded-tender|activeDepartment)[\/a-zA-Z0-9_\-:]*)["\']',
    ]

    found_endpoints: Set[str] = set()
    for filename, code in scripts.items():
        for pat in eval_patterns:
            for match in re.findall(pat, code, re.IGNORECASE):
                if "/" in match and len(match) > 3 and not match.startswith("http"):
                    found_endpoints.add(f"{match}  (in {filename})")

    for ep in sorted(found_endpoints):
        print(f"  [FOUND] {ep}")

    print("\n" + "-" * 100)
    print("2. RESERVED TENDERS & CRITERIA DISCOVERY")
    print("-" * 100)
    reserved_patterns = [
        r'["\']([a-zA-Z0-9_\-:]*reserved[a-zA-Z0-9_\-:]*)["\']',
        r'["\']([a-zA-Z0-9_\-:]*sc_st[a-zA-Z0-9_\-:]*)["\']',
        r'["\']([a-zA-Z0-9_\-:]*preference[a-zA-Z0-9_\-:]*)["\']',
    ]
    found_reserved: Set[str] = set()
    for filename, code in scripts.items():
        for pat in reserved_patterns:
            for match in re.findall(pat, code, re.IGNORECASE):
                if len(match) > 3:
                    found_reserved.add(f"{match}  (in {filename})")

    for rsv in sorted(found_reserved):
        print(f"  [FOUND] {rsv}")

    print("\n" + "-" * 100)
    print("3. WORKS & SERVICES COMPARISON PROPERTIES")
    print("-" * 100)
    works_props = set()
    for filename, code in scripts.items():
        for m in re.findall(r'(tender(?:Works|Services|Work|Service)[A-Za-z0-9_]*)', code):
            works_props.add(f"{m}  (in {filename})")

    for prop in sorted(works_props)[:25]:
        print(f"  [PROP] {prop}")

    print("\n" + "=" * 100)
    print(" Discovery complete. Only verified code matches shown above.")
    print("=" * 100)


if __name__ == "__main__":
    discover_endpoints()
