# Model 1 - Port Congestion & Turnaround: Model Card

Trained 2026-09-30T07:15:16+00:00 | target `turnaround_days (ETCD - arrival, observed per vessel)`

1608 observed vessel turnarounds across 11 ports and 12 snapshot dates.

## Validation
chronological block split, last 3 snapshot dates held out entirely.

Whole dates are held out rather than random rows, because every vessel at a port on one day shares identical congestion features. A random row split puts near-duplicates on both sides and inflates the score.

| model | MAE (days) | RMSE (days) | R2 | bias (days) |
|---|---|---|---|---|
| port_median_baseline | 2.31 | 3.95 | -0.031 | -1.28 |
| global_median_baseline | 2.55 | 4.29 | -0.216 | -1.81 |
| gradient_boosting | 2.33 | 3.79 | 0.050 | -0.70 |
| random_forest | 2.61 | 3.87 | 0.010 | -0.02 |

## Deployed model: `gradient_boosting`

MAE vs port-median baseline: **-0.6%** (RMSE +4.0%).

**Reading this honestly:** The model ties the port-median baseline on MAE (-0.6%) and is +4.0% on RMSE. On 3 held-out snapshot dates that margin is inside noise, so this should be read as 'no demonstrated modelling gain over knowing the port's normal turnaround'. The model is deployed because it also uses queue and occupancy, which a static median ignores, and it degrades gracefully on a port it has never seen.

Residual quantiles (days): p50 -0.461, p80 1.705, p90 4.456. Live predictions are reported as a range built from these, not as a bare point.

## Observed vs predicted turnaround, by port (held-out dates)

| port | n | observed median | predicted median |
|---|---|---|---|
| KRISHNAPATNAM | 86 | 4.0 | 4.0 |
| HALDIA | 58 | 3.5 | 3.67 |
| VISAKHAPATNAM | 56 | 5.0 | 5.35 |
| ENNORE | 48 | 2.5 | 3.57 |
| DHAMRA | 45 | 5.0 | 5.22 |
| CHENNAI | 40 | 2.0 | 2.7 |
| GANGAVARAM | 30 | 2.0 | 3.79 |
| GOPALPUR | 6 | 8.0 | 5.87 |
| KARAIKAL | 5 | 3.0 | 3.27 |
| SAGAR | 4 | 2.0 | 3.84 |
| KATTUPALLI | 3 | 4.0 | 3.34 |

## Provenance

- Target: observed (port authority line-up: arrival and ETCD per vessel)
- Features: observed (same line-up) + Open-Meteo weather

## Known limits

1. Only 12 snapshot dates in one month. The held-out set is 3 dates, so this is a sanity check on direction, not a performance claim.
2. ETCD is reported by the port and its accuracy is not verifiable here.
3. Turnaround is only observable once a vessel completes discharge, so recent snapshots contribute fewer completed voyages. The chronological split puts those dates in the test set, which is the honest arrangement.
4. A turnaround figure describes a completed voyage. The live congestion SCORE is a separate, forward-looking quantity and is not this target.
