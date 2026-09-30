"""
Open-Meteo marine/weather fetch -> data/external/port_weather_daily.csv

Free, no key. Two calls per port:
  * archive API  - daily history (for training-window features)
  * forecast API - 7 day forward max wind / precipitation (for live risk warnings)

Ports are taken from data/port_constraints.csv, which carries the coordinates.
A port with no coordinates is skipped and reported, never guessed.

Usage:  python -m data_pipeline.fetchers.open_meteo_weather
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PORTS_CSV = ROOT / "data" / "port_constraints.csv"
OUT = ROOT / "data" / "external" / "port_weather_daily.csv"

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"

DAILY = ["wind_speed_10m_max", "precipitation_sum", "wind_gusts_10m_max"]
# Sahoo/FIMA cyclone proxy: sustained wind at 10m in km/h.
# 62 km/h ~ 32 kt (cyclonic storm), 88 km/h ~ 47 kt (severe cyclonic storm) per IMD scale.
CYCLONE_KMH = 62.0
GALE_KMH = 40.0

TIMEOUT = 30
UA = "FreightIQ/2.0 (student project; contact via repo)"


def _get_json(url: str) -> Optional[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        print(f"[weather] request failed: {e}")
        return None


def _fmt(iso: str) -> str:
    return iso.replace("T00:00", "")


def fetch_port(lat: float, lon: float, port: str,
               start: str = "2025-09-01", end: Optional[str] = None) -> List[dict]:
    end = end or pd.Timestamp.now("UTC").strftime("%Y-%m-%d")
    q = (f"?latitude={lat}&longitude={lon}&start_date={start}&end_date={end}"
         f"&daily={','.join(DAILY)}&timezone=UTC&wind_speed_unit=kmh")
    j = _get_json(ARCHIVE + q)
    if not j or "daily" not in j:
        return []
    d = j["daily"]
    rows = []
    for i, day in enumerate(d["time"]):
        ws = d.get(DAILY[0], [None] * len(d["time"]))[i]
        pr = d.get(DAILY[1], [None] * len(d["time"]))[i]
        gu = d.get(DAILY[2], [None] * len(d["time"]))[i]
        if ws is None:
            continue
        rows.append({
            "port": port, "date": _fmt(day),
            "wind_max_kmh": ws, "gust_max_kmh": gu, "precip_mm": pr,
            "wind_max_kt": round(ws / 1.852, 2),
            "gale_flag": int(ws >= GALE_KMH),
            "cyclone_flag": int(ws >= CYCLONE_KMH),
        })
    return rows


def fetch_forecast(lat: float, lon: float, port: str) -> Optional[Dict]:
    q = (f"?latitude={lat}&longitude={lon}&daily={','.join(DAILY)}"
         f"&forecast_days=7&timezone=UTC&wind_speed_unit=kmh")
    j = _get_json(FORECAST + q)
    if not j or "daily" not in j:
        return None
    d = j["daily"]
    rows = []
    for i, day in enumerate(d["time"]):
        ws = d.get(DAILY[0], [None] * len(d["time"]))[i]
        if ws is None:
            continue
        rows.append({"date": _fmt(day), "wind_max_kmh": ws, "wind_max_kt": round(ws / 1.852, 2),
                     "gust_max_kmh": d.get(DAILY[2], [None] * len(d["time"]))[i],
                     "precip_mm": d.get(DAILY[1], [None] * len(d["time"]))[i],
                     "cyclone_flag": int(ws >= CYCLONE_KMH)})
    return {"port": port, "generated_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
            "daily": rows}


def build(start: str = "2025-09-01", pause: float = 0.4) -> Optional[pd.DataFrame]:
    if not PORTS_CSV.exists():
        print(f"[weather] {PORTS_CSV} missing; cannot resolve port coordinates")
        return None
    ports = pd.read_csv(PORTS_CSV)
    if not {"latitude", "longitude", "port_name"}.issubset(ports.columns):
        print("[weather] port_constraints.csv lacks coordinates")
        return None

    all_rows: List[dict] = []
    for _, p in ports.iterrows():
        lat, lon = p.get("latitude"), p.get("longitude")
        if pd.isna(lat) or pd.isna(lon):
            print(f"[weather] {p['port_name']}: no coordinates, skipped")
            continue
        r = fetch_port(float(lat), float(lon), str(p["port_name"]), start=start)
        print(f"[weather] {p['port_name']:22s} {len(r):5d} days")
        all_rows.extend(r)
        time.sleep(pause)

    if not all_rows:
        print("[weather] no rows retrieved (network?). Leaving cache untouched.")
        return None

    df = pd.DataFrame(all_rows).drop_duplicates(["port", "date"]).sort_values(["port", "date"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"[weather] wrote {OUT} ({len(df)} rows, {df['port'].nunique()} ports, "
          f"{df['date'].min()} .. {df['date'].max()})")
    return df


if __name__ == "__main__":
    r = build()
    raise SystemExit(0 if r is not None else 1)
