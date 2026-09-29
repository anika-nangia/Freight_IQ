"""Deterministic, explainable weather-risk scoring (0-100).

Score = gust + sustained wind + precipitation amount + precipitation
probability + visibility + severe weather code. Every component uses the named
tiers below, so thresholds can be tuned in one place. Maximum contributions
add up to exactly 100.
"""
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.schemas.weather import (
    CurrentWeather,
    ForecastPoint,
    RiskFactor,
    RiskLevel,
    WeatherRisk,
)

MIN_SCORE = 0
MAX_SCORE = 100
LOW_MAX = 29
MODERATE_MAX = 59
HIGH_MAX = 79


@dataclass(frozen=True)
class Tier:
    threshold: float
    points: int
    impact: RiskLevel


# Ordered mild -> severe; the most severe matching tier wins.
GUST_TIERS_KMH = (
    Tier(35, 5, RiskLevel.LOW),
    Tier(50, 10, RiskLevel.MODERATE),
    Tier(65, 15, RiskLevel.HIGH),
    Tier(80, 20, RiskLevel.SEVERE),
)
WIND_TIERS_KMH = (
    Tier(25, 3, RiskLevel.LOW),
    Tier(40, 6, RiskLevel.MODERATE),
    Tier(55, 8, RiskLevel.HIGH),
    Tier(70, 10, RiskLevel.SEVERE),
)
PRECIP_TIERS_MM_H = (
    Tier(2.5, 4, RiskLevel.LOW),
    Tier(7.5, 8, RiskLevel.MODERATE),
    Tier(15, 12, RiskLevel.HIGH),
    Tier(30, 15, RiskLevel.SEVERE),
)
PRECIP_PROB_TIERS_PCT = (
    Tier(40, 2, RiskLevel.LOW),
    Tier(60, 4, RiskLevel.MODERATE),
    Tier(80, 7, RiskLevel.HIGH),
    Tier(95, 10, RiskLevel.SEVERE),
)
# Lower visibility is worse (value <= threshold).
VISIBILITY_TIERS_M = (
    Tier(5000, 3, RiskLevel.LOW),
    Tier(2000, 7, RiskLevel.MODERATE),
    Tier(1000, 11, RiskLevel.HIGH),
    Tier(500, 15, RiskLevel.SEVERE),
)
# WMO weather codes: code -> (label, points, impact)
SEVERE_WEATHER_CODES: dict[int, tuple[str, int, RiskLevel]] = {
    45: ("Fog", 5, RiskLevel.MODERATE),
    48: ("Depositing rime fog", 5, RiskLevel.MODERATE),
    65: ("Heavy rain", 10, RiskLevel.HIGH),
    67: ("Heavy freezing rain", 10, RiskLevel.HIGH),
    82: ("Violent rain showers", 12, RiskLevel.HIGH),
    95: ("Thunderstorm", 20, RiskLevel.HIGH),
    96: ("Thunderstorm with slight hail", 30, RiskLevel.SEVERE),
    99: ("Thunderstorm with heavy hail", 30, RiskLevel.SEVERE),
}


def level_for_score(score: int) -> RiskLevel:
    if score <= LOW_MAX:
        return RiskLevel.LOW
    if score <= MODERATE_MAX:
        return RiskLevel.MODERATE
    if score <= HIGH_MAX:
        return RiskLevel.HIGH
    return RiskLevel.SEVERE


def _present(values: Iterable[float | None]) -> list[float]:
    return [v for v in values if v is not None]


def _pick_tier(
    value: float, tiers: Sequence[Tier], *, higher_is_worse: bool = True
) -> Tier | None:
    matched: Tier | None = None
    for tier in tiers:
        hit = value >= tier.threshold if higher_is_worse else value <= tier.threshold
        if hit:
            matched = tier
    return matched


def _tiered_factor(
    name: str,
    unit: str,
    value: float | None,
    tiers: Sequence[Tier],
    *,
    higher_is_worse: bool = True,
) -> RiskFactor | None:
    if value is None:
        return None
    tier = _pick_tier(value, tiers, higher_is_worse=higher_is_worse)
    if tier is None:
        return None
    return RiskFactor(
        factor=name, value=value, unit=unit, impact=tier.impact, points=tier.points
    )


def _weather_code_factor(codes: Iterable[int | None]) -> RiskFactor | None:
    worst: tuple[int, str, int, RiskLevel] | None = None
    for code in codes:
        if code is None or code not in SEVERE_WEATHER_CODES:
            continue
        label, points, impact = SEVERE_WEATHER_CODES[code]
        if worst is None or points > worst[2]:
            worst = (code, label, points, impact)
    if worst is None:
        return None
    code, label, points, impact = worst
    return RiskFactor(
        factor="Severe weather condition",
        value=code,
        unit="WMO code",
        impact=impact,
        points=points,
        detail=label,
    )


def calculate_weather_risk(
    current: CurrentWeather | None, forecast: Sequence[ForecastPoint]
) -> WeatherRisk:
    """Score the worst conditions across current + forecast window."""
    observations: list[CurrentWeather | ForecastPoint] = [
        *([current] if current else []),
        *forecast,
    ]
    gust = _present(o.wind_gust_kmh for o in observations)
    wind = _present(o.wind_speed_kmh for o in observations)
    precip = _present(o.precipitation_mm for o in observations)
    prob = _present(getattr(o, "precipitation_probability", None) for o in observations)
    visibility = _present(o.visibility_m for o in observations)
    codes = [o.weather_code for o in observations]

    if not any((gust, wind, precip, prob, visibility, _present(codes))):
        return WeatherRisk()

    candidates = (
        _tiered_factor("Wind gusts", "km/h", max(gust, default=None), GUST_TIERS_KMH),
        _tiered_factor("Wind speed", "km/h", max(wind, default=None), WIND_TIERS_KMH),
        _tiered_factor(
            "Precipitation", "mm/h", max(precip, default=None), PRECIP_TIERS_MM_H
        ),
        _tiered_factor(
            "Precipitation probability", "%", max(prob, default=None),
            PRECIP_PROB_TIERS_PCT,
        ),
        _tiered_factor(
            "Visibility", "m", min(visibility, default=None), VISIBILITY_TIERS_M,
            higher_is_worse=False,
        ),
        _weather_code_factor(codes),
    )
    factors = [f for f in candidates if f is not None]
    score = max(MIN_SCORE, min(MAX_SCORE, sum(f.points for f in factors)))
    return WeatherRisk(score=score, level=level_for_score(score), factors=factors)
