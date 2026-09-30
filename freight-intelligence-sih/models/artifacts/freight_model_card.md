# Model 2 - Freight Rate Forecaster: Model Card

Trained 2026-09-30T19:19:14+00:00 | target `log(rate[t+2w] / rate[t])` | loss asymmetric, alpha=2.5 under-forecast / beta=1.0 over-forecast

## Validation
walk-forward refit every week, min 12 training weeks, scored on the unseen week only.
220 rows, 11 lanes, 20 weeks (2025-10-31 to 2026-03-13). Scored on 88 out-of-sample rows across 8 weeks.

## Candidates (walk-forward, out-of-sample)

| model | asym regret | MAE $/MT | RMSE $/MT | MAPE % | direction acc % |
|---|---|---|---|---|---|
| persistence | 0.2758 | 3.341 | 5.066 | 9.66 | n/a |
| arima | 0.2465 | 3.065 | 4.740 | 9.06 | 80 |
| ridge | 0.2439 | 3.996 | 5.719 | 13.87 | 79 |
| xgb | 0.2226 | 3.087 | 4.652 | 9.79 | 89 |

## Deployed model: `xgb`
Asymmetric regret +19.3% versus persistence on a single seed.

### Is that difference real?

Paired bootstrap over 8 out-of-sample weeks: regret improvement **+0.0696**, 95% CI [+0.0193, +0.1335].

Verdict: **xgb reliably better than persistence**.

### Quote this as a range, not a point

Across 4 seeds the regret reduction is **+18.0% to +19.3%**.

| candidate | regret range across seeds | spread |
|---|---|---|
| persistence | 0.2758 to 0.2758 | 0.0000 |
| arima | 0.2465 to 0.2465 | 0.0000 |
| ridge | 0.2440 to 0.2440 | 0.0000 |
| xgb | 0.2226 to 0.2263 | 0.0037 |

Only 8 out-of-sample weeks. The regret reduction moves between 18.0% and 19.3% across seeds, so quote the range. The ranking (XGBoost ahead of ARIMA, Ridge and persistence) is stable, the margins are not large.

## Intervals
Conformal, from walk-forward residuals, with the upper band widened for the 2.5x under-forecast penalty.

| coverage | lower offset | upper offset |
|---|---|---|
| p50 | 0.0588 | 0.0929 |
| p80 | 0.1624 | 0.2568 |
| p90 | 0.2390 | 0.3780 |

## Feature-group ablation

Reference: `xgb` at regret 0.22256.

A group is called helpful only when the paired bootstrap over weeks puts the regret difference above zero at 95%. A point estimate alone is not evidence: the differences here are of the same order as week-to-week noise, and a zero-tolerance rule gave verdicts that flipped between machines.

| group | regret without it | 95% CI on the difference | verdict |
|---|---|---|---|
| weather_nowcast | - | - | not testable: pre-registered experiment, and the result is NOT stable. With the full 33-feature set, discharge nowcast made the model worse (0.2318 vs 0.2299 with no weather). With the reduced 9-feature set it was better by 1.3% (0.2204 vs 0.2226). A verdict that flips when an unrelated group is added is noise, not signal. Withheld because no reliable effect was established, not because it was proven harmful. |
| weather_origin | - | - | not testable: same pre-registered experiment, same instability: worse on the full set (0.2333), better by 0.7% on the reduced set. Withheld for the same reason. Note the coordinates are unverified reference geography. |
| commodity | - | - | not testable: pre-registered and ablation: World Bank coal, iron ore and oil are global series that do not move with these corridors over a 20-week window. Removing them improved regret in the ablation. |
| baltic | - | - | not testable: measured: inclusion worsened XGBoost (0.2245 -> 0.2376) and Ridge (0.2511 -> 0.2770). Only composite BDI was supplied (no BCI/BPI/BSI/BHSI), and BDI is Capesize-weighted while these lanes are Supramax/Panamax/Handymax, so it is a weak proxy for this freight. |

Features **excluded** from the deployed model: momentum, weather_nowcast, weather_origin, commodity, baltic, level.

The practical reading: the only finding that survives a noise floor is that a fitted model beats persistence. Which features produce that is not established on 8 out-of-sample weeks, and should not be asserted to a reviewer.


## Regime robustness

Training-move 75th percentile: 0.0582 log-return.

| regime | rows | regret | MAE $/MT |
|---|---|---|---|
| high-volatility | 36 | 0.4516 | 5.627 |
| normal | 52 | 0.0640 | 1.328 |

This is the check the earlier single-split run could not do. If the two regimes differ sharply, the headline number describes the calm period only.

## Provenance

- Target rates: observed (project dataset, upstream publication unconfirmed)
- Features in the deployed model: ret_1w, ret_2w, ret_4w, roll_cv_8w, dev_from_mean_4w, log_rate, log_rate_vs_class, load_port_code, vessel_class_code
- Fetched but excluded: momentum, weather_nowcast, weather_origin, commodity, baltic, level
- Market data: World Bank Pink Sheet and Open-Meteo, both observed, but the ablation shows they do not add to the forecast at this sample size
- Baltic index features: unavailable - no free source reachable

## Known limits

1. Rate source publication is unconfirmed. Metrics inherit that uncertainty.
2. ~26 weeks of history. This is a short panel, not a market database.
3. Lanes are port pairs, not terminals. No terminal-level rate differences are invented.
4. Deliberately excluded: month_sin, month_cos, weeks_since_start, ret_8w - too little history for a seasonality claim.
5. Weekly rows inside one week are correlated, so the effective sample is weeks, not rows.
