"""
Builds model-ready features from the raw tables. This is where "derived,
not collected raw" features get computed (section 7 minus the label, which
lives in labels.py).

Kept as plain pandas functions (not tied to the ORM) so they can run both
inside the API (pulling from DB) and offline in a notebook/training script
(pulling from CSV exports) without duplication.
"""

from __future__ import annotations
import pandas as pd
import numpy as np


def compute_turnaround_days(lineup_df: pd.DataFrame) -> pd.DataFrame:
    """Adds turnaround_days = etcd_date - arrived_date (in days)."""
    df = lineup_df.copy()
    df["arrived_date"] = pd.to_datetime(df["arrived_date"])
    df["etcd_date"] = pd.to_datetime(df["etcd_date"])
    df["turnaround_days"] = (df["etcd_date"] - df["arrived_date"]).dt.days
    return df


def compute_port_congestion_rolling(lineup_df: pd.DataFrame, window_days: int = 7) -> pd.DataFrame:
    """Rolling avg turnaround + vessel count per port as a congestion proxy,
    useful when a dedicated real-time congestion feed isn't available."""
    df = compute_turnaround_days(lineup_df)
    df = df.sort_values("record_date")
    grouped = (
        df.groupby("port")
        .apply(
            lambda g: g.set_index("record_date")
            .rolling(f"{window_days}D")
            .agg({"turnaround_days": "mean", "vessel_name": "count"})
            .rename(columns={"vessel_name": "vessel_count"})
        )
        .reset_index()
    )
    return grouped


def merge_market_features(
    freight_df: pd.DataFrame,
    bdi_df: pd.DataFrame,
    fx_df: pd.DataFrame,
    coal_import_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Joins freight rate observations with same-day BDI/FX, and (optionally)
    the latest available monthly coal-import volume for that origin country.
    This is the primary feature table the forecaster trains on.
    """
    df = freight_df.copy()
    df["record_date"] = pd.to_datetime(df["record_date"])
    bdi_df = bdi_df.copy()
    bdi_df["record_date"] = pd.to_datetime(bdi_df["record_date"])
    fx_df = fx_df.copy()
    fx_df["record_date"] = pd.to_datetime(fx_df["record_date"])

    df = df.merge(bdi_df, on="record_date", how="left")
    df = df.merge(fx_df, on="record_date", how="left")

    # lag/rolling features on the target itself, per route+class
    df = df.sort_values("record_date")
    group_cols = ["origin_country", "destination_port", "vessel_class"]
    df["rate_lag_7d"] = df.groupby(group_cols)["rate_usd_per_tonne"].shift(7)
    df["rate_rolling_mean_14d"] = (
        df.groupby(group_cols)["rate_usd_per_tonne"]
        .transform(lambda s: s.rolling(14, min_periods=3).mean())
    )
    df["rate_rolling_std_14d"] = (
        df.groupby(group_cols)["rate_usd_per_tonne"]
        .transform(lambda s: s.rolling(14, min_periods=3).std())
    )

    # seasonality
    df["month"] = df["record_date"].dt.month
    df["day_of_week"] = df["record_date"].dt.dayofweek
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    if coal_import_df is not None and not coal_import_df.empty:
        cdf = coal_import_df.copy()
        df["year_month"] = df["record_date"].dt.strftime("%Y-%m")
        df = df.merge(
            cdf.rename(columns={"volume_tonnes": "coal_import_volume_tonnes"}),
            on=["year_month", "origin_country"],
            how="left",
        )

    return df


def check_port_fit(vessel_class, port_constraints: dict, vessel_dims: dict | None = None) -> tuple[bool, list[str]]:
    """Checks whether a vessel (by class, or exact dims if provided) fits a
    port's physical constraints. Mirrors Problem #3 in the PS: draft, LOA,
    beam, berth availability must all be checked.

    port_constraints: dict as in app.constants.EAST_COAST_PORTS / PortConstraints
    vessel_dims: optional {'loa':.., 'beam':.., 'draft':..} for exact-vessel checks
    """
    from app.constants import VESSEL_CLASS_SPECS, VESSEL_CLASS_ORDER

    reasons = []
    max_class = port_constraints.get("max_vessel_class")
    if max_class is not None:
        if VESSEL_CLASS_ORDER.index(vessel_class) > VESSEL_CLASS_ORDER.index(max_class):
            reasons.append(f"{vessel_class.value} exceeds port's max handleable class ({max_class.value})")

    dims = vessel_dims or VESSEL_CLASS_SPECS[vessel_class]
    loa = dims.get("loa") or dims.get("loa_typical")
    beam = dims.get("beam") or dims.get("beam_typical")
    draft = dims.get("draft") or dims.get("draft_typical")

    if port_constraints.get("max_loa") and loa and loa > port_constraints["max_loa"]:
        reasons.append(f"LOA {loa}m exceeds port max {port_constraints['max_loa']}m")
    if port_constraints.get("max_beam") and beam and beam > port_constraints["max_beam"]:
        reasons.append(f"Beam {beam}m exceeds port max {port_constraints['max_beam']}m")
    if port_constraints.get("max_draft") and draft and draft > port_constraints["max_draft"]:
        reasons.append(f"Draft {draft}m exceeds port max {port_constraints['max_draft']}m")

    return (len(reasons) == 0), reasons
