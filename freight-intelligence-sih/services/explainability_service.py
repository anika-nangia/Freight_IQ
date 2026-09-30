"""
Explainability: turns model outputs into one sentence a charterer can act on.

THE PROBLEM IT SOLVES
    The unified recommendation panel showed three separate technical readouts and left
    the operator to combine them. "Decision fatigue" is exactly that: three confident
    numbers, no single answer, and the manager has to work out what to do.

WHAT THIS IS
    A thin narrative layer over the outputs of Model 1, Model 2, the constraint tables
    and the risk monitor. It exists to reduce decision fatigue, so it produces one
    recommended action with its reasoning in plain language, plus the conditions that
    would change the advice.

HARD RULE ON NUMBERS - read this before changing anything
    Every figure in the narrative is computed here from the model outputs and injected
    into the text as a pre-formatted string. An LLM, if one is configured, is given
    those strings and is asked only to phrase around them. It is never asked to produce,
    infer, round or adjust a number, and the output is re-checked: if any number the
    LLM returned does not appear in the facts it was given, the deterministic
    narrative is used instead.

    That check is not decoration. An LLM asked to "explain these results" will
    cheerfully produce $3.47/tonne because that reads better than $3.13. On a charter
    desk that is a fabricated number attached to a real recommendation, which is the
    single worst failure this system could have.

PROVIDERS
    Deterministic (default, always available, no key, offline, cannot hallucinate)
    Optional LLM via environment variable FREIGHTIQ_LLM_PROVIDER + a key. Falls back
    to deterministic on any error, timeout or failed verification.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROVIDER = os.environ.get("FREIGHTIQ_LLM_PROVIDER", "").strip().lower()
LLM_TIMEOUT = float(os.environ.get("FREIGHTIQ_LLM_TIMEOUT", "12"))

SYSTEM_PROMPT = (
    "You are a chartering analyst writing one paragraph for a shipping manager. "
    "You are given FACTS that have already been computed, including every number. "
    "Rules: use ONLY the numbers in the FACTS, verbatim - never calculate, convert, "
    "round or invent a figure. Do not add any number that is not in the FACTS. "
    "Do not use the words 'likely' or 'probably'. Be direct, plain and under 90 words. "
    "Output only the paragraph."
)


# --------------------------------------------------------------------------
# fact extraction - the single source of every number in the output
# --------------------------------------------------------------------------
def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def build_facts(forecast: Optional[Dict[str, Any]], congestion: Optional[Dict[str, Any]],
                risk: Optional[Dict[str, Any]], vessel: Optional[Dict[str, Any]],
                timing: Optional[Dict[str, Any]], idle: Optional[Dict[str, Any]],
                origin: str, destination: str, vessel_class: str,
                cargo_volume_mt: float) -> Dict[str, Any]:
    """Everything the narrative is allowed to say, as a flat fact sheet."""
    f: Dict[str, Any] = {
        "corridor": f"{origin} to {destination}",
        "vessel_class_requested": vessel_class,
        "cargo_tonnes": cargo_volume_mt,
    }

    if forecast and forecast.get("available"):
        spot = _num(forecast.get("current_observed_rate_usd_mt"))
        point = _num(forecast.get("forecast_rate_usd_mt"))
        lo = _num(forecast.get("lower_bound_usd_mt"))
        hi = _num(forecast.get("upper_bound_usd_mt"))
        f["rate_observed_usd_per_tonne"] = spot
        f["rate_forecast_usd_per_tonne"] = point
        f["rate_lower_usd_per_tonne"] = lo
        f["rate_upper_usd_per_tonne"] = hi
        f["rate_horizon_days"] = forecast.get("horizon_days")
        f["rate_as_of"] = forecast.get("current_observed_rate_as_of")
        f["rate_change_pct"] = _num(forecast.get("predicted_change_pct"))
        f["direction_accuracy_pct"] = _dir_acc(forecast)
        f["exposure_usd"] = (forecast.get("cargo_context") or {}).get("exposure_at_forecast_usd")
    else:
        f["rate_observed_usd_per_tonne"] = None
        f["rate_unavailable_reason"] = (forecast or {}).get("reason")

    if congestion and congestion.get("available"):
        f["congestion_score"] = _num(congestion.get("congestion_score"))
        f["congestion_category"] = congestion.get("congestion_category")
        f["queue_waiting_vessels"] = (congestion.get("lineup") or {}).get("queue_waiting")
        ta = congestion.get("turnaround_estimate") or {}
        p80 = ta.get("p80_range_days") or []
        f["port_stay_p80_days"] = p80[1] if len(p80) == 2 else None
        f["port_stay_model"] = (congestion.get("model"))
    if risk and risk.get("available"):
        f["risk_action"] = risk.get("action")
        f["risk_urgency"] = risk.get("urgency")
        f["risk_avoid_adding"] = risk.get("avoid_adding_vessels")
        f["risk_why"] = risk.get("why") or []
        f["risk_missing"] = risk.get("missing_inputs") or []
    if timing and timing.get("available"):
        f["timing_action"] = timing.get("action")
        f["timing_signal_strength"] = _num(timing.get("signal_strength_vs_interval"))
        f["timing_reads_as_signal"] = timing.get("reads_as_signal")
    if vessel and vessel.get("available"):
        f["vessel_recommended"] = vessel.get("recommended_vessel")
        f["vessel_cost_per_tonne"] = _num(vessel.get("cost_per_ton_usd"))
        f["vessel_margin_usd"] = _num(vessel.get("expected_margin_usd_per_voyage"))
        f["vessel_margin_per_tonne"] = _num(vessel.get("expected_margin_usd_per_tonne"))
        f["vessel_origin_verified"] = vessel.get("origin_limits_verified")
        f["vessel_ranking_basis"] = vessel.get("ranking_basis")
    if idle and idle.get("available"):
        f["idle_deadhead_risk"] = idle.get("deadhead_risk_tier")
        f["idle_export_import_ratio"] = (
            (idle.get("observed_flow") or {}).get("export_to_import_ratio"))
    return f


def _dir_acc(forecast: Dict[str, Any]) -> Optional[float]:
    m = forecast.get("model_validation") if isinstance(forecast.get("model_validation"), dict) else None
    v = _num(forecast.get("directional_accuracy_pct"))
    if v is not None:
        return v
    return None


def fact_sentence(f: Dict[str, Any]) -> Dict[str, str]:
    """Pre-formatted strings. The LLM receives these, not raw numbers."""
    out: Dict[str, str] = {}
    if f.get("rate_observed_usd_per_tonne") is not None:
        out["rate"] = (f"{f['rate_observed_usd_per_tonne']} USD/tonne observed, forecast "
                       f"{f['rate_forecast_usd_per_tonne']} USD/tonne in "
                       f"{f.get('rate_horizon_days')} days "
                       f"(80% band {f['rate_lower_usd_per_tonne']} to "
                       f"{f['rate_upper_usd_per_tonne']})")
    if f.get("congestion_category"):
        out["congestion"] = (f"{f['congestion_category']} congestion at the destination, "
                             f"{f.get('queue_waiting_vessels')} vessels waiting, modelled "
                             f"port stay up to {f.get('port_stay_p80_days')} days")
    if f.get("vessel_recommended"):
        s = f"{f['vessel_recommended']} recommended"
        if f.get("vessel_margin_usd") is not None:
            s += f", expected margin {f['vessel_margin_usd']:.0f} USD per voyage"
        out["vessel"] = s
    if f.get("risk_action"):
        out["action"] = f["risk_action"]
    return out


# --------------------------------------------------------------------------
# deterministic narrative - always available, never invents anything
# --------------------------------------------------------------------------
def _money(v: Any, dp: int = 0) -> str:
    """Format a dollar figure with separators, or return an empty string."""
    n = _num(v)
    if n is None:
        return ""
    return f"{n:,.{dp}f}"


def _money_short(v: Any) -> str:
    """Whole dollars under a million, otherwise millions to two decimals.

    "$0.99 million" is both clumsy and arguably misleading, because a reader
    compares it against the full figures elsewhere on the page.
    """
    n = _num(v)
    if n is None:
        return ""
    if abs(n) < 1_000_000:
        return f"${n:,.0f}"
    return f"${n / 1_000_000:,.2f} million"


# The risk service reports which inputs were absent using internal model labels.
# A chartering reader does not know what "Model 1" refers to.
_MISSING_PLAIN = [
    (re.compile(r"congestion\s*\(Model\s*1\)\s*for this port", re.I),
     "the berth line-up for this port"),
    (re.compile(r"freight forecast\s*\(Model\s*2\)\s*for this corridor", re.I),
     "a rate forecast for this lane"),
    (re.compile(r"weather\s*\(no observation for this port\)", re.I),
     "a weather observation for this port"),
    (re.compile(r"weather.*", re.I), "a weather observation for this port"),
    (re.compile(r"congestion.*", re.I), "the berth line-up for this port"),
    (re.compile(r"freight forecast.*", re.I), "a rate forecast for this lane"),
]


def _plain_missing(items: List[str]) -> List[str]:
    out: List[str] = []
    for it in items:
        s = str(it)
        for rx, plain in _MISSING_PLAIN:
            if rx.search(s):
                s = plain
                break
        if s not in out:
            out.append(s)
    return out


def _plain_num(v: Any, dp: int = 2) -> str:
    n = _num(v)
    return "" if n is None else f"{n:,.{dp}f}"


def _count_word(n: float) -> str:
    """'no ships waiting' reads better than '0.0 vessels waiting'."""
    if abs(n) < 0.05:
        return "no ships waiting"
    return f"{n:.0f} ship{'s' if abs(n - 1) > 0.05 else ''} waiting"


def _horizon_phrase(days: Any) -> str:
    n = _num(days)
    if n is None:
        return "shortly"
    if n <= 10:
        return f"in {n:.0f} days"
    if n <= 20:
        return "in a fortnight"
    if n <= 45:
        return f"in about {n / 7:.0f} weeks"
    return f"in about {n / 30:.0f} months"


def _band_phrase(f: Dict[str, Any]) -> str:
    lo, hi = _num(f.get("rate_lower_usd_per_tonne")), _num(f.get("rate_upper_usd_per_tonne"))
    if lo is None or hi is None:
        return ""
    return f"anywhere from {_plain_num(lo)} to {_plain_num(hi)}"


def deterministic_narrative(f: Dict[str, Any]) -> str:
    """Plain-English rationale, built only from the facts in `f`.

    The numbers are unchanged from what the models returned - this only decides how
    they are worded. The previous wording was written for a reader who already knew
    the methodology: it named the models, said "80% band" twice in one sentence, and
    printed a raw figure like 2756065 with no thousands separator. A chartering
    reader needs the number and the caveat, not the labels.
    """
    parts: List[str] = []
    action = f.get("risk_action") or "HOLD / MONITOR"
    parts.append(f"Recommendation: {action}.")

    lane = f.get("corridor") or "this lane"
    spot = _num(f.get("rate_observed_usd_per_tonne"))
    fwd = _num(f.get("rate_forecast_usd_per_tonne"))

    if spot is not None and fwd is not None:
        band = _band_phrase(f)
        lo = _num(f.get("rate_lower_usd_per_tonne"))
        hi = _num(f.get("rate_upper_usd_per_tonne"))
        outside = (hi is not None and fwd > hi) or (lo is not None and fwd < lo)
        move = _num(f.get("rate_change_pct"))
        if move is None:
            parts.append(
                f"Rates on {lane} are ${_plain_num(spot)} a tonne today. We expect "
                f"${_plain_num(fwd)} {_horizon_phrase(f.get('rate_horizon_days'))}.")
        else:
            verb = "up" if move > 0 else ("down" if move < 0 else "flat")
            tail = f", {verb} {abs(move):.1f}%" if abs(move) >= 0.05 else ""
            parts.append(
                f"Rates on {lane} are ${_plain_num(spot)} a tonne today. We expect "
                f"${_plain_num(fwd)} {_horizon_phrase(f.get('rate_horizon_days'))}{tail}.")
            if band and not outside:
                parts.append(f"In practice it could land {band} a tonne, so treat that as "
                             f"a direction rather than a price to lock in.")
            elif band and outside:
                # The point estimate sits outside the interval built from the model's
                # own residuals. Printing both without comment reads as a contradiction,
                # so say so rather than let a reader trip over it.
                side = "above" if hi is not None and fwd > hi else "below"
                parts.append(
                    f"Be careful with that figure: it sits {side} the "
                    f"{_plain_num(lo)} to {_plain_num(hi)} range our own error bars allow "
                    f"for, so the size of the move is not reliable even though the "
                    f"direction is.")
    else:
        reason = f.get("rate_unavailable_reason")
        parts.append("We have no rate forecast for this lane"
                     + (f" ({reason})." if reason else "."))

    cat = f.get("congestion_category")
    q = _num(f.get("queue_waiting_vessels"))
    stay = _num(f.get("port_stay_p80_days"))
    if cat:
        berth = _count_word(q if q is not None else 0.0)
        if stay is not None:
            parts.append(
                f"The berth at the discharge port is {str(cat).lower()}, with {berth}, "
                f"and a ship should berth and sail inside about {stay:.0f} days.")
        else:
            parts.append(f"The berth at the discharge port is {str(cat).lower()}, with {berth}.")
    elif cat is None and f.get("risk_missing"):
        parts.append("We have no line-up reading for the discharge port on this query.")

    vessel = f.get("vessel_recommended")
    if vessel:
        margin = _num(f.get("vessel_margin_usd"))
        tonnes = _num(f.get("cargo_tonnes"))
        s = f"A {vessel} is the right size for this cargo"
        if margin is not None:
            cargo_txt = f" on a {tonnes:,.0f} tonne parcel" if tonnes else ""
            s += f", and should put about {_money_short(margin)} back{cargo_txt}."
        else:
            s += "."
        parts.append(s)
        if f.get("vessel_origin_verified") is False:
            parts.append("Check the loading port can actually accept her before fixing.")

    if f.get("idle_deadhead_risk"):
        parts.append(
            f"Return cargo at the discharge port scores {f['idle_deadhead_risk']} risk "
            f"on the observed import/export balance.")

    if f.get("risk_avoid_adding"):
        parts.append("Do not send another ship to this port until this clears.")
    if f.get("risk_missing"):
        parts.append("Decided without " + "; ".join(_plain_missing(f["risk_missing"])) + ".")

    return " ".join(parts)


# --------------------------------------------------------------------------
# optional LLM - phrasing only, numbers verified afterwards
# --------------------------------------------------------------------------
def _llm_configured() -> bool:
    return bool(PROVIDER) and bool(os.environ.get("FREIGHTIQ_LLM_API_KEY"))


def _allowed_numbers(f: Dict[str, Any]) -> set:
    """Every number the narrative is permitted to contain."""
    allowed = set()
    for v in f.values():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            x = float(v)
            allowed.add(f"{x:g}")
            allowed.add(f"{x:.1f}")
            allowed.add(f"{x:.2f}")
            allowed.add(f"{x:.0f}")
            # Large money figures are also written in millions in the deterministic
            # text. That is the same value restated, not new information, so it must
            # not be treated as an invented figure - otherwise an LLM faithfully
            # copying the supplied phrasing gets its draft thrown away.
            if abs(x) >= 1_000_000:
                m = x / 1_000_000
                allowed.add(f"{m:g}")
                allowed.add(f"{m:.1f}")
                allowed.add(f"{m:.2f}")
    for s in fact_sentence(f).values():
        allowed.update(re.findall(r"-?\d+(?:\.\d+)?", s))
    return allowed


def _numbers_in(text: str) -> set:
    """Numeric tokens in a draft, ignoring model names.

    "Model 2 projects the rate..." contains a 2 that is a model label, not a data
    figure. Left in, every well-written narrative was rejected by the verification
    step for mentioning Model 1 or Model 2, which would have silently disabled the LLM
    path in normal use.
    """
    cleaned = re.sub(r"\bModel\s+\d+\b", "Model", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:Model|MODEL)\s*[A-Z]?\d*\b", "Model", cleaned)
    # Thousands separators are presentation, not a different value. Without this,
    # "$991,665" is read as the two tokens 991 and 665, neither of which is in the
    # allowed set, and a correctly written LLM draft would be thrown away.
    cleaned = re.sub(r"(?<=\d),(?=\d{3}\b)", "", cleaned)
    return set(re.findall(r"-?\d+(?:\.\d+)?", cleaned))


def _call_llm(facts_block: str) -> Optional[str]:
    provider = PROVIDER
    key = os.environ.get("FREIGHTIQ_LLM_API_KEY", "")
    model = os.environ.get("FREIGHTIQ_LLM_MODEL", "")
    if provider in ("openai", "gpt"):
        url = "https://api.openai.com/v1/chat/completions"
        model = model or "gpt-4o-mini"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    elif provider in ("anthropic", "claude"):
        url = "https://api.anthropic.com/v1/messages"
        model = model or "claude-3-5-sonnet-latest"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01",
                   "Content-Type": "application/json"}
    elif provider in ("gemini", "google"):
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model or 'gemini-1.5-flash'}:generateContent?key={key}")
        headers = {"Content-Type": "application/json"}
    elif provider in ("ollama", "local"):
        base = os.environ.get("FREIGHTIQ_LLM_BASE", "http://127.0.0.1:11434")
        url = f"{base}/api/chat"
        headers = {"Content-Type": "application/json"}
    else:
        return None

    if provider in ("anthropic", "claude"):
        body = {"model": model, "max_tokens": 400, "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": facts_block}]}
    elif provider in ("gemini", "google"):
        body = {"contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + facts_block}]}],
                "generationConfig": {"maxOutputTokens": 400}}
    elif provider in ("ollama", "local"):
        body = {"model": model or "llama3.1", "stream": False,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                             {"role": "user", "content": facts_block}]}
    else:
        body = {"model": model, "max_tokens": 400,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                             {"role": "user", "content": facts_block}]}

    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            ValueError, OSError) as e:
        print(f"[explain] LLM call failed ({type(e).__name__}); using deterministic text")
        return None

    try:
        if provider in ("anthropic", "claude"):
            return "".join(b.get("text", "") for b in data.get("content", []))
        if provider in ("gemini", "google"):
            return "".join(p.get("text", "") for p in
                           data["candidates"][0]["content"]["parts"])
        if provider in ("ollama", "local"):
            return data.get("message", {}).get("content", "")
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


class ExplainabilityService:
    def explain(self, **kw: Any) -> Dict[str, Any]:
        f = build_facts(
            forecast=kw.get("forecast"), congestion=kw.get("congestion"),
            risk=kw.get("risk"), vessel=kw.get("vessel"), timing=kw.get("timing"),
            idle=kw.get("idle"), origin=kw.get("origin", "?"),
            destination=kw.get("destination", "?"),
            vessel_class=kw.get("vessel_class", "?"),
            cargo_volume_mt=kw.get("cargo_volume_mt", 0))
        deterministic = deterministic_narrative(f)
        result: Dict[str, Any] = {
            "available": True,
            "recommendation": deterministic,
            "source": "deterministic",
            "facts": f,
            "confidence": {
                "level": "high" if len(f.get("risk_why", [])) >= 2 else "medium",
                "basis": "built only from model outputs present in this response",
            },
        }

        if not _llm_configured():
            result["llm"] = {
                "configured": False,
                "reason": "no provider set. Set FREIGHTIQ_LLM_PROVIDER and "
                          "FREIGHTIQ_LLM_API_KEY to enable narrative phrasing; the "
                          "deterministic text above is served meanwhile.",
            }
            return result

        facts_block = ("FACTS (use these numbers verbatim, add nothing):\n"
                       + json.dumps(f, indent=2, default=str)
                       + "\n\nPre-formatted:\n"
                       + json.dumps(fact_sentence(f), indent=2, default=str))
        text = _call_llm(facts_block)
        if not text:
            result["llm"] = {"configured": True, "used": False,
                             "reason": "call failed or returned nothing; deterministic used"}
            return result

        # Verification. If the LLM emitted a number we did not supply, the whole
        # narrative is discarded, because a single invented figure contaminates the
        # recommendation it is attached to.
        invented = _numbers_in(text) - _allowed_numbers(f)
        if invented:
            result["llm"] = {
                "configured": True, "used": False,
                "reason": "rejected: the draft contained figures absent from the facts",
                "unsourced_figures": sorted(invented)[:8],
            }
            return result

        result["recommendation"] = text.strip()
        result["source"] = f"llm:{PROVIDER}"
        result["llm"] = {"configured": True, "used": True,
                         "verified": True,
                         "note": "all numbers checked against the supplied facts"}
        return result


_SERVICE: Optional[ExplainabilityService] = None


def get_service() -> ExplainabilityService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ExplainabilityService()
    return _SERVICE
