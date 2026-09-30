"""
Model 2 - XGBoost freight-rate forecaster with an asymmetric regret objective.

Trains on data/freight_training_matrix.csv (built by data_pipeline/build_training_matrix.py).
Target  : log(rate_{t+H} / rate_t)  -> scale-free, works across routes priced $15..$58/MT.
Split   : strictly chronological by date (70/15/15 of unique dates). Never random.
Compared against: (a) persistence (predict 0% change), (b) Ridge regression.
Every metric written to artifacts/model2_metrics.json is computed, none hardcoded.
"""
import json
from pathlib import Path
from typing import Dict, Any
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "data" / "freight_training_matrix.csv"
ART = ROOT / "models" / "model_2_freight" / "artifacts"
ALPHA, BETA = 2.5, 1.0   # under-forecast costs 2.5x over-forecast (missed spike = booked too late)

BASE_FEATURES = ["ret_1w", "ret_2w", "ret_4w", "roll_cv_4w", "dev_from_mean_4w",
                 "log_rate", "load_port_code", "vessel_type_code"]
# month_sin/cos deliberately excluded: only ~5 months of history, so they act as a time index, not seasonality.
BDI_FEATURES = ["bdi_ret_1w", "bdi_ret_4w", "bdi_vol_4w"]


def asymmetric_regret_objective(preds: np.ndarray, dtrain: xgb.DMatrix, alpha=ALPHA, beta=BETA):
    """Asymmetrically weighted squared error. L = w * (p - y)^2 / 2,
    w = alpha if p < y (under-forecast) else beta.
    grad = dL/dp = w * (p - y);  hess = w.   (Sign matters: under-forecast => grad < 0 => pushes p UP.)"""
    err = preds - dtrain.get_label()
    w = np.where(err < 0, alpha, beta)
    return w * err, w


def regret(y_true, y_pred, alpha=ALPHA, beta=BETA) -> float:
    e = y_true - y_pred
    return float(np.mean(np.where(e > 0, alpha * e, beta * -e)))


def _split(df: pd.DataFrame):
    dates = np.sort(df["date"].unique())
    n = len(dates)
    tr_end, va_end = dates[int(n * 0.70) - 1], dates[int(n * 0.85) - 1]
    return (df[df.date <= tr_end], df[(df.date > tr_end) & (df.date <= va_end)], df[df.date > va_end])


def _scores(df, y_pred, cur_rate_col="rate_usd_mt") -> Dict[str, float]:
    y = df["target_ret"].values
    p = y_pred
    rate_true = df["future_rate"].values
    rate_pred = df[cur_rate_col].values * np.exp(p)
    ss_res, ss_tot = np.sum((rate_true - rate_pred) ** 2), np.sum((rate_true - rate_true.mean()) ** 2)
    return {
        "rmse_usd_mt": float(np.sqrt(np.mean((rate_true - rate_pred) ** 2))),
        "mae_usd_mt": float(np.mean(np.abs(rate_true - rate_pred))),
        "r2_level": float(1 - ss_res / ss_tot),
        "asym_regret_logret": regret(y, p),
        "directional_accuracy": (float(np.mean(np.sign(p) == np.sign(y))) if np.any(p != 0) else None),
    }


def train() -> Dict[str, Any]:
    df = pd.read_csv(MATRIX, parse_dates=["date"])
    feats = BASE_FEATURES + [c for c in BDI_FEATURES if c in df.columns]
    tr, va, te = _split(df)
    X = lambda d: d[feats].values
    dtr, dva, dte = (xgb.DMatrix(X(d), label=d["target_ret"].values, feature_names=feats) for d in (tr, va, te))

    params = {"max_depth": 3, "eta": 0.05, "subsample": 0.8, "colsample_bytree": 0.8,
              "min_child_weight": 5, "lambda": 5.0, "seed": 42, "disable_default_eval_metric": 1}
    booster = xgb.train(params, dtr, num_boost_round=400, obj=asymmetric_regret_objective,
                        evals=[(dva, "val")], custom_metric=lambda p, d: ("regret", regret(d.get_label(), p)),
                        early_stopping_rounds=30, verbose_eval=False)
    p_xgb = booster.predict(dte, iteration_range=(0, booster.best_iteration + 1))

    sc = StandardScaler().fit(X(tr))
    ridge = Ridge(alpha=10.0).fit(sc.transform(X(tr)), tr["target_ret"])
    p_ridge = ridge.predict(sc.transform(X(te)))
    p_zero = np.zeros(len(te))

    res = {
        "n_train": len(tr), "n_val": len(va), "n_test": len(te),
        "train_dates": [str(tr.date.min().date()), str(tr.date.max().date())],
        "test_dates": [str(te.date.min().date()), str(te.date.max().date())],
        "n_test_weeks": int(te.date.nunique()),
        "features": feats, "best_iteration": int(booster.best_iteration),
        "xgb_asymmetric": _scores(te, p_xgb),
        "ridge_baseline": _scores(te, p_ridge),
        "persistence_baseline": _scores(te, p_zero),
    }
    gain = booster.get_score(importance_type="gain")
    tot = sum(gain.values()) or 1.0
    res["feature_importance_gain"] = {k: round(v / tot, 4) for k, v in sorted(gain.items(), key=lambda kv: -kv[1])}
    res["caveat"] = (f"Test set = {res['n_test_weeks']} weeks x {te.route_id.nunique()} routes; "
                     "rows within a week are correlated. Treat as indicative, not statistically conclusive.")
    ART.mkdir(exist_ok=True)
    booster.save_model(str(ART / "model2_xgb.json"))
    (ART / "model2_metrics.json").write_text(json.dumps(res, indent=2))
    return res


class XGBoostFreightTrainer:
    """API-compatible wrapper for backend/main.py. Returns CACHED real metrics
    (main.py calls train_model() per request - never retrain there)."""
    def train_model(self) -> Dict[str, Any]:
        f = ART / "model2_metrics.json"
        res = json.loads(f.read_text()) if f.exists() else train()
        x, base = res["xgb_asymmetric"], res["persistence_baseline"]
        red = 100 * (1 - x["asym_regret_logret"] / base["asym_regret_logret"]) if base["asym_regret_logret"] else 0.0
        return {"model_architecture": "XGBoost (asymmetric regret objective)",
                "performance": {"rmse_usd_ton": round(x["rmse_usd_mt"], 3), "mae_usd_ton": round(x["mae_usd_mt"], 3),
                                "r2_score": round(x["r2_level"], 3),
                                "backtest_accuracy_pct": round(100 * x["directional_accuracy"], 1) if x["directional_accuracy"] is not None else None,
                                "asymmetric_regret_score": round(x["asym_regret_logret"], 4),
                                "baseline_ols_regret": round(base["asym_regret_logret"], 4),
                                "regret_reduction_pct": round(red, 1)},
                "feature_importance_shap": res["feature_importance_gain"], "details": res}


if __name__ == "__main__":
    print(json.dumps(train(), indent=2))
