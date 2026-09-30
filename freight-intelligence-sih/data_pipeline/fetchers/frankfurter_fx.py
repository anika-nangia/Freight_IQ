"""
USD/INR reference rate -> data/external/fx_usd_inr.csv

Free, no key. Frankfurter serves ECB reference rates. Used only to present USD
amounts in INR; it is deliberately NOT a model feature (it would not help predict
a USD-denominated freight rate).

Usage:  python -m data_pipeline.fetchers.frankfurter_fx
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "external" / "fx_usd_inr.csv"
ENDPOINT = "https://api.frankfurter.dev/v1/{start}..{end}?base=USD&symbols=INR"
TIMEOUT = 30
UA = "FreightIQ/2.0 (student project)"


def _get(url: str) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        print(f"[fx] request failed: {e}")
        return None


def build(start: str = "2024-01-01") -> Optional[pd.DataFrame]:
    end = pd.Timestamp.now("UTC").strftime("%Y-%m-%d")
    j = _get(ENDPOINT.format(start=start, end=end))
    if not j or "rates" not in j:
        print("[fx] no rate data returned; leaving cache untouched")
        return None

    rows = [{"date": d, "usd_inr": v.get("INR")} for d, v in j["rates"].items()]
    if not rows:
        print("[fx] empty rate set")
        return None

    df = pd.DataFrame(rows).sort_values("date")
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["usd_inr"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"[fx] wrote {OUT} ({len(df)} rows, {df['date'].min().date()} .. {df['date'].max().date()}, "
          f"latest {df['usd_inr'].iloc[-1]})")
    return df


if __name__ == "__main__":
    r = build()
    raise SystemExit(0 if r is not None else 1)
