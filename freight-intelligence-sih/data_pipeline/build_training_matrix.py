"""
Step 1 - Build the Model 2 training matrix from REAL per-route freight rates.

Source : data/training_matrix.csv  (weekly $/MT observations, 11 route+class
         series x 26 weeks, 2025-10-03 .. 2026-03-27)
Optional: data/bdi_history_merged.csv (columns: date, BDI). If present it is
         joined as-of (backward) so a row never sees a BDI value from its future.

Everything here is derived only from information available at time t.
The targets look forward (t + HORIZON_WEEKS) and are used for training/eval only.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RATES_PATH = ROOT / "data" / "training_matrix.csv"
BDI_PATH = ROOT / "data" / "bdi_history_merged.csv"
OUT_PATH = ROOT / "data" / "freight_training_matrix.csv"

HORIZON_WEEKS = 2   # forecast horizon (weekly data)
WAIT_TOL = 0.02     # a >2% drop within the horizon counts as "should have waited"


def load_rates() -> pd.DataFrame:
    df = pd.read_csv(RATES_PATH, parse_dates=["date"], encoding="utf-8-sig")
    # Normalise inconsistent labels ("paradip" vs "Paradip"), strip whitespace
    for c in ["load_port", "unload_port", "vessel_type"]:
        df[c] = df[c].astype(str).str.strip().str.title()
    df["vessel_type"] = df["vessel_type"].str.replace(" ", "", regex=False)  # "Handy Max" -> "HandyMax"
    df["route_id"] = df["load_port"] + "->" + df["unload_port"] + "|" + df["vessel_type"]
    dup = df.duplicated(["route_id", "date"]).sum()
    if dup:
        df = df.groupby(["route_id", "date", "load_port", "unload_port", "vessel_type"],
                        as_index=False).agg(rate_usd_mt=("rate_usd_mt", "mean"),
                                            cargo_intake=("cargo_intake", "mean"))
    return df.sort_values(["route_id", "date"]).reset_index(drop=True)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("route_id")["rate_usd_mt"]
    df["log_rate"] = np.log(df["rate_usd_mt"])
    for k in (1, 2, 4):
        df[f"ret_{k}w"] = np.log(df["rate_usd_mt"] / g.shift(k))
    df["roll_mean_4w"] = g.transform(lambda s: s.rolling(4, min_periods=4).mean())
    df["roll_cv_4w"] = g.transform(lambda s: s.rolling(4, min_periods=4).std()) / df["roll_mean_4w"]
    df["dev_from_mean_4w"] = np.log(df["rate_usd_mt"] / df["roll_mean_4w"])
    m = df["date"].dt.month
    df["month_sin"], df["month_cos"] = np.sin(2 * np.pi * m / 12), np.cos(2 * np.pi * m / 12)
    for c in ["load_port", "vessel_type"]:
        df[f"{c}_code"] = df[c].astype("category").cat.codes
    return df


def add_bdi(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    if not BDI_PATH.exists():
        print(f"[warn] {BDI_PATH.name} not found - building WITHOUT BDI features")
        return df, False
    bdi = pd.read_csv(BDI_PATH, parse_dates=["date"]).sort_values("date")
    bdi["bdi_ret_1w"] = np.log(bdi["BDI"] / bdi["BDI"].shift(5))   # ~5 trading days
    bdi["bdi_ret_4w"] = np.log(bdi["BDI"] / bdi["BDI"].shift(20))
    bdi["bdi_vol_4w"] = np.log(bdi["BDI"]).diff().rolling(20).std()
    keep = bdi[["date", "BDI", "bdi_ret_1w", "bdi_ret_4w", "bdi_vol_4w"]]
    out = pd.merge_asof(df.sort_values("date"), keep, on="date", direction="backward")
    return out.sort_values(["route_id", "date"]).reset_index(drop=True), True


def add_targets(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("route_id")["rate_usd_mt"]
    df["future_rate"] = g.shift(-HORIZON_WEEKS)
    df["target_ret"] = np.log(df["future_rate"] / df["rate_usd_mt"])
    # min over the NEXT HORIZON weeks (excludes today)
    fut_min = g.transform(lambda s: s[::-1].shift(1).rolling(HORIZON_WEEKS, min_periods=HORIZON_WEEKS).min()[::-1])
    df["min_rate_in_window"] = fut_min
    df["should_have_waited"] = (fut_min < df["rate_usd_mt"] * (1 - WAIT_TOL)).astype("float")
    df.loc[fut_min.isna(), "should_have_waited"] = np.nan
    df["potential_savings_usd_mt"] = (df["rate_usd_mt"] - fut_min).clip(lower=0)
    return df


def build() -> pd.DataFrame:
    rates = load_rates()
    rates = add_features(rates)
    rates, has_bdi = add_bdi(rates)
    rates = add_targets(rates)
    feat_cols = ["ret_1w", "ret_2w", "ret_4w", "roll_cv_4w", "dev_from_mean_4w"]
    if has_bdi:
        feat_cols += ["bdi_ret_1w", "bdi_ret_4w", "bdi_vol_4w"]
    n0 = len(rates)
    rates = rates.dropna(subset=feat_cols + ["target_ret"]).reset_index(drop=True)
    print(f"{n0} raw rows -> {len(rates)} usable rows | {rates['route_id'].nunique()} routes | "
          f"{rates['date'].min().date()} .. {rates['date'].max().date()} | BDI: {has_bdi}")
    print(f"should_have_waited rate: {rates['should_have_waited'].mean():.1%}")
    rates.to_csv(OUT_PATH, index=False)
    return rates


if __name__ == "__main__":
    build()
