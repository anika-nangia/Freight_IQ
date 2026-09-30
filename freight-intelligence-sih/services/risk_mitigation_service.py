"""
Pillar (d): Risk Monitor - a combined ACTION from both models, not a severity badge.

WHAT CHANGED AND WHY
    The previous version returned a Low/Medium/High tier computed from congestion and
    weather alone. Model 2 was not consulted at all, so the panel could say "risk: low"
    while the forecast was screaming that rates were about to move.

    A charterer's real question is not "how busy is the port" but "should I commit a
    vessel, and when". That needs both models:

        Model 2  -> is the market about to move against me?
        Model 1  -> if I commit a vessel, where does it sit, and for how long?
        Weather  -> can the berth actually work tomorrow?

    So this now emits an ACTION with its reasoning, not a severity:

        CHARTER NOW   rates rising AND port congested - the worst combination, both
                      the price and the berth are turning against you
        LOCK IN       rates rising, port clear - take the rate before the market moves
        HOLD          no urgency either way
        WAIT          rates falling - stay spot and let them come to you
        AVOID ADDING  an explicit flag when committing more tonnage is the wrong move

    Every reason cites which model produced it and how confident that model is. If a
    model is missing the output degrades to what can be said, and says what is missing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402

# Operational thresholds. POLICY, not fitted parameters, with the basis named.
THRESHOLDS = {
    "cyclonic_storm_kt": 32.0,     # IMD: 31-47 kt cyclonic storm
    "severe_cyclonic_kt": 47.0,    # IMD: 48-63 kt severe cyclonic storm
    "gale_kt": 25.0,
    "queue_days_high": 2.0,
    "queue_days_critical": 4.0,
    "congestion_high": 0.55,
    "congestion_critical": 0.75,
}
# A forecast counts as "moving" when the modelled change is at least this fraction of
# the interval half-width. Below it the model is saying "I do not know", and treating
# that as a signal is how a forecast engine talks a charterer into a bad trade.
SIGNAL_FRACTION = 0.35


def _first(d: Optional[Dict[str, Any]], *keys: str) -> Optional[Any]:
    if not d:
        return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _isnan(v: Any) -> bool:
    try:
        return v != v
    except TypeError:
        return True


def _num(v: Any) -> Optional[float]:
    if v is None or _isnan(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class RiskMonitorService:
    """Fuse Model 1, Model 2 and weather into one chartering action."""

    def assess(self, port: str,
               forecast: Optional[Dict[str, Any]] = None,
               congestion: Optional[Dict[str, Any]] = None,
               weather: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        inputs: Dict[str, Any] = {}
        drivers: List[Dict[str, Any]] = []
        missing: List[str] = []
        reasons: List[str] = []

        # ------------------------------------------------------- Model 2 signal
        direction, strength, conf = _read_forecast(forecast)
        # Recorded even when unknown, so a panel can say "no signal" rather than
        # silently omitting the field and letting a reader assume it wasn't checked.
        inputs["rate_direction"] = direction
        inputs["rate_signal_strength"] = round(strength, 3)
        if forecast is None or not forecast.get("available"):
            missing.append("freight forecast (Model 2) for this corridor")
        else:
            inputs["rate_forecast_usd_mt"] = forecast.get("forecast_rate_usd_mt")
            inputs["rate_forecast_usd_mt"] = forecast.get("forecast_rate_usd_mt")
            inputs["rate_observed_usd_mt"] = forecast.get("current_observed_rate_usd_mt")
            inputs["rate_as_of"] = forecast.get("current_observed_rate_as_of")
            inputs["rate_interval_pct"] = _band_pct(forecast)
            drivers.append({
                "model": "Model 2 - freight forecast",
                "reads": f"{forecast.get('current_observed_rate_usd_mt')} USD/MT now, "
                         f"{forecast.get('forecast_rate_usd_mt')} in "
                         f"{forecast.get('horizon_days')} days",
                "direction": direction,
                "confidence": conf,
                "as_of": forecast.get("current_observed_rate_as_of"),
            })
            if direction == "rising":
                reasons.append(
                    f"Model 2 projects the rate up to "
                    f"{forecast.get('forecast_rate_usd_mt')} USD/MT from "
                    f"{forecast.get('current_observed_rate_usd_mt')} "
                    f"({_signed_pct(forecast)}%), which is {strength:.0%} of the model's "
                    f"own uncertainty band.")
            elif direction == "falling":
                reasons.append(
                    f"Model 2 projects the rate down to "
                    f"{forecast.get('forecast_rate_usd_mt')} USD/MT "
                    f"({_signed_pct(forecast)}%), {strength:.0%} of the uncertainty band.")
            else:
                reasons.append(
                    f"Model 2's move ({_signed_pct(forecast)}%) sits inside its own "
                    f"uncertainty band, so it gives no directional signal.")

        # ------------------------------------------------------- Model 1 signal
        congestion_score, turnaround, queue, cat = _read_congestion(congestion)
        if congestion is None or not congestion.get("available"):
            missing.append("congestion (Model 1) for this port")
        else:
            inputs["congestion_score"] = congestion_score
            inputs["congestion_category"] = cat
            inputs["queue_waiting_vessels"] = queue
            inputs["modelled_turnaround_p80_days"] = turnaround
            drivers.append({
                "model": "Model 1 - port congestion",
                "reads": f"{queue} vessels queued, {cat} congestion, "
                         f"modelled port stay {turnaround} days (80% band)",
                "direction": "worse" if (congestion_score or 0) >= THRESHOLDS["congestion_high"] else "clear",
                "confidence": (congestion or {}).get("confidence", {}).get("level"),
                "as_of": (congestion or {}).get("lineup", {}).get("as_of"),
            })
            if (congestion_score or 0) >= THRESHOLDS["congestion_critical"]:
                reasons.append(
                    f"Model 1 puts {port} at critical congestion: {queue} vessels at "
                    f"anchor and a modelled port stay of up to {turnaround} days.")
            elif (congestion_score or 0) >= THRESHOLDS["congestion_high"]:
                reasons.append(
                    f"Model 1 shows {queue} vessels waiting at {port}, so a committed "
                    f"vessel queues rather than berths on arrival.")
            else:
                reasons.append(
                    f"Model 1 shows {port} operating normally ({cat}, {queue} waiting).")

        # --------------------------------------------------------- weather signal
        wind = _num(_first(weather, "wind_max_kt", "weather_wind_max_kt"))
        precip = _num(_first(weather, "precip_mm", "weather_precip_mm"))
        w_as_of = _first(weather, "date", "as_of", "weather_as_of")
        if wind is None:
            missing.append("weather (no observation for this port)")
            weather_band = "unknown"
        else:
            if wind >= THRESHOLDS["severe_cyclonic_kt"]:
                weather_band = "severe"
            elif wind >= THRESHOLDS["cyclonic_storm_kt"]:
                weather_band = "cyclonic"
            elif wind >= THRESHOLDS["gale_kt"]:
                weather_band = "gale"
            else:
                weather_band = "clear"
            inputs["weather_wind_max_kt"] = wind
            inputs["weather_precip_mm"] = precip
            inputs["weather_as_of"] = w_as_of
            drivers.append({
                "model": "Open-Meteo observed weather",
                "reads": f"peak wind {wind} kt over 7 days"
                         + (f", {precip} mm rain" if precip is not None else ""),
                "direction": weather_band,
                "confidence": "observed",
                "as_of": w_as_of,
            })
            if weather_band in ("severe", "cyclonic"):
                reasons.append(
                    f"Open-Meteo shows {wind} kt sustained, in IMD cyclonic-storm "
                    f"territory. Discharge can be suspended.")
            elif weather_band == "gale":
                reasons.append(
                    f"Open-Meteo shows {wind} kt, enough to slow berthing work.")

        # ------------------------------------------------------------- the action
        action, avoid_adding, urgency = _decide(direction, congestion_score, weather_band,
                                                 strength, forecast, congestion)
        if not drivers:
            return {
                "available": False,
                "port": port,
                "action": "NO ASSESSMENT",
                "reason": "no model inputs available for this port",
                "provenance": prov.unavailable("port_lineups", "no inputs"),
            }

        confidence = _confidence(forecast, congestion, missing)
        return {
            "available": True,
            "port": port,
            "action": action,
            "urgency": urgency,
            "avoid_adding_vessels": avoid_adding,
            "why": reasons,
            "drivers": drivers,
            "inputs": inputs,
            "missing_inputs": missing,
            "model_coverage": f"{len(drivers)} of 3 input families present "
                              f"(freight forecast, congestion, weather)",
            "headline": _headline(port, action, avoid_adding, drivers),
            "confidence": confidence,
            "mitigations": _mitigations(action, avoid_adding, turnaround, weather_band),
            "thresholds": THRESHOLDS,
            "threshold_basis": "Operational policy: IMD cyclone wind categories for wind, "
                               "and a policy band for berth congestion. Not fitted "
                               "parameters. The signal threshold is derived from each "
                               "model's own published uncertainty band.",
            "news_signal": {
                "available": False,
                "reason": "No verified disruption feed is connected. The previous "
                          "implementation returned three hardcoded news items with fixed "
                          "dates, which made the risk output constant regardless of "
                          "conditions. Removed rather than replaced.",
            },
            "provenance": prov.provenance_block(["route_rates_weekly", "port_lineups",
                                                 "port_weather"]),
        }


# --------------------------------------------------------------------------
# readers
# --------------------------------------------------------------------------
def _read_forecast(forecast: Optional[Dict[str, Any]]) -> Tuple[str, float, str]:
    """Direction from Model 2, judged against its own uncertainty band."""
    if not forecast or not forecast.get("available"):
        return "unknown", 0.0, "unavailable"
    spot = _num(forecast.get("current_observed_rate_usd_mt"))
    point = _num(forecast.get("forecast_rate_usd_mt"))
    lo = _num(forecast.get("lower_bound_usd_mt"))
    hi = _num(forecast.get("upper_bound_usd_mt"))
    if None in (spot, point, lo, hi):
        return "unknown", 0.0, "unavailable"
    half = (hi - lo) / 2.0
    move = point - spot
    strength = abs(move) / half if half > 0 else 0.0
    if strength < SIGNAL_FRACTION:
        return "flat", strength, (forecast.get("confidence") or {}).get("level", "medium")
    return ("rising" if move > 0 else "falling"), strength, \
        (forecast.get("confidence") or {}).get("level", "medium")


def _read_congestion(c: Optional[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float],
                                                           Optional[float], Optional[str]]:
    if not c or not c.get("available"):
        return None, None, None, None
    ta = c.get("turnaround_estimate") or {}
    p80 = ta.get("p80_range_days") or [None, None]
    return (_num(c.get("congestion_score")),
            _num(p80[1]) if len(p80) == 2 else None,
            _num((c.get("lineup") or {}).get("queue_waiting")),
            c.get("congestion_category"))


def _band_pct(forecast: Dict[str, Any]) -> Optional[str]:
    spot = _num(forecast.get("current_observed_rate_usd_mt"))
    lo = _num(forecast.get("lower_bound_usd_mt"))
    hi = _num(forecast.get("upper_bound_usd_mt"))
    if None in (spot, lo, hi) or not spot:
        return None
    return f"-{100 * (spot - lo) / spot:.0f}% / +{100 * (hi - spot) / spot:.0f}%"


def _signed_pct(forecast: Dict[str, Any]) -> str:
    spot = _num(forecast.get("current_observed_rate_usd_mt"))
    point = _num(forecast.get("forecast_rate_usd_mt"))
    if None in (spot, point) or not spot:
        return "?"
    return f"{100 * (point - spot) / spot:+.1f}"


# --------------------------------------------------------------------------
# the decision
# --------------------------------------------------------------------------
def _decide(direction: str, congestion: Optional[float], weather: str,
            strength: float, forecast: Optional[Dict[str, Any]],
            c: Optional[Dict[str, Any]]) -> Tuple[str, bool, str]:
    """Fuse the three signals into one action. Explicit table, no black box."""
    busy = congestion is not None and congestion >= THRESHOLDS["congestion_high"]
    critical = congestion is not None and congestion >= THRESHOLDS["congestion_critical"]
    weather_bad = weather in ("cyclonic", "severe")

    if direction == "rising" and (busy or weather_bad):
        return ("CHARTER NOW", True, "high")
    if direction == "rising" and not busy:
        return ("LOCK IN", False, "high")
    if direction == "falling" and not busy:
        return ("WAIT", False, "medium")
    if direction == "falling" and busy:
        return ("WAIT, DO NOT ADD TONNAGE", True, "high")
    # direction == flat, or unknown
    if critical or weather_bad:
        return ("HOLD - DEFER FIXING", True, "medium")
    if busy:
        return ("HOLD - PORT WILL DETERIORATE", True, "medium")
    return ("HOLD / MONITOR", False, "low")


def _headline(port: str, action: str, avoid_adding: bool, drivers: List[Dict[str, Any]]) -> str:
    src = " + ".join(d["model"].split(" - ")[0] for d in drivers)
    tail = " Do not commit additional tonnage until this clears." if avoid_adding else ""
    return f"{action} at {port}, from {src}.{tail}"


def _confidence(forecast, congestion, missing: List[str]) -> Dict[str, Any]:
    reasons = []
    if not forecast or not forecast.get("available"):
        reasons.append("no freight forecast, so the rate signal is absent")
    if not congestion or not congestion.get("available"):
        reasons.append("no congestion reading, so the berth signal is absent")
    if any("weather" in m for m in missing):
        reasons.append("no weather observation, so the sailing signal is absent")
    if forecast and forecast.get("available"):
        c = (forecast.get("confidence") or {}).get("reasons") or []
        reasons.extend(c)
    level = "high" if not missing else "medium" if len(missing) == 1 else "low"
    return {"level": level, "missing": missing, "reasons": reasons,
            "note": "An action with a low flag means the recommendation rests on fewer "
                    "signals, not that it is a different kind of answer."}


def _mitigations(action: str, avoid_adding: bool, turnaround: Optional[float],
                 weather: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if avoid_adding:
        out.append({
            "action": "Do not add tonnage at this port",
            "detail": "Committing an additional vessel converts a rate problem into a "
                      "berth problem. The modelled port stay is "
                      + (f"up to {turnaround} days at the 80% band." if turnaround
                         else "not available for this port."),
        })
    if action in ("CHARTER NOW", "LOCK IN"):
        out.append({
            "action": "Secure tonnage before the move",
            "detail": "Model 2's direction is the driver here. If you want the upside "
                      "without the exposure, fix part of the requirement and leave the "
                      "remainder on spot.",
        })
    if action.startswith("WAIT"):
        out.append({
            "action": "Stay on spot and re-check weekly",
            "detail": "Model 2 projects a lower rate, so a fixed commitment now is the "
                      "expensive error. Re-run the query after the next observation.",
        })
    if weather in ("cyclonic", "severe"):
        out.append({
            "action": "Weather clause",
            "detail": "Sustained wind is in cyclonic-storm territory. Cover loading and "
                      "discharge suspension explicitly; see BIMCO GENCON 1994 as a "
                      "reference, not as advice.",
        })
    if not out:
        out.append({
            "action": "No action required",
            "detail": "Neither model nor weather indicates a reason to change the current "
                      "plan. Re-check when the line-up or the forecast moves.",
        })
    return out


_SERVICE: Optional[RiskMonitorService] = None


def get_service() -> RiskMonitorService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RiskMonitorService()
    return _SERVICE
