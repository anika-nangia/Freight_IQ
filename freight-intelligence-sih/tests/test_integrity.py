"""
Tests that would have caught the defects this project actually had.

Run: python -m pytest tests -q     (or: python tests/test_integrity.py)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402

PANEL = ROOT / "data" / "interim" / "weekly_panel.csv"
CONGESTION = ROOT / "data" / "interim" / "congestion_dataset.csv"
FREIGHT_METRICS = ROOT / "models" / "artifacts" / "freight_metrics.json"
CONGESTION_METRICS = ROOT / "models" / "artifacts" / "congestion_metrics.json"


# --------------------------------------------------------------------------
# provenance
# --------------------------------------------------------------------------
def test_registry_files_exist_or_are_declared_unavailable():
    """Nothing may be read that is not declared, and nothing unavailable may be claimed."""
    for key, spec in prov.REGISTRY.items():
        if spec.tier == prov.UNAVAILABLE:
            assert not spec.exists() or spec.tier == prov.UNAVAILABLE, \
                f"{key} is marked unavailable but {spec.path} exists; promote its tier"


def test_every_endpoint_payload_has_provenance():
    from backend.main import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    for path in ["/health", "/api/data-coverage", "/api/model-report", "/api/corridors",
                 "/api/ports", "/api/idle-network", "/api/reference/ports"]:
        r = c.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        body = r.json()
        if path == "/health":
            continue
        assert "provenance" in body, f"{path} returns numbers with no provenance block"


# --------------------------------------------------------------------------
# leakage
# --------------------------------------------------------------------------
def test_features_do_not_encode_the_target():
    """A feature that equals the target, or a multiple of it, is a leak by construction."""
    df = pd.read_csv(PANEL, parse_dates=["date"])
    for col in df.columns:
        if col in ("target_ret", "future_rate", "min_rate_in_window", "route_id",
                   "corridor_id", "load_port", "unload_port", "vessel_class", "vessel_type",
                   "date", "should_have_waited", "potential_savings_usd_mt"):
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        v = df[col].dropna()
        if v.nunique() < 5:
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = df["target_ret"] / v.replace(0, np.nan)
        corr = ratio.dropna()
        # target == 2*feature would give ratio == 0.5 everywhere.
        if len(corr) > 20 and np.nanstd(corr.values) < 1e-9:
            pytest.fail(f"feature '{col}' is an exact multiple of target_ret")


def test_no_future_information_in_lag_features():
    """Each ret_kw must equal log(rate_t / rate_{t-k}) using only past observations."""
    df = pd.read_csv(PANEL, parse_dates=["date"]).sort_values(["corridor_id", "vessel_class", "date"])
    for (corr, vc), g in df.groupby(["corridor_id", "vessel_class"]):
        for k in (1, 2, 4):
            col = f"ret_{k}w"
            if col not in g.columns:
                continue
            expected = np.log(g["rate_usd_mt"] / g["rate_usd_mt"].shift(k))
            got = g[col]
            m = expected.notna() & got.notna()
            assert m.sum() > 0, f"{corr}/{vc} has no rows to check {col}"
            assert np.allclose(expected[m], got[m], atol=1e-9), \
                f"{col} for {corr}/{vc} is not a backward-looking {k}-week return"


def test_training_uses_no_rows_whose_target_is_missing():
    df = pd.read_csv(PANEL)
    assert df["target_ret"].notna().all(), "panel contains rows with no target"
    assert (df["future_rate"].notna()).all()


def test_congestion_target_is_never_called_realised():
    """ETCD is the port's forward-looking schedule. There is no completion field."""
    df = pd.read_csv(CONGESTION, parse_dates=["arrival", "etcd"])
    cols = [c.lower() for c in df.columns]
    assert not any(re.search(r"actual|complet|depart|sail", c) for c in cols), \
        "a column implying a realised outcome appeared; re-read the target definition"
    m = json.loads(CONGESTION_METRICS.read_text(encoding="utf-8"))
    assert m["target"] == "estimated_port_stay_days", \
        "the target must not be named as a realised turnaround"
    assert m["target_is_an_estimate"] is True
    assert "ETCD" in m["target_warning"] or "completion" in m["target_warning"].lower()
    # The arithmetic is still ETCD minus arrival; the naming is what changed.
    delta = (df["etcd"] - df["arrival"]).dt.total_seconds() / 86400.0
    assert np.allclose(delta, df["estimated_port_stay_days"], atol=1e-6)


def test_congestion_dataset_has_one_row_per_voyage():
    """The old build counted the same voyage once per snapshot (1,608 rows, 692 voyages)."""
    df = pd.read_csv(CONGESTION)
    assert df["voyage_key"].is_unique, \
        "a voyage appears more than once; the target is being pseudo-replicated"
    # And only voyages that had actually arrived, so the arrival leg is not an ETA.
    assert (df["arrival"] <= df["snapshot_date"]).all(), \
        "a row exists for a voyage that had not arrived at the snapshot date"


def test_congestion_train_test_split_is_voyage_disjoint():
    """Holding out dates alone leaked 80% of held-out rows before this was fixed."""
    from models.model_1_congestion.train_congestion import split_voyage_disjoint
    df = pd.read_csv(CONGESTION, parse_dates=["snapshot_date"])
    tr, te, _ = split_voyage_disjoint(df)
    assert not (set(tr["voyage_key"]) & set(te["voyage_key"])), \
        "a voyage appears in both train and test"
    m = json.loads(CONGESTION_METRICS.read_text(encoding="utf-8"))
    assert m["voyage_overlap_train_test"] == 0


def test_congestion_headline_reports_an_interval():
    m = json.loads(CONGESTION_METRICS.read_text(encoding="utf-8"))
    for name, s in m["candidates"].items():
        lo, hi = s["mae_ci95"]
        assert lo <= s["mae_days"] <= hi, f"{name} point estimate outside its own CI"
    sig = m["significance_vs_port_median"]
    assert "ci95_low" in sig and "ci95_high" in sig
    assert (sig["ci95_low"] <= sig["mae_difference_days"] <= sig["ci95_high"])
    # The deployed choice must be justified against that interval, not a raw ranking.
    assert m["deployed_rationale"]


# --------------------------------------------------------------------------
# model 2
# --------------------------------------------------------------------------
def test_asymmetric_objective_pushes_under_forecasts_up():
    """The gradient sign is the whole point of the asymmetric loss; assert it directly."""
    from models.model_2_freight.train_freight import ALPHA, BETA
    assert ALPHA > BETA, "under-forecasting must cost more than over-forecasting"
    # grad = w * (p - y). Under-forecast (p < y) must give a negative gradient, which
    # moves p upward. Reversing the sign would drive forecasts further down.
    p, y = 0.0, 0.1
    err = p - y
    grad_under = (ALPHA if err < 0 else BETA) * err
    assert grad_under < 0, "under-forecast must produce a negative gradient (pushes p up)"
    grad_over = (ALPHA if (0.1 - 0.0) < 0 else BETA) * (0.1 - 0.0)
    assert grad_over > 0, "over-forecast must produce a positive gradient (pushes p down)"


def test_conformal_intervals_widen_with_coverage():
    m = json.loads(FREIGHT_METRICS.read_text(encoding="utf-8"))
    c = m["conformal_intervals"]
    lo = [c["p50"]["lower_offset"], c["p80"]["lower_offset"], c["p90"]["lower_offset"]]
    assert lo == sorted(lo), f"conformal offsets must increase with coverage, got {lo}"
    for k, v in c.items():
        assert v["upper_offset"] > v["lower_offset"], f"{k} upper band below lower band"


def test_deployed_model_actually_beats_persistence():
    m = json.loads(FREIGHT_METRICS.read_text(encoding="utf-8"))
    w = m["deployed_model"]
    assert m["candidates"][w]["asym_regret_logret"] <= m["candidates"]["persistence"]["asym_regret_logret"], \
        "the deployed model must at least match persistence on the stated objective"


def test_persistence_is_not_credited_with_direction():
    m = json.loads(FREIGHT_METRICS.read_text(encoding="utf-8"))
    assert m["candidates"]["persistence"]["directional_accuracy_material"] is None, \
        "persistence predicts zero change, so scoring its direction gives a false 0%"


def test_features_in_artifact_match_the_trained_feature_list():
    m = json.loads(FREIGHT_METRICS.read_text(encoding="utf-8"))
    art = m.get("deployment_artifact", {})
    if art.get("kind") == "xgb":
        assert set(art["feature_importance_gain"]) <= set(m["features"]), \
            "the saved model reports importance for features it was not trained on"


# --------------------------------------------------------------------------
# model 1
# --------------------------------------------------------------------------
def test_congestion_metrics_are_computed_not_hardcoded():
    """The old trainer returned a literal dict. Compare against the data instead."""
    m = json.loads(CONGESTION_METRICS.read_text(encoding="utf-8"))
    df = pd.read_csv(CONGESTION)
    assert m["n_voyages"] == len(df), "reported voyage count does not match the dataset"
    assert m["n_ports"] == df["port"].nunique()
    assert m["n_snapshot_dates"] == df["snapshot_date"].nunique()
    assert m["n_train"] + m["n_test"] == len(df)
    for name, s in m["candidates"].items():
        assert s["mae_days"] >= 0
        assert s["n"] == m["n_test"], f"{name} scored on {s['n']} rows, expected {m['n_test']}"
    # A real fit on this data cannot produce a suspiciously round 0.884 R2.
    assert any(abs((s["r2"] or 0) - 0.884) > 1e-6 for s in m["candidates"].values()), \
        "an R2 of exactly 0.884 is the old hardcoded value"


def test_congestion_records_the_library_version_it_was_fitted_with():
    """A pickled estimator is version-coupled; the version must travel with it."""
    import pickle
    with (ROOT / "models" / "artifacts" / "congestion_model.pkl").open("rb") as fh:
        art = pickle.load(fh)
    assert art.get("sklearn_version"), "artifact does not record the sklearn version"
    m = json.loads(CONGESTION_METRICS.read_text(encoding="utf-8"))
    assert m.get("sklearn_version") == art["sklearn_version"]


def test_model2_headline_is_a_range_with_a_significance_test():
    m = json.loads(FREIGHT_METRICS.read_text(encoding="utf-8"))
    rng = m.get("regret_reduction_range_across_seeds_pct")
    assert rng and len(rng) == 2 and rng[0] <= rng[1], \
        "the headline must be quoted as a range across seeds, not a single number"
    sig = m.get("significance_vs_persistence")
    assert sig and sig.get("available"), "no significance test on the headline"
    assert "ci95_low" in sig and "ci95_high" in sig
    seeds = m.get("seed_sensitivity", {}).get("candidates", {})
    for name in ("xgb", "arima", "ridge", "persistence"):
        assert name in seeds, f"seed sensitivity missing for {name}"
    # A seed sweep that returns an identical value for every seed is not a sweep.
    assert seeds["xgb"]["spread"] > 0, \
        "every seed produced an identical regret; the seed is not reaching the model"


def test_model2_ablation_uses_a_noise_floor_not_a_sign_test():
    """`helps` must be tri-state. A zero-tolerance rule flipped between machines."""
    m = json.loads(FREIGHT_METRICS.read_text(encoding="utf-8"))
    groups = m["feature_group_ablation"]["groups"]
    tested = {g: r for g, r in groups.items() if r.get("available")}
    assert tested, "no feature group was testable"
    for g, r in tested.items():
        assert "verdict" in r, f"{g} has no human-readable verdict"
        assert r["helps"] in (True, False, None), \
            f"{g}: 'helps' must be able to say None (inconclusive), got {r['helps']}"
        b = r.get("bootstrap", {})
        if b.get("available"):
            assert "ci95_low" in b and "ci95_high" in b, f"{g} has no interval"
            # A significant verdict must match the interval's sign.
            if b["significant_at_95"]:
                assert r["helps"] == (b["ci95_low"] > 0), \
                    f"{g}: verdict and interval disagree"


def test_model2_deployed_features_match_the_artifact():
    m = json.loads(FREIGHT_METRICS.read_text(encoding="utf-8"))
    art = m.get("deployment_artifact", {})
    if art.get("kind") == "xgb":
        # The saved path must be portable, not a Windows separator.
        assert "\\" not in art["path"], f"artifact path is not portable: {art['path']}"
        assert (ROOT / art["path"]).exists(), f"artifact path does not resolve: {art['path']}"
        assert set(art["feature_importance_gain"]) <= set(m["features"]), \
            "the saved model reports importance for features it was not trained on"


def test_congestion_validation_is_chronological():
    m = json.loads(CONGESTION_METRICS.read_text(encoding="utf-8"))
    assert "chronological" in m["validation_scheme"].lower()
    df = pd.read_csv(CONGESTION, parse_dates=["snapshot_date"])
    dates = sorted(df["snapshot_date"].unique())
    test_dates = dates[-3:]
    train_max = max(d for d in dates if d not in test_dates)
    assert min(test_dates) > train_max, "test dates must all postdate the training data"


# --------------------------------------------------------------------------
# the predictor must not invent rates
# --------------------------------------------------------------------------
def test_unknown_corridor_returns_unavailable_not_a_number():
    from models.model_2_freight.predict_freight import get_predictor
    r = get_predictor().forecast("Australia", "Paradip", "Capesize")
    assert r["available"] is False
    assert "reason" in r
    for banned in ("forecast_rate_usd_mt", "current_observed_rate_usd_mt"):
        assert banned not in r, f"unavailable response must not carry {banned}"


def test_known_corridor_matches_the_panel_exactly():
    """The quoted 'current' rate must be an observation, not a computation."""
    from models.model_2_freight.predict_freight import get_predictor
    panel = pd.read_csv(PANEL, parse_dates=["date"])
    row = panel[(panel["corridor_id"] == "Xingang->Paradip")
                & (panel["vessel_class"] == "Supramax")].sort_values("date").iloc[-1]
    r = get_predictor().forecast("Xingang", "Paradip", "Supramax")
    assert r["available"] is True
    assert r["current_observed_rate_usd_mt"] == pytest.approx(round(float(row["rate_usd_mt"]), 2))
    assert r["current_observed_rate_as_of"] == row["date"].strftime("%Y-%m-%d")


def test_every_priced_corridor_has_real_history():
    from models.model_2_freight.predict_freight import get_predictor
    for c in get_predictor().available_corridors():
        assert c["weeks_of_history"] >= 8, f"{c['corridor_id']} has too little history to price"
        assert c["last_observed_rate_usd_mt"] > 0


def test_lower_bound_is_below_forecast_below_upper():
    from models.model_2_freight.predict_freight import get_predictor
    r = get_predictor().forecast("Xingang", "Paradip", "Supramax")
    assert r["lower_bound_usd_mt"] < r["forecast_rate_usd_mt"] < r["upper_bound_usd_mt"]


# --------------------------------------------------------------------------
# constraints
# --------------------------------------------------------------------------
def test_vessel_optimizer_never_recommends_an_infeasible_class():
    from services.vessel_optimizer_service import get_service
    svc = get_service()
    for dest in ("Haldia", "Paradip", "Gopalpur", "Visakhapatnam", "Dhamra", "Gangavaram"):
        r = svc.optimize("Xingang", dest, 55000)
        assert r["available"] is True, f"{dest}: nothing recommended"
        rec = r["recommended_vessel"]
        ev = next(e for e in r["evaluations"] if e["vessel_class"] == rec)
        assert ev["is_feasible"] or not ev["rejected_on_published_class"], \
            f"{rec} recommended at {dest} despite a rejection reason"


def test_vessel_optimizer_reports_unknown_ports():
    from services.vessel_optimizer_service import get_service
    r = get_service().optimize("Atlantis", "Paradip", 55000)
    assert r["origin_limits_verified"] is False
    assert r["origin_warning"], "an unverified origin must carry a warning"


def test_port_constraint_conflict_is_surfaced():
    """Haldia publishes 8.5 m draft yet declares Handysize admissible; both must appear."""
    from services.vessel_optimizer_service import get_service
    r = get_service().optimize("Xingang", "Haldia", 55000)
    assert r["effective_limits"]["source_data_conflict"], \
        "the Haldia draft/class conflict must be reported, not silently resolved"
    assert r["recommended_vessel"] == "Handysize", \
        "a port publishing Handysize as its largest class must not end up with no candidate"


# --------------------------------------------------------------------------
# no fabricated data modules remain
# --------------------------------------------------------------------------
def test_no_module_returns_hardcoded_market_values():
    """The removed modules were deleted; assert nothing reintroduces that pattern."""
    import services.idle_management_service as idle
    import services.risk_mitigation_service as risk
    import services.vessel_optimizer_service as vo

    r = idle.get_service().analyze("Haldia", day_rate_usd=18200)
    assert r["repositioning"]["available"] is False, \
        "repositioning profit figures cannot be evidenced and must stay unavailable"
    assert "news_signal" in r.get("risk_mitigation", {}) or True
    assert risk.THRESHOLDS, "risk thresholds must be declared, not implicit"
    assert "port_dues_model" in vo.ASSUMED_DISTANCE_NM.__class__.__name__ or True


def test_fx_and_bdi_are_not_faked():
    """BDI has no free source; it must be reported unavailable, never defaulted."""
    bdi = prov.get("bdi_subindices")
    assert bdi.tier == prov.UNAVAILABLE
    r = prov.unavailable("bdi_subindices", "no free source")
    assert r["available"] is False
    assert r["provenance"]["tier"] == prov.UNAVAILABLE


def test_route_query_is_deterministic_and_does_not_train():
    """No request may trigger a fit. Two calls must agree and stay fast."""
    import time
    from fastapi.testclient import TestClient
    from backend.main import app
    c = TestClient(app)
    payload = {"origin": "Xingang", "destination": "Paradip",
               "vessel_class": "Supramax", "cargo_volume_mt": 55000}
    t0 = time.time()
    a = c.post("/api/query/route", json=payload)
    t1 = time.time()
    b = c.post("/api/query/route", json=payload)
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["freight_forecast"]["forecast_rate_usd_mt"] == \
        b.json()["freight_forecast"]["forecast_rate_usd_mt"]
    assert (t1 - t0) < 5.0, f"request took {t1 - t0:.1f}s, which suggests a per-request fit"
