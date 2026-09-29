"""Vessel lists and per-port operational metrics from vessel_snapshots.csv."""
import pandas as pd

from app.data.ports import find_port
from app.data.vessel_loader import load_vessels
from app.errors import NotFoundError, PortNotFoundError

_COLS = ["vessel_id", "snapshot_date", "port", "status", "berth_name", "vessel_name", "vessel_type",
         "vessel_dimensions", "loa_m", "draft_m", "cargo", "cargo_category", "quantity_mts_numeric",
         "direction_norm", "arrival_or_eta", "berth_or_etb", "etc_or_etcd", "origin_destination"]


def _v(x):
    if pd.isna(x):
        return None
    if isinstance(x, pd.Timestamp):
        return x.date().isoformat()
    return x.item() if hasattr(x, "item") else x


def _rec(r) -> dict:
    out = {c: _v(r[c]) for c in _COLS if c in r.index}
    out["direction"] = out.pop("direction_norm", None)
    out["quantity_mts"] = out.pop("quantity_mts_numeric", None)
    return out


def _port_rows(d: pd.DataFrame, port_name: str) -> pd.DataFrame:
    p = find_port(port_name)
    sub = d[d["port"].str.lower() == (p.name if p else port_name).strip().lower()]
    if sub.empty:
        raise PortNotFoundError(port_name)
    return sub


def list_vessels(port=None, status=None, snapshot: str | None = "latest", limit=200) -> list[dict]:
    d = load_vessels()
    if port:
        d = _port_rows(d, port)
    if status:
        d = d[d["status"].str.lower() == status.lower()]
    if snapshot == "latest" and not d.empty:
        d = d[d["snapshot_date"] == d["snapshot_date"].max()]
    return [_rec(r) for _, r in d.head(limit).iterrows()]


def get_vessel(vessel_id: str) -> dict:
    d = load_vessels()
    hit = d[d["vessel_id"] == vessel_id]
    if hit.empty:
        raise NotFoundError("Vessel record was not found.")
    return _rec(hit.iloc[0])


def _counts(day: pd.DataFrame) -> dict:
    st = day["status"].str.lower()
    qty = day["quantity_mts_numeric"]
    return {
        "working": int((st == "working").sum()),
        "waiting": int((st == "waiting").sum()),
        "expected": int((st == "expected").sum()),
        "waiting_and_expected": int((st == "waiting & expected").sum()),
        "total_vessels": int(len(day)),
        "waiting_mts": float(qty[st == "waiting"].sum()),
        "expected_inbound_mts": float(qty[st.isin(["expected", "waiting & expected"])].sum()),
    }


def port_operations(port_name: str) -> dict:
    """Latest-snapshot counts + a berth-utilisation PROXY (no berth capacity in data)."""
    sub = _port_rows(load_vessels(), port_name)
    latest = sub["snapshot_date"].max()
    day = sub[sub["snapshot_date"] == latest]
    berths_seen = sub["berth_name"].dropna().nunique()
    berths_now = day.loc[day["status"].str.lower() == "working", "berth_name"].dropna().nunique()
    return {
        "port": sub["port"].iloc[0], "snapshot_date": latest.date().isoformat(), **_counts(day),
        "berths_seen_in_dataset": int(berths_seen), "berths_working_now": int(berths_now),
        "berth_utilisation_proxy_pct": round(100 * berths_now / berths_seen, 1) if berths_seen else None,
        "notes": "Proxy only: berths_seen is distinct berth names across all snapshots, not true berth capacity. "
                 "Some ports report 'Waiting & Expected' as one combined status.",
    }


def port_queue_history(port_name: str) -> list[dict]:
    sub = _port_rows(load_vessels(), port_name)
    return [{"date": dt.date().isoformat(), **_counts(g)} for dt, g in sub.groupby("snapshot_date")]


# ---------- derived metrics used by congestion fallback, risk and recommendation ----------

def _queue_metrics(day: pd.DataFrame) -> dict:
    """Queue-based congestion index. NOT the model congestion score.

    index = waiting / (working + waiting) * 100. Ports that only report the
    combined status 'Waiting & Expected' (e.g. Paradip) cannot be split, so
    the index is None for them rather than a guess.
    """
    st = day["status"].str.lower()
    waiting, working = int((st == "waiting").sum()), int((st == "working").sum())
    combined = int((st == "waiting & expected").sum())
    idx = None
    if waiting + working > 0 and not (combined and waiting == 0 and working == 0):
        idx = round(100 * waiting / (waiting + working), 1)
    w = day[st == "waiting"]
    days = (w["snapshot_date"] - w["arrival_or_eta"]).dt.days.clip(lower=0).dropna()
    return {
        "queue_congestion_index": idx, "waiting": waiting, "working": working,
        "avg_waiting_days": round(float(days.mean()), 1) if len(days) else None,
    }


def derived_congestion_latest() -> list[dict]:
    d = load_vessels()
    out = []
    for port, sub in d.groupby("port"):
        latest = sub["snapshot_date"].max()
        out.append({"port": port, "date": latest.date().isoformat(),
                    **_queue_metrics(sub[sub["snapshot_date"] == latest])})
    return sorted(out, key=lambda r: r["port"])


def derived_congestion_history(port_name: str) -> list[dict]:
    sub = _port_rows(load_vessels(), port_name)
    return [{"port": sub["port"].iloc[0], "date": dt.date().isoformat(), **_queue_metrics(g)}
            for dt, g in sub.groupby("snapshot_date")]


MIN_SNAPSHOTS_FOR_BASELINE = 3


def risk_inputs(port_name: str) -> dict:
    """berth_availability (proxy) and demand volume vs the port's own median."""
    sub = _port_rows(load_vessels(), port_name)
    ops = port_operations(port_name)
    per_day = [_counts(g)["expected_inbound_mts"] for _, g in sub.groupby("snapshot_date")]
    ref = float(pd.Series(per_day).median()) if len(per_day) >= MIN_SNAPSHOTS_FOR_BASELINE else None
    util = ops["berth_utilisation_proxy_pct"]
    return {
        "berth_availability": round(100 - util, 1) if util is not None else None,
        "demand_volume": ops["expected_inbound_mts"],
        "demand_volume_reference": ref if ref and ref > 0 else None,
    }


def observed_limits(port_name: str) -> dict:
    """Largest LOA/draft and vessel classes actually seen at the port. Precedent, not a rule."""
    sub = _port_rows(load_vessels(), port_name)
    return {
        "port": sub["port"].iloc[0],
        "max_observed_loa_m": _v(sub["loa_m"].max()),
        "max_observed_draft_m": _v(sub["draft_m"].max()),
        "vessel_classes_seen": sorted(sub["vessel_type"].dropna().str.upper().unique().tolist()),
        "vessels_with_dimensions": int(sub["loa_m"].notna().sum()),
    }
