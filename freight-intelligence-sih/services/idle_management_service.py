"""
Pillar (c): Idle Scenario Management & Deadheading Reduction Service
Analyzes future low-demand periods for imports/exports.
Suggests alternative loading ports and backhaul opportunities to avoid sitting idle or deadheading empty containers/vessels.
"""

from typing import Dict, Any, List

class IdleManagementService:
    # Port backhaul and repositioning opportunities network along East Coast India
    REPOSITIONING_NETWORK = {
        "tuticorin": [
            {
                "alt_port": "Kakinada",
                "distance_nm": 490,
                "transit_days": 1.6,
                "opportunity": "Agricultural Grain & Rice Bulk Export",
                "cargo_availability": "High (35,000 MT/week)",
                "bunker_fuel_cost_usd": 14200,
                "net_profit_gain_usd": 48500,
                "action": "Ballast to Kakinada for agricultural export rather than returning empty to Paradip."
            },
            {
                "alt_port": "Chennai",
                "distance_nm": 320,
                "transit_days": 1.0,
                "opportunity": "Finished Steel Coils & Project Cargo",
                "cargo_availability": "Moderate (18,000 MT/week)",
                "bunker_fuel_cost_usd": 9500,
                "net_profit_gain_usd": 32000,
                "action": "Position vessel to Chennai for coastal finished steel shipment."
            }
        ],
        "haldia": [
            {
                "alt_port": "Dhamra",
                "distance_nm": 95,
                "transit_days": 0.4,
                "opportunity": "Thermal Coal Coastal Movement to West Coast",
                "cargo_availability": "Very High (65,000 MT/week)",
                "bunker_fuel_cost_usd": 3800,
                "net_profit_gain_usd": 41200,
                "action": "Immediate short hop to Dhamra to lift coastal thermal coal; avoids riverine draft idling."
            }
        ],
        "visakhapatnam": [
            {
                "alt_port": "Gangavaram",
                "distance_nm": 15,
                "transit_days": 0.1,
                "opportunity": "Bauxite & Pellets coastal parcel",
                "cargo_availability": "High (45,000 MT/week)",
                "bunker_fuel_cost_usd": 1200,
                "net_profit_gain_usd": 28000,
                "action": "Cross-harbor repositioning to Gangavaram deep berth for quick bulk turnaround."
            },
            {
                "alt_port": "Paradip",
                "distance_nm": 260,
                "transit_days": 0.9,
                "opportunity": "Iron Ore Fines export to China",
                "cargo_availability": "High (80,000 MT/week)",
                "bunker_fuel_cost_usd": 8500,
                "net_profit_gain_usd": 54000,
                "action": "Ballast north to Paradip mechanised iron ore terminal for immediate loading."
            }
        ],
        "paradip": [
            {
                "alt_port": "Dhamra",
                "distance_nm": 70,
                "transit_days": 0.3,
                "opportunity": "Limestone import discharge & coastal coal",
                "cargo_availability": "High",
                "bunker_fuel_cost_usd": 2900,
                "net_profit_gain_usd": 31000,
                "action": "Shift to Dhamra to bypass 4-day Paradip coal waiting queue."
            }
        ]
    }

    def analyze_idle_scenarios(
        self,
        discharge_port: str,
        vessel_class: str = "Supramax",
        daily_charter_rate: float = 18400.0,
        inbound_demand_level: str = "Low"
    ) -> Dict[str, Any]:
        """
        Calculates idle cost losses across 7, 14, and 21 day delay scenarios
        and generates proactive repositioning / backhaul recommendations.
        """
        scenarios = []
        for days in [7, 14, 21]:
            idle_loss = days * daily_charter_rate
            fuel_hotel_load = days * 1800.0  # Auxiliary generator bunker burn in port
            total_idle_drain = idle_loss + fuel_hotel_load
            scenarios.append({
                "idle_days": days,
                "charter_cost_loss_usd": idle_loss,
                "hotel_fuel_burn_usd": fuel_hotel_load,
                "total_idle_loss_usd": total_idle_drain,
                "loss_inr_lakhs": round((total_idle_drain * 83.42) / 100000, 2)
            })
            
        port_key = discharge_port.lower()
        options = self.REPOSITIONING_NETWORK.get(port_key, [
            {
                "alt_port": "Paradip",
                "distance_nm": 220,
                "transit_days": 0.8,
                "opportunity": "Coastal Thermal Coal / Ore Parcel",
                "cargo_availability": "Moderate",
                "bunker_fuel_cost_usd": 7200,
                "net_profit_gain_usd": 35000,
                "action": "Reposition vessel to Paradip to pick up coastal cargo rather than idling."
            }
        ])
        
        top_alt = options[0]
        repositioning_alert = (
            f"Low return demand at {discharge_port}; pre-book backhaul route from {top_alt['alt_port']} "
            f"({top_alt['opportunity']}) to avoid empty deadheading and save ~${top_alt['net_profit_gain_usd']:,}."
        )
        
        return {
            "discharge_port": discharge_port,
            "vessel_class": vessel_class,
            "daily_charter_rate_usd": daily_charter_rate,
            "inbound_demand_status": inbound_demand_level,
            "deadhead_risk_tier": "High" if inbound_demand_level == "Low" else "Moderate",
            "idle_scenarios": scenarios,
            "repositioning_alert": repositioning_alert,
            "suggested_alternative_ports": options,
            "workers_advisory": (
                f"Crew and terminal operations can be reallocated to {top_alt['alt_port']} "
                f"inbound parcels within {top_alt['transit_days']} days transit instead of waiting idle."
            )
        }
