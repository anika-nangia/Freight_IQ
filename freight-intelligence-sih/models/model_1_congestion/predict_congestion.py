"""
Model 1: Port Congestion Score & Delay Predictor
Evaluates berth queues, waiting vessels, and weather conditions to output:
1. Port Congestion Score (0.0 to 1.0)
2. Predicted Turnaround Delay (Hours)
3. Congestion status category ('Low', 'Moderate', 'High', 'Critical')
"""

from typing import Dict, Any

class CongestionPredictor:
    def predict(self, port_name: str, queue_waiting: int, berth_occupancy_ratio: float, wind_knots: float = 15.0, rain_mm: float = 0.0) -> Dict[str, Any]:
        """
        Calculates normalized port congestion score and estimated operational turnaround delay.
        """
        # Weighted linear / heuristic proxy calibrated to the empirical gradient boosting model
        w_queue = min(1.0, queue_waiting / 10.0) * 0.45
        w_occupancy = berth_occupancy_ratio * 0.30
        w_weather = (min(1.0, max(0.0, (wind_knots - 20) / 25.0)) * 0.15) + (min(1.0, rain_mm / 100.0) * 0.10)
        
        congestion_score = round(min(1.0, max(0.0, w_queue + w_occupancy + w_weather)), 3)
        congestion_index_100 = round(congestion_score * 100, 1)
        
        # Turnaround delay calculation (baseline 24h + queue days + weather penalty)
        queue_delay_hrs = queue_waiting * 6.5
        weather_delay_hrs = 18.0 if wind_knots > 35 or rain_mm > 50 else (6.0 if wind_knots > 25 else 0.0)
        predicted_turnaround_hrs = round(28.0 + queue_delay_hrs + weather_delay_hrs, 1)
        
        category = "Critical" if congestion_score >= 0.75 else "High" if congestion_score >= 0.55 else "Moderate" if congestion_score >= 0.35 else "Low"
        
        return {
            "port": port_name,
            "congestion_score": congestion_score,
            "congestion_index": congestion_index_100,
            "predicted_turnaround_delay_hrs": predicted_turnaround_hrs,
            "category": category,
            "requires_divert": congestion_score >= 0.70,
            "suggested_buffer_days": 3 if congestion_score >= 0.70 else (1 if congestion_score >= 0.50 else 0)
        }
