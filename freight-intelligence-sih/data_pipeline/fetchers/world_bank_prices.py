"""
World Bank Pink Sheet -> data/external/world_bank_pink_sheet.csv

Free, no key, official. The .xlsx is a download-once artefact; this parses it into
a tidy monthly CSV of the series that matter for dry bulk:
    coal_australia   - Australian thermal coal, USD/mt   (demand/cost driver)
    coal_safrica     - South African coal, USD/mt       (competing origin)
    iron_ore         - Iron ore cfr spot, USD/dmtu      (Capesize driver)
    crude_oil_avg    - Crude oil average, USD/bbl       (bunker proxy)

Download if the cache is missing:
    https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Monthly.xlsx
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_XLSX = ROOT / "data" / "raw" / "CMO-Historical-Data-Monthly.xlsx"
OUT = ROOT / "data" / "external" / "world_bank_pink_sheet.csv"
URL = ("https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025"
       "/related/CMO-Historical-Data-Monthly.xlsx")

# Canonical column name -> substring used in the sheet header
WANTED: Dict[str, str] = {
    "coal_australia": "Coal, Australian",
    "coal_south_africa": "Coal, South African",
    "iron_ore_cfr_spot": "Iron ore, cfr spot",
    "crude_oil_avg": "Crude oil, average",
    "crude_oil_brent": "Crude oil, Brent",
}
SHEET = "Monthly Prices"
HEADER_ROW = 4          # row containing the series names
UNITS_ROW = 5           # row containing units
DATA_START = 6          # first observation


def build(limit_recent_months: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Parse the workbook. Returns None (and prints why) if the file is absent."""
    if not RAW_XLSX.exists():
        print(f"[world_bank] raw workbook not found at {RAW_XLSX}")
        print(f"[world_bank] download it from: {URL}")
        return None

    raw = pd.read_excel(RAW_XLSX, sheet_name=SHEET, header=None)
    names = [str(v) for v in raw.iloc[HEADER_ROW].tolist()]
    units = [str(v) for v in raw.iloc[UNITS_ROW].tolist()]

    out: Dict[str, pd.Series] = {}
    month_col = pd.to_datetime(raw.iloc[DATA_START:, 0].astype(str).str.replace("M", "-"),
                               format="%Y-%m", errors="coerce")
    for col, needle in WANTED.items():
        hits = [i for i, n in enumerate(names) if needle in n]
        if not hits:
            print(f"[world_bank] column not found: {needle}")
            continue
        i = hits[0]
        vals = pd.to_numeric(raw.iloc[DATA_START:, i], errors="coerce")
        out[col] = pd.Series(vals.values, index=month_col.values, name=col).dropna()
        print(f"[world_bank] {col:20s} {units[i]:10s} n={len(out[col]):5d} "
              f"{out[col].index.min().date()} .. {out[col].index.max().date()}")

    if not out:
        print("[world_bank] no usable columns found")
        return None

    df = pd.DataFrame(out).sort_index()
    df.index.name = "month"
    if limit_recent_months:
        df = df.tail(limit_recent_months)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT)
    print(f"[world_bank] wrote {OUT} ({len(df)} months)")
    return df


if __name__ == "__main__":
    r = build()
    sys.exit(0 if r is not None else 1)
