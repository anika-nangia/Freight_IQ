from app.schemas.weather import CurrentWeather, ForecastPoint, RiskLevel
from app.services import weather_risk as wr
from app.services.weather_risk import calculate_weather_risk


def point(**kw) -> ForecastPoint:
    return ForecastPoint(datetime="2026-09-29T12:00", **kw)


def test_low_case():
    risk = calculate_weather_risk(
        CurrentWeather(wind_speed_kmh=10, wind_gust_kmh=15, visibility_m=20000, weather_code=1),
        [point(precipitation_probability=10, precipitation_mm=0)],
    )
    assert risk.level == RiskLevel.LOW
    assert risk.score == 0
    assert risk.factors == []


def test_moderate_case():
    risk = calculate_weather_risk(
        None,
        [point(wind_gust_kmh=55, wind_speed_kmh=45, precipitation_mm=8,
               precipitation_probability=70, visibility_m=1800)],
    )
    assert risk.level == RiskLevel.MODERATE
    assert 30 <= risk.score <= 59


def test_high_case():
    risk = calculate_weather_risk(
        None,
        [point(wind_gust_kmh=70, wind_speed_kmh=60, precipitation_mm=20,
               precipitation_probability=90, visibility_m=900, weather_code=95)],
    )
    assert risk.level == RiskLevel.HIGH
    assert 60 <= risk.score <= 79
    assert {f.factor for f in risk.factors} >= {"Wind gusts", "Visibility"}


def test_score_clamped_at_100_and_severe():
    risk = calculate_weather_risk(
        None,
        [point(wind_gust_kmh=200, wind_speed_kmh=150, precipitation_mm=100,
               precipitation_probability=100, visibility_m=10, weather_code=99)],
    )
    assert risk.score == 100
    assert risk.level == RiskLevel.SEVERE


def test_max_tier_points_sum_to_exactly_100():
    total = sum(
        max(t.points for t in tiers)
        for tiers in (wr.GUST_TIERS_KMH, wr.WIND_TIERS_KMH, wr.PRECIP_TIERS_MM_H,
                      wr.PRECIP_PROB_TIERS_PCT, wr.VISIBILITY_TIERS_M)
    ) + max(p for _, p, _ in wr.SEVERE_WEATHER_CODES.values())
    assert total == wr.MAX_SCORE


def test_score_always_within_bounds():
    for gust in (0, 30, 60, 90, 300):
        risk = calculate_weather_risk(None, [point(wind_gust_kmh=gust, visibility_m=100)])
        assert 0 <= risk.score <= 100


def test_no_data_is_unknown_not_low():
    risk = calculate_weather_risk(None, [point()])
    assert risk.level == RiskLevel.UNKNOWN
    assert risk.score is None


def test_uses_worst_case_across_window():
    risk = calculate_weather_risk(
        CurrentWeather(wind_gust_kmh=10),
        [point(wind_gust_kmh=10), point(wind_gust_kmh=66)],
    )
    gust = next(f for f in risk.factors if f.factor == "Wind gusts")
    assert gust.value == 66 and gust.impact == RiskLevel.HIGH


def test_disclaimer_present():
    assert "not an official maritime safety" in calculate_weather_risk(None, [point(wind_gust_kmh=40)]).disclaimer
