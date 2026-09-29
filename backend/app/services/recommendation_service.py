"""Unified recommendation: market entry + vessel + operational risk + weather.

Weather is a RISK MODIFIER only. It never changes the market-entry or vessel
status; it can only raise the overall risk level and add caution to the
decision. All thresholds are named constants: align them with the existing
FreightIQ logic if it defines its own cut-offs.
"""
from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    RiskSummary,
    StatusReason,
    WeatherSummary,
)
from app.schemas.weather import PortWeatherResponse, RiskLevel

LOW_CONGESTION_BELOW = 40.0
HIGH_CONGESTION_AT_OR_ABOVE = 70.0
ATTRACTIVE_RATE_PERCENTILE_AT_OR_BELOW = 30.0
EXPENSIVE_RATE_PERCENTILE_AT_OR_ABOVE = 70.0
RISING_MOMENTUM_PCT = 3.0
FALLING_MOMENTUM_PCT = -3.0
FAVOURABLE_MIN_POINTS = 2
UNFAVOURABLE_MAX_POINTS = -2
BERTH_HIGH_RISK_BELOW = 20.0
BERTH_MODERATE_RISK_BELOW = 50.0
DEMAND_PRESSURE_RATIO = 1.25

_LEVEL_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MODERATE: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.SEVERE: 3,
}
_ELEVATED = (RiskLevel.HIGH, RiskLevel.SEVERE)


def _market_entry(req: RecommendationRequest) -> StatusReason:
    points = 0
    assessed = 0
    notes: list[str] = []

    if req.congestion_score is not None:
        assessed += 1
        cong = req.congestion_score
        if cong < LOW_CONGESTION_BELOW:
            points += 1
            notes.append(f"Port congestion is low ({cong:.0f}%).")
        elif cong >= HIGH_CONGESTION_AT_OR_ABOVE:
            points -= 1
            notes.append(f"Port congestion is high ({cong:.0f}%).")
        else:
            notes.append(f"Port congestion is moderate ({cong:.0f}%).")

    if req.freight_rate_percentile is not None:
        assessed += 1
        pct = req.freight_rate_percentile
        if pct <= ATTRACTIVE_RATE_PERCENTILE_AT_OR_BELOW:
            points += 1
            notes.append(f"Freight rate is low versus its history (percentile {pct:.0f}).")
        elif pct >= EXPENSIVE_RATE_PERCENTILE_AT_OR_ABOVE:
            points -= 1
            notes.append(f"Freight rate is high versus its history (percentile {pct:.0f}).")
        else:
            notes.append(f"Freight rate is mid-range versus its history (percentile {pct:.0f}).")
    elif req.freight_rate is not None:
        notes.append("Freight rate supplied without a historical percentile; not scored.")

    if req.rate_momentum_14d is not None:
        assessed += 1
        mom = req.rate_momentum_14d
        if mom >= RISING_MOMENTUM_PCT:
            points += 1
            notes.append(f"14-day rate momentum is rising ({mom:+.1f}%), favouring booking before further rises.")
        elif mom <= FALLING_MOMENTUM_PCT:
            points -= 1
            notes.append(f"14-day rate momentum is falling ({mom:+.1f}%), favouring waiting.")
        else:
            notes.append(f"14-day rate momentum is flat ({mom:+.1f}%).")

    if assessed == 0:
        return StatusReason(
            status="INSUFFICIENT_DATA",
            reason="No congestion, freight-rate percentile or momentum data supplied.",
        )
    if points >= FAVOURABLE_MIN_POINTS:
        status = "FAVOURABLE"
    elif points <= UNFAVOURABLE_MAX_POINTS:
        status = "UNFAVOURABLE"
    else:
        status = "NEUTRAL"
    return StatusReason(status=status, reason=" ".join(notes))


def _vessel(req: RecommendationRequest) -> StatusReason:
    detail = f" {req.vessel_compatibility_reason}" if req.vessel_compatibility_reason else ""
    if req.vessel_compatibility is True:
        return StatusReason(status="COMPATIBLE", reason="Vessel fits the port's physical constraints." + detail)
    if req.vessel_compatibility is False:
        return StatusReason(status="INCOMPATIBLE", reason="Vessel does not fit the port's physical constraints." + detail)
    return StatusReason(status="UNKNOWN", reason="Vessel compatibility was not supplied.")


def _bump(level: RiskLevel) -> RiskLevel:
    order = [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH]
    return order[min(order.index(level) + 1, len(order) - 1)]


def _operational_risk(req: RecommendationRequest) -> tuple[RiskLevel, str]:
    notes: list[str] = []
    level: RiskLevel | None = None

    if req.berth_availability is not None:
        avail = req.berth_availability
        if avail < BERTH_HIGH_RISK_BELOW:
            level = RiskLevel.HIGH
        elif avail < BERTH_MODERATE_RISK_BELOW:
            level = RiskLevel.MODERATE
        else:
            level = RiskLevel.LOW
        notes.append(f"Berth availability is {avail:.0f}%.")

    if req.demand_volume is not None and req.demand_volume_reference is not None:
        ratio = req.demand_volume / req.demand_volume_reference
        if ratio >= DEMAND_PRESSURE_RATIO:
            notes.append(f"Demand volume is {ratio:.2f}x its reference, adding pressure.")
            level = _bump(level) if level else RiskLevel.MODERATE
        else:
            notes.append(f"Demand volume is {ratio:.2f}x its reference.")
            level = level or RiskLevel.LOW
    elif req.demand_volume is not None:
        notes.append("Demand volume supplied without a reference; not scored.")

    if level is None:
        return RiskLevel.UNKNOWN, "No berth-availability or demand data supplied."
    return level, " ".join(notes)


def _overall(levels: list[RiskLevel]) -> RiskLevel:
    known = [lvl for lvl in levels if lvl in _LEVEL_ORDER]
    return max(known, key=_LEVEL_ORDER.__getitem__) if known else RiskLevel.UNKNOWN


def _decide(market: StatusReason, vessel: StatusReason, overall: RiskLevel) -> str:
    if vessel.status == "INCOMPATIBLE":
        return "RESOLVE VESSEL COMPATIBILITY"
    if market.status == "INSUFFICIENT_DATA":
        return "INSUFFICIENT DATA"
    if market.status == "UNFAVOURABLE":
        return "WAIT"
    if market.status == "FAVOURABLE":
        return "CHARTER WITH CAUTION" if overall in _ELEVATED else "CHARTER NOW"
    return "MONITOR"


def _weather_summary(weather: PortWeatherResponse) -> WeatherSummary:
    return WeatherSummary(
        available=weather.available,
        score=weather.risk.score,
        level=weather.risk.level,
        key_factors=weather.risk.factors,
        message=weather.message,
        provider=weather.provider,
        fetched_at=weather.fetched_at,
    )


def _risk_reason(op_level: RiskLevel, op_note: str, weather: PortWeatherResponse) -> str:
    if weather.available and weather.risk.score is not None:
        weather_note = (
            f"Weather risk is {weather.risk.level.value} (score {weather.risk.score}/100)."
        )
    else:
        weather_note = "Weather risk was not assessed (weather data unavailable)."
    return f"{op_note} {weather_note}"


def _summary(decision: str, market: StatusReason, overall: RiskLevel,
             vessel: StatusReason, weather: PortWeatherResponse) -> str:
    first = {
        "RESOLVE VESSEL COMPATIBILITY": "The selected vessel is not compatible with this port, so that must be resolved first.",
        "INSUFFICIENT DATA": "There is not enough market data to form a recommendation.",
        "WAIT": "Market conditions currently favour waiting.",
        "CHARTER NOW": "Market conditions are generally supportive of chartering now.",
        "CHARTER WITH CAUTION": "Market conditions support chartering, but the recommendation carries elevated risk.",
        "MONITOR": "Market signals are mixed; keep monitoring.",
    }[decision]
    if not weather.available:
        second = "Weather risk could not be assessed, so it is not factored in."
    elif weather.risk.level in _ELEVATED:
        second = f"Weather risk is {weather.risk.level.value}; plan for possible operational delays."
    else:
        second = f"Weather risk is {weather.risk.level.value}."
    if vessel.status == "UNKNOWN" and decision in ("CHARTER NOW", "CHARTER WITH CAUTION"):
        second += " Vessel compatibility has not been verified."
    return f"{first} {second}"


def build_recommendation(
    req: RecommendationRequest,
    weather: PortWeatherResponse,
    derived: dict[str, str] | None = None,
) -> RecommendationResponse:
    market = _market_entry(req)
    vessel = _vessel(req)
    op_level, op_note = _operational_risk(req)
    overall = _overall([op_level, weather.risk.level])
    decision = _decide(market, vessel, overall)

    factors = weather.risk.factors
    explanations = [market.reason, vessel.reason, _risk_reason(op_level, op_note, weather)]
    if factors:
        listed = "; ".join(f"{f.factor} {f.value:g} {f.unit} ({f.impact.value})" for f in factors)
        explanations.append(f"Weather risk drivers: {listed}.")

    inputs = req.model_dump(exclude={"port_name", "use_bdi_market_data"})
    provenance = {k: ("PROVIDED_BY_CALLER" if v is not None else "UNAVAILABLE") for k, v in inputs.items()}
    provenance.update(derived or {})
    if derived:
        explanations.append(
            "Inputs marked DERIVED_FROM_BDI use the global Baltic Dry Index as a proxy, "
            "not port-specific freight rates."
        )
    provenance["weather_observations"] = "REAL_DATA" if weather.available else "UNAVAILABLE"
    provenance["weather_risk_score"] = "DERIVED_METRIC" if weather.available else "UNAVAILABLE"
    provenance["market_entry"] = "DERIVED_METRIC"
    provenance["decision"] = "DERIVED_METRIC"

    return RecommendationResponse(
        port=weather.port,
        decision=decision,
        summary=_summary(decision, market, overall, vessel, weather),
        market_entry=market,
        vessel=vessel,
        risk=RiskSummary(
            overall_level=overall,
            operational_level=op_level,
            weather_level=weather.risk.level,
            weather_score=weather.risk.score,
            reason=_risk_reason(op_level, op_note, weather),
        ),
        weather=_weather_summary(weather),
        explanations=explanations,
        explanation_inputs={
            "inputs": inputs,
            "weather_risk_score": weather.risk.score,
            "weather_factors": [f.model_dump(mode="json") for f in factors],
            "current_weather": weather.current.model_dump() if weather.current else None,
        },
        data_provenance=provenance,
    )
