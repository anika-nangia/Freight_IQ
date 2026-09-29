"""Deterministic, structured evidence for the Explainability section.

This is factual evidence derived from the recommendation inputs, NOT AI text.
`ai_narrative` is a placeholder for the future AI model and is always None here.
"""
from app.schemas.recommendation import RecommendationResponse

_LABELS = {
    "congestion_score": ("Congestion score", "/100", "lower is better"),
    "freight_rate": ("Freight rate", "", ""),
    "freight_rate_percentile": ("Freight rate percentile", "th pct", "lower means cheaper vs history"),
    "rate_momentum_14d": ("14-day rate momentum", "%", "positive means rates rising"),
    "berth_availability": ("Berth availability", "%", "higher is better"),
    "demand_volume": ("Demand volume", "", ""),
}


def _impact(key: str, v: float) -> str:
    if key == "congestion_score":
        return "positive" if v < 34 else "negative" if v > 66 else "neutral"
    if key == "freight_rate_percentile":
        return "positive" if v <= 33 else "negative" if v >= 67 else "neutral"
    if key == "rate_momentum_14d":
        return "negative" if v > 0 else "positive" if v < 0 else "neutral"
    if key == "berth_availability":
        return "positive" if v >= 66 else "negative" if v < 34 else "neutral"
    return "neutral"


def build_evidence(rec: RecommendationResponse) -> dict:
    inputs = rec.explanation_inputs.get("inputs", {})
    factors = []
    for key, (label, unit, note) in _LABELS.items():
        v = inputs.get(key)
        factors.append({
            "factor": label, "value": v, "unit": unit,
            "impact": "unavailable" if v is None else _impact(key, v),
            "reason": f"Not provided; excluded from the decision." if v is None else note or "Provided input.",
            "source": rec.data_provenance.get(key, "UNAVAILABLE"),
        })
    for label, status in (("Market entry", rec.market_entry), ("Vessel", rec.vessel)):
        factors.append({"factor": label, "value": status.status, "unit": "", "impact": "info",
                        "reason": status.reason, "source": "DERIVED_METRIC"})
    for f in rec.weather.key_factors:
        factors.append({"factor": f"Weather: {f.factor}", "value": f.value, "unit": f.unit,
                        "impact": f.impact.value.lower(), "reason": f"Contributes {f.points} weather-risk points.",
                        "source": "REAL_DATA"})
    return {
        "port": rec.port, "decision": rec.decision, "summary": rec.summary,
        "factors": factors, "rule_based_explanations": rec.explanations,
        "ai_narrative": None, "ai_narrative_status": "NOT_CONFIGURED",
    }
