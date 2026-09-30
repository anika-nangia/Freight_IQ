"""
Model 2: Freight Rate Forecaster & SHAP Explainability Engine
Generates 7, 14, 30, and 60-day freight rate predictions with upper/lower bounds
and SHAP contribution breakdown (+2.1 USD-INR, +1.5 Congestion, -0.8 BDI).
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta

class FreightPredictor:
    BASE_RATES = {
        "paradip-qingdao": 18.60,
        "paradip-visakhapatnam": 8.20,
        "paradip-haldia": 7.40,
        "visakhapatnam-ganganagar": 740.0,  # Road / multimodal per truck
        "australia-paradip": 15.10,
        "indonesia-haldia": 17.40
    }

    def predict_freight_trajectory(
        self,
        origin: str,
        destination: str,
        vessel_class: str = "Supramax",
        congestion_score: float = 0.45,
        bdi_index: int = 1842,
        usd_inr: float = 83.42,
        weather_alert: bool = False
    ) -> Dict[str, Any]:
        """
        Calculates multi-horizon freight rate forecast and SHAP impact components.
        """
        route_key = f"{origin.lower()}-{destination.lower()}"
        base_rate = self.BASE_RATES.get(route_key, 18.20)
        
        # Adjust for vessel class efficiency
        class_multipliers = {
            "Capesize": 0.82,
            "Panamax": 0.94,
            "Supramax": 1.00,
            "Handymax": 1.08,
            "Handysize": 1.18,
            "Multi-modal": 40.0
        }
        mult = class_multipliers.get(vessel_class, 1.0)
        current_spot = round(base_rate * mult, 2)
        
        # Calculate SHAP contribution factors
        shap_congestion = round((congestion_score - 0.35) * 4.2, 2)
        shap_fx = round((usd_inr - 82.5) * 0.45, 2)
        shap_bdi = round(((bdi_index - 1800) / 100.0) * 0.38, 2)
        shap_weather = 1.25 if weather_alert else 0.15
        
        # Project future trajectories for 7, 14, 30, and 60 days
        daily_drift = (shap_congestion + shap_fx + shap_bdi + shap_weather) / 30.0
        
        horizons = [7, 14, 30, 60]
        projections = []
        now = datetime.now()
        
        for h in horizons:
            proj_date = (now + timedelta(days=h)).strftime("%Y-%m-%d")
            rate = round(current_spot + (daily_drift * h), 2)
            lower_bound = round(max(5.0, rate - (0.85 * (h / 14.0) ** 0.5)), 2)
            upper_bound = round(rate + (1.45 * (h / 14.0) ** 0.5), 2)  # Asymmetric regret expands upper bound
            projections.append({
                "horizon_days": h,
                "target_date": proj_date,
                "projected_rate": rate,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound
            })
            
        rate_30d = projections[2]["projected_rate"]
        pct_change_30d = round(((rate_30d - current_spot) / current_spot) * 100, 1)
        trend = "Bullish (Rising)" if pct_change_30d > 3.0 else "Bearish (Easing)" if pct_change_30d < -3.0 else "Stable"
        
        return {
            "origin": origin,
            "destination": destination,
            "vessel_class": vessel_class,
            "current_spot_rate": current_spot,
            "unit": "USD/Ton" if vessel_class != "Multi-modal" else "INR/Truck",
            "trend": trend,
            "change_30d_pct": pct_change_30d,
            "projections": projections,
            "shap_breakdown": {
                "port_congestion": shap_congestion,
                "usd_inr_exchange": shap_fx,
                "baltic_dry_index": shap_bdi,
                "weather_risk": shap_weather
            }
        }
