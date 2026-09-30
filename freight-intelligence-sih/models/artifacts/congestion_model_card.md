# Model 1 - Port Congestion: Model Card

Trained 2026-09-30T13:47:51+00:00

## What the target is

`estimated_port_stay_days`

> **The target is the port's own published schedule (etc_or_etcd - arrival), not a measured turnaround. The source line-up data has no actual completion field, so realised turnaround cannot be modelled. This model predicts what the port says, which is a useful cross-check on the port's own estimate but is not independent ground truth.**

## Validation

chronological block split on the last 3 snapshot dates, with voyage-level disjointness asserted.
268 train voyages, 79 test voyages across ['2026-08-26', '2026-08-27', '2026-08-31']. Voyage overlap between train and test: **0**.

The previous version held out dates but not voyages, and 80% of held-out rows shared a voyage with training. That is fixed and asserted.

| model | MAE (days) | 95% CI | RMSE | R2 |
|---|---|---|---|---|
| port_median_baseline | 2.639 | [1.98, 3.39] | 4.183 | -0.092 |
| global_median_baseline | 2.722 | [2.08, 3.43] | 4.138 | -0.069 |
| gradient_boosting | 2.757 | [2.09, 3.47] | 4.257 | -0.131 |
| random_forest | 2.993 | [2.40, 3.63] | 4.143 | -0.071 |

## Is the model actually better than knowing the port's usual figure?

Best fitted candidate `gradient_boosting` minus `port_median_baseline`:

- MAE difference: **-0.118 days**
- 95% CI on that difference: [-0.378, +0.137]
- Verdict: **the difference is inside resampling noise; treat the two as equivalent**

Any candidate with a positive R2: **False**. A negative R2 means the candidate is worse than simply predicting the held-out mean.

## Deployed: `port_median_baseline`

A baseline wins on held-out MAE and no fitted model beat it by an amount the data can distinguish from zero, so the baseline is deployed. Shipping the gradient boosting model would add noise and a false impression of skill.

A paired bootstrap over voyages, resampling both candidates on the same draws. Comparing two MAE numbers and picking the smaller is not evidence; this is.

## Provenance

- Target: estimated by the port (not an outcome)
- Features: observed line-up state + Open-Meteo weather

## Known limits

1. 111 contributes 0 of 347 voyages (0%), so the effective sample is much smaller than the row count.
2. Only 3 held-out dates and 79 voyages. The confidence intervals above are wide for that reason; read them before the point estimates.
3. No realised turnaround exists in the data. If actual port stay matters, this needs a completion or departure field that the line-up does not carry.
4. Because the target is the port's own schedule, part of any skill is the port anticipating its own queue, not the model anticipating the port.
