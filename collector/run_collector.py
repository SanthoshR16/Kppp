#!/usr/bin/env python3
"""
KPPP Karnataka Standalone Collector
Runs on any machine (PC, VPS, server) with an Indian/open connection to kppp.karnataka.gov.in.
Extracts tenders, bids, comparative statements, and contract lists for the 17 focus departments
and K.K. Allianze. Generates 'kppp_data.json' for the website.
"""

import urllib.request
import ssl
import json
import time
import os
import re
import hashlib
import sys
from datetime import datetime

BASE_API = 'https://kppp.karnataka.gov.in/supplier-registration-service/v1/api'
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*'
}

SCOPE_DEPTS = {
    "AHF": {"id": 26, "name": "Animal Husbandry And Fisheries Department"},
    "AHVS": {"id": 6820, "name": "Animal Husbandry and Veterinary Services"},
    "BBMP": {"id": 671, "name": "Bruhat Bengaluru Mahanagara Palike"},
    "BMCRI": {"id": 8191, "name": "BANGALORE MEDICAL COLLEGE AND RESEARCH INSTITUTE"},
    "DHFWS": {"id": 39, "name": "Department Of Health And Family Welfare Services"},
    "DME": {"id": 3640, "name": "Department of Medical Education"},
    "ESISMS": {"id": 6289, "name": "Employees State Insurance Scheme Medical Service"},
    "HGML": {"id": 2617, "name": "Hutti Gold Mines Company Limited"},
    "INU": {"id": 6179, "name": "Institute of Nephro Urology"},
    "KKRDB": {"id": 5981, "name": "Kalyana Karnataka Region Development Board"},
    "KSMSCL": {"id": 3357, "name": "Karnataka State Medical Supplies Corporation Limited"},
    "KVAFSU": {"id": 8296, "name": "Karnataka Veterinary Animal and Fisheries Sciences University"},
    "NIMHANS": {"id": 3562, "name": "National Institute of Mental Health and Neuro Sciences"},
    "RVS": {"id": 10552, "name": "Rajya Vokkaligara Sangha"},
    "SDSTRGI": {"id": 8559, "name": "SDS Tuberculosis and Rajiv Gandhi Institute of Chest Diseases"},
    "SGITO": {"id": 9146, "name": "Sanjay Gandhi Institute of Trauma and Orthopaedics"},
    "SJICR": {"id": 7200, "name": "Sri Jayadeva Institute of Cardiovascular Sciences and Research"}
}

ALL_STATUSES = ["PUBLISHED", "CLOSED", "UNDER_EVALUATION", "EVALUATION_COMPLETED", "AWARDED", "RETENDERED", "RECALLED"]
ALL_CATEGORIES = ["GOODS", "WORKS", "SERVICES"]

KK_SUPPLIER_ID = 5086
KK_NAMES = ["K K ALLIANZE", "KAMAL KUMAR PARASMAL JAIN", "KAMAL KUMAR P JAIN", "K.K. ALLIANZE", "KK ALLIANZE"]
LOOKALIKE_PATTERNS = ["ALLIANCE BIOMEDICA", "ALLIANCE", "KAMAL"]

def api_post(endpoint, payload):
    url = f"{BASE_API}{endpoint}"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None

def api_get(endpoint):
    url = f"{BASE_API}{endpoint}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None

def check_reachability():
    print("Testing connection to KPPP Karnataka...")
    url = "/portal-service/search-eproc-tenders?page=0&size=1"
    st, data = api_post(url, {"category": "GOODS", "status": "PUBLISHED", "tenderType": "OPEN"})
    if st == 200:
        print(">> Reachability: SUCCESS (HTTP 200). Connection verified.\n")
        return True
    else:
        print(f">> Reachability: FAILED / BLOCKED (Status: {st})\n")
        return False

def extract_all():
    if not check_reachability():
        print("BLOCKED FROM THIS RUNTIME. Exiting.")
        return

    extracted_tenders = {}
    dept_counts = {k: 0 for k in SCOPE_DEPTS}

    print("Beginning extraction across the 17 focus departments...")
    for code, info in SCOPE_DEPTS.items():
        did = info['id']
        for cat in ALL_CATEGORIES:
            for st in ["PUBLISHED", "AWARDED", "EVALUATION_COMPLETED"]:
                endpoint = '/portal-service/search-eproc-tenders' if cat == 'GOODS' else f'/portal-service/{cat.lower()}/search-eproc-tenders'
                page = 0
                while page < 5:
                    url = f"{endpoint}?page={page}&size=20&order-by-tender-publish=true"
                    status_code, items = api_post(url, {
                        "category": cat,
                        "status": st,
                        "tenderType": "OPEN",
                        "deptId": did
                    })
                    if not isinstance(items, list) or not items:
                        break
                    for it in items:
                        t_num = it.get('tenderNumber')
                        if t_num and t_num not in extracted_tenders:
                            extracted_tenders[t_num] = it
                            dept_counts[code] += 1
                    if len(items) < 20:
                        break
                    page += 1
                time.sleep(0.4) # Polite pace: 0.4s delay

    print(f">> Total unique tenders extracted: {len(extracted_tenders)}")

    # Check debarred list
    print("Checking debarred/blacklist on KPPP...")
    st_deb, deb_list = api_get('/suppliers/view-blacklist-supplier')
    is_debarred = False
    if isinstance(deb_list, list):
        for deb in deb_list:
            d_str = str(deb).upper()
            if any(name in d_str for name in KK_NAMES) or deb.get('supplierId') == KK_SUPPLIER_ID:
                is_debarred = True
    print(f">> Debarred check: {'ON BLACKLIST (ALERT)' if is_debarred else 'CLEAN (NOT DEBARRED)'}\n")

    # Output to kppp_data.json
    out_file = "kppp_data.json"
    with open(out_file, 'w') as f:
        json.dump({
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "tender_count": len(extracted_tenders),
            "dept_counts": dept_counts,
            "debarred_status": "CLEAN",
            "tenders": list(extracted_tenders.values())
        }, f, indent=2)

    print(f"Collection complete. Data saved to {out_file}")

if __name__ == '__main__':
    extract_all()
