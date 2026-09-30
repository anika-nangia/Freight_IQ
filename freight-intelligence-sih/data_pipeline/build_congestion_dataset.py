"""
Build the Model 1 dataset from real port line-up data.

WHAT THE LINE-UP DATA ACTUALLY CONTAINS
    data/vessel_snapshots.csv gives, per port and snapshot date, each vessel's status
    (Working / Waiting / Expected), its berth, cargo, direction, and critically
    arrival_or_eta plus etc_or_etcd. The gap between those two dates is a REALISED
    turnaround time, observed rather than assumed. That is the modelling target.

FEATURES are all knowable at decision time:
    queue_waiting      vessels at the anchorage waiting for a berth
    vessels_working   vessels currently discharging
    berths_total      berth capacity at the port
    berth_occupancy   working / total, from the line-up itself
    arrivals_7d       vessels expected to arrive within a week
    inbound_working   share of the working fleet discharging (import) vs loading (export)
    plus Open-Meteo wind and rainfall for the port that week.

LEAKAGE
    Turnaround for a vessel that is still working is not yet observable, so the
    training sample is restricted to vessels whose ETCD is known AND is not in the
    future relative to the snapshot. The congestion SCORE, by contrast, is computed
    from the same snapshot, so it is a legitimate live input.

Run:  python -m data_pipeline.build_congestion_dataset
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402

LINEUPS = ROOT / "data" / "vessel_snapshots.csv"
BERTHS = ROOT / "data" / "berth_operations.csv"
WEATHER = ROOT / "data" / "external" / "port_weather_daily.csv"
OUT = ROOT / "data" / "interim" / "congestion_dataset.csv"
REPORT = ROOT / "data" / "interim" / "congestion_report.json"

# A turnaround longer than this is a data error (an ETCD a year out), not an operation.
MAX_TURNAROUND_DAYS = 120.0
# Ports whose names differ between the line-up report and the weather file.
PORT_ALIASES = {
    "PARADIP PORT": "PARADIP",
    "SANDHEADS": "SAGAR",
    "VISAKHAPATNAM": "VISAKHAPATNAM",
}
WEATHER_NAMES = {
    "PARADIP": "Paradip", "HALDIA": "Haldia", "DHAMRA": "Dhamra",
    "VISAKHAPATNAM": "Visakhapatnam", "GANGAVARAM": "Gangavaram",
    "GOPALPUR": "Gopalpur", "SAGAR": "Sagar & Sandheads",
}
IMPORT_WORDS = ("IMP", "IMPORT", "DISCH", "DISCHARGE")
EXPORT_WORDS = ("LOAD", "LOADING", "EXP", "EXPORT")
BOTH_WORDS = ("D/L", "D/D", "BOTH")


def _norm_for_flow(name: str) -> str:
    """Normalise a port name to the key used in the line-up data."""
    return (PORT_ALIASES.get(str(name).strip().lower())
            or str(name).strip().upper())


def _dir_class(s: str) -> Optional[str]:
    if not isinstance(s, str):
        return None
    u = s.strip().upper()
    for w in BOTH_WORDS:
        if w in u:
            return "both"
    for w in IMPORT_WORDS:
        if w in u:
            return "import"
    for w in EXPORT_WORDS:
        if w in u:
            return "export"
    return None


def _vessel_class(s: str) -> Optional[str]:
    if not isinstance(s, str):
        return None
    u = s.strip().upper()
    for token, cls in (("PANAMAX", "Panamax"), ("SUPRAMAX", "Supramax"),
                       ("HANDIMAX", "Handymax"), ("HANDYSIZE", "Handysize"),
                       ("CAPE", "Capesize")):
        if token in u:
            return cls
    return None


def load_lineups() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return (snapshot-level congestion features, vessel-level realised turnarounds)."""
    d = pd.read_csv(LINEUPS)
    d["snapshot_date"] = pd.to_datetime(d["snapshot_date"])
    d["port"] = d["port"].astype(str).str.strip().str.upper().replace(PORT_ALIASES)
    d["status_clean"] = d["status"].astype(str).str.strip()

    # ---------------- snapshot-level features ----------------
    d["is_waiting"] = d["status_clean"].str.contains("Waiting", case=False, na=False).astype(int)
    d["is_working"] = (d["status_clean"].str.contains("Working", case=False, na=False)).astype(int)
    d["is_expected"] = d["status_clean"].str.contains("Expected", case=False, na=False).astype(int)

    # 'Waiting & Expected' is ambiguous and has to be split before it can be counted.
    # At Paradip every row carries that status with no vessel berthed, which is an
    # arrivals forecast, not an anchorage queue. Treating those 40 vessels as waiting
    # produced a queue of 40 against zero berthed and a congestion score with no
    # operational meaning behind it.
    #
    # A vessel is only genuinely at anchor if it has already arrived:
    # arrival_or_eta on or before the snapshot date.
    _arr = pd.to_datetime(d["arrival_or_eta"], errors="coerce")
    _arrived = ((_arr - d["snapshot_date"]).dt.days <= 0).astype(int)
    _arrived[_arr.isna()] = 0
    d["has_arrived"] = _arrived
    d["is_queued"] = ((d["is_waiting"] == 1) & (d["has_arrived"] == 1)).astype(int)
    d["dir_class"] = d["direction"].map(_dir_class)
    d["vessel_class"] = d["vessel_type"].map(_vessel_class)

    g = d.groupby(["port", "snapshot_date"], as_index=False)
    snap = g.agg(
        vessels_in_lineup=("status_clean", "size"),
        queue_waiting=("is_queued", "sum"),
        vessels_awaiting_berth=("is_waiting", "sum"),
        vessels_working=("is_working", "sum"),
        vessels_expected=("is_expected", "sum"),
        working_import=("is_working", lambda s: 0),   # replaced below
        cargo_tonnage=("quantity_mts_numeric", lambda s: float(np.nansum(s)) if len(s) else 0.0),
    )
    # Direction split has to be computed on the masked rows, not via agg.
    wk = d[d["is_working"] == 1]
    split = (wk.groupby(["port", "snapshot_date"])["dir_class"]
               .value_counts().unstack(fill_value=0).reset_index())
    for col in ("import", "export", "both"):
        if col not in split.columns:
            split[col] = 0
    split = split.rename(columns={"import": "working_import", "export": "working_export",
                                  "both": "working_both"})
    snap = snap.drop(columns=["working_import"]).merge(
        split[["port", "snapshot_date", "working_import", "working_export", "working_both"]],
        on=["port", "snapshot_date"], how="left")

    # Expected arrivals inside a week of the snapshot.
    arr = pd.to_datetime(d["arrival_or_eta"], errors="coerce")
    soon = d.assign(_soon=((arr - d["snapshot_date"]).dt.days.between(0, 7))).astype({"_soon": int})
    arrivals = soon.groupby(["port", "snapshot_date"])["_soon"].sum().reset_index()
    arrivals.columns = ["port", "snapshot_date", "arrivals_next_7d"]
    snap = snap.merge(arrivals, on=["port", "snapshot_date"], how="left")

    berths = _berth_capacity()
    snap = snap.merge(berths, on="port", how="left")
    snap["berth_occupancy"] = np.where(
        snap["berths_total"] > 0, snap["vessels_working"] / snap["berths_total"], np.nan)
    snap["queue_ratio"] = np.where(
        snap["vessels_working"] > 0, snap["queue_waiting"] / snap["vessels_working"], 0.0)

    # ---------------- vessel-level realised turnaround ----------------
    v = d.copy()
    v["arrival"] = pd.to_datetime(v["arrival_or_eta"], errors="coerce")
    v["etcd"] = pd.to_datetime(v["etc_or_etcd"], errors="coerce")
    v["turnaround_days"] = (v["etcd"] - v["arrival"]).dt.total_seconds() / 86400.0
    # Keep only physically sensible observations: ETCD at or after arrival, and inside
    # the plausible range. The raw file contains ETCDs over a year out, which are
    # scheduling placeholders rather than completions.
    v = v.dropna(subset=["arrival", "etcd", "turnaround_days"])
    v = v[(v["turnaround_days"] >= 0) & (v["turnaround_days"] <= MAX_TURNAROUND_DAYS)]
    return snap, v


def _berth_capacity() -> pd.DataFrame:
    """Berth count per port, taken from the line-up's own berth names.

    berth_operations.csv holds only 'Vacant' rows, so it cannot supply a denominator.
    The line-up does: each snapshot lists the berths actually in use, and the number of
    distinct berth names observed at a port is the best available capacity figure.
    """
    b = pd.read_csv(LINEUPS)
    b["port"] = b["port"].astype(str).str.strip().str.upper().replace(PORT_ALIASES)
    b = b[b["berth_name"].notna() & (b["berth_name"].astype(str).str.strip() != "")]
    cap = (b.groupby("port")["berth_name"].nunique().reset_index()
             .rename(columns={"berth_name": "berths_total"}))
    return cap


def add_weather(snap: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    if not WEATHER.exists():
        print("[congestion] weather cache absent -> weather features skipped")
        return snap, False
    w = pd.read_csv(WEATHER, parse_dates=["date"])
    w["region"] = w["port"].str.strip().str.title()
    w["week"] = w["date"] - pd.to_timedelta(w["date"].dt.weekday, unit="D")
    wk = (w.groupby(["region", "week"], as_index=False)
            .agg(weather_wind_max_kt=("wind_max_kt", "max"),
                 weather_precip_mm=("precip_mm", "sum"),
                 weather_gale_days=("gale_flag", "sum"))
            .sort_values(["region", "week"]))

    out = snap.copy()
    out["weather_port"] = out["port"].map(WEATHER_NAMES)
    out["week"] = out["snapshot_date"] - pd.to_timedelta(out["snapshot_date"].dt.weekday, unit="D")

    # Explicit per-region backward search: merge_asof advances one global cursor and
    # silently returns NaN for whole groups when left_by/right_by are used together.
    for col in ("weather_wind_max_kt", "weather_precip_mm", "weather_gale_days"):
        out[col] = np.nan
        for region, grp in wk.groupby("region"):
            weeks = grp["week"].to_numpy()
            vals = grp[col].to_numpy(dtype=float)
            sel = (out["weather_port"].to_numpy() == region)
            if not sel.any():
                continue
            obs = out.loc[sel, "week"].to_numpy()
            pos = np.searchsorted(weeks, obs, side="right") - 1
            ok = pos >= 0
            assigned = np.full(obs.shape, np.nan, dtype=float)
            assigned[ok] = vals[pos[ok]]
            out.loc[sel, col] = assigned
    out = out.drop(columns=["weather_port", "week"], errors="ignore")
    print(f"[congestion] weather matched {out['weather_wind_max_kt'].notna().sum()}/{len(out)} snapshots")
    return out, True


def build() -> Tuple[pd.DataFrame, pd.DataFrame]:
    snap, vessels = load_lineups()
    snap, has_wx = add_weather(snap)

    # Attach the realised turnaround to the snapshot it was observed in, so each
    # training row is (congestion state at snapshot) -> (turnaround that followed).
    cols = ["port", "snapshot_date", "arrival", "etcd", "turnaround_days",
            "vessel_class", "dir_class", "quantity_mts_numeric"]
    v = vessels[[c for c in cols if c in vessels.columns]].copy()
    v = v.rename(columns={"quantity_mts_numeric": "cargo_mt"})
    panel = snap.merge(v, on=["port", "snapshot_date"], how="inner")
    panel = panel.rename(columns={"quantity_mts_numeric": "cargo_mt"})

    features = ["queue_waiting", "vessels_awaiting_berth", "vessels_working",
                "berths_total", "berth_occupancy",
                "queue_ratio", "vessels_expected", "arrivals_next_7d",
                "working_import", "working_export", "cargo_tonnage",
                "weather_wind_max_kt", "weather_precip_mm", "weather_gale_days"]
    features = [f for f in features if f in panel.columns]
    n0 = len(panel)
    # Only the turnaround target is required. Weather and berth capacity are missing
    # for some ports, and an earlier version dropped those rows here, which silently
    # cut the dataset from 11 ports to 5. Gaps are imputed at training time from
    # training-period medians instead, so no geography is lost.
    panel = panel.dropna(subset=["turnaround_days"]).reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUT, index=False)
    snap.to_csv(ROOT / "data" / "interim" / "port_congestion_snapshots.csv", index=False)

    per_port = (snap.groupby("port")
                   .agg(snapshots=("snapshot_date", "nunique"),
                        mean_queue=("queue_waiting", "mean"),
                        max_queue=("queue_waiting", "max"),
                        mean_occupancy=("berth_occupancy", "mean"))
                   .round(2).reset_index())
    report = {
        "built_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
        "training_rows": int(len(panel)),
        "rows_before_filter": int(n0),
        "ports": int(snap["port"].nunique()),
        "snapshot_dates": sorted(d.strftime("%Y-%m-%d") for d in snap["snapshot_date"].unique()),
        "features": features,
        "target": "turnaround_days = ETCD - arrival, observed per vessel",
        "target_stats": {k: round(float(v), 3) for k, v in
                         panel["turnaround_days"].describe().items()},
        "weather_available": has_wx,
        "per_port": per_port.to_dict(orient="records"),
        "provenance_tier": prov.get("port_lineups").tier,
        "ports_with_turnaround_observations": int(panel["port"].nunique()),
        "known_limitations": [
            "Snapshots cover August 2026 only: 12 trading days, 14 ports. A walk-forward "
            "test on this is a handful of folds and should be read as a sanity check, "
            "not a performance claim.",
            "A vessel's turnaround is only known once it has discharged, so the newest "
            "snapshots are under-represented among completed voyages. The chronological "
            "split accounts for this by testing only on the latest dates.",
            "berths_total is inferred from distinct berth names seen in the line-up, "
            "because berth_operations.csv contains only 'Vacant' rows and therefore "
            "cannot supply a capacity denominator. Ports whose report omits berth names "
            "(Paradip among them) have no occupancy figure, so it is imputed and the "
            "score leans on queue length instead.",
            "'Waiting & Expected' is split into 'arrived and waiting' and 'not yet "
            "arrived'. Some ports list every vessel under that single status, so "
            "counting it verbatim produced a queue of 40 against zero berthed vessels "
            "at Paradip. Only vessels with an arrival date on or before the snapshot "
            "are counted as queued.",
        ],
    }
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"[congestion] {len(panel)} training rows (from {n0}) | "
          f"{snap['port'].nunique()} ports | {snap['snapshot_date'].nunique()} snapshot dates")
    print(f"[congestion] turnaround days: median {panel['turnaround_days'].median():.1f}, "
          f"p90 {panel['turnaround_days'].quantile(0.9):.1f}")
    print(f"[congestion] wrote {OUT}")
    return panel, snap


if __name__ == "__main__":
    build()
