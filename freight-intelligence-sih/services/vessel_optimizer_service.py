"""
Pillar (b): Vessel Type Optimization Service (With Port Physical Constraints)
Selects the optimal vessel class (Handysize, Supramax, Panamax, Capesize)
considering port draft, LOA, beam, and crane limits.
"""

from typing import Dict, Any, List

class VesselOptimizerService:
    # Port constraint lookup table (draft in m, max LOA in m)
    PORT_LIMITS = {
        "haldia": {"max_draft": 8.5, "max_loa": 210.0, "max_vessel_class": "Handysize", "name": "Haldia"},
        "paradip": {"max_draft": 14.5, "max_loa": 295.0, "max_vessel_class": "Capesize", "name": "Paradip"},
        "visakhapatnam": {"max_draft": 18.0, "max_loa": 320.0, "max_vessel_class": "Capesize", "name": "Visakhapatnam"},
        "dhamra": {"max_draft": 17.0, "max_loa": 300.0, "max_vessel_class": "Capesize", "name": "Dhamra"},
        "gangavaram": {"max_draft": 21.0, "max_loa": 350.0, "max_vessel_class": "Capesize", "name": "Gangavaram"},
        "gopalpur": {"max_draft": 9.0, "max_loa": 185.0, "max_vessel_class": "Handymax", "name": "Gopalpur"},
        "sagar": {"max_draft": 9.5, "max_loa": 230.0, "max_vessel_class": "Panamax", "name": "Sagar & Sandheads"},
        "tuticorin": {"max_draft": 14.2, "max_loa": 250.0, "max_vessel_class": "Panamax", "name": "VOC Tuticorin"},
        "kakinada": {"max_draft": 14.0, "max_loa": 240.0, "max_vessel_class": "Panamax", "name": "Kakinada"}
    }

    VESSEL_CLASSES = [
        {"class": "Handysize", "dwt": 35000, "draft": 10.0, "loa": 150.0, "daily_rate": 13500, "handling_tpd": 8000},
        {"class": "Handymax", "dwt": 45000, "draft": 11.2, "loa": 175.0, "daily_rate": 15200, "handling_tpd": 9500},
        {"class": "Supramax", "dwt": 58000, "draft": 12.5, "loa": 190.0, "daily_rate": 18400, "handling_tpd": 12000},
        {"class": "Panamax", "dwt": 75000, "draft": 14.5, "loa": 225.0, "daily_rate": 22800, "handling_tpd": 18000},
        {"class": "Capesize", "dwt": 180000, "draft": 18.0, "loa": 290.0, "daily_rate": 34500, "handling_tpd": 25000}
    ]

    def optimize_vessel_selection(
        self,
        origin_port: str,
        destination_port: str,
        cargo_volume_mt: float,
        voyage_distance_nm: float = 3800.0
    ) -> Dict[str, Any]:
        """
        Filters out vessel classes violating port draft or LOA limits,
        calculates total freight cost per ton, and selects the minimum cost vessel.
        """
        dest_limits = self.PORT_LIMITS.get(destination_port.lower(), {"max_draft": 14.5, "max_loa": 295.0, "name": destination_port})
        orig_limits = self.PORT_LIMITS.get(origin_port.lower(), {"max_draft": 18.0, "max_loa": 320.0, "name": origin_port})
        
        effective_max_draft = min(dest_limits["max_draft"], orig_limits["max_draft"])
        effective_max_loa = min(dest_limits["max_loa"], orig_limits["max_loa"])
        
        voyage_speed_knots = 13.0
        sea_days = (voyage_distance_nm / (voyage_speed_knots * 24.0))
        
        evaluated_vessels = []
        for v in self.VESSEL_CLASSES:
            # Check physical feasibility
            draft_ok = v["draft"] <= effective_max_draft
            loa_ok = v["loa"] <= effective_max_loa
            
            # Port and handling days
            port_days = cargo_volume_mt / v["handling_tpd"]
            total_voyage_days = round(sea_days + port_days, 1)
            
            # Total cost formula: (Daily Rate * Voyage Days + Port Dues) / Cargo Volume
            port_dues_est = v["dwt"] * 0.65 * 0.75 + 5000  # Pilotage + Berth hire
            charter_cost = v["daily_rate"] * total_voyage_days
            total_trip_cost = charter_cost + port_dues_est
            
            cost_per_ton = round(total_trip_cost / (min(cargo_volume_mt, v["dwt"])), 2)
            
            status = "Eligible"
            reason = "Fully compliant with port draft and LOA"
            if not draft_ok:
                status = "Rejected"
                reason = f"Draft {v['draft']}m exceeds port limit of {effective_max_draft}m"
            elif not loa_ok:
                status = "Rejected"
                reason = f"LOA {v['loa']}m exceeds berth limit of {effective_max_loa}m"
                
            evaluated_vessels.append({
                "vessel_class": v["class"],
                "dwt": v["dwt"],
                "draft_m": v["draft"],
                "loa_m": v["loa"],
                "daily_rate_usd": v["daily_rate"],
                "total_voyage_days": total_voyage_days,
                "total_trip_cost_usd": round(total_trip_cost, 2),
                "cost_per_ton_usd": cost_per_ton,
                "is_eligible": status == "Eligible",
                "status": status,
                "constraint_reason": reason
            })
            
        eligible = [v for v in evaluated_vessels if v["is_eligible"]]
        if not eligible:
            # Fallback to Handysize
            recommended = evaluated_vessels[0]
        else:
            # Pick lowest cost per ton that accommodates the cargo volume
            recommended = min(eligible, key=lambda x: x["cost_per_ton_usd"])
            
        return {
            "origin_port": orig_limits["name"],
            "destination_port": dest_limits["name"],
            "cargo_volume_mt": cargo_volume_mt,
            "effective_max_draft_m": effective_max_draft,
            "effective_max_loa_m": effective_max_loa,
            "recommended_vessel": recommended["vessel_class"],
            "optimal_cost_per_ton_usd": recommended["cost_per_ton_usd"],
            "estimated_trip_cost_usd": recommended["total_trip_cost_usd"],
            "headline": f"{recommended['vessel_class']} recommended for {cargo_volume_mt:,.0f} MT at {dest_limits['name']} (Optimal cost: ${recommended['cost_per_ton_usd']}/ton).",
            "evaluations": evaluated_vessels
        }
