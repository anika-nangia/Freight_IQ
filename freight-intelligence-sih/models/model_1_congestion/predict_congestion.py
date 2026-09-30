"""
Model 1 inference: port congestion score and turnaround range.

Replaces a hand-weighted linear formula that was described in the code as
"calibrated to the empirical gradient boosting model" but had never been calibrated
to anything. The weights below are a hardcoded guess at queue and weather effects.

Now the score is derived from the fitted model in
models/model_1_congestion/train_congestion.py, and the turnaround figure is a range
from the model's measured residual quantiles rather than a bare point.

Two quantities, kept distinct because they answer different questions:
  * turnaround_estimate  forward-looking, from the model, with a range
  * observed_turnaround  historical, computed from the line-up data
Conflating them would let a historical figure masquerade as a prediction.
"""
from __future__ import annotations

import json
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402

ART = ROOT / "models" / "artifacts"
MODEL_PATH = ART / "congestion_model.json"
METRICS_PATH = ART / "congestion_metrics.json"
SNAPSHOTS = ROOT / "data" / "interim" / "port_congestion_snapshots.csv"
DATASET = ROOT / "data" / "interim" / "congestion_dataset.csv"
WEATHER = ROOT / "data" / "external" / "port_weather_daily.csv"

PORT_ALIASES = {
    "paradip port": "PARADIP", "sandheads": "SAGAR",
    "visakhapatnam": "VISAKHAPATNAM", "gopalpur": "GOPALPUR",
    "krishnapatnam": "KRISHNAPATNAM", "kakinada": "KAKINADA",
    "kattupalli": "KATTUPALLI", "karaikal": "KARAIKAL", "ennore": "ENNORE",
    "chennai": "CHENNAI", "haldia": "HALDIA", "dhamra": "DHAMRA",
    "gangavaram": "GANGAVARAM", "sagar": "SAGAR",
}
WEATHER_NAMES = {
    "PARADIP": "Paradip", "HALDIA": "Haldia", "DHAMRA": "Dhamra",
    "VISAKHAPATNAM": "Visakhapatnam", "GANGAVARAM": "Gangavaram",
    "GOPALPUR": "Gopalpur", "SAGAR": "Sagar & Sandheads",
}

# Congestion bands. The thresholds are policy, not fitted parameters, and are
# labelled as such wherever they are reported.
BANDS = [(0.75, "Critical"), (0.55, "High"), (0.35, "Moderate"), (0.0, "Low")]


def _norm_port(name: str) -> str:
    return PORT_ALIASES.get(str(name).strip().lower(), str(name).strip().upper())


class CongestionPredictor:
    """Score a port from its live line-up, using the fitted turnaround model."""

    def __init__(self, model_path: Path = MODEL_PATH, metrics_path: Path = METRICS_PATH,
                 snapshots: Path = SNAPSHOTS, dataset: Path = DATASET) -> None:
        self.model_path, self.metrics_path = model_path, metrics_path
        self.snapshots_path, self.dataset_path = snapshots, dataset
        self._bundle = None
        self._metrics: Optional[Dict[str, Any]] = None
        self._snapshots: Optional[pd.DataFrame] = None
        self._history: Optional[pd.DataFrame] = None
        self._weather: Optional[pd.DataFrame] = None

    # ---------------------------------------------------------------- loading
    def _load(self) -> None:
        if self._bundle is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"{self.model_path} missing. Run: python -m models.model_1_congestion.train_congestion")
        if not self.metrics_path.exists():
            raise FileNotFoundError(f"{self.metrics_path} missing")
        with self.model_path.open("rb") as fh:
            self._bundle = pickle.load(fh)
        self._metrics = json.loads(self.metrics_path.read_text(encoding="utf-8"))
        if self.snapshots_path.exists():
            self._snapshots = pd.read_csv(self.snapshots_path, parse_dates=["snapshot_date"])
        if self.dataset_path.exists():
            self._history = pd.read_csv(self.dataset_path, parse_dates=["snapshot_date"])
        if WEATHER.exists():
            w = pd.read_csv(WEATHER, parse_dates=["date"])
            w["region"] = w["port"].str.strip().str.title()
            w = w.sort_values("date")
            self._weather = w

    @property
    def metrics(self) -> Dict[str, Any]:
        self._load()
        return self._metrics  # type: ignore[return-value]

    def latest_snapshot_date(self) -> Optional[str]:
        self._load()
        if self._snapshots is None or self._snapshots.empty:
            return None
        return self._snapshots["snapshot_date"].max().strftime("%Y-%m-%d")

    def known_ports(self) -> List[str]:
        self._load()
        if self._snapshots is None:
            return []
        return sorted(self._snapshots["port"].unique().tolist())

    # ------------------------------------------------------------------ inputs
    def _lineup_features(self, port: str) -> Optional[Dict[str, Any]]:
        """Most recent line-up row for a port, with the date it was observed."""
        self._load()
        if self._snapshots is None or self._snapshots.empty:
            return None
        p = _norm_port(port)
        rows = self._snapshots[self._snapshots["port"] == p]
        if rows.empty:
            return None
        r = rows.sort_values("snapshot_date").iloc[-1]
        return {
            "as_of": r["snapshot_date"].strftime("%Y-%m-%d"),
            "queue_waiting": float(r["queue_waiting"]),
            "vessels_awaiting_berth": float(r.get("vessels_awaiting_berth", np.nan))
            if pd.notna(r.get("vessels_awaiting_berth", np.nan)) else None,
            "vessels_working": float(r["vessels_working"]),
            "vessels_expected": float(r["vessels_expected"]),
            "arrivals_next_7d": float(r["arrivals_next_7d"]),
            "berths_total": float(r["berths_total"]) if pd.notna(r["berths_total"]) else np.nan,
            "berth_occupancy": float(r["berth_occupancy"]) if pd.notna(r["berth_occupancy"]) else np.nan,
            "queue_ratio": float(r["queue_ratio"]) if pd.notna(r["queue_ratio"]) else 0.0,
            "working_import": float(r["working_import"]) if pd.notna(r["working_import"]) else 0.0,
            "working_export": float(r["working_export"]) if pd.notna(r["working_export"]) else 0.0,
            "cargo_tonnage": float(r["cargo_tonnage"]) if pd.notna(r["cargo_tonnage"]) else 0.0,
        }

    def _weather_features(self, port: str) -> Dict[str, Any]:
        """Latest observed weather for the port, or blanks if we do not cover it."""
        out = {"weather_wind_max_kt": np.nan, "weather_precip_mm": np.nan,
               "weather_gale_days": np.nan, "weather_as_of": None}
        if self._weather is None:
            return out
        region = WEATHER_NAMES.get(_norm_port(port))
        if region is None:
            return out
        rows = self._weather[self._weather["region"] == region]
        if rows.empty:
            return out
        recent = rows.tail(7)
        out.update({
            "weather_wind_max_kt": float(recent["wind_max_kt"].max()),
            "weather_precip_mm": float(recent["precip_mm"].sum()),
            "weather_gale_days": float(recent["gale_flag"].sum()),
            "weather_as_of": rows["date"].max().strftime("%Y-%m-%d"),
        })
        return out

    # ----------------------------------------------------------------- scoring
    def _score_turnaround(self, feats: Dict[str, Any]) -> Dict[str, Any]:
        b = self._bundle
        medians = b.get("impute_medians", {})
        row = {c: feats.get(c, medians.get(c, 0.0)) for c in b["features"]}
        for c, v in medians.items():
            if row.get(c) is None or (isinstance(row.get(c), float) and np.isnan(row[c])):
                row[c] = v
        X = np.array([[float(row[c]) for c in b["features"]]], dtype=float)
        point = float(b["model"].predict(X)[0])
        q = (self._metrics or {}).get("residual_quantiles_days", {"p50": 0, "p80": 2, "p90": 4})
        return {
            "point_days": point,
            "p50_band_days": [round(max(0.0, point + q["p50"]), 1), round(max(0.0, point - q["p50"]), 1)],
            "p80_band_days": [round(max(0.0, point + q["p80"]), 1), round(max(0.0, point - q["p80"]), 1)],
            "p90_band_days": [round(max(0.0, point + q["p90"]), 1), round(max(0.0, point - q["p90"]), 1)],
        }

    def _observed(self, port: str) -> Optional[Dict[str, Any]]:
        """Historical turnaround at this port, from completed voyages only."""
        self._load()
        if self._history is None:
            return None
        h = self._history[self._history["port"] == _norm_port(port)]
        if h.empty:
            return None
        return {
            "n_vessels": int(len(h)),
            "median_days": round(float(h["turnaround_days"].median()), 1),
            "mean_days": round(float(h["turnaround_days"].mean()), 1),
            "p90_days": round(float(h["turnaround_days"].quantile(0.9)), 1),
            "period": [h["snapshot_date"].min().strftime("%Y-%m-%d"),
                       h["snapshot_date"].max().strftime("%Y-%m-%d")],
            "note": "completed voyages only (a vessel still working has no ETCD yet)",
        }

    def predict(self, port_name: str) -> Dict[str, Any]:
        """Congestion assessment for a port, from its latest line-up.

        Note the signature change: the old version took queue_waiting and
        berth_occupancy_ratio as arguments, which meant the caller had to invent them.
        Reading them from the line-up removes the fabricated inputs.
        """
        self._load()
        p = _norm_port(port_name)
        lineup = self._lineup_features(p)
        if lineup is None:
            return {
                "available": False,
                "port": port_name,
                "reason": f"no line-up data for '{p}'",
                "ports_with_data": self.known_ports(),
                "provenance": prov.unavailable("port_lineups",
                                               f"no line-up data for '{p}'"),
            }

        feats = {**lineup, **{k: v for k, v in self._weather_features(p).items()
                              if k in self._bundle["features"]}}
        ta = self._score_turnaround(feats)
        obs = self._observed(p)

        # Congestion score: a policy-mapped index, not a model output. The model
        # predicts turnaround; turning that into a 0-1 score needs a threshold
        # decision, and those thresholds are ours to own, so they are stated.
        queue_pressure = min(1.0, lineup["queue_waiting"] / 10.0)
        occupancy = lineup["berth_occupancy"] if not np.isnan(lineup["berth_occupancy"]) else 0.0
        inflow = min(1.0, lineup["arrivals_next_7d"] / 20.0)
        score = round(min(1.0, 0.45 * queue_pressure + 0.35 * occupancy + 0.20 * inflow), 3)
        band = next(name for thr, name in BANDS if score >= thr)

        out: Dict[str, Any] = {
            "available": True,
            "port": p,
            "congestion_score": score,
            "congestion_index_100": round(score * 100, 1),
            "congestion_category": band,
            "score_basis": "policy mapping from line-up pressure, not a fitted output. "
                           "Thresholds: " + ", ".join(f">={t} {n}" for t, n in BANDS),
            "turnaround_estimate": {
                "point_days": round(ta["point_days"], 1),
                "p80_range_days": sorted(ta["p80_band_days"]),
                "p90_range_days": sorted(ta["p90_band_days"]),
                "horizon": "per voyage, from the fitted model",
            },
            "observed_turnaround": obs,
            "lineup": lineup,
            "weather": self._weather_features(p),
            "requires_divert": score >= 0.70,
            "suggested_buffer_days": 3 if score >= 0.70 else 1 if score >= 0.50 else 0,
            "model": (self._metrics or {}).get("deployed_model"),
            "model_validation": (self._metrics or {}).get("validation_scheme"),
            "model_mae_days": ((self._metrics or {}).get("candidates", {})
                               .get((self._metrics or {}).get("deployed_model"), {}) or {}
                               ).get("mae_days"),
            "model_honesty": (self._metrics or {}).get("honest_reading"),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        out["provenance"] = prov.provenance_block(["port_lineups", "berth_status", "port_weather"])
        out["confidence"] = {
            "level": "low" if lineup["as_of"] < (self._snapshots["snapshot_date"].max()
                                                 ).strftime("%Y-%m-%d") else "medium",
            "reasons": [
                f"line-up observed {lineup['as_of']}, not live",
                f"{(self._metrics or {}).get('n_snapshot_dates', '?')} snapshot dates of history",
            ],
        }
        return out

    def port_summary(self) -> List[Dict[str, Any]]:
        self._load()
        if self._snapshots is None:
            return []
        latest = self._snapshots["snapshot_date"].max()
        rows = self._snapshots[self._snapshots["snapshot_date"] == latest]
        out = []
        for _, r in rows.sort_values("queue_waiting", ascending=False).iterrows():
            s = self.predict(r["port"])
            if s.get("available"):
                out.append({
                    "port": s["port"],
                    "congestion_score": s["congestion_score"],
                    "category": s["congestion_category"],
                    "queue_waiting": s["lineup"]["queue_waiting"],
                    "turnaround_p80_days": s["turnaround_estimate"]["p80_range_days"],
                    "as_of": s["lineup"]["as_of"],
                })
        return out


_PREDICTOR: Optional[CongestionPredictor] = None


def get_predictor() -> CongestionPredictor:
    global _PREDICTOR
    if _PREDICTOR is None:
        _PREDICTOR = CongestionPredictor()
    return _PREDICTOR


if __name__ == "__main__":
    print(json.dumps(get_predictor().port_summary(), indent=2))
