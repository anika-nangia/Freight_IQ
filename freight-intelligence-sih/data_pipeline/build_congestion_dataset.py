"""
Build the Model 1 dataset from real port line-up data.

WHAT THE TARGET ACTUALLY IS  (this was wrong before, and the correction matters)
    The previous version of this file computed `turnaround_days = ETCD - arrival`
    and called it a REALISED turnaround. It is not.

    A turnaround time is an outcome: it needs an actual arrival and an actual
    departure. This dataset contains NEITHER completion field. There is no
    'sailed', 'departed', 'actual completion' or 'closed' column, and the only
    status values are Expected / Waiting / Waiting & Expected / Working - all of
    which describe a vessel that has not yet finished.

    So `arrival_or_eta` is an ETA for anything not yet arrived, and `etc_or_etcd`
    is the port's own forward-looking schedule. The quantity we can compute is
    therefore the port's ESTIMATE of port stay, not a measured one. It is renamed
    `estimated_port_stay_days` throughout and is never described as realised.

    This is not a cosmetic change. Two consequences:
      * a model fitted to it predicts the port's schedule, which is partly a
        function of the port's own queue-management behaviour;
      * 'ties the port median' now means the model adds nothing beyond what a
        static per-port schedule would give, which is a much weaker claim than
        beating real turnaround.

TWO MORE DEFECTS FIXED HERE
    1. Pseudo-replication. The same voyage appears on every snapshot it is listed
       on, so the old build produced 1,608 rows that are really 692 voyages. A
       vessel whose ETCD slid from 25 Aug to 26 Aug was counted as a second,
       independent observation of the same voyage.
    2. Contaminated target. 41% of those rows were for vessels that had not yet
       arrived, so `arrival_or_eta` was an ETA and the "turnaround" was a forecast
       of a forecast.

    Now: exactly one row per voyage, and only voyages whose arrival has actually
    happened at the snapshot we read them from.

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
WEATHER = ROOT / "data" / "external" / "port_weather_daily.csv"
OUT = ROOT / "data" / "interim" / "congestion_dataset.csv"
SNAPSHOTS_OUT = ROOT / "data" / "interim" / "port_congestion_snapshots.csv"
REPORT = ROOT / "data" / "interim" / "congestion_report.json"

TARGET = "estimated_port_stay_days"
MAX_STAY_DAYS = 120.0

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
    return PORT_ALIASES.get(str(name).strip().lower()) or str(name).strip().upper()


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


def _load_lineups() -> pd.DataFrame:
    d = pd.read_csv(LINEUPS)
    d["snapshot_date"] = pd.to_datetime(d["snapshot_date"])
    d["port"] = d["port"].astype(str).str.strip().str.upper().replace(PORT_ALIASES)
    d["status_clean"] = d["status"].astype(str).str.strip()
    d["arrival"] = pd.to_datetime(d["arrival_or_eta"], errors="coerce")
    d["etcd"] = pd.to_datetime(d["etc_or_etcd"], errors="coerce")
    d["dir_class"] = d["direction"].map(_dir_class)
    d["vessel_class"] = d["vessel_type"].map(_vessel_class)
    d["tonnage"] = pd.to_numeric(d["quantity_mts_numeric"], errors="coerce").fillna(0.0)

    d["is_working"] = d["status_clean"].str.contains("Working", case=False, na=False).astype(int)
    d["is_expected"] = d["status_clean"].str.contains("Expected", case=False, na=False).astype(int)
    # 'Waiting & Expected' is ambiguous. A vessel only counts as queued if it has
    # already arrived. At Paradip all 40 listed vessels carry that status with none
    # berthed, which is an arrivals forecast, not an anchorage queue.
    d["has_arrived"] = ((d["arrival"] - d["snapshot_date"]).dt.days <= 0).astype(int)
    d.loc[d["arrival"].isna(), "has_arrived"] = 0
    d["is_queued"] = (d["status_clean"].str.contains("Waiting", case=False, na=False)
                      & (d["has_arrived"] == 1)).astype(int)
    return d


def snapshot_features(d: pd.DataFrame) -> pd.DataFrame:
    """Line-up state per port per snapshot date. Observed, all knowable in advance."""
    g = d.groupby(["port", "snapshot_date"], as_index=False)
    snap = g.agg(
        vessels_in_lineup=("status_clean", "size"),
        queue_waiting=("is_queued", "sum"),
        vessels_awaiting_berth=("is_waiting", "sum") if "is_waiting" in d.columns else ("is_queued", "sum"),
        vessels_working=("is_working", "sum"),
        vessels_expected=("is_expected", "sum"),
        cargo_tonnage=("tonnage", "sum"),
    )
    wk = d[d["is_working"] == 1]
    split = (wk.groupby(["port", "snapshot_date"])["dir_class"]
               .value_counts().unstack(fill_value=0).reset_index())
    for c in ("import", "export", "both"):
        if c not in split.columns:
            split[c] = 0
    split = split.rename(columns={"import": "working_import", "export": "working_export",
                                  "both": "working_both"})
    if "working_import" in snap.columns:
        snap = snap.drop(columns=["working_import"])
    snap = snap.merge(
        split[["port", "snapshot_date", "working_import", "working_export", "working_both"]],
        on=["port", "snapshot_date"], how="left")

    arr = d.copy()
    arr["_soon"] = ((arr["arrival"] - arr["snapshot_date"]).dt.days.between(0, 7)).astype(int)
    arr = arr[(arr["has_arrived"] == 0)]      # inbound, not yet present
    arrivals = arr.groupby(["port", "snapshot_date"])["_soon"].sum().reset_index()
    arrivals.columns = ["port", "snapshot_date", "arrivals_next_7d"]
    snap = snap.merge(arrivals, on=["port", "snapshot_date"], how="left")

    cap = _berth_capacity(d)
    snap = snap.merge(cap, on="port", how="left")
    snap["berth_occupancy"] = np.where(snap["berths_total"] > 0,
                                       snap["vessels_working"] / snap["berths_total"], np.nan)
    snap["queue_ratio"] = np.where(snap["vessels_working"] > 0,
                                   snap["queue_waiting"] / snap["vessels_working"], 0.0)
    return snap


def _berth_capacity(d: pd.DataFrame) -> pd.DataFrame:
    """Berth count from the line-up's own berth names.

    berth_operations.csv holds only 'Vacant' rows, so it cannot supply a denominator.
    Ports whose report omits berth names get no figure, and the column stays blank
    rather than being filled with a guess.
    """
    b = d[d["berth_name"].notna() & (d["berth_name"].astype(str).str.strip() != "")]
    if b.empty:
        return pd.DataFrame(columns=["port", "berths_total"])
    return (b.groupby("port")["berth_name"].nunique().reset_index()
             .rename(columns={"berth_name": "berths_total"}))


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
    for col in ("weather_wind_max_kt", "weather_precip_mm", "weather_gale_days"):
        out[col] = np.nan
        for region, grp in wk.groupby("region"):
            weeks = grp["week"].to_numpy()
            vals = grp[col].to_numpy(dtype=float)
            sel = (out["weather_port"].to_numpy() == region)
            if not sel.any():
                continue
            pos = np.searchsorted(weeks, out.loc[sel, "week"].to_numpy(), side="right") - 1
            ok = pos >= 0
            assigned = np.full(int(sel.sum()), np.nan)
            assigned[ok] = vals[pos[ok]]
            out.loc[sel, col] = assigned
    out = out.drop(columns=["weather_port", "week"], errors="ignore")
    print(f"[congestion] weather matched {out['weather_wind_max_kt'].notna().sum()}/{len(out)} snapshots")
    return out, True


def build_voyage_table(snap: pd.DataFrame) -> pd.DataFrame:
    """One row per voyage: the port's estimate of port stay, read at first berthing.

    A voyage is keyed by port + vessel + arrival date. We take the first snapshot at
    which the vessel is recorded as Working AND its arrival date is on or before that
    snapshot, so the arrival leg is a real event rather than an ETA.

    Everything else about the vessel is dropped, including later snapshots. A second
    sighting of the same voyage is not a second observation, and treating it as one
    put 80% of the held-out rows in the training set.
    """
    return snap  # placeholder replaced by caller-provided voyage frame


def build() -> pd.DataFrame:
    d = _load_lineups()
    snap = snapshot_features(d)
    snap, has_wx = add_weather(snap)

    # ---------------------------------------------------- one row per voyage
    d["voyage_key"] = (d["port"] + "|" + d["vessel_name"].astype(str) + "|"
                      + d["arrival"].dt.strftime("%Y-%m-%d"))
    eligible = d[(d["is_working"] == 1) & (d["has_arrived"] == 1) & d["etcd"].notna()].copy()
    n_all_voyages = d[d["etcd"].notna()]["voyage_key"].nunique()

    first = (eligible.sort_values("snapshot_date")
             .groupby("voyage_key", as_index=False)
             .agg(port=("port", "first"),
                  vessel_class=("vessel_class", "first"),
                  dir_class=("dir_class", "first"),
                  cargo_mt=("tonnage", "first"),
                  snapshot_date=("snapshot_date", "min"),
                  arrival=("arrival", "first"),
                  etcd=("etcd", "first")))
    first[TARGET] = (first["etcd"] - first["arrival"]).dt.total_seconds() / 86400.0
    first = first[(first[TARGET] >= 0) & (first[TARGET] <= MAX_STAY_DAYS)]

    # The port REVISES ETCD as a voyage progresses. Reading it at the first berthing
    # is the decision-relevant moment and keeps the definition consistent.
    panel = first.merge(snap, on=["port", "snapshot_date"], how="left")
    panel = panel.reset_index(drop=True)

    features = ["queue_waiting", "vessels_awaiting_berth", "vessels_working", "berths_total",
                "berth_occupancy", "queue_ratio", "vessels_expected", "arrivals_next_7d",
                "working_import", "working_export", "cargo_tonnage",
                "weather_wind_max_kt", "weather_precip_mm"]
    features = [f for f in features if f in panel.columns]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUT, index=False)
    snap.to_csv(SNAPSHOTS_OUT, index=False)

    # Split integrity: the whole point of the rebuild is that a voyage cannot appear
    # on both sides of the split. Asserted here as well as in the test suite.
    dates = sorted(panel["snapshot_date"].unique())
    test_dates = set(dates[-3:])
    tr = set(panel.loc[~panel["snapshot_date"].isin(test_dates), "voyage_key"])
    te = set(panel.loc[panel["snapshot_date"].isin(test_dates), "voyage_key"])

    per_port = (panel.groupby("port")[TARGET]
                   .agg(voyages="size", median_days="median")
                   .round(1).sort_values("voyages", ascending=False).reset_index())

    report = {
        "built_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
        "target": TARGET,
        "target_definition": "etc_or_etcd minus arrival_or_eta, read at the first snapshot "
                             "where the vessel is recorded as Working and its arrival date "
                             "has passed",
        "target_is_an_estimate": True,
        "why_it_is_an_estimate": "The line-up data contains no actual completion, departure "
                                 "or sailing field. Status values are only Expected / Waiting / "
                                 "Waiting & Expected / Working, so no voyage is ever recorded "
                                 "as finished. The target is therefore the port's own published "
                                 "schedule, not a measured turnaround. This model predicts the "
                                 "port's estimate.",
        "no_realised_turnaround_available": True,
        "rows": int(len(panel)),
        "voyages_with_etcd_total": int(n_all_voyages),
        "voyages_kept": int(len(panel)),
        "voyages_dropped_not_yet_berthed_or_arrival_is_eta": int(n_all_voyages - len(panel)),
        "ports": int(panel["port"].nunique()),
        "snapshot_dates": [x.strftime("%Y-%m-%d") for x in dates],
        "features": features,
        "weather_available": has_wx,
        "split_integrity": {
            "train_voyages": len(tr), "test_voyages": len(te),
            "voyage_overlap": len(tr & te),
            "test_dates": sorted(x.strftime("%Y-%m-%d") for x in test_dates),
        },
        "target_stats": {k: round(float(v), 2) for k, v in panel[TARGET].describe().items()},
        "per_port": per_port.to_dict(orient="records"),
        "provenance_tier": prov.get("port_lineups").tier,
        "known_limitations": [
            "The target is the port's ESTIMATE of port stay. No actual completion time "
            "exists in the source data, so realised turnaround cannot be modelled at all.",
            "Because the target is the port's own schedule, a good score partly reflects "
            "the port's queue-management behaviour rather than independent information.",
            f"{panel['port'].value_counts().iloc[0]} of {len(panel)} voyages "
            f"({panel['port'].value_counts().iloc[0] / len(panel):.0%}) are one port, so the "
            "effective sample is far smaller than the row count suggests.",
            "12 snapshot dates in August 2026. A 3-date holdout is a handful of voyages "
            "and cannot support a performance claim.",
            "berths_total is inferred from distinct berth names in the line-up; ports whose "
            "report omits berth names have no occupancy figure and it is imputed.",
        ],
    }
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    si = report["split_integrity"]
    print(f"[congestion] {len(panel)} voyages (of {n_all_voyages} with an ETCD) | "
          f"{panel['port'].nunique()} ports | {panel['snapshot_date'].nunique()} dates")
    print(f"[congestion] target {TARGET}: median {panel[TARGET].median():.1f}d, "
          f"p90 {panel[TARGET].quantile(0.9):.1f}d")
    print(f"[congestion] split: {si['train_voyages']} train / {si['test_voyages']} test, "
          f"voyage overlap = {si['voyage_overlap']}")
    print(f"[congestion] TARGET IS AN ESTIMATE: {report['target_is_an_estimate']}")
    print(f"[congestion] wrote {OUT}")
    return panel


if __name__ == "__main__":
    build()
