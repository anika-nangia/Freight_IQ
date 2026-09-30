# Model 2 - Freight Rate Forecaster: Model Card

Trained 2026-09-30T10:19:48+00:00 | target `log(rate[t+2w] / rate[t])` | loss asymmetric, alpha=2.5 under-forecast / beta=1.0 over-forecast

## Validation
walk-forward refit every week, min 12 training weeks, scored on the unseen week only.
220 rows, 11 lanes, 20 weeks (2025-10-31 to 2026-03-13). Scored on 88 out-of-sample rows across 8 weeks.

## Candidates (walk-forward, out-of-sample)

| model | asym regret | MAE $/MT | RMSE $/MT | MAPE % | direction acc % |
|---|---|---|---|---|---|
| persistence | 0.2758 | 3.341 | 5.066 | 9.66 | n/a |
| arima | 0.2465 | 3.065 | 4.740 | 9.06 | 80 |
| ridge | 0.2511 | 4.504 | 6.898 | 16.16 | 83 |
| xgb | 0.2245 | 3.134 | 4.704 | 9.79 | 86 |

## Deployed model: `xgb`
Asymmetric regret +18.6% versus persistence on a single seed.

### Is that difference real?

Paired bootstrap over 8 out-of-sample weeks: regret improvement **+0.0716**, 95% CI [+0.0173, +0.1453].

Verdict: **xgb reliably better than persistence**.

### Quote this as a range, not a point

Across 4 seeds the regret reduction is **+17.5% to +19.8%**.

| candidate | regret range across seeds | spread |
|---|---|---|
| persistence | 0.2758 to 0.2758 | 0.0000 |
| arima | 0.2465 to 0.2465 | 0.0000 |
| ridge | 0.2511 to 0.2511 | 0.0000 |
| xgb | 0.2213 to 0.2276 | 0.0063 |

Only 8 out-of-sample weeks. The regret reduction moves between 17.5% and 19.8% across seeds, so quote the range. The ranking (XGBoost ahead of ARIMA, Ridge and persistence) is stable, the margins are not large.

## Intervals
Conformal, from walk-forward residuals, with the upper band widened for the 2.5x under-forecast penalty.

| coverage | lower offset | upper offset |
|---|---|---|
| p50 | 0.0616 | 0.0973 |
| p80 | 0.1665 | 0.2632 |
| p90 | 0.2540 | 0.4016 |

## Feature-group ablation

Reference: `xgb` at regret 0.22446.

A group is called helpful only when the paired bootstrap over weeks puts the regret difference above zero at 95%. A point estimate alone is not evidence: the differences here are of the same order as week-to-week noise, and a zero-tolerance rule gave verdicts that flipped between machines.

| group | regret without it | 95% CI on the difference | verdict |
|---|---|---|---|
| momentum | 0.2465 | [-0.1364, +0.0001] | no reliable effect (95% interval spans zero) |
| weather | 0.2230 | [-0.0092, +0.0054] | no reliable effect (95% interval spans zero) |
| commodity | 0.2221 | [-0.0103, +0.0073] | no reliable effect (95% interval spans zero) |
| baltic | - | - | not testable: no feature from this group survived panel pruning |
| level | 0.2222 | [-0.0264, +0.0138] | no reliable effect (95% interval spans zero) |

Features **excluded** from the deployed model: momentum, weather, commodity, baltic, level.

The practical reading: the only finding that survives a noise floor is that a fitted model beats persistence. Which features produce that is not established on 8 out-of-sample weeks, and should not be asserted to a reviewer.


## Regime robustness

Training-move 75th percentile: 0.0582 log-return.

| regime | rows | regret | MAE $/MT |
|---|---|---|---|
| high-volatility | 36 | 0.4547 | 5.704 |
| normal | 52 | 0.0651 | 1.354 |

This is the check the earlier single-split run could not do. If the two regimes differ sharply, the headline number describes the calm period only.

## Provenance

- Target rates: observed (project dataset, upstream publication unconfirmed)
- Features in the deployed model: ret_1w, ret_2w, ret_4w, roll_cv_8w, dev_from_mean_4w, log_rate, log_rate_vs_class, load_port_code, vessel_class_code, coal_aus_ret_4w, coal_saf_ret_4w, iron_ore_ret_4w, crude_oil_ret_4w, coal_aus_level, coal_saf_level, iron_ore_level, crude_oil_level, wind_max_kt, log_precip, rainy_days
- Fetched but excluded: momentum, weather, commodity, baltic, level
- Market data: World Bank Pink Sheet and Open-Meteo, both observed, but the ablation shows they do not add to the forecast at this sample size
- Baltic index features: unavailable - no free source reachable

## Known limits

1. Rate source publication is unconfirmed. Metrics inherit that uncertainty.
2. ~26 weeks of history. This is a short panel, not a market database.
3. Lanes are port pairs, not terminals. No terminal-level rate differences are invented.
4. Deliberately excluded: month_sin, month_cos, weeks_since_start, ret_8w - too little history for a seasonality claim.
5. Weekly rows inside one week are correlated, so the effective sample is weeks, not rows.
