"""
Build the monthly corridor table: the modelling target for contract-horizon work.

WHY MONTHLY
    Charter decisions are made on monthly averages ("fix N voyages at $X over Q4"),
    not on a single week's assessment. The weekly series is kept for short-horizon
    entry timing; this table is what the contract module reads.

STRUCTURE  one row per (corridor, vessel_class, month)
    corridor_id     load_port -> discharge_region
    vessel_class    Handysize / Handymax / Supramax / Panamax / Capesize
    month           month-end date of the observation
    rate_usd_mt     month-end assessment, then month mean of that month's weeks
    ...             lagged market features (World Bank), all as-of backward

NO LOOKAHEAD
    World Bank publishes the Pink Sheet with roughly a two-month lag, so commodity
    features are shifted one full month before they are allowed to enter a row dated
    month M. Baltic features are joined as-of backward from data/external/bdi_subindices.csv
    and are simply absent while that file does not exist (tier = unavailable).

Run:  python -m data_pipeline.build_corridor_table
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402

RATES = ROOT / "data" / "training_matrix.csv"
PINK = ROOT / "data" / "external" / "world_bank_pink_sheet.csv"
BDI = ROOT / "data" / "external" / "bdi_subindices.csv"
WEATHER = ROOT / "data" / "external" / "port_weather_daily.csv"
OUT = ROOT / "data" / "interim" / "corridor_monthly.csv"
REPORT = ROOT / "data" / "interim" / "corridor_table_report.json"

# World Bank series -> suffix used in feature names
COMMODITY = {
    "coal_australia": "coal_aus",
    "coal_south_africa": "coal_saf",
    "iron_ore_cfr_spot": "iron_ore",
    "crude_oil_avg": "crude_oil",
}
# Publication lag of the Pink Sheet, in months. Applied to every commodity feature.
COMMODITY_LAG_MONTHS = 1

CLASS_OF_INDEX = {"bci": "Capesize", "bpi": "Panamax", "bsi": "Supramax", "bhsi": "Handysize"}


# --------------------------------------------------------------------------
# Loading + cleaning
# --------------------------------------------------------------------------
def load_rates() -> pd.DataFrame:
    """Weekly observations with inconsistent labels normalised."""
    df = pd.read_csv(RATES, parse_dates=["date"], encoding="utf-8-sig")
    for c in ["load_port", "unload_port", "vessel_type"]:
        df[c] = df[c].astype(str).str.strip().str.title()
    df["vessel_type"] = df["vessel_type"].str.replace(r"\s+", "", regex=True)  # Handy Max -> HandyMax

    # 'Paradip' and 'paradip' were separate series in the source; they are the same port.
    df["unload_port"] = df["unload_port"].replace({"paradip": "Paradip"})

    df["corridor_id"] = df["load_port"] + "->" + df["unload_port"]
    df["vessel_class"] = df["vessel_type"].replace({"HandyMax": "Handymax", "HandyMax": "Handymax"})

    # Collapse any residual duplicates within a week (same corridor+class+date).
    key = ["corridor_id", "vessel_class", "date"]
    if df.duplicated(key).any():
        n = int(df.duplicated(key).sum())
        print(f"[corridor] collapsing {n} duplicate corridor/week rows (mean of the duplicates)")
        df = df.groupby(key, as_index=False).agg(
            rate_usd_mt=("rate_usd_mt", "mean"), cargo_intake=("cargo_intake", "mean"))

    return df.sort_values(["corridor_id", "vessel_class", "date"]).reset_index(drop=True)


def to_monthly(weekly: pd.DataFrame) -> pd.DataFrame:
    """Collapse weeks to calendar months. Rates keep both the month-end and the mean."""
    w = weekly.copy()
    w["month"] = w["date"].values.astype("datetime64[M]")

    g = w.groupby(["corridor_id", "load_port", "unload_port", "vessel_class", "month"], as_index=False)
    m = g.agg(rate_usd_mt=("rate_usd_mt", "last"),        # month-end assessment
              rate_mean_usd_mt=("rate_usd_mt", "mean"),  # month average
              rate_min_usd_mt=("rate_usd_mt", "min"),
              rate_max_usd_mt=("rate_usd_mt", "max"),
              cargo_intake_mt=("cargo_intake", "mean"),
              n_weeks=("rate_usd_mt", "size"),
              last_observation=("date", "max"))
    m = m.sort_values(["corridor_id", "vessel_class", "month"]).reset_index(drop=True)
    return m


# --------------------------------------------------------------------------
# Feature groups
# --------------------------------------------------------------------------
def add_lane_features(m: pd.DataFrame) -> pd.DataFrame:
    """Within-corridor momentum and volatility. Uses only data up to month M."""
    m = m.sort_values(["corridor_id", "vessel_class", "month"]).copy()
    g = m.groupby(["corridor_id", "vessel_class"])["rate_usd_mt"]
    m["log_rate"] = np.log(m["rate_usd_mt"])
    for k in (1, 2, 3):
        m[f"ret_{k}m"] = np.log(m["rate_usd_mt"] / g.shift(k))
    m["roll_mean_3m"] = g.transform(lambda s: s.rolling(3, min_periods=3).mean())
    m["roll_std_6m"] = g.transform(lambda s: s.rolling(6, min_periods=4).std())
    m["roll_cv_6m"] = m["roll_std_6m"] / m["roll_mean_3m"]
    m["dev_from_mean_3m"] = np.log(m["rate_usd_mt"] / m["roll_mean_3m"])
    # Corridor spread against the all-lane mean of the same class: levels differ by
    # 3-4x across lanes, so a spread is far more stationary than a level.
    cm = m.groupby(["vessel_class", "month"])["log_rate"].transform("mean")
    m["log_spread_vs_class"] = m["log_rate"] - cm
    return m


def add_commodity_features(m: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """Merge World Bank prices as-of, then lag for publication delay."""
    if not PINK.exists():
        print(f"[corridor] {PINK.name} absent -> commodity features skipped")
        return m, False

    px = pd.read_csv(PINK, parse_dates=["month"]).rename(columns={"month": "_m"})
    px = px.set_index("_m").sort_index()

    # Lag by the publication delay so month M only sees data published by then.
    px = px.shift(COMMODITY_LAG_MONTHS)

    # Normalise each series to z-scores computed on the training period only later;
    # here we just keep log levels and 1/3-month momentum.
    out = m.sort_values("month").copy()
    for src, dst in COMMODITY.items():
        if src not in px.columns:
            print(f"[corridor] {src} not in pink sheet")
            continue
        s = px[src]
        out[f"{dst}_level"] = out["month"].map(s)
        out[f"{dst}_ret_1m"] = out["month"].map(np.log(s / s.shift(1)))
        out[f"{dst}_ret_3m"] = out["month"].map(np.log(s / s.shift(3)))

    n_filled = out[[f"{d}_ret_1m" for d in COMMODITY.values() if f"{d}_ret_1m" in out]].notna().all(axis=1).sum()
    print(f"[corridor] commodity features joined, {n_filled}/{len(out)} rows fully populated")
    return out, True


def add_bdi_features(m: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """Merge Baltic sub-indices as-of backward. Absent file -> feature group absent."""
    if not BDI.exists():
        print(f"[corridor] {BDI.name} absent -> BDI features skipped (tier=unavailable)")
        return m, False
    b = pd.read_csv(BDI, parse_dates=["date"]).sort_values("date")
    cols = [c for c in ["bdi", "bci", "bpi", "bsi", "bhsi"] if c in b.columns]
    if not cols:
        return m, False
    b["_m"] = b["date"].values.astype("datetime64[M]")
    b = b.groupby("_m")[cols].mean()                 # daily -> monthly mean
    b["bdi_ret_1m"] = np.log(b["bdi"] / b["bdi"].shift(1))
    b["bdi_ret_3m"] = np.log(b["bdi"] / b["bdi"].shift(3))
    b["bdi_vol_6m"] = np.log(b["bdi"]).diff().rolling(6).std()
    for cls_col, cls in CLASS_OF_INDEX.items():
        if cls_col in b.columns:
            b[f"{cls_col}_ret_1m"] = np.log(b[cls_col] / b[cls_col].shift(1))
    b = b.reset_index().rename(columns={"_m": "month"})

    out = pd.merge_asof(m.sort_values("month"), b.sort_values("month"),
                        on="month", direction="backward")
    # Per-vessel-class sub-index momentum, resolved at model time from vessel_class.
    # The column is only created when at least one sub-index is present; the file
    # supplied so far carries composite BDI only, so this block is a no-op rather
    # than a KeyError on a column that was never built.
    for cls_col, cls in CLASS_OF_INDEX.items():
        src = f"{cls_col}_ret_1m"
        if src in out.columns:
            out["class_index_ret_1m"] = out[src].where(out["vessel_class"] == cls)
    if "class_index_ret_1m" in out.columns:
        out["class_index_ret_1m"] = out.groupby("month")["class_index_ret_1m"].transform("mean")
    else:
        print(f"[corridor] no class sub-indices in {BDI.name}; "
              f"per-class index momentum unavailable")
    return out, True


def add_weather_features(m: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """Monthly weather summary per discharge port, as-of backward."""
    if not WEATHER.exists():
        print(f"[corridor] {WEATHER.name} absent -> weather features skipped")
        return m, False
    w = pd.read_csv(WEATHER, parse_dates=["date"])
    w["month"] = w["date"].values.astype("datetime64[M]")
    wm = w.groupby(["port", "month"], as_index=False).agg(
        wind_max_kt=("wind_max_kt", "max"),
        wind_mean_kt=("wind_max_kt", "mean"),
        precip_mm=("precip_mm", "sum"),
        gale_days=("gale_flag", "sum"),
        cyclone_days=("cyclone_flag", "sum"),
    )
    wm["port"] = wm["port"].str.strip().str.title()
    wm = wm.rename(columns={"port": "unload_port"})

    out = m.merge(wm, on=["unload_port", "month"], how="left")
    hit = out["wind_max_kt"].notna().sum()
    print(f"[corridor] weather joined for {hit}/{len(out)} rows "
          f"({out['unload_port'].nunique()} discharge ports in table vs {wm['unload_port'].nunique()} with data)")
    return out, True


# --------------------------------------------------------------------------
def build() -> pd.DataFrame:
    weekly = load_rates()
    m = to_monthly(weekly)
    m = add_lane_features(m)
    m, has_cmd = add_commodity_features(m)
    m, has_bdi = add_bdi_features(m)
    m, has_wx = add_weather_features(m)

    m = m.sort_values(["corridor_id", "vessel_class", "month"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    m.to_csv(OUT, index=False)

    # Coverage report so the API can state exactly what this table does and does not have.
    per_lane = (m.groupby(["corridor_id", "vessel_class"])
                  .agg(months=("month", "nunique"),
                       first=("month", "min"), last=("month", "max"),
                       mean_rate=("rate_usd_mt", "mean"))
                  .reset_index())
    per_lane["first"] = per_lane["first"].dt.strftime("%Y-%m")
    per_lane["last"] = per_lane["last"].dt.strftime("%Y-%m")
    per_lane["mean_rate"] = per_lane["mean_rate"].round(2)

    report = {
        "built_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
        "rows": int(len(m)),
        "corridors": int(m["corridor_id"].nunique()),
        "vessel_classes": sorted(m["vessel_class"].unique().tolist()),
        "months": int(m["month"].nunique()),
        "period": [m["month"].min().strftime("%Y-%m"), m["month"].max().strftime("%Y-%m")],
        "feature_groups_present": {
            "lane_momentum": True,
            "world_bank_commodity": has_cmd,
            "baltic_subindices": has_bdi,
            "port_weather": has_wx,
        },
        "per_lane": per_lane.to_dict(orient="records"),
        "target_provenance_tier": prov.get("route_rates_weekly").tier,
        "known_limitations": [
            f"Only {m['month'].nunique()} monthly points per corridor: a 1-6 month-ahead "
            "monthly model cannot be validated on this depth. Short-horizon (weekly) "
            "forecasting carries the statistical weight; monthly output is presented as "
            "a conditional path, not a fitted monthly model.",
            "Corridors are port-pair level, not terminal level. No per-terminal rate "
            "differences are invented.",
            "Rate provenance is unconfirmed; see data_pipeline/provenance.py.",
        ],
    }
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"[corridor] {len(m)} rows | {m['corridor_id'].nunique()} corridors | "
          f"{m['month'].nunique()} months ({m['month'].min():%Y-%m}..{m['month'].max():%Y-%m})")
    print(f"[corridor] wrote {OUT}")
    print(f"[corridor] report  {REPORT}")
    return m


if __name__ == "__main__":
    build()
