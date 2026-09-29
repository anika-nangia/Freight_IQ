"""Congestion-score dataset loader.

The real dataset (from Aditi) is NOT in the repo yet, so column names are
matched case/space/underscore-insensitively against the candidate lists below.
Nothing is invented: a missing file or unmatched required column gives a clear
DATASET_UNAVAILABLE error. Adjust CANDIDATES once the real header is known.
"""
import logging
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.config import get_settings
from app.data.loaders import resolve_data_dir
from app.errors import DatasetError

logger = logging.getLogger(__name__)

CANDIDATES: dict[str, list[str]] = {
    "port": ["port", "destination_port", "destination", "port_name"],
    "date": ["date", "datetime", "day"],
    "congestion_score": ["model_congestion_score", "congestion_score", "congestion", "score"],
    "freight_rate": ["freight_rate", "freight", "rate", "price"],
    "rate_momentum_14d": ["rate_momentum_14d", "momentum_14d", "14d_rate_momentum", "rate_momentum"],
}
REQUIRED = ("port", "congestion_score")


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


def _find_file() -> Path:
    configured = get_settings().congestion_file
    if configured:
        p = Path(configured)
        p = p if p.is_absolute() else resolve_data_dir() / p
        if p.exists():
            return p
        raise DatasetError(f"Congestion file '{configured}' was not found.")
    for f in sorted(resolve_data_dir().glob("*.csv")):
        if "congest" in f.name.lower():
            return f
    raise DatasetError(
        "Congestion dataset not found. Put the congestion CSV (name containing "
        "'congestion') in backend/data or set CONGESTION_FILE."
    )


@lru_cache(maxsize=2)
def _load(path: str) -> pd.DataFrame:
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig", thousands=",")
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DatasetError("Could not read the congestion dataset.") from exc
    by_key = {_key(c): c for c in raw.columns}
    mapping = {}
    for field, names in CANDIDATES.items():
        col = next((by_key[n] for n in names if n in by_key), None)
        if col is not None:
            mapping[field] = col
    missing = [f for f in REQUIRED if f not in mapping]
    if missing:
        raise DatasetError(
            f"Congestion dataset is missing columns for {missing}. Found: {list(raw.columns)}."
        )
    frame = pd.DataFrame({f: raw[c] for f, c in mapping.items()})
    frame["port"] = frame["port"].astype(str).str.strip()
    for f in ("congestion_score", "freight_rate", "rate_momentum_14d"):
        if f in frame:
            frame[f] = pd.to_numeric(frame[f], errors="coerce")
    if "date" in frame:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce", dayfirst=True)
        frame = frame.sort_values("date")
    logger.info("Loaded %d congestion rows with columns %s", len(frame), list(frame.columns))
    return frame.reset_index(drop=True)


def load_congestion() -> pd.DataFrame:
    return _load(str(_find_file()))


def clear_congestion_cache() -> None:
    _load.cache_clear()
