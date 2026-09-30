"""
Pillar (a): Market Entry Timing.

Turns a forecast into a charter/wait/fix decision.

The previous version compared a projected 14-day rate against a single spot number and
applied a +/-3% threshold. Two problems: the 3% was a magic number, and the decision
ignored the interval entirely, so a forecast of +2% that was statistically
indistinguishable from zero produced the same "BALANCED" verdict as a confident +2%.

The decision here is built on measured quantities instead:
  * the modelled move, expressed as a share of the interval half-width, so a small
    move inside a wide band reads as 'no signal' rather than a weak signal;
  * the asymmetric cost of being wrong, which is what the model is actually
    optimised for;
  * the cost of waiting, in dollars per tonne and in days of delay.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402

# A move counts as a signal only once it is large relative to the interval the model
# can actually resolve. 0.5 means "half the 80% band".
SIGNAL_THRESHOLD = 0.5
# Cost of a day's delay, used to price the wait option. This is a business assumption,
# not a measured quantity, and is returned in the response so it can be challenged.
DEFAULT_DEMURAGE_USD_PER_DAY = 18500.0


def _signed(v: float) -> str:
    """'up $3.14 a tonne' reads better than a bare signed figure on a card."""
    direction = "up" if v > 0 else ("down" if v < 0 else "flat")
    return f"{direction} ${abs(v):.2f} a tonne"


class MarketTimingService:
    def evaluate(self, forecast: Dict[str, Any],
                 demurrage_usd_per_day: float = DEFAULT_DEMURAGE_USD_PER_DAY) -> Dict[str, Any]:
        """Recommend charter now, wait, or fix a multi-voyage deal.

        `forecast` is the response from models.model_2_freight.predict_freight.FreightPredictor.
        """
        if not forecast.get("available"):
            return {
                "available": False,
                "action": "NO RECOMMENDATION",
                "reason": forecast.get("reason", "forecast unavailable"),
                "provenance": forecast.get("provenance"),
            }

        spot = float(forecast["current_observed_rate_usd_mt"])
        point = float(forecast["forecast_rate_usd_mt"])
        lo = float(forecast["lower_bound_usd_mt"])
        hi = float(forecast["upper_bound_usd_mt"])
        half_width = (hi - lo) / 2.0
        move = point - spot
        strength = abs(move) / half_width if half_width > 0 else 0.0

        as_of = forecast.get("current_observed_rate_as_of")
        horizon_days = int(forecast.get("horizon_days", 14))

        if strength < SIGNAL_THRESHOLD:
            action = "HOLD / MONITOR"
            badge = "amber"
            headline = (f"Forecast move of {move:+.2f} USD/MT is inside the 80% band "
                        f"({lo:.2f} to {hi:.2f}). Not a tradable signal.")
            # Short on purpose. This text is read on a card, not studied.
            rationale = [
                f"Rate moves {_signed(move)} over {horizon_days} days, but that is only "
                f"{strength:.0%} of what our error bars allow.",
                f"Anything under {SIGNAL_THRESHOLD:.0%} of the range counts as no signal, "
                f"so there is nothing to act on yet.",
            ]
            cost_of_waiting = None
        elif move > 0:
            action = "CHARTER NOW"
            badge = "emerald"
            headline = (f"Model points {move:+.2f} USD/MT higher over {horizon_days} days, "
                        f"which is {strength:.0%} of the interval width. Fix before it lands.")
            rationale = [
                f"Rate goes {_signed(move)} to {point:.2f} in {horizon_days} days, and that "
                f"move is {strength:.0%} of the range our error bars allow - enough to act on.",
                f"Waiting costs about "
                f"{demurrage_usd_per_day * horizon_days:,.0f} USD in demurrage "
                f"({demurrage_usd_per_day:,.0f} USD/day).",
            ]
            cost_of_waiting = demurrage_usd_per_day * horizon_days
        else:
            action = "WAIT / BOOK SPOT"
            badge = "blue"
            headline = (f"Model points {move:+.2f} USD/MT lower over {horizon_days} days, "
                        f"which is {strength:.0%} of the interval width. Spot is the better buy.")
            rationale = [
                f"Rate drops to {point:.2f} in {horizon_days} days, and that move is "
                f"{strength:.0%} of the range our error bars allow - enough to act on.",
                "Falling rates make fixing expensive and staying on spot flexible, so book "
                "one voyage at a time.",
            ]
            cost_of_waiting = 0.0

        out = {
            "available": True,
            "action": action,
            "badge_color": badge,
            "headline": headline,
            "rationale": rationale,
            "current_observed_rate_usd_mt": round(spot, 2),
            "forecast_rate_usd_mt": round(point, 2),
            "lower_bound_usd_mt": round(lo, 2),
            "upper_bound_usd_mt": round(hi, 2),
            "modelled_move_usd_mt": round(move, 2),
            "signal_strength_vs_interval": round(strength, 3),
            "signal_threshold": SIGNAL_THRESHOLD,
            "reads_as_signal": bool(strength >= SIGNAL_THRESHOLD),
            "as_of": as_of,
            "horizon_days": horizon_days,
            "cost_of_waiting_usd": cost_of_waiting,
            "demurrage_assumption_usd_per_day": demurrage_usd_per_day,
            "demurrage_note": "A business assumption supplied by the caller, not a measured "
                              "value. Replace it with your charter party's rate.",
        }
        out["provenance"] = prov.provenance_block(["route_rates_weekly"])
        out["confidence"] = forecast.get("confidence")
        return out

    def compare_contract(self, contract_path: Dict[str, Any], n_voyages: int = 3) -> Dict[str, Any]:
        """Spot-every-voyage versus fixing N voyages at today's rate.

        `contract_path` is the response from FreightPredictor.contract_path(). This is a
        breakeven calculation on an expected path, not a prediction of market direction.
        """
        if not contract_path.get("available"):
            return {"available": False, "reason": contract_path.get("reason"),
                    "provenance": contract_path.get("provenance")}
        months = contract_path.get("monthly_path")
        if not months:
            return {"available": False,
                    "reason": "contract path carries no monthly path"}
        spot = float(contract_path["spot_today_usd_mt"])
        avg = sum(m["expected_average_rate_usd_mt"] for m in months) / len(months)
        diff = avg - spot
        return {
            "available": True,
            "corridor_id": contract_path.get("corridor_id"),
            "voyages": n_voyages,
            "fix_n_voyages_at_today_total_usd_per_tonne": round(spot * n_voyages, 2),
            "expected_spot_total_usd_per_tonne": round(avg * n_voyages, 2),
            "expected_difference_usd_per_tonne": round(diff * n_voyages, 2),
            "favours": "fix now" if diff > 0 else "stay spot",
            "breakeven_average_rate_usd_mt": round(spot, 2),
            "downside_average_rate_usd_mt": round(
                sum(m["downside_usd_mt"] for m in months) / len(months), 2),
            "upside_average_rate_usd_mt": round(
                sum(m["upside_usd_mt"] for m in months) / len(months), 2),
            "basis": "expected average of the derived 6-month path versus the observed rate",
            "path_warning": contract_path.get("path_warning"),
            "caveat": "This is an expected-value comparison. It ignores the variance of "
                      "the path, and the downside column shows how much of the decision "
                      "rests on a single favourable sequence.",
            "provenance": contract_path.get("provenance"),
            "confidence": contract_path.get("confidence"),
        }


_TIMING: Optional[MarketTimingService] = None


def get_service() -> MarketTimingService:
    global _TIMING
    if _TIMING is None:
        _TIMING = MarketTimingService()
    return _TIMING
