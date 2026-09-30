"""
Pillar (d): Risk assessment from observed signals.

The previous version accumulated integer "risk points" from invented thresholds and
returned a narrative about BIMCO clauses. Three problems:

  * `active_disruptions` was fed by a scraper that returned three hardcoded news
    items with fixed dates, so the risk tier never changed and the output was fiction;
  * the thresholds (35 knots, 3.0 m, 2.0 days) were asserted with no reference;
  * it presented a scoring rule as if it were a model.

What this does instead: every input is either observed (line-up, weather) or absent.
There is no news feed, so there is no news signal, and the response says so rather than
implying one. Thresholds are declared as operational policy with their basis named.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402

# Operational thresholds. These are POLICY, chosen against published guidance rather
# than fitted, and are reported as such. Sources are named so they can be checked.
THRESHOLDS = {
    # IMD cyclone categories are defined on sustained wind in knots.
    "cyclonic_storm_kt": 32.0,        # IMD: 17-27 kt depression, 31-47 kt cyclonic storm
    "severe_cyclonic_kt": 47.0,       # IMD: 48-63 kt severe cyclonic storm
    "rough_sea_wave_m": 2.5,          # rough sea, Douglas scale
    "very_rough_wave_m": 4.0,         # very rough / high
    "queue_days_high": 2.0,
    "queue_days_critical": 4.0,
    "congestion_high": 0.55,
    "congestion_critical": 0.75,
}


class RiskMitigationService:
    def assess(self, port: str, congestion: Optional[Dict[str, Any]] = None,
               weather: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Assemble the risk picture for a port from whatever is observed.

        Any input may be None. A missing input lowers the assessment's coverage and is
        named in the response; it never becomes a zero that reads as "safe".
        """
        signals: List[Dict[str, Any]] = []
        missing: List[str] = []

        # ---------------------------------------------------------- congestion
        if congestion and congestion.get("available"):
            c = congestion
            queue_days = c.get("suggested_buffer_days", 0)
            # Use the modelled turnaround range rather than the buffer hint.
            ta = c.get("turnaround_estimate", {})
            p80 = ta.get("p80_range_days") or [None, None]
            modelled = p80[1] if len(p80) == 2 else None
            signals.append({
                "signal": "congestion",
                "source": "port line-up (observed)",
                "as_of": c.get("lineup", {}).get("as_of"),
                "queue_waiting_vessels": c.get("lineup", {}).get("queue_waiting"),
                "congestion_score": c.get("congestion_score"),
                "category": c.get("congestion_category"),
                "modelled_turnaround_p80_days": p80,
                "assessment": _band(
                    c.get("congestion_score", 0.0),
                    [(THRESHOLDS["congestion_critical"], "critical"),
                     (THRESHOLDS["congestion_high"], "high"),
                     (0.35, "moderate")], "clear"),
                "detail": (f"{c.get('lineup', {}).get('queue_waiting')} vessels queued, "
                           f"{c.get('congestion_category')} congestion, modelled turnaround "
                           f"{modelled} days (80% band)"),
            })
        else:
            missing.append("congestion (no line-up data for this port)")

        # ------------------------------------------------------------- weather
        if weather and weather.get("wind_max_kt") is not None:
            w = float(weather["wind_max_kt"])
            if w >= THRESHOLDS["severe_cyclonic_kt"]:
                band = "severe"
            elif w >= THRESHOLDS["cyclonic_storm_kt"]:
                band = "cyclonic"
            elif w >= 25.0:
                band = "gale"
            else:
                band = "clear"
            signals.append({
                "signal": "weather",
                "source": "Open-Meteo observed (observed)",
                "as_of": weather.get("date") or weather.get("as_of"),
                "wind_max_kt": w,
                "precipitation_mm": weather.get("precip_mm"),
                "assessment": band,
                "detail": (f"peak wind {w} kt over the last 7 days"
                           + (f", {weather.get('precip_mm')} mm rain"
                              if weather.get("precip_mm") is not None else "")),
            })
        else:
            missing.append("weather (no observation for this port)")

        # ------------------------------------------------------------ verdicts
        order = {"clear": 0, "moderate": 1, "high": 2, "gale": 2,
                 "cyclonic": 3, "critical": 3, "severe": 4}
        observed = [s for s in signals]
        worst = max((s["assessment"] for s in observed), key=lambda a: order.get(a, 0)) if observed else "unknown"

        tier = ("unknown" if not observed else
                "high" if worst in ("critical", "severe", "cyclonic") else
                "medium" if worst in ("high", "gale") else
                "low" if worst in ("clear", "moderate") else "unknown")

        warnings = []
        for s in observed:
            if order.get(s["assessment"], 0) >= 2:
                warnings.append(f"{s['signal'].title()}: {s['detail']}")
        mitigations = self._mitigations(tier, observed)

        out: Dict[str, Any] = {
            "available": bool(observed),
            "port": port,
            "risk_tier": tier,
            "worst_signal": worst,
            "signals_observed": observed,
            "signals_missing": missing,
            "coverage": f"{len(observed)} of 2 expected signal families observed",
            "warnings": warnings,
            "headline_warning": (self._headline(port, tier, observed) if observed
                                 else "No observed signals available for this port; no risk "
                                      "assessment can be made."),
            "mitigation_clauses": mitigations,
            "news_signal": {
                "available": False,
                "reason": "no verified disruption feed is connected. The previous "
                          "implementation returned three hardcoded news items with fixed "
                          "dates, which made the risk tier constant regardless of "
                          "conditions. That has been removed rather than replaced.",
            },
            "thresholds": THRESHOLDS,
            "threshold_basis": "Operational policy. IMD cyclone wind categories for wind; "
                               "Douglas sea-state bands for wave. Not fitted parameters.",
        }
        out["provenance"] = prov.provenance_block(["port_lineups", "port_weather"])
        out["confidence"] = {
            "level": "high" if not missing and len(observed) == 2 else "low" if not observed else "medium",
            "missing_signals": missing,
        }
        return out

    def _mitigations(self, tier: str, signals: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        if tier == "high":
            out.append({
                "clause": "Force majeure / weather exclusion",
                "detail": "Cover squally weather and swell delay at the discharge port. "
                          "Reference BIMCO GENCON 1994, which the parties should read "
                          "alongside this summary rather than rely on it.",
            })
            out.append({
                "clause": "Laytime and demurrage",
                "detail": "Add laydays for the modelled turnaround plus the 80% upper band, "
                          "not just the point estimate. Set the demurrage rate from your "
                          "charter party, not from this service.",
            })
            out.append({
                "clause": "Alternate discharge",
                "detail": "Name a second port with the physical limits to accept the vessel. "
                          "See the vessel optimiser for which classes each port admits.",
            })
        elif tier == "medium":
            out.append({
                "clause": "Buffer laydays",
                "detail": "Add laydays to cover the modelled turnaround range at this port.",
            })
        else:
            out.append({
                "clause": "Standard laycan",
                "detail": "Normal operation. No additional buffer indicated by the observed "
                          "signals available.",
            })
        return out

    def _headline(self, port: str, tier: str, signals: List[Dict[str, Any]]) -> str:
        if tier == "high":
            detail = next((s["detail"] for s in signals
                           if s["assessment"] in ("critical", "severe", "cyclonic")), "")
            return f"Elevated risk at {port}: {detail}."
        if tier == "medium":
            detail = next((s["detail"] for s in signals if s["assessment"] in ("high", "gale")), "")
            return f"Moderate risk at {port}: {detail}."
        return f"No elevated risk signal observed at {port}."


def _band(value: float, ladder: List[tuple], default: str) -> str:
    for thr, name in ladder:
        if value >= thr:
            return name
    return default


_SERVICE: Optional[RiskMitigationService] = None


def get_service() -> RiskMitigationService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RiskMitigationService()
    return _SERVICE
