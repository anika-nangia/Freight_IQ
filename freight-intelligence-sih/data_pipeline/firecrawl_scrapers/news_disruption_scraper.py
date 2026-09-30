"""
News Disruption Scraper
Monitors maritime news, port circulars, and weather advisories for disruption keywords:
'strike', 'draft restriction', 'dredging', 'cyclone', 'loading halt'.
"""

from typing import List, Dict, Any
from datetime import datetime

class NewsDisruptionScraper:
    KEYWORDS = ["strike", "draft restriction", "dredging", "cyclone", "depression", "halt", "berth maintenance"]

    def extract_recent_disruptions(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "DISR-2026-081",
                "source": "Maritime Board Circular",
                "port": "Haldia",
                "severity": "medium",
                "headline": "Emergency maintenance dredging active at Haldia Dock Complex entrance channel",
                "detail": "Draft temporarily capped at 8.2m until next spring tide cycle. Handysize vessels advised to lighter before entry.",
                "keywords_matched": ["dredging", "draft restriction"],
                "active_until": "2026-09-04",
                "reported_at": "2026-08-28"
            },
            {
                "id": "DISR-2026-082",
                "source": "IMD Weather Warning",
                "port": "Paradip",
                "severity": "high",
                "headline": "Deep depression over North Bay of Bengal: Squally winds 30-40 knots",
                "detail": "Port issues Local Cautionary Signal No. 3. Loading operations halted at mechanised coal berths 1 & 2.",
                "keywords_matched": ["cyclone", "depression", "halt"],
                "active_until": "2026-09-02",
                "reported_at": "2026-08-29"
            },
            {
                "id": "DISR-2026-083",
                "source": "Port Trust Operational Notice",
                "port": "Visakhapatnam",
                "severity": "low",
                "headline": "Routine conveyor belt maintenance scheduled for Berth OB-1",
                "detail": "Minor 6-hour planned maintenance window on Friday night. Alternative conveyor systems operational.",
                "keywords_matched": ["berth maintenance"],
                "active_until": "2026-08-31",
                "reported_at": "2026-08-29"
            }
        ]

    def has_disruption_for_port(self, port_name: str) -> Dict[str, Any]:
        disruptions = [d for d in self.extract_recent_disruptions() if d["port"].lower() == port_name.lower()]
        if not disruptions:
            return {"active": False, "disruptions": []}
        return {"active": True, "highest_severity": max([d["severity"] for d in disruptions]), "disruptions": disruptions}
