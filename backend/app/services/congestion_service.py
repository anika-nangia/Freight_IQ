"""Congestion scoreboard / port-map data. Values come only from the dataset."""
import pandas as pd

from app.data.congestion_loader import load_congestion
from app.errors import DatasetError
from app.services import vessel_service
from app.data.ports import find_port
from app.errors import PortNotFoundError

METRICS = ("congestion_score", "freight_rate", "rate_momentum_14d")


def _clean(v):
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    if hasattr(v, "item"):  # numpy scalar -> python
        return v.item()
    return v


def _row(r: pd.Series) -> dict:
    return {k: _clean(r[k]) for k in r.index}


def _port_frame(frame: pd.DataFrame, port_name: str) -> pd.DataFrame:
    p = find_port(port_name)
    target = (p.name if p else port_name).strip().lower()
    sub = frame[frame["port"].str.lower() == target]
    if sub.empty:
        raise PortNotFoundError(port_name)
    return sub


def latest_all() -> list[dict]:
    """One latest row per port, for the scoreboard boxes and port map."""
    frame = load_congestion()
    if "date" in frame:
        frame = frame.dropna(subset=["date"])
        frame = frame.sort_values("date").groupby("port", as_index=False).tail(1)
    else:
        frame = frame.drop_duplicates("port", keep="last")
    return [_row(r) for _, r in frame.sort_values("port").iterrows()]


def latest_for(port_name: str) -> dict:
    return _row(_port_frame(load_congestion(), port_name).iloc[-1])


def history_for(port_name: str, limit: int | None = None) -> list[dict]:
    sub = _port_frame(load_congestion(), port_name)
    if limit:
        sub = sub.tail(limit)
    return [_row(r) for _, r in sub.iterrows()]


# ---------- with automatic fallback to vessel-snapshot-derived queue metrics ----------

def scoreboard() -> dict:
    try:
        return {"source": "CONGESTION_DATASET", "ports": latest_all()}
    except DatasetError as exc:
        ports = vessel_service.derived_congestion_latest()  # raises DatasetError if also missing
        return {"source": "DERIVED_FROM_VESSEL_SNAPSHOTS", "ports": ports,
                "note": f"Model congestion score unavailable ({exc.message}) - showing queue-based index."}


def port_latest(port_name: str) -> dict:
    try:
        return {"source": "CONGESTION_DATASET", **latest_for(port_name)}
    except DatasetError:
        return {"source": "DERIVED_FROM_VESSEL_SNAPSHOTS", **vessel_service.derived_congestion_history(port_name)[-1]}


def port_history(port_name: str, limit: int | None = None) -> dict:
    try:
        return {"source": "CONGESTION_DATASET", "port": port_name, "history": history_for(port_name, limit)}
    except DatasetError:
        h = vessel_service.derived_congestion_history(port_name)
        return {"source": "DERIVED_FROM_VESSEL_SNAPSHOTS", "port": port_name, "history": h[-limit:] if limit else h}
