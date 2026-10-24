from __future__ import annotations

from typing import Iterable, List

from config import PRIORITY_DEPARTMENTS, STATE_NAME


class KarnatakaKPPPAdapter:
    """Adapter responsible for the Karnataka portal rules and metadata."""

    state = STATE_NAME
    source_name = "kppp_karnataka"
    public_endpoints = {
        "tender_search": "/#/portal/searchTender/live",
        "full_tender_view": "/#/portal/tenderView",
        "tender_file_list": "/#/portal/tenderDocs",
        "comparative_statement": "/#/portal/comparisonStatement",
        "itemwise_selected_bid": "/#/portal/selectedBids",
        "awarded_tender_list": "/#/portal/awardedTenders",
        "contract_list": "/#/portal/contracts",
        "debarred_suppliers": "/#/portal/debarred",
        "auctions": "/#/portal/auctions",
        "department_directory": "/#/portal/departmentDirectory",
        "metrics_counter": "/#/portal/metrics",
    }

    @classmethod
    def supported_departments(cls) -> List[str]:
        return PRIORITY_DEPARTMENTS + [
            "AAKAR", "BDA", "BMRCL", "CIF", "DPAR", "HFW", "KPTCL", "PWD",
        ]

    @classmethod
    def source_url(cls) -> str:
        return "https://kppp.karnataka.gov.in"

    @classmethod
    def metadata(cls) -> dict:
        return {
            "state": cls.state,
            "source_name": cls.source_name,
            "priority_departments": PRIORITY_DEPARTMENTS,
            "public_endpoints": cls.public_endpoints,
        }
