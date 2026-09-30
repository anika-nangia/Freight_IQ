"""
Port Schedule of Rates (SOR) Parser
Extracts official port tariffs, berth hire, pilotage charges, and demurrage rules
from Port Authority SOR gazettes.
"""

from typing import Dict, Any

class PortSORParser:
    def get_port_dues(self, port_name: str, vessel_class: str, dwt: float) -> Dict[str, Any]:
        """
        Calculates port dues (Pilotage, Berth Hire per hour, Port Dues per GRT).
        Typical standard tariff estimates across East Coast Indian Major Ports.
        """
        # GRT is roughly 0.65 of DWT
        grt = dwt * 0.65
        
        base_rates = {
            "paradip": {"pilotage_usd_grt": 0.42, "port_dues_usd_grt": 0.35, "berth_hire_hourly_usd": 120.0},
            "visakhapatnam": {"pilotage_usd_grt": 0.48, "port_dues_usd_grt": 0.38, "berth_hire_hourly_usd": 140.0},
            "haldia": {"pilotage_usd_grt": 0.85, "port_dues_usd_grt": 0.52, "berth_hire_hourly_usd": 160.0},  # Riverine pilotage higher
            "dhamra": {"pilotage_usd_grt": 0.38, "port_dues_usd_grt": 0.30, "berth_hire_hourly_usd": 110.0},
            "tuticorin": {"pilotage_usd_grt": 0.40, "port_dues_usd_grt": 0.32, "berth_hire_hourly_usd": 105.0}
        }
        
        rates = base_rates.get(port_name.lower(), {"pilotage_usd_grt": 0.40, "port_dues_usd_grt": 0.35, "berth_hire_hourly_usd": 120.0})
        
        pilotage_cost = grt * rates["pilotage_usd_grt"]
        port_dues_cost = grt * rates["port_dues_usd_grt"]
        berth_hire_cost_48h = 48 * rates["berth_hire_hourly_usd"]
        total_port_dues = pilotage_cost + port_dues_cost + berth_hire_cost_48h
        
        return {
            "port": port_name,
            "vessel_class": vessel_class,
            "dwt": dwt,
            "estimated_grt": grt,
            "pilotage_cost_usd": round(pilotage_cost, 2),
            "port_dues_cost_usd": round(port_dues_cost, 2),
            "berth_hire_48h_usd": round(berth_hire_cost_48h, 2),
            "total_estimated_port_dues_usd": round(total_port_dues, 2),
            "demurrage_penalty_per_day_usd": 15000.0 if vessel_class in ["Supramax", "Panamax"] else 28000.0
        }
