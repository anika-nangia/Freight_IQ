"""Loader for vessel_snapshots.csv (daily port vessel-movement snapshots).

Only what the file contains is exposed. Sparse columns stay None: vessel_type
is filled for ~7% of rows, dimensions for ~26%.
ASSUMPTION: `vessel_dimensions` like "179.90/7.43" is LOA(m)/draft(m).
Raw text is always returned alongside the parsed numbers.
"""
import logging
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.data.loaders import resolve_data_dir
from app.data.ports import find_port
from app.errors import DatasetError

logger = logging.getLogger(__name__)

REQUIRED = ["snapshot_date", "port", "status", "vessel_name"]
_DIM = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)?\s*$")


def _direction(v) -> str | None:
    if pd.isna(v):
        return None
    t = str(v).strip().upper()
    if t == "D/L":
        return "BOTH"
    if t in {"L", "LOAD", "LOADING"}:
        return "LOAD"
    if t.startswith("D") or t in {"IMP", "IMPORT"}:
        return "DISCHARGE"
    return None


def _dims(v):
    m = _DIM.match(str(v)) if not pd.isna(v) else None
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2)) if m.group(2) else None


def _find_file() -> Path:
    for f in sorted(resolve_data_dir().glob("*.csv")):
        if "vessel_snapshot" in f.name.lower():
            return f
    raise DatasetError("Vessel snapshot dataset not found (expected vessel_snapshots.csv in the data dir).")


@lru_cache(maxsize=2)
def _load(path: str) -> pd.DataFrame:
    try:
        d = pd.read_csv(path, encoding="utf-8-sig")
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DatasetError("Could not read the vessel snapshot dataset.") from exc
    missing = [c for c in REQUIRED if c not in d.columns]
    if missing:
        raise DatasetError(f"Vessel snapshot dataset is missing columns: {missing}.")
    d["port_raw"] = d["port"].astype(str).str.strip()
    d["port"] = d["port_raw"].map(lambda n: (find_port(n).name if find_port(n) else n.title()))
    for c in ("snapshot_date", "arrival_or_eta", "berth_or_etb", "etc_or_etcd"):
        if c in d:
            d[c] = pd.to_datetime(d[c], errors="coerce", dayfirst=True)
    d["direction_norm"] = d["direction"].map(_direction) if "direction" in d else None
    parsed = d["vessel_dimensions"].map(_dims) if "vessel_dimensions" in d else []
    d["loa_m"] = [p[0] for p in parsed]
    d["draft_m"] = [p[1] for p in parsed]
    d["vessel_id"] = ["v" + str(i) for i in range(len(d))]
    logger.info("Loaded %d vessel snapshot rows", len(d))
    return d


def load_vessels() -> pd.DataFrame:
    return _load(str(_find_file()))


def clear_vessel_cache() -> None:
    _load.cache_clear()
