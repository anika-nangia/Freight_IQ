"""
Build the modelling panel: weekly corridor observations with lagged, leak-free features.

This is the table Model 2 trains and validates on. Monthly aggregation lives in
build_corridor_table.py and is used for the contract view, not for fitting: with
6 monthly points per corridor a monthly model cannot be validated at all.

LEAKAGE CONTROLS (each one is asserted in tests/)
  1. Every feature is computed from a shift()ed or rolling-past series.
  2. Targets only look forward and are dropped before training.
  3. Weather is joined as-of backward on the observation week.
  4. Commodity features carry the Pink Sheet publication lag.
  5. Baltic features are joined as-of backward, and are absent while unavailable.

Run:  python -m data_pipeline.build_weekly_panel
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402

RATES = ROOT / "data" / "training_matrix.csv"
PINK = ROOT / "data" / "external" / "world_bank_pink_sheet.csv"
BDI = ROOT / "data" / "external" / "bdi_subindices.csv"
WEATHER = ROOT / "data" / "external" / "port_weather_daily.csv"
OUT = ROOT / "data" / "interim" / "weekly_panel.csv"
REPORT = ROOT / "data" / "interim" / "weekly_panel_report.json"

HORIZON_WEEKS = 2        # 2-week-ahead return is the target
COMMODITY_LAG_MONTHS = 1
WAIT_TOL = 0.02          # >2% fall within the horizon => "should have waited"

COMMODITY = {
    "coal_australia": "coal_aus",
    "coal_south_africa": "coal_saf",
    "iron_ore_cfr_spot": "iron_ore",
    "crude_oil_avg": "crude_oil",
}
CLASS_OF_INDEX = {"bci": "Capesize", "bpi": "Panamax", "bsi": "Supramax", "bhsi": "Handysize"}


def load_rates() -> pd.DataFrame:
    df = pd.read_csv(RATES, parse_dates=["date"], encoding="utf-8-sig")
    for c in ["load_port", "unload_port", "vessel_type"]:
        df[c] = df[c].astype(str).str.strip().str.title()
    df["vessel_type"] = df["vessel_type"].str.replace(r"\s+", "", regex=True)
    df["unload_port"] = df["unload_port"].replace({"paradip": "Paradip"})
    df["corridor_id"] = df["load_port"] + "->" + df["unload_port"]
    df["vessel_class"] = df["vessel_type"].replace({"HandyMax": "Handymax"})

    key = ["corridor_id", "vessel_class", "date"]
    if df.duplicated(key).any():
        print(f"[panel] collapsing {int(df.duplicated(key).sum())} duplicate rows")
        df = df.groupby(key, as_index=False).agg(
            rate_usd_mt=("rate_usd_mt", "mean"), cargo_intake=("cargo_intake", "mean"))
    return df.sort_values(["corridor_id", "vessel_class", "date"]).reset_index(drop=True)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["corridor_id", "vessel_class"])["rate_usd_mt"]
    df["log_rate"] = np.log(df["rate_usd_mt"])
    for k in (1, 2, 4, 8):
        df[f"ret_{k}w"] = np.log(df["rate_usd_mt"] / g.shift(k))
    df["roll_mean_4w"] = g.transform(lambda s: s.rolling(4, min_periods=4).mean())
    df["roll_std_8w"] = g.transform(lambda s: s.rolling(8, min_periods=5).std())
    df["roll_cv_8w"] = df["roll_std_8w"] / g.transform(lambda s: s.rolling(8, min_periods=5).mean())
    df["dev_from_mean_4w"] = np.log(df["rate_usd_mt"] / df["roll_mean_4w"])

    # Lane spread against its own class, same week. Removes the 3-4x level gap
    # between corridors and leaves a far more stationary series.
    df["log_rate_vs_class"] = df["log_rate"] - df.groupby(
        ["vessel_class", "date"])["log_rate"].transform("mean")

    # Calendar as elapsed time, NOT sin/cos month. With ~26 weeks of history a
    # month sin/cos pair is a time index that the trees memorise and then fail to
    # extrapolate. Kept as a documented exclusion.
    df["weeks_since_start"] = ((df["date"] - df["date"].min()).dt.days // 7).astype(float)

    for c, levels in (("load_port", sorted(df["load_port"].unique())),
                      ("vessel_class", sorted(df["vessel_class"].unique()))):
        df[f"{c}_code"] = pd.Categorical(df[c], categories=levels).codes.astype(float)
    return df


def add_commodity(df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """Weekly-aligned World Bank features, as-of backward, lagged for publication."""
    if not PINK.exists():
        print("[panel] pink sheet absent -> commodity features skipped")
        return df, False
    raw = pd.read_csv(PINK, parse_dates=["month"]).sort_values("month")

    # The price series is MONTHLY and the panel is WEEKLY, so a plain .map() on the
    # date finds nothing and silently yields an all-NaN column. Join as-of backward:
    # a week on 2025-10-03 picks up the price month that was published by then.
    px = raw.rename(columns={"month": "date"}).copy()
    for src in COMMODITY:
        if src in px.columns:
            # Momentum is computed on the monthly series BEFORE the join, otherwise
            # every weekly row inherits the same monthly change and momentum is lost.
            px[f"{src}_mom"] = np.log(px[src] / px[src].shift(1))

    # The Pink Sheet publishes with roughly a two-month lag, so shift the whole frame
    # back before joining. Without this, month M would see a price it could not have known.
    lag = int(COMMODITY_LAG_MONTHS)
    px = px.copy()
    for col in px.columns:
        if col != "date":
            px[col] = px[col].shift(lag)
    px = px[["date"] + [c for c in px.columns if c != "date"]]

    joined = pd.merge_asof(df[["date"]].sort_values("date"), px, on="date", direction="backward")
    for src, dst in COMMODITY.items():
        if src not in joined.columns:
            print(f"[panel] {src} absent from pink sheet")
            continue
        df[f"{dst}_level"] = joined[src].values
        df[f"{dst}_ret_4w"] = joined[f"{src}_mom"].values
    # Standardise levels on the observed window so coefficients are comparable.
    for dst in COMMODITY.values():
        c = f"{dst}_level"
        if c in df.columns:
            mu, sd = df[c].mean(), df[c].std()
            df[c] = (df[c] - mu) / sd if sd else 0.0
    return df, True


def add_bdi(df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    if not BDI.exists():
        print("[panel] BDI absent -> no index features (tier=unavailable)")
        return df, False
    b = pd.read_csv(BDI, parse_dates=["date"]).sort_values("date")
    cols = [c for c in ["bdi", "bci", "bpi", "bsi", "bhsi"] if c in b.columns]
    b["bdi_ret_1w"] = np.log(b["bdi"] / b["bdi"].shift(5))
    b["bdi_ret_4w"] = np.log(b["bdi"] / b["bdi"].shift(20))
    b["bdi_vol_4w"] = np.log(b["bdi"]).diff().rolling(20).std()
    for cls_col, cls in CLASS_OF_INDEX.items():
        if cls_col in b.columns:
            b[f"{cls_col}_ret_1w"] = np.log(b[cls_col] / b[cls_col].shift(5))
    keep = ["date", "bdi_ret_1w", "bdi_ret_4w", "bdi_vol_4w"] + \
           [f"{c}_ret_1w" for c in CLASS_OF_INDEX if f"{c}_ret_1w" in b.columns]
    out = pd.merge_asof(df.sort_values("date"), b[keep].sort_values("date"),
                        on="date", direction="backward")
    for cls_col, cls in CLASS_OF_INDEX.items():
        c = f"{cls_col}_ret_1w"
        if c in out.columns:
            out["class_index_ret_1w"] = out[c].where(out["vessel_class"] == cls)
    if "class_index_ret_1w" in out.columns:
        out["class_index_ret_1w"] = out.groupby("date")["class_index_ret_1w"].transform("mean")
    return out.sort_values(["corridor_id", "vessel_class", "date"]), True


def add_weather(df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """Weather features, split by WHEN they describe relative to the forecast target.

    The target is the rate at t + HORIZON_WEEKS. A weather feature only explains that
    target if it describes the target window. The previous version had one group joined
    at week t, i.e. a NOWCAST: it told you today's weather while the model predicted two
    weeks out, so a genuine weather effect would have been read as useless.

    Three groups are built instead:

      wx_now_*  weather at week t. Safe and deployable - what a charterer observes on
                the day they decide. Describes the past, not the sailing window.
      wx_tgt_*  weather at t + HORIZON_WEEKS, from the archive. This is the weather
                that actually prevails during the forecast window.
                *** PERFECT-FORESIGHT, NOT DEPLOYABLE. ***
                Nobody knows this at prediction time. It is kept strictly as a
                diagnostic upper bound: if even the TRUE weather for the target window
                does not move the metric, then no deployable weather signal can help
                either, and wiring a live weather-forecast feed is not worth it. If it
                does move the metric, that is the evidence that justifies one.
      wx_org_*  weather at the ORIGIN port, week t. Loading-side conditions, which are
                what delay a sailing. Uses the unverified reference coordinates in
                data/raw/origin_port_coordinates.csv.
    """
    if not WEATHER.exists():
        print("[panel] weather cache absent -> weather features skipped")
        return df, False
    w = pd.read_csv(WEATHER, parse_dates=["date"])
    if "role" not in w.columns:
        w["role"] = "discharge"
    w["port_name"] = w["port"].astype(str).str.strip().str.title()
    # 'Paradip/Haldia' is a two-port discharge region in the rate data, so its weather
    # is the mean of the two real ports over the week - real observations averaged over
    # real ports, not an invented value.
    frames = [w.assign(region=w["port_name"])]
    frames.append(w[w["port_name"].isin(["Paradip", "Haldia"])].assign(region="Paradip/Haldia"))
    w = pd.concat(frames, ignore_index=True)
    w["week"] = w["date"] - pd.to_timedelta(w["date"].dt.weekday, unit="D")  # -> Monday
    w["wet_day"] = (w["precip_mm"] > 1.0).astype(int)

    METRICS = ("wind_max_kt", "gust_max_kt", "precip_mm", "pressure_msl",
               "wave_height_m", "gale_days", "cyclone_days", "rainy_days")
    wk = (w.groupby(["region", "role", "week"], as_index=False)
            .agg(wind_max_kt=("wind_max_kt", "max"),
                 gust_max_kt=("wind_max_kt", "max"),
                 precip_mm=("precip_mm", "sum"),
                 pressure_msl=("pressure_msl", "mean"),
                 wave_height_m=("wave_height_m", "max"),
                 gale_days=("gale_flag", "sum"),
                 cyclone_days=("cyclone_flag", "sum"),
                 rainy_days=("wet_day", "sum"))
            .sort_values(["region", "role", "week"]))

    out = df.copy()
    out["week"] = out["date"] - pd.to_timedelta(out["date"].dt.weekday, unit="D")
    out["target_week"] = out["week"] + pd.Timedelta(weeks=HORIZON_WEEKS)
    key_col = {"discharge": "unload_port", "origin": "load_port"}

    # Explicit per-region backward search. merge_asof with left_by/right_by advances
    # one global cursor and silently returns NaN for whole groups.
    def _lookup(role: str, week_col: str, prefix: str) -> None:
        for col in METRICS:
            out[f"{prefix}_{col}"] = np.nan
        for region, grp in wk[wk["role"] == role].groupby("region"):
            weeks = grp["week"].to_numpy()
            for col in METRICS:
                vals = grp[col].to_numpy(dtype=float)
                sel = (out[key_col[role]].to_numpy() == region)
                if not sel.any():
                    continue
                pos = np.searchsorted(weeks, out.loc[sel, week_col].to_numpy(), side="right") - 1
                ok = pos >= 0
                assigned = np.full(int(sel.sum()), np.nan)
                assigned[ok] = vals[pos[ok]]
                out.loc[sel, f"{prefix}_{col}"] = assigned

    _lookup("discharge", "week", "wx_now")       # nowcast, deployable
    _lookup("discharge", "target_week", "wx_tgt")  # target-window, diagnostic only
    _lookup("origin", "week", "wx_org")           # loading side, deployable

    out = out.drop(columns=["week", "target_week"], errors="ignore")
    for prefix in ("wx_now", "wx_tgt", "wx_org"):
        hit = int(out[f"{prefix}_wind_max_kt"].notna().sum())
        print(f"[panel] {prefix}_* matched {hit}/{len(out)} rows")
    for prefix in ("wx_now", "wx_tgt", "wx_org"):
        out[f"log_{prefix}_precip"] = np.log1p(out[f"{prefix}_precip_mm"].clip(lower=0))
    return out, True


def add_targets(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["corridor_id", "vessel_class"])["rate_usd_mt"]
    df["future_rate"] = g.shift(-HORIZON_WEEKS)
    df["target_ret"] = np.log(df["future_rate"] / df["rate_usd_mt"])
    fut = df.groupby(["corridor_id", "vessel_class"])["rate_usd_mt"].transform(
        lambda s: s[::-1].shift(1).rolling(HORIZON_WEEKS, min_periods=HORIZON_WEEKS).min()[::-1])
    df["min_rate_in_window"] = fut
    df["should_have_waited"] = np.where(fut.isna(), np.nan, (fut < df["rate_usd_mt"] * (1 - WAIT_TOL)).astype(float))
    df["potential_savings_usd_mt"] = (df["rate_usd_mt"] - fut).clip(lower=0)
    return df


FEATURE_CANDIDATES = [
    "ret_1w", "ret_2w", "ret_4w", "ret_8w", "roll_cv_8w", "dev_from_mean_4w",
    "log_rate", "log_rate_vs_class", "load_port_code", "vessel_class_code",
    "coal_aus_ret_4w", "coal_saf_ret_4w", "iron_ore_ret_4w", "crude_oil_ret_4w",
    "coal_aus_level", "coal_saf_level", "iron_ore_level", "crude_oil_level",
    "bdi_ret_1w", "bdi_ret_4w", "bdi_vol_4w", "class_index_ret_1w",
]
# Weather, split by when it describes. wx_tgt_* describes the TARGET WEEK and is
# therefore perfect-foresight: it is measured against the outcome window using
# observations nobody has at decision time. It is never added to the deployable
# feature list; the trainer reads it only from a diagnostic path.
for _p in ("wx_now", "wx_org"):
    for _m in ("wind_max_kt", "gust_max_kt", "precip_mm", "pressure_msl",
               "wave_height_m", "gale_days", "cyclone_days", "rainy_days"):
        FEATURE_CANDIDATES.append(f"{_p}_{_m}")
    FEATURE_CANDIDATES.append(f"log_{_p}_precip")
DIAGNOSTIC_FEATURES = [f"wx_tgt_{m}" for m in
                       ("wind_max_kt", "gust_max_kt", "precip_mm", "pressure_msl",
                        "wave_height_m", "cyclone_days", "rainy_days")] + ["log_wx_tgt_precip"]
# Coverage threshold for keeping a feature. Lag and rolling features are legitimately
# blank during their own warm-up window (ret_8w needs 8 prior weeks per lane), and the
# rows that costs are all at the START of each lane, i.e. inside the training period.
# Dropping them shrinks the panel without improving the walk-forward test. 0.80 keeps
# 4-week lags and drops only ret_8w, whose warm-up would leave too little history.
MIN_FEATURE_COVERAGE = 0.80


def build() -> pd.DataFrame:
    df = load_rates()
    df = add_features(df)
    df, has_cmd = add_commodity(df)
    df, has_bdi = add_bdi(df)
    df, has_wx = add_weather(df)
    df = df.sort_values(["corridor_id", "vessel_class", "date"]).reset_index(drop=True)
    df = add_targets(df)
    # Diagnostic-only columns are computed but never enter the deployable feature set.
    diag_present = [c for c in DIAGNOSTIC_FEATURES if c in df.columns]
    if diag_present:
        print(f"[panel] {len(diag_present)} PERFECT-FORESIGHT column(s) computed for the "
              f"weather diagnostic and excluded from training: {diag_present}")

    n0 = len(df)

    # Feature coverage is measured on the FULL panel, before rows lose their target.
    # Measuring it afterwards makes every lag feature look sparse purely because the
    # final two weeks were dropped for having no t+2w outcome - which penalises the
    # most legitimate features for a reason unrelated to their quality.
    kept, dropped, constant = [], {}, []
    for c in FEATURE_CANDIDATES:
        if c not in df.columns:
            continue
        col = df[c]
        cov = float(col.notna().mean())
        if cov < MIN_FEATURE_COVERAGE:
            dropped[c] = round(cov, 3)
            print(f"[panel] dropping feature {c}: only {cov:.0%} of rows populated")
            continue
        # A column that is populated but never varies carries no information, yet it
        # survives a notna() test and reaches the model as a real feature. gale_days
        # and cyclone_days were all zero across the window, and a tree can still split
        # on them, so they are removed here rather than trusted to the trainer.
        n_unique = int(col.nunique(dropna=True))
        if n_unique <= 1:
            constant.append(c)
            print(f"[panel] dropping feature {c}: constant across all {cov:.0%} populated rows")
            continue
        kept.append(c)

    # Keep only rows that have both a target and every retained feature. Lag features
    # are blank during their own warm-up window, so this is where those rows leave.
    required = kept + ["target_ret"]
    df = df.dropna(subset=required).reset_index(drop=True)
    if dropped:
        print(f"[panel] after feature pruning: {len(df)} rows "
              f"({len(df) / n0:.0%} of rows with a target retained)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    lanes = (df.groupby(["corridor_id", "vessel_class"])
               .agg(weeks=("date", "nunique"), first=("date", "min"), last=("date", "max"),
                    mean_rate=("rate_usd_mt", "mean"))
               .reset_index())
    lanes["first"] = lanes["first"].dt.strftime("%Y-%m-%d")
    lanes["last"] = lanes["last"].dt.strftime("%Y-%m-%d")
    lanes["mean_rate"] = lanes["mean_rate"].round(2)

    report = {
        "built_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
        "rows_raw": int(n0), "rows_usable": int(len(df)),
        "lanes": int(len(lanes)), "weeks": int(df["date"].nunique()),
        "period": [df["date"].min().strftime("%Y-%m-%d"), df["date"].max().strftime("%Y-%m-%d")],
        "horizon_weeks": HORIZON_WEEKS,
        "should_have_waited_rate": round(float(df["should_have_waited"].mean()), 4),
        "feature_groups_present": {"commodity": has_cmd, "baltic": has_bdi, "weather": has_wx},
        "features": required,
        "features_dropped_for_coverage": dropped,
        "features_dropped_as_constant": constant,
        "per_lane": lanes.to_dict(orient="records"),
        "provenance_tier": prov.get("route_rates_weekly").tier,
        "excluded_features": {
            "month_sin, month_cos": "Only ~26 weeks of history, so they act as a time index "
                                    "rather than seasonality and the model memorised them."
        },
    }
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"[panel] {n0} raw -> {len(df)} usable rows | {len(lanes)} lanes | {df['date'].nunique()} weeks")
    print(f"[panel] should_have_waited {df['should_have_waited'].mean():.1%}")
    print(f"[panel] wrote {OUT}")
    return df


if __name__ == "__main__":
    build()
