# Model 2 - Freight Rate Forecaster: Model Card

Trained 2026-09-30T07:19:38+00:00 | target `log(rate[t+2w] / rate[t])` | loss asymmetric, alpha=2.5 under-forecast / beta=1.0 over-forecast

## Validation
walk-forward refit every week, min 12 training weeks, scored on the unseen week only.
220 rows, 11 lanes, 20 weeks (2025-10-31 to 2026-03-13). Scored on 88 out-of-sample rows across 8 weeks.

## Candidates (walk-forward, out-of-sample)

| model | asym regret | MAE $/MT | RMSE $/MT | MAPE % | direction acc % |
|---|---|---|---|---|---|
| persistence | 0.2758 | 3.341 | 5.066 | 9.66 | n/a |
| arima | 0.2465 | 3.065 | 4.740 | 9.06 | 80 |
| ridge | 0.2453 | 3.977 | 5.697 | 13.71 | 77 |
| xgb | 0.2240 | 3.121 | 4.670 | 9.69 | 90 |

## Deployed model: `xgb`
Asymmetric regret +18.8% versus persistence.

## Intervals
Conformal, from walk-forward residuals, with the upper band widened for the 2.5x under-forecast penalty.

| coverage | lower offset | upper offset |
|---|---|---|
| p50 | 0.0610 | 0.0964 |
| p80 | 0.1643 | 0.2597 |
| p90 | 0.2650 | 0.4190 |

## Feature-group ablation

Reference: `xgb` at regret 0.22446. positive regret_delta means the model got WORSE without the group, i.e. the group helped.

| group | regret without it | delta | verdict |
|---|---|---|---|
| momentum | 0.2465 | +0.0220 | helps |
| weather | 0.2230 | -0.0014 | no measurable benefit |
| commodity | 0.2221 | -0.0024 | no measurable benefit |
| baltic | - | - | not testable: no feature from this group survived panel pruning |
| level | 0.2222 | -0.0023 | no measurable benefit |

**The deployed model uses only: ret_1w, ret_2w, ret_4w, roll_cv_8w, dev_from_mean_4w.**

Groups **weather, commodity, baltic, level** are excluded from the deployed model. Feature importance ranked weather at the top, but removing it changed regret by roughly 0.001, i.e. not at all. Over five months rainfall is largely a proxy for the monsoon, and a tree will use it to identify the period rather than to explain a rate. Importance is not contribution, and this is the difference between the two.

A group that shows no measurable benefit is not evidence of a driver. It is evidence that the model found another way to reach the same answer.


## Regime robustness

Training-move 75th percentile: 0.0582 log-return.

| regime | rows | regret | MAE $/MT |
|---|---|---|---|
| high-volatility | 36 | 0.4593 | 5.682 |
| normal | 52 | 0.0612 | 1.349 |

This is the check the earlier single-split run could not do. If the two regimes differ sharply, the headline number describes the calm period only.

## Provenance

- Target rates: observed (project dataset, upstream publication unconfirmed)
- Features in the deployed model: ret_1w, ret_2w, ret_4w, roll_cv_8w, dev_from_mean_4w
- Fetched but excluded: weather, commodity, baltic, level
- Market data: World Bank Pink Sheet and Open-Meteo, both observed, but the ablation shows they do not add to the forecast at this sample size
- Baltic index features: unavailable - no free source reachable

## Known limits

1. Rate source publication is unconfirmed. Metrics inherit that uncertainty.
2. ~26 weeks of history. This is a short panel, not a market database.
3. Lanes are port pairs, not terminals. No terminal-level rate differences are invented.
4. Deliberately excluded: month_sin, month_cos, weeks_since_start, ret_8w - too little history for a seasonality claim.
5. Weekly rows inside one week are correlated, so the effective sample is weeks, not rows.
