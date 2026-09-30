"""
Computes the 'should-have-waited' label (section 7): for every booking,
did the rate fall further within the next N days? This trains/evaluates
the asymmetric wait-vs-book recommendation (Expected Output A).

Deliberately kept separate from feature_engineering.py since a label is
only ever computed on *historical* data (you need to know what actually
happened next), never at inference time.
"""

from __future__ import annotations
import pandas as pd

from app.config import settings


def compute_should_have_waited_labels(
    freight_df: pd.DataFrame,
    window_days: int | None = None,
) -> pd.DataFrame:
    """
    freight_df must have columns: record_date, origin_country,
    destination_port, vessel_class, rate_usd_per_tonne — one row per day
    per route+class (the same granularity as FreightRateObservation).

    Returns freight_df with added columns:
        min_rate_in_window, should_have_waited, potential_savings_usd_per_tonne
    """
    window_days = window_days or settings.SHOULD_HAVE_WAITED_WINDOW_DAYS

    df = freight_df.copy()
    df["record_date"] = pd.to_datetime(df["record_date"])
    df = df.sort_values("record_date")

    group_cols = ["origin_country", "destination_port", "vessel_class"]

    def _label_group(g: pd.DataFrame) -> pd.DataFrame:
        g = g.set_index("record_date")
        # min rate over the *next* window_days (excluding today), looking forward
        future_min = (
            g["rate_usd_per_tonne"]
            .iloc[::-1]
            .rolling(window=f"{window_days}D", min_periods=1)
            .min()
            .iloc[::-1]
        )
        # shift so "today" isn't included in its own forward window
        g["min_rate_in_window"] = future_min.shift(-1)
        g["should_have_waited"] = g["min_rate_in_window"] < g["rate_usd_per_tonne"]
        g["potential_savings_usd_per_tonne"] = (
            g["rate_usd_per_tonne"] - g["min_rate_in_window"]
        ).clip(lower=0)
        return g.reset_index()

    labeled = df.groupby(group_cols, group_keys=False).apply(_label_group)
    return labeled
