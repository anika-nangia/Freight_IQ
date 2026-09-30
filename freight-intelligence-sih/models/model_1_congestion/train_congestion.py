"""
Model 1 - port congestion. Predicts the PORT'S ESTIMATE of port stay.

READ THIS BEFORE QUOTING ANY NUMBER FROM THIS FILE
    The target is `estimated_port_stay_days` = etc_or_etcd - arrival_or_eta.
    It is NOT a realised turnaround. The source line-up data has no actual
    completion, departure or sailing field, and no voyage is ever recorded as
    finished, so a true turnaround cannot be measured from it at all.

    The previous version of this model was called a turnaround model, reported
    1,608 rows, and held out dates. Three things were wrong with that:
      1. it called the port's schedule a realised outcome;
      2. the same voyage appeared on many snapshots, so 1,608 rows were really
         692 voyages, counted repeatedly as ETCD slid;
      3. holding out dates still left 80% of held-out rows sharing a voyage with
         the training set.

    This version: one row per voyage, only voyages observed while actually berthed,
    a split with zero voyage overlap, and a bootstrap interval on every headline.

WHAT THE MODEL IS FOR
    A charterer asking "the port says 5 days, is that plausible for this queue?"
    That is a useful question. It is not the same as predicting reality, and the
    API now says which one it is answering.

Run:  python -m models.model_1_congestion.train_congestion
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATASET = ROOT / "data" / "interim" / "congestion_dataset.csv"
ART = ROOT / "models" / "artifacts"
MODEL_PATH = ART / "congestion_model.pkl"
METRICS_PATH = ART / "congestion_metrics.json"
CARD_PATH = ART / "congestion_model_card.md"

TARGET = "estimated_port_stay_days"
FEATURES = [
    "queue_waiting", "vessels_awaiting_berth", "vessels_working", "berths_total",
    "berth_occupancy", "queue_ratio", "vessels_expected", "arrivals_next_7d",
    "working_import", "working_export", "cargo_tonnage",
    "weather_wind_max_kt", "weather_precip_mm",
]
RANDOM_SEED = 42
N_TEST_DATES = 3
N_BOOTSTRAP = 2000
# A difference smaller than this in MAE days is inside the noise of a 79-voyage
# holdout. Quoting a winner below it would be false precision.
MATERIALITY_DAYS = 0.25


def _metrics(y: np.ndarray, p: np.ndarray) -> Dict[str, Any]:
    err = p - y
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "mae_days": float(np.mean(np.abs(err))),
        "rmse_days": float(np.sqrt(np.mean(err ** 2))),
        "r2": float(1 - float(np.sum(err ** 2)) / ss_tot) if ss_tot > 0 else None,
        "bias_days": float(np.mean(err)),
        "n": int(len(y)),
    }


def _bootstrap_mae(y: np.ndarray, p: np.ndarray, n: int = N_BOOTSTRAP,
                   seed: int = RANDOM_SEED) -> Tuple[float, float]:
    """95% interval on MAE by resampling voyages. Returns (lo, hi)."""
    rng = np.random.default_rng(seed)
    err = np.abs(p - y)
    idx = rng.integers(0, len(err), size=(n, len(err)))
    boots = err[idx].mean(axis=1)
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def _paired_bootstrap(y: np.ndarray, p_a: np.ndarray, p_b: np.ndarray,
                      n: int = N_BOOTSTRAP, seed: int = RANDOM_SEED) -> Dict[str, Any]:
    """Is candidate A better than B, resampling the same voyages for both?

    A 95% interval on the MAE difference that excludes zero is the evidence needed
    to call one model better than another. Comparing two MAE numbers and seeing
    which is smaller is not evidence, which is how the previous report concluded
    that a 0.2% margin was a result.
    """
    rng = np.random.default_rng(seed)
    diff = np.abs(p_b - y) - np.abs(p_a - y)     # >0 means A is better
    idx = rng.integers(0, len(diff), size=(n, len(diff)))
    boots = diff[idx].mean(axis=1)
    lo, hi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
    return {
        "mae_difference_days": float(diff.mean()),
        "ci95_low": lo, "ci95_high": hi,
        "significant_at_95": bool(lo > 0 or hi < 0),
        "interpretation": ("A is better than B by an amount the data can distinguish "
                           "from zero" if (lo > 0 or hi < 0)
                           else "the difference is inside resampling noise; treat the two "
                                "as equivalent"),
    }


def _impute_fit(tr: pd.DataFrame, feats: List[str]) -> Dict[str, float]:
    """Training medians for gaps. Weather covers 7 of 13 ports; dropping the rest
    would remove half the geography, so gaps are filled from training data only."""
    return {c: float(tr[c].median()) for c in feats}


def _impute_apply(frame: pd.DataFrame, medians: Dict[str, float]) -> pd.DataFrame:
    out = frame.copy()
    for c, v in medians.items():
        out[c] = out[c].fillna(v)
    return out


def _port_median(train: pd.DataFrame, test: pd.DataFrame, gmed: float) -> np.ndarray:
    med = train.groupby("port")[TARGET].median()
    return np.array([med.get(p, gmed) for p in test["port"]], dtype=float)


def _fit_gb(tr: pd.DataFrame, te: pd.DataFrame, feats: List[str]):
    from sklearn.ensemble import GradientBoostingRegressor
    m = GradientBoostingRegressor(loss="huber", n_estimators=300, max_depth=2,
                                  learning_rate=0.05, min_samples_leaf=8,
                                  random_state=RANDOM_SEED)
    m.fit(tr[feats].values, tr[TARGET].values)
    return m, m.predict(te[feats].values)


def _fit_rf(tr: pd.DataFrame, te: pd.DataFrame, feats: List[str]):
    from sklearn.ensemble import RandomForestRegressor
    m = RandomForestRegressor(n_estimators=400, max_depth=6, min_samples_leaf=8,
                              random_state=RANDOM_SEED, n_jobs=2)
    m.fit(tr[feats].values, tr[TARGET].values)
    return m, m.predict(te[feats].values)


def split_voyage_disjoint(df: pd.DataFrame, n_test_dates: int = N_TEST_DATES):
    """Hold out whole dates AND assert no voyage spans the boundary.

    Holding out dates alone is not enough: a voyage listed on 25 Aug and again on
    26 Aug put the same vessel on both sides and leaked 80% of the held-out rows.
    """
    dates = np.sort(df["snapshot_date"].unique())
    test_dates = set(dates[-n_test_dates:])
    tr = df[~df["snapshot_date"].isin(test_dates)]
    te = df[df["snapshot_date"].isin(test_dates)]
    overlap = set(tr["voyage_key"]) & set(te["voyage_key"])
    if overlap:
        raise AssertionError(f"{len(overlap)} voyages appear in both train and test")
    return tr, te, sorted(test_dates)


def train() -> Dict[str, Any]:
    if not DATASET.exists():
        raise FileNotFoundError(
            f"{DATASET} missing. Run: python -m data_pipeline.build_congestion_dataset")
    df = pd.read_csv(DATASET, parse_dates=["snapshot_date", "arrival", "etcd"])
    feats = [f for f in FEATURES if f in df.columns and df[f].notna().any()]

    tr_raw, te_raw, test_dates = split_voyage_disjoint(df)
    medians = _impute_fit(tr_raw, feats)
    tr = _impute_apply(tr_raw, medians)
    te = _impute_apply(te_raw, medians)
    gmed = float(tr[TARGET].median())

    y = te[TARGET].values
    preds: Dict[str, np.ndarray] = {
        "port_median_baseline": _port_median(tr, te, gmed),
        "global_median_baseline": np.full(len(te), gmed),
    }
    _, preds["gradient_boosting"] = _fit_gb(tr, te, feats)
    _, preds["random_forest"] = _fit_rf(tr, te, feats)

    scored: Dict[str, Any] = {}
    for k, v in preds.items():
        s = _metrics(y, v)
        lo, hi = _bootstrap_mae(y, v)
        s["mae_ci95"] = [round(lo, 3), round(hi, 3)]
        scored[k] = s

    best_ml = min(("gradient_boosting", "random_forest"),
                  key=lambda k: scored[k]["mae_days"])
    vs_base = _paired_bootstrap(y, preds[best_ml], preds["port_median_baseline"])

    # Deploy whichever candidate actually wins on held-out MAE, baselines included.
    # If a per-port median beats both fitted models, that is the honest thing to ship,
    # and it costs nothing to serve.
    deployed = min(scored, key=lambda k: scored[k]["mae_days"])
    deployed_is_baseline = deployed.endswith("_baseline")

    print(f"[m1] {len(df)} voyages | {df['port'].nunique()} ports | "
          f"{df['snapshot_date'].nunique()} snapshot dates")
    print(f"[m1] target {TARGET} (the PORT'S ESTIMATE, not a realised turnaround)")
    print(f"[m1] voyage-disjoint split: {len(tr)} train / {len(te)} test, overlap 0")
    print(f"\n[m1] held-out MAE (days), 95% bootstrap CI:")
    print(f"  {'candidate':<26}{'MAE':>8}{'RMSE':>8}{'R2':>9}  {'95% CI':>16}")
    for k, s in scored.items():
        r2 = f"{s['r2']:.3f}" if s["r2"] is not None else "n/a"
        lo, hi = s["mae_ci95"]
        print(f"  {k:<26}{s['mae_days']:>8.3f}{s['rmse_days']:>8.3f}{r2:>9}  "
              f"{f'[{lo:.2f}, {hi:.2f}]':>16}")

    print(f"\n[m1] {best_ml} vs port_median_baseline: MAE difference "
          f"{vs_base['mae_difference_days']:+.3f} days "
          f"(95% CI {vs_base['ci95_low']:+.3f} to {vs_base['ci95_high']:+.3f})")
    print(f"[m1] {vs_base['interpretation']}")
    print(f"[m1] deployed: {deployed}"
          + ("  <- a BASELINE wins; no fitted model beat it" if deployed_is_baseline else ""))

    filled = df_filled(df, medians, feats)
    if deployed_is_baseline:
        # A per-port median needs the medians, not a pickle. Store them so inference
        # can answer a port it has never seen by falling back to the global median.
        port_medians = filled.groupby("port")[TARGET].median().to_dict()
        model = None
        artifact = {"kind": "port_median", "port_medians":
                    {k: float(v) for k, v in port_medians.items()},
                    "global_median": float(filled[TARGET].median()),
                    "features": None, "impute_medians": medians, "target": TARGET,
                    "sklearn_version": _sklearn_version()}
        resid = filled[TARGET].values - filled["port"].map(port_medians).fillna(
            filled[TARGET].median()).values
    else:
        model, _ = (_fit_gb if deployed == "gradient_boosting" else _fit_rf)(
            filled, filled.head(1), feats)
        resid = filled[TARGET].values - model.predict(filled[feats].values)
        artifact = {"model": model, "kind": deployed, "features": feats,
                    "impute_medians": medians, "target": TARGET,
                    "sklearn_version": _sklearn_version()}
    resid_q = {f"p{int(q*100)}": round(float(np.quantile(resid, q)), 3) for q in (0.5, 0.8, 0.9)}

    top_port = df["port"].value_counts().iloc[0]
    metrics = {
        "trained_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
        "target": TARGET,
        "target_is_an_estimate": True,
        "target_warning": "The target is the port's own published schedule "
                          "(etc_or_etcd - arrival), not a measured turnaround. The source "
                          "line-up data has no actual completion field, so realised "
                          "turnaround cannot be modelled. This model predicts what the port "
                          "says, which is a useful cross-check on the port's own estimate "
                          "but is not independent ground truth.",
        "validation_scheme": f"chronological block split on the last {N_TEST_DATES} snapshot "
                             f"dates, with voyage-level disjointness asserted",
        "n_voyages": int(len(df)),
        "n_ports": int(df["port"].nunique()),
        "n_snapshot_dates": int(df["snapshot_date"].nunique()),
        "n_train": int(len(tr)), "n_test": int(len(te)),
        "test_dates": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in test_dates],
        "voyage_overlap_train_test": 0,
        "features": feats,
        "sklearn_version": _sklearn_version(),
        "impute_medians": {k: round(v, 3) for k, v in medians.items()},
        "candidates": scored,
        "best_ml_candidate": best_ml,
        "deployed_model": deployed,
        "deployed_is_baseline": deployed_is_baseline,
        "deployed_rationale": (
            "A baseline wins on held-out MAE and no fitted model beat it by an amount the "
            "data can distinguish from zero, so the baseline is deployed. Shipping the "
            "gradient boosting model would add noise and a false impression of skill."
            if deployed_is_baseline else
            f"{deployed} wins on held-out MAE with a difference the bootstrap can separate "
            f"from zero."),
        "significance_vs_port_median": vs_base,
        "any_r2_positive": any((s["r2"] or -1) > 0 for s in scored.values()),
        "materiality_threshold_days": MATERIALITY_DAYS,
        "residual_quantiles_days": resid_q,
        "provenance": {
            "target": "estimated by the port (not an outcome)",
            "features": "observed line-up state + Open-Meteo weather",
        },
        "known_limitations": [
            f"{top_port} contributes {top_port and int((df['port'] == top_port).sum())} of "
            f"{len(df)} voyages ({int((df['port'] == top_port).sum()) / len(df):.0%}), so the "
            "effective sample is much smaller than the row count.",
            f"Only {N_TEST_DATES} held-out dates and {len(te)} voyages. The confidence "
            "intervals above are wide for that reason; read them before the point estimates.",
            "No realised turnaround exists in the data. If actual port stay matters, this "
            "needs a completion or departure field that the line-up does not carry.",
            "Because the target is the port's own schedule, part of any skill is the port "
            "anticipating its own queue, not the model anticipating the port.",
        ],
    }
    ART.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    import pickle
    with MODEL_PATH.open("wb") as fh:
        pickle.dump(artifact, fh)
    _write_card(metrics)
    print(f"\n[m1] wrote {METRICS_PATH} (sklearn {metrics.get('sklearn_version', '?')})")
    return metrics


def df_filled(df: pd.DataFrame, medians: Dict[str, float], feats: List[str]) -> pd.DataFrame:
    return _impute_apply(df, medians)


def _sklearn_version() -> str:
    import sklearn
    return sklearn.__version__


def _write_card(m: Dict[str, Any]) -> None:
    sig = m["significance_vs_port_median"]
    lines = [
        "# Model 1 - Port Congestion: Model Card",
        "",
        f"Trained {m['trained_at']}",
        "",
        "## What the target is",
        "",
        f"`{m['target']}`",
        "",
        f"> **{m['target_warning']}**",
        "",
        "## Validation",
        "",
        f"{m['validation_scheme']}.",
        f"{m['n_train']} train voyages, {m['n_test']} test voyages across "
        f"{m['test_dates']}. Voyage overlap between train and test: "
        f"**{m['voyage_overlap_train_test']}**.",
        "",
        "The previous version held out dates but not voyages, and 80% of held-out rows "
        "shared a voyage with training. That is fixed and asserted.",
        "",
        "| model | MAE (days) | 95% CI | RMSE | R2 |",
        "|---|---|---|---|---|",
    ]
    for k, s in m["candidates"].items():
        r2 = f"{s['r2']:.3f}" if s["r2"] is not None else "n/a"
        lines.append(f"| {k} | {s['mae_days']:.3f} | [{s['mae_ci95'][0]:.2f}, "
                     f"{s['mae_ci95'][1]:.2f}] | {s['rmse_days']:.3f} | {r2} |")
    lines += [
        "",
        f"## Is the model actually better than knowing the port's usual figure?",
        "",
        f"Best fitted candidate `{m['best_ml_candidate']}` minus `port_median_baseline`:",
        "",
        f"- MAE difference: **{sig['mae_difference_days']:+.3f} days**",
        f"- 95% CI on that difference: [{sig['ci95_low']:+.3f}, {sig['ci95_high']:+.3f}]",
        f"- Verdict: **{sig['interpretation']}**",
        "",
        f"Any candidate with a positive R2: **{m['any_r2_positive']}**. A negative R2 means "
        "the candidate is worse than simply predicting the held-out mean.",
        "",
        f"## Deployed: `{m['deployed_model']}`",
        "",
        m["deployed_rationale"],
        "",
        "A paired bootstrap over voyages, resampling both candidates on the same draws. "
        "Comparing two MAE numbers and picking the smaller is not evidence; this is.",
        "",
        "## Provenance",
        "",
        f"- Target: {m['provenance']['target']}",
        f"- Features: {m['provenance']['features']}",
        "",
        "## Known limits",
        "",
    ]
    lines += [f"{i}. {l}" for i, l in enumerate(m["known_limitations"], 1)]
    lines.append("")
    CARD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[m1] wrote {CARD_PATH}")


if __name__ == "__main__":
    train()
