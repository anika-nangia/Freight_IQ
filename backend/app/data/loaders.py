"""Load and validate the Baltic Dry Index CSV files.

Every *.csv in the data directory is read; files may overlap (the 3-year file is
a subset of the 5-year file). Rows are de-duplicated by date.
"""
import logging
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.config import get_settings
from app.errors import DatasetError

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATE_FORMAT = "%d-%m-%Y"
REQUIRED_COLUMNS = {"Date", "Price"}
OUTPUT_COLUMNS = ["date", "price", "open", "high", "low", "change_pct"]


def resolve_data_dir(data_dir: str | None = None) -> Path:
    path = Path(data_dir or get_settings().data_dir)
    return path if path.is_absolute() else BACKEND_ROOT / path


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(float("nan"), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce")


def read_bdi_file(path: Path) -> pd.DataFrame:
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig", thousands=",")
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DatasetError(f"Could not read dataset file {path.name}.") from exc

    missing = REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise DatasetError(
            f"Dataset file {path.name} is missing columns: {sorted(missing)}."
        )

    change = raw["Change %"].astype(str).str.replace("%", "", regex=False) if "Change %" in raw else None
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["Date"], format=DATE_FORMAT, errors="coerce"),
            "price": _numeric(raw, "Price"),
            "open": _numeric(raw, "Open"),
            "high": _numeric(raw, "High"),
            "low": _numeric(raw, "Low"),
            "change_pct": pd.to_numeric(change, errors="coerce") if change is not None else float("nan"),
        }
    )
    dropped = int(frame[["date", "price"]].isna().any(axis=1).sum())
    if dropped:
        logger.warning("Dropped %d unparseable rows from %s", dropped, path.name)
    return frame.dropna(subset=["date", "price"])


@lru_cache(maxsize=4)
def _load(directory: str) -> pd.DataFrame:
    folder = Path(directory)
    # Other datasets (vessel snapshots, congestion) live in the same folder; skip them.
    skip = ("vessel_snapshot", "congest")
    files = sorted(f for f in folder.glob("*.csv") if not any(k in f.name.lower() for k in skip))
    if not files:
        raise DatasetError("No dataset CSV files were found.")

    combined = pd.concat([read_bdi_file(f) for f in files], ignore_index=True)
    conflicts = combined.groupby("date")["price"].nunique()
    if (conflicts > 1).any():
        logger.warning("%d dates have conflicting prices across files", int((conflicts > 1).sum()))
    combined = (
        combined.sort_values("date")
        .drop_duplicates(subset="date", keep="last")
        .reset_index(drop=True)
    )
    if combined.empty:
        raise DatasetError("Dataset contains no valid rows.")
    logger.info("Loaded %d BDI rows (%s to %s) from %d file(s)",
                len(combined), combined["date"].min().date(), combined["date"].max().date(), len(files))
    return combined[OUTPUT_COLUMNS]


def load_bdi(data_dir: str | None = None) -> pd.DataFrame:
    """Cached, date-sorted, de-duplicated BDI frame. Do not mutate the result."""
    return _load(str(resolve_data_dir(data_dir)))


def clear_dataset_cache() -> None:
    _load.cache_clear()
