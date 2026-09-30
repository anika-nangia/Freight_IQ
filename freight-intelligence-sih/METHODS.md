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
| Model 2, freight rate | log rate at t+2 weeks | walk-forward refit weekly, 8 unseen weeks, 88 rows | XGBoost, **+18.0% to +19.3% regret vs persistence** (range over 4 seeds), CI excludes zero |
| Model 1, congestion | **port's estimate** of port stay | 3 held-out dates, 347 voyages, voyage-disjoint | **A per-port median wins. No fitted model beat it.** All R² negative |

Two results are negative and are reported as such:

- **Model 1 has no demonstrated modelling value.** Once the leakage was removed, every
  fitted candidate is worse than knowing a port's usual figure.
- **No feature group in Model 2 is statistically separable from zero**, including
  momentum. The only finding that survives a noise floor is that a fitted model beats
  persistence.

---

## 1a. Corrections to the previous version of this report

An earlier draft of this document claimed the deployed Model 2 used momentum features
only, and that weather and commodity features were shown not to help. **That claim has
been withdrawn.** It rested on a regret difference of about 0.002 with a zero-tolerance
rule (`helps = reg > base`), and the verdict flipped between machines. With a paired
bootstrap noise floor, no feature group's contribution is separable from zero on 8
out-of-sample weeks. The deployed model now uses the full feature set and the report
makes no per-feature claim.

The headline number was also quoted as a point. It is a range, because XGBoost's regret
moves between 0.2213 and 0.2276 across seeds.

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
| Ridge | 0.2439 | 4.00 | 5.72 | 79% |
| **XGBoost (deployed)** | **0.2226** | **3.09** | **4.65** | **89%** |

Direction accuracy is measured only on moves the training period treated as material;
persistence predicts exactly zero change, so scoring it on direction is meaningless and it
reports `null`.

### The ablation, and what it does and does not show

Feature importance ranked weather as the strongest driver. Importance is not
contribution, so each group is refit without it and the difference tested.

| Group | Regret without it | 95% CI on the difference | Verdict |
|---|---|---|---|
| Momentum | 0.2465 | [−0.1364, +0.0001] | no reliable effect |
| Weather | 0.2230 | [−0.0092, +0.0054] | no reliable effect |
| Commodity | 0.2221 | [−0.0103, +0.0073] | no reliable effect |
| Baltic | — | — | not testable, no data |
| Level | 0.2222 | [−0.0264, +0.0138] | no reliable effect |

**No group, including momentum, is separable from zero.** The previous version of this
analysis used a zero-tolerance rule and concluded "momentum only"; that conclusion is
withdrawn. Bootstrap resamples **weeks**, not rows, because the 11 lanes in a week share
a market and their errors are not independent.

The deployed model therefore uses the full feature set, and no per-feature claim is made.
On 8 out-of-sample weeks, *which* features produce the result is not established.

### Headline, quoted as a range

Paired bootstrap over the 8 out-of-sample weeks: regret improvement of XGBoost over
persistence **+0.0696, 95% CI [+0.0193, +0.1335]**. The interval excludes zero, so this
difference is real.

Across four seeds XGBoost's reduction over persistence ranges 0.180–0.193, i.e.
**+18.0% to +19.3%**. Quote the range, not the point. The ranking (XGBoost ahead of
ARIMA, Ridge and persistence) is stable across seeds and environments; the margin is
modest.


### Regime check

Split by whether the realised move exceeded the training-period 75th percentile:

| Regime | Rows | Regret | MAE \$/MT |
|---|---|---|---|
| High volatility | 36 | 0.452 | 5.63 |
| Normal | 52 | 0.064 | 1.33 |

The model degrades sharply in the high-volatility regime. The headline number describes
the calmer half of the sample. This is the check the earlier single-split run could not
perform.

### Intervals

Split-conformal on walk-forward residuals, with the upper band widened by √(2.5) to
protect the asymmetric penalty. Offsets increase with coverage, asserted in tests.

---

## 5. Model 1: port congestion

### The target is an estimate, not an outcome

`estimated_port_stay_days` = `etc_or_etcd − arrival_or_eta`, read at the first snapshot
where a vessel is recorded as Working.

**The source data contains no actual completion, departure or sailing field.** The only
status values are Expected / Waiting / Waiting & Expected / Working, so no voyage is
ever recorded as finished. A true turnaround needs an actual arrival and an actual
departure, and this dataset has neither. The quantity is therefore the **port's own
published schedule**, and a model fitted to it predicts what the port says.

That weakens the previous "beats the port median" framing in a specific way: beating a
per-port median of the port's own schedule is a much lower bar than beating real
turnaround, and it is not met either.

### Three defects in the previous build

1. **The target was mislabelled** as a realised turnaround. Corrected, and the rename is
   asserted in the tests.
2. **Pseudo-replication.** The same voyage appeared on every snapshot it was listed on,
   so 1,608 rows were really 692 voyages. A vessel whose ETCD slid from 25 to 26 August
   was counted as a second, independent observation. Now: exactly one row per voyage.
3. **Contaminated target.** 41% of those rows were for vessels that had not yet
   arrived, so `arrival_or_eta` was an ETA and the "turnaround" was a forecast of a
   forecast. Now restricted to voyages already berthed.

Additionally, **the split leaked**: holding out dates still left **80% of held-out rows
(304 of 381) sharing a voyage with the training set**, because a voyage listed on both
25 and 26 August straddled the boundary. Holding out voyages as well as dates gives
268 train / 79 test with **zero overlap**, asserted in the builder and the tests.

### Results

| Candidate | MAE (days) | 95% CI | RMSE | R² |
|---|---|---|---|---|
| **Port-median baseline (deployed)** | **2.639** | [1.98, 3.39] | 4.183 | −0.092 |
| Global-median baseline | 2.722 | [2.08, 3.43] | 4.138 | −0.069 |
| Gradient boosting | 2.757 | [2.09, 3.47] | 4.257 | −0.131 |
| Random forest | 2.993 | [2.40, 3.63] | 4.143 | −0.071 |

Paired bootstrap, gradient boosting minus port median: **−0.118 days, 95% CI
[−0.378, +0.137]**. The interval spans zero, so the two are equivalent.

**Every R² is negative**, meaning each candidate is worse than simply predicting the
held-out mean. The deployed artifact is therefore the per-port median, because that is
what the data supports. Shipping the gradient boosting model would add noise and a false
impression of skill.

The previous implementation returned a hardcoded `r2: 0.884` from a function that read
no data at all.

### Sampling concentration

Visakhapatnam supplies 111 of 347 voyages (32%). The effective sample is well below 347,
which is why every confidence interval above is wide.


---

## 6. What was removed, and why

| Removed / corrected | Reason |
|---|---|
| `predict_freight.py` `BASE_RATES` | Invented rates: `australia-paradip: 15.10`, with `18.20` returned for any unknown corridor |
| Hand-written "SHAP breakdown" | Multiplication of hand-picked coefficients, not model output. Replaced with leave-one-out contributions from the fitted booster |
| `train_congestion.py` metrics | Hardcoded `r2: 0.884`, `n_samples: 450` from a function that fitted nothing |
| **`turnaround_days` label** | ETCD is the port's forward estimate. No completion field exists in the data. Renamed `estimated_port_stay_days` and flagged everywhere |
| **Model 1's 1,608 rows** | Really 692 voyages, each counted once per snapshot listing. Now one row per voyage |
| **Model 1's date-only split** | 80% of held-out rows shared a voyage with training. Now voyage-disjoint, asserted |
| **`helps = reg > base`** | Zero tolerance on a 0.002 difference; verdict flipped between machines. Replaced with a paired bootstrap over weeks, tri-state verdict |
| **Single-seed headline** | Moved 18.8%→20.2% between environments. Now a range across four seeds plus a significance test |
| **Windows path in artifact** | `models\artifacts\...` is not portable. Now POSIX separators, asserted |
| `fx_market_api.py` | Returned `bdi: 1842`, `usd_inr: 83.42` as constants. BDI has no free source and is now marked unavailable; FX comes from ECB |
| Both Firecrawl scrapers | Simulated. The berth scraper fed invented queues into congestion scoring |
| Both PDF parsers | Returned hardcoded dictionaries. The ISS parser supplied fabricated MMT traffic figures that drove deadhead risk |
| Repositioning opportunity list | Claimed specific profit figures (e.g. "net profit gain 41,200 USD" ballasting Haldia to Dhamra) present in no source file |
| News disruption feed | Three hardcoded items with fixed dates, so risk tier never changed |
| `distance_km: 2147 if ... else 3850` in `main.py` | Hardcoded. Now computed from port coordinates, flagged as assumed when an endpoint lacks them |
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

**Seeds that never reached the model.** The seed sweep reported an identical regret for
all four seeds. `seed: int = RANDOM_SEED` as a default argument captures the value at
definition time, so reassigning the module global did nothing. Seed is now threaded
explicitly, and a test asserts the sweep produces a non-zero spread.

**A bootstrap comparing two identical models.** The ablation's noise floor initially
built *both* candidates from the reduced feature set, so every difference was exactly
zero and "no effect" was the right answer for the wrong reason. The two feature sets are
now passed separately, and comparing a candidate with itself returns an explicit error
rather than a spurious null.

---

## 8. Known limits

1. **Rate provenance is unconfirmed.** The largest single caveat. See §2.
2. **~20 weeks of lane history.** Short for a freight market. 11 corridors, 2 origin
   clusters (China and the Black Sea), 1 discharge region pair. There is no US,
   Australia, Indonesia, Mozambique or Handysize rate history, so the API returns
   "no rate history" for those lanes rather than a proxy number.
3. **8 out-of-sample weeks.** Everything in Model 2 rests on this. It is enough to
   establish that a fitted model beats persistence, and not enough to attribute that to
   any feature group.
4. **Model 1's target is the port's estimate, not reality.** No completion field exists
   in the data. If actual port stay matters, the dataset needs one.
5. **Model 1 has no modelling value.** A per-port median wins; all R² are negative.
6. **12 snapshot dates in one month**, concentrated in a few ports. Model 1's intervals
   are wide for that reason.
7. **Port dues are a placeholder.** No tariff data is held. It changes the cost ranking
   between similar classes. It does not affect feasibility, which depends only on
   physical limits.
8. **Idle repositioning is not quoted.** It would need rate and distance data for
   candidate ports.
9. **Demurrage, hotel bunkers, and speed are business assumptions**, returned in the
   API response so a caller can substitute their own.
10. **Rows within a week are correlated**, so the effective sample size is weeks, not
    rows. This is why both bootstraps resample weeks.
11. **Library versions are pinned** for a reason: the congestion artifact is a pickled
    sklearn estimator and is version-coupled. A rebuild on a different sklearn or
    XGBoost version moves the headline, so the seed range in the model card is what to
    compare against.

---

## 9. What would most improve the system

Ranked by expected gain per unit of effort.

1. **Confirm the rate source.** Everything in Model 2 rests on it.
2. **Add an actual completion / departure field** to the line-up data. Without one,
   Model 1 can only ever predict the port's own schedule, and no amount of modelling
   will change that.
3. **Add route rates for the missing lanes.** US, Australia, Indonesia, Mozambique and
   Handysize currently return "no rate history". This is the binding constraint on
   coverage, not on accuracy.
4. **Get more line-up months.** 12 dates concentrated in one port cannot support Model
   1's evaluation. More months would let the fitted models be tested properly, and might
   make the fitted model beat the median.
5. **Supply the Baltic CSV.** BCI, BPI, BSI and BHSI are the natural class-level
   features. Junaid's own audit found BDI did *not* help his ARIMA, so measure rather
   than assume — and note that on this panel the ablation could not establish an effect
   for any external feature group, so BDI is unlikely to be the lever it appears to be.
6. **Get terminal-level rate data.** Rates are currently port-pair level, so no
   terminal-level differences are invented.
7. **Add port tariffs** to replace the dues placeholder in the cost ranking.
