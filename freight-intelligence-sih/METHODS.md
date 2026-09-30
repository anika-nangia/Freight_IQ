# Methods and Validation Report

FreightIQ dry bulk chartering decision support. This document states what the system
knows, how it was validated, and where it should not be trusted.

Regenerate everything with `python run_pipeline.py`. Read the machine-readable version
of this report at `GET /api/model-report` and the data-coverage panel at
`GET /api/data-coverage`.

---

## 1. Summary of results

| Model | Target | Validation | Result |
|---|---|---|---|
| Model 2, freight rate | log rate at t+2 weeks | walk-forward refit weekly, 8 unseen weeks, 88 rows | XGBoost, **18.8% lower asymmetric regret than persistence** |
| Model 1, congestion | turnaround days (ETCD − arrival) | last 3 snapshot dates held out, 381 rows | Gradient boosting, **ties the port-median baseline (−0.6% MAE, +4.0% RMSE)** |

Model 1 is reported as a tie on purpose. A 0.6% MAE difference on three held-out dates
is inside noise, and the model card says so rather than quoting the flattering R².

---

## 2. Data, and how much of it is real

| Dataset | Tier | Period | Rows | Source |
|---|---|---|---|---|
| Route freight rates | observed, **provenance unconfirmed** | 2025-10-03 → 2026-03-27 | 286 | Project dataset, upstream publication unknown |
| Port vessel line-ups | observed | 2026-08-10 → 2026-08-31 | 3,133 | Port authority daily reports |
| Berth status | observed | 2026-08-10 → 2026-08-31 | 452 | Port authority berth reports |
| Port constraints | observed | static | 7 ports | Published berth capability |
| Loading terminal limits | observed | static | 13 terminals | Terminal operators, per-row source URL |
| Vessel class specs | observed | static | 5 classes | Class reference data |
| World Bank Pink Sheet | observed | 1960 → 2025-12 | 792 months | World Bank, CC-BY 4.0 |
| Port weather | observed | 2025-09-01 → 2026-09-30 | 2,765 | Open-Meteo, CC-BY 4.0 |
| USD/INR | observed | 2023-12-29 → 2026-09-29 | 702 | ECB via Frankfurter |
| **Baltic sub-indices** | **unavailable** | — | 0 | Subscription only |

Three free sources are fetched and cached, so the models rest partly on data with a
public provenance. **Baltic sub-indices have no free redistribution route.** Every
endpoint was tried at build time:

| Source | Result |
|---|---|
| investing.com | HTTP 403, Cloudflare challenge |
| stooq.com | JavaScript challenge page |
| FRED | connection timeout from this network |
| balticexchange.com | bot challenge page |
| Yahoo Finance | no listing for ^BDI, ^BCI, ^BPI, ^BSI, ^BHSI |

The loader `data_pipeline/fetchers/bdi_subindices.py` therefore scrapes nothing and
ships no default. Supply a CSV and the feature group switches on automatically.

### The unresolved provenance gap

`data/training_matrix.csv` is treated as observed, but the publication it was compiled
from has not been confirmed. **Every Model 2 metric inherits that uncertainty.** If the
rates were estimated rather than assessed, the model's accuracy measures how well it
fits whatever produced them. This is the single most important thing to resolve, and
the fastest route is asking whoever committed the file.

Two properties of that file are worth checking against the source report: week-to-week
autocorrelation is roughly 0.93 on most corridors, and each corridor carries exactly one
cargo size across all 26 weeks. Both are consistent with a compiled weekly report, and
neither rules out an estimate.

---

## 3. Leakage controls

Each is asserted in `tests/test_integrity.py`.

1. **Backward-looking lags only.** `ret_kw` is `log(rate_t / rate_{t−k})`, verified per
   lane against a recomputation.
2. **Publication lag on commodity prices.** The World Bank Pink Sheet publishes with
   roughly a two-month lag, so the whole price frame is shifted one month before
   joining. Without it, a row dated month M would see a price it could not have known.
3. **As-of joins.** Weather and Baltic features are joined as-of backward on the week
   start, never forward-matched.
4. **Chronological splits only.** Both models hold out whole dates. A random row split
   would put near-duplicates on both sides, because every vessel at a port on one day
   shares identical congestion features.
5. **Targets dropped before fitting.** Rows without an outcome never enter training.
6. **Month sin/cos excluded.** With ~26 weeks of history they act as a time index. An
   earlier run ranked them first among features and then failed to extrapolate.

---

## 4. Model 2: freight rate forecasting

**Target** `log(rate[t+2w] / rate[t])`, scale-free across corridors priced \$15–\$58/MT.
**Loss** asymmetric, under-forecast penalised 2.5×, because a missed spike means booking
after the market has already moved. The gradient sign is asserted directly in the tests,
because an earlier version had it reversed and pushed under-forecasts further down.

**Validation** walk-forward: refit every week, score only the unseen week. 8 out-of-sample
weeks, 88 rows.

| Candidate | Asym. regret | MAE \$/MT | RMSE \$/MT | Direction acc. |
|---|---|---|---|---|
| Persistence (no change) | 0.2758 | 3.34 | 5.07 | n/a |
| Per-lane ARIMA(0,1,1) | 0.2465 | 3.07 | 4.74 | 80% |
| Ridge | 0.2511 | 4.50 | 6.90 | 83% |
| **XGBoost (deployed)** | **0.2245** | **3.13** | **4.70** | **86%** |

### The ablation is the important result

Feature importance said weather was the strongest driver. The ablation disagreed:

| Group | Regret without it | Verdict |
|---|---|---|
| Momentum | 0.2465 | **helps** |
| Weather | 0.2230 | no measurable benefit |
| Commodity | 0.2221 | no measurable benefit |
| Baltic | — | not testable, no data |
| Level | 0.2222 | no measurable benefit |

Removing weather made regret *marginally better*. Over a five-month window rainfall is
largely a proxy for the monsoon, and a tree will use it to identify the period rather
than to explain a rate. **The deployed model therefore uses momentum features only.**
Presenting the full model would have meant telling a reviewer that rain drives freight
rates, which the data does not support.

This is a real result, not a caveat. The lane history is the signal; the market data we
attached does not add to it at this sample size.

### Regime check

Split by whether the realised move exceeded the training-period 75th percentile:

| Regime | Rows | Regret | MAE \$/MT |
|---|---|---|---|
| High volatility | 36 | 0.444 | 5.64 |
| Normal | 52 | 0.071 | 1.51 |

The model degrades sharply in the high-volatility regime. The headline number describes
the calmer half of the sample. This is the check the earlier single-split run could not
perform.

### Intervals

Split-conformal on walk-forward residuals, with the upper band widened by √(2.5) to
protect the asymmetric penalty. Offsets increase with coverage, asserted in tests.

---

## 5. Model 1: port congestion and turnaround

**Target** `turnaround_days = ETCD − arrival`, observed per vessel. 1,608 real
observations, 11 ports, 12 August 2026 snapshot dates.

| Candidate | MAE (days) | RMSE (days) | R² |
|---|---|---|---|
| Port-median baseline | 2.31 | 3.95 | −0.031 |
| **Gradient boosting (deployed)** | 2.33 | **3.79** | **0.050** |
| Random forest | 2.61 | 3.87 | 0.010 |

**This is a tie.** The previous implementation returned a hardcoded `r2: 0.884` from a
function that read no data at all. The honest reading: on three held-out dates the model
shows no demonstrated gain over knowing a port's normal turnaround. It is deployed
because it also uses queue and occupancy, which a static median ignores, and it degrades
sensibly on an unseen port. Predictions are reported as ranges from measured residual
quantiles, not as bare points.

---

## 6. What was removed, and why

| Removed | Reason |
|---|---|
| `predict_freight.py` `BASE_RATES` | Invented rates: `australia-paradip: 15.10`, with `18.20` returned for any unknown corridor |
| Hand-written "SHAP breakdown" | Multiplication of hand-picked coefficients, not model output. Replaced with leave-one-out contributions from the fitted booster |
| `train_congestion.py` metrics | Hardcoded `r2: 0.884`, `n_samples: 450` from a function that fitted nothing |
| `fx_market_api.py` | Returned `bdi: 1842`, `usd_inr: 83.42` as constants. BDI has no free source and is now marked unavailable; FX comes from ECB |
| Both Firecrawl scrapers | Simulated. The berth scraper fed invented queues into congestion scoring |
| Both PDF parsers | Returned hardcoded dictionaries. The ISS parser supplied fabricated MMT traffic figures that drove deadhead risk |
| `iss_report_parser` traffic figures | Fed invented inbound/outbound ratios into the idle analysis |
| Repositioning opportunity list | Claimed specific profit figures (e.g. "net profit gain 41,200 USD" ballasting Haldia to Dhamra) present in no source file and not derivable from the line-ups |
| News disruption feed | Three hardcoded items with fixed dates, so risk tier never changed |
| `distance_km: 2147 if ... else 3850` in `main.py` | Hardcoded. Now computed from port coordinates, and flagged as assumed when either endpoint lacks them |
| `train_model()` per API request | Retrained on every call. Metrics now load from files; asserted by a test |
| Four modules importing a non-existent `app` package | Could not run at all |

The news scraper and the PDF parsers are the consequential removals: they were not
merely unused, they were feeding fabricated inputs into the risk and idle outputs, which
is worse than having no feature.

---

## 7. Data-quality conflicts found and how they are handled

**"Waiting & Expected" is ambiguous.** At Paradip all 40 listed vessels carry that
status with none berthed. Counted verbatim it produced a queue of 40 against zero
working vessels and a congestion score with no operational meaning. Only vessels whose
arrival date is on or before the snapshot are now counted as queued.

**Port data contradicts itself.** `port_constraints.csv` gives Haldia an 8.5 m draft
limit while also declaring Handysize its largest admitted class, yet the smallest class
reference draft is 10.0 m. Applied naively this rejects every vessel at a port that
publishes a class. The published class is treated as the authority for admissibility,
the numeric limits gate anything larger, and the conflict is reported in the response
rather than resolved silently.

**Constant features passed a null check.** `gale_days` and `cyclone_days` were entirely
zero across the window, yet survived a not-null test and reached the model as real
features. The panel now drops columns with a single unique value.

**A silent join failure.** Commodity features were 0% populated because weekly dates
never exact-match a monthly price index. The join was rewritten as-of backward, and
monthly momentum is computed on the monthly series before joining, otherwise every
weekly row inherits the same monthly change.

**Inverted conformal quantiles.** The first implementation used the (1−c) quantile,
producing a p50 band wider than p90. Corrected, with monotonicity asserted.

**A false 0% on the baseline.** Persistence predicts exactly zero, so scoring
`sign(0)` against a real move always missed, making the strongest baseline look
directionally useless. Persistence now reports `null` for direction.

---

## 8. Known limits

1. **Rate provenance is unconfirmed.** The largest single caveat. See §2.
2. **~20 weeks of lane history.** Short for a freight market. 11 corridors, 2 origin
   clusters (China and the Black Sea), 1 discharge region pair. There is no US,
   Australia, Indonesia, Mozambique or Handysize rate history, so the API returns
   "no rate history" for those lanes rather than a proxy number.
3. **6 monthly points per corridor.** No monthly model is fitted, because it could not
   be validated. The 1–6 month contract path is an extrapolation of the validated
   weekly model, labelled `derived_path`, with the interval scaled by √horizon.
4. **12 snapshot dates in one month.** Model 1's evaluation is 3 held-out dates. It is a
   direction check, not a performance claim.
5. **Model 1 does not beat its baseline.** Stated above rather than buried.
6. **Weather is confounded with the monsoon** over this window, and the ablation shows
   it adds nothing. It is excluded from the deployed model.
7. **Port dues are a placeholder.** No tariff data is held. It changes the cost ranking
   between similar classes. It does not affect feasibility, which depends only on
   physical limits.
8. **Idle repositioning is not quoted.** It would need rate and distance data for
   candidate ports.
9. **Demurrage, hotel bunkers, and speed are business assumptions**, returned in the
   API response so a caller can substitute their own.
10. **Rows within a week are correlated**, so the effective sample size is weeks, not
    rows.

---

## 9. What would most improve the system

Ranked by expected gain per unit of effort.

1. **Confirm the rate source.** Everything in Model 2 rests on it.
2. **Add route rates for the missing lanes.** US, Australia, Indonesia, Mozambique and
   Handysize currently return "no rate history". This is the binding constraint on
   coverage, not on accuracy.
3. **Supply the Baltic CSV.** BCI, BPI, BSI and BHSI are the natural class-level
   features, and Junaid's own audit found BDI did *not* help his ARIMA, so measure it
   rather than assume it.
4. **Extend the line-up history past August 2026.** Model 1 needs more dates before its
   evaluation means anything.
5. **Get terminal-level rate data.** Rates are currently port-pair level, so no
   terminal-level differences are invented.
6. **Add port tariffs** to replace the dues placeholder in the cost ranking.
