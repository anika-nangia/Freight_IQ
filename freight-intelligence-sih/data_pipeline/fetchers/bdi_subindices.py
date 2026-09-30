"""
Baltic Exchange sub-indices loader -> data/external/bdi_subindices.csv

The Baltic Exchange does not redistribute this data for free. At build time every
free endpoint we tried refused us:
    investing.com   HTTP 403 (Cloudflare challenge)
    stooq.com       JavaScript challenge page
    FRED            connection timeout from this network
    balticexchange.com  bot challenge page
    Yahoo Finance   no listing for ^BDI / ^BCI / ^BPI / ^BSI / ^BHSI

So this module deliberately does NOT scrape anything and does NOT ship a default
value. It validates a CSV that a human downloaded and copies it into place.

Expected columns (case-insensitive, date first):
    date, bdi, bci, bpi, bsi, bhsi
Extra columns are kept. `bc*` are optional: without them the class-index feature
group is simply marked unavailable and the corridor model runs alone.

One-time download (any of):
  * Baltic Exchange, Data Services -> Market Information  (subscription)
  * Barchart / Investing / MacroMicro free tier  (one CSV download)

Usage:  python -m data_pipeline.fetchers.bdi_subindices --input <downloaded.csv>
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "data" / "external" / "bdi_subindices.csv"

REQUIRED = ["date"]
OPTIONAL = ["bdi", "bci", "bpi", "bsi", "bhsi"]
CLASS_OF = {"bci": "Capesize", "bpi": "Panamax", "bsi": "Supramax", "bhsi": "Handysize"}


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names, parse dates, sort, reject unusable files."""
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"missing required column(s): {missing}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["date"])
    for c in OPTIONAL:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    present = [c for c in OPTIONAL if c in df.columns and df[c].notna().any()]
    if not present:
        raise ValueError(f"none of {OPTIONAL} present with usable values")

    df = df.sort_values("date").drop_duplicates("date", keep="last")
    print(f"[bdi] validated {len(df)} rows, {df['date'].min().date()} .. {df['date'].max().date()}")
    print(f"[bdi] indices present: {present}")
    missing_cls = [f"{c} ({CLASS_OF[c]})" for c in CLASS_OF if c not in present]
    if missing_cls:
        print(f"[bdi] class sub-indices absent, those classes fall back to corridor-only: {missing_cls}")
    return df


def install(src: Path) -> Optional[pd.DataFrame]:
    if not src.exists():
        print(f"[bdi] {src} does not exist. Nothing to install. Tier stays 'unavailable'.")
        return None
    df = validate(pd.read_csv(src))
    DEST.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DEST, index=False)
    print(f"[bdi] wrote {DEST}")
    return df


def status() -> bool:
    print(f"[bdi] {'present' if DEST.exists() else 'absent'} at {DEST}")
    if DEST.exists():
        d = pd.read_csv(DEST, parse_dates=["date"])
        print(f"[bdi] {len(d)} rows, {d['date'].min().date()} .. {d['date'].max().date()}")
    return DEST.exists()


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", "-i", help="path to a downloaded Baltic Exchange CSV")
    p.add_argument("--status", action="store_true", help="report whether the file is installed")
    a = p.parse_args(argv)
    if a.status or not a.input:
        return 0 if status() else 1
    try:
        install(Path(a.input))
        return 0
    except ValueError as e:
        print(f"[bdi] rejected: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
