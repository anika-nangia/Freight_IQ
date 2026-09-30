"""
Pillar (d): Risk Mitigation & Early Warning System Service
Combines 3 real-time signals:
1. Port Congestion Score (ETCD - Arrival > 48 hrs)
2. Marine Weather / Cyclone Alert (Wind > 35 kts or wave > 3m)
3. Maritime News Disruption Flags ('strike', 'dredging', 'draft restriction')
Generates Risk Tier Badges (Low / Medium / High) and contract buffer advice.
"""

from typing import Dict, Any, List

class RiskMitigationService:
    def assess_risk(
        self,
        port_name: str,
        congestion_score: float = 0.55,
        queue_waiting_days: float = 3.5,
        wind_speed_knots: float = 24.0,
        wave_height_m: float = 2.2,
        active_disruptions: List[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes multi-signal risk telemetry into composite risk rating and mitigation strategy.
        """
        active_disruptions = active_disruptions or []
        
        # 1. Congestion risk
        congestion_flag = queue_waiting_days >= 2.0 or congestion_score >= 0.60
        
        # 2. Weather risk
        weather_flag = wind_speed_knots >= 30.0 or wave_height_m >= 2.8
        
        # 3. Disruption risk
        news_flag = len(active_disruptions) > 0
        
        # Composite score
        risk_points = 0
        if queue_waiting_days >= 4.0: risk_points += 3
        elif queue_waiting_days >= 2.0: risk_points += 2
        elif queue_waiting_days >= 1.0: risk_points += 1
        
        if wind_speed_knots >= 35.0 or wave_height_m >= 3.0: risk_points += 3
        elif wind_speed_knots >= 25.0: risk_points += 1
        
        if news_flag: risk_points += 2
        
        if risk_points >= 5:
            risk_tier = "High"
            badge_color = "red"
            suggested_action = f"High Congestion / Weather at {port_name}: Divert to adjacent deep port or add 3-day buffer to contract duration."
        elif risk_points >= 3:
            risk_tier = "Medium"
            badge_color = "amber"
            suggested_action = f"{port_name} berth congestion queue currently at {queue_waiting_days:.1f} days. Factor demurrage clauses into negotiations."
        else:
            risk_tier = "Low"
            badge_color = "emerald"
            suggested_action = f"{port_name} operations running normal. Standard 24h laycan terms apply."
            
        warnings = []
        if queue_waiting_days >= 3.0:
            warnings.append(f"Waiting queue currently at {queue_waiting_days:.1f} days (ETCD - Arrival > 48 hrs).")
        if weather_flag:
            warnings.append(f"Squally weather: Wind speed {wind_speed_knots} kts, wave height {wave_height_m}m in Bay of Bengal.")
        if news_flag:
            warnings.append(f"Active disruption alerts: {', '.join(active_disruptions)}.")
            
        return {
            "port": port_name,
            "risk_tier": risk_tier,
            "badge_color": badge_color,
            "risk_score_points": risk_points,
            "queue_waiting_days": queue_waiting_days,
            "wind_speed_knots": wind_speed_knots,
            "wave_height_m": wave_height_m,
            "warnings": warnings,
            "headline_warning": suggested_action,
            "mitigation_clauses": [
                "Demurrage rate capped at standard BIMCO GENCON 1994 provisions ($18,500/day).",
                "Force majeure clause covering monsoon loading halts and swell delays.",
                f"Recommended contract buffer: {3 if risk_tier == 'High' else 1} additional laydays."
            ]
        }
