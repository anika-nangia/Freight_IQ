"""
Pillar (a): Optimal Market Entry Timing Service
Evaluates forecasted rate trajectory momentum to recommend:
'Lock Contract Now (Within 3 Days)' vs 'Hold on Spot Market; Secure Mid-Term in 2 Weeks'.
"""

from typing import Dict, Any, List

class MarketTimingService:
    def evaluate_timing(
        self,
        current_spot: float,
        projections: List[Dict[str, Any]],
        volatility_pct: float = 4.5
    ) -> Dict[str, Any]:
        """
        Calculates forecast slope and generates actionable timing advice.
        """
        rate_7d = projections[0]["projected_rate"] if len(projections) > 0 else current_spot
        rate_14d = projections[1]["projected_rate"] if len(projections) > 1 else current_spot
        rate_30d = projections[2]["projected_rate"] if len(projections) > 2 else current_spot
        
        diff_14d = rate_14d - current_spot
        slope_pct = (diff_14d / current_spot) * 100
        
        if slope_pct > 3.0:
            action = "LOCK CONTRACT NOW"
            horizon_window = "Within 48 to 72 Hours"
            hedge_savings = round(diff_14d, 2)
            headline = f"Lock Contract Now (Within 3 Days) to hedge against an estimated ${hedge_savings}/ton spike."
            rationale = [
                f"14-day forward rate projection indicates a +{round(slope_pct, 1)}% momentum upward.",
                f"Historical volatility is currently {volatility_pct}%; upward asymmetric risk is elevated.",
                f"Securing vessel charter commitments today protects cargo margins from port queue premiums."
            ]
            badge_color = "emerald"
        elif slope_pct < -3.0:
            action = "HOLD ON SPOT MARKET"
            horizon_window = "Secure Mid-Term Charter in 2 Weeks"
            savings = round(abs(diff_14d), 2)
            headline = f"Hold on spot market; secure mid-term charter in 2 weeks to save ~${savings}/ton."
            rationale = [
                f"Freight market is easing by {round(abs(slope_pct), 1)}% due to incoming ballast fleet availability.",
                "Short-term spot bookings recommended for immediate requirements.",
                "Delay multi-voyage contract fixation until bottom of the 14-day cycle is reached."
            ]
            badge_color = "blue"
        else:
            action = "MONITOR WITH GUARDRAILS"
            horizon_window = "Watch 7-Day Window"
            headline = "Market in balanced equilibrium. Fix spot contracts with standard laycan clauses."
            rationale = [
                "Rate trajectory is displaying sideways range-bound movement within ±2.5%.",
                "Keep contract durations flexible between 15 to 30 days."
            ]
            badge_color = "amber"
            
        return {
            "action": action,
            "horizon_window": horizon_window,
            "headline": headline,
            "slope_momentum_pct": round(slope_pct, 2),
            "estimated_price_delta_14d": round(diff_14d, 2),
            "rationale": rationale,
            "badge_color": badge_color
        }
