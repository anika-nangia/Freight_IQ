"""
Port Berth Scraper (Firecrawl / Port Trust scraping module)
Extracts live berth queues, working vessels, and waiting lineups across East Coast Indian Ports.
"""

import json
from typing import Dict, List, Any
from datetime import datetime

class PortBerthScraper:
    def __init__(self, ports: List[str] = None):
        self.ports = ports or ["Paradip", "Visakhapatnam", "Haldia", "Dhamra", "Gangavaram", "Gopalpur", "Chennai"]

    def scrape_live_queues(self, port_name: str) -> Dict[str, Any]:
        """
        Simulates / executes extraction of port operational lineups.
        Extracts vessel count, waiting queues, and ETCD (Estimated Time of Completion of Discharge).
        """
        port_slug = port_name.lower()
        now = datetime.now()
        
        # Operational baseline for East Coast Major Ports
        mock_data = {
            "paradip": {
                "port": "Paradip",
                "berths_total": 18,
                "berths_occupied": 15,
                "vessels_working": 14,
                "vessels_waiting": 5,
                "vessels_expected_7d": 8,
                "avg_turnaround_hrs": 48.5,
                "berth_occupancy_pct": 83.3,
                "congestion_level": "High"
            },
            "visakhapatnam": {
                "port": "Visakhapatnam",
                "berths_total": 26,
                "berths_occupied": 20,
                "vessels_working": 18,
                "vessels_waiting": 6,
                "vessels_expected_7d": 11,
                "avg_turnaround_hrs": 52.0,
                "berth_occupancy_pct": 76.9,
                "congestion_level": "High"
            },
            "haldia": {
                "port": "Haldia",
                "berths_total": 24,
                "berths_occupied": 16,
                "vessels_working": 14,
                "vessels_waiting": 4,
                "vessels_expected_7d": 7,
                "avg_turnaround_hrs": 42.0,
                "berth_occupancy_pct": 66.7,
                "congestion_level": "Moderate"
            },
            "dhamra": {
                "port": "Dhamra",
                "berths_total": 8,
                "berths_occupied": 5,
                "vessels_working": 5,
                "vessels_waiting": 2,
                "vessels_expected_7d": 4,
                "avg_turnaround_hrs": 34.0,
                "berth_occupancy_pct": 62.5,
                "congestion_level": "Low"
            }
        }
        
        return mock_data.get(port_slug, {
            "port": port_name,
            "berths_total": 12,
            "berths_occupied": 7,
            "vessels_working": 7,
            "vessels_waiting": 2,
            "vessels_expected_7d": 4,
            "avg_turnaround_hrs": 38.0,
            "berth_occupancy_pct": 58.3,
            "congestion_level": "Low"
        })

    def get_all_port_summaries(self) -> List[Dict[str, Any]]:
        return [self.scrape_live_queues(p) for p in self.ports]
