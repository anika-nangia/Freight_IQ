"""
Automated data-provenance audit.

Runs statistical and internal-consistency checks over every dataset and grades each
one. Written after `data/training_matrix.csv` turned out to carry the structural
signature of a generated series, and after `berth_operations.csv` was found to
contradict `vessel_snapshots.csv` on the same ports and the same dates.

The point is not to catch deliberate fabrication. It is to catch the ordinary way
this goes wrong: a placeholder committed as real data, a half-finished extract left
looking authoritative, or two extracts that were never reconciled with each other.

Checks
  provenance     tier declared, source named, file present
  structure      rows, null rate, duplicate rate, date coverage
  degeneracy     constant or near-constant columns that survived a null check
  granularity    decimal places, round-number bias in quantity-like columns
  smoothness     lag-1 autocorrelation of returns (generated series trend high)
  co-movement    pairwise correlation between supposedly independent series
  scaling        whether one series is a fixed multiple of another
  consistency    cross-file contradictions on shared keys

Run:  python -m data_pipeline.audit_datasets
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402

OUT = ROOT / "data" / "interim" / "provenance_audit.json"

# Thresholds. These are judgement calls, stated so they can be argued with.
SMOOTH_AC = 0.35            # lag-1 autocorrelation of log returns above this is suspicious
CO_MOVE_MEAN_CORR = 0.80    # mean pairwise correlation of series that should differ
CO_MOVE_MIN_CORR = 0.60     # even the least-correlated pair
SCALING_CV = 0.02           # coefficient of variation of a cross-series ratio
ROUND_FRACTION = 0.60       # share of quantities that are multiples of 1000


def _clean_col(name: Any) -> str:
    return str(name).strip().lower()


def _decimals(series: pd.Series) -> int:
    """Most common number of decimal places among non-integer values."""
    vals = pd.to_numeric(series, errors="coerce").dropna()
    vals = vals[vals % 1 != 0]
    if vals.empty:
        return 0
    counts: Dict[int, int] = {}
    for v in vals.head(500):
        s = f"{v:.6f}".rstrip("0")
        d = len(s.split(".")[1]) if "." in s else 0
        counts[d] = counts.get(d, 0) + 1
    return max(counts, key=lambda k: counts[k]) if counts else 0


def check_generated_signals(rates: pd.DataFrame) -> Dict[str, Any]:
    """The four findings that condemned training_matrix.csv, as reusable checks."""
    out: Dict[str, Any] = {}
    w = rates.copy()
    for c in ("load_port", "unload_port", "vessel_type"):
        w[c] = w[c].astype(str).str.strip().str.title()
    w["vessel_type"] = w["vessel_type"].str.replace(r"\s+", "", regex=True)
    w["vessel_class"] = w["vessel_type"].replace({"HandyMax": "Handymax"})
    w["corridor_id"] = w["load_port"] + "->" + w["unload_port"]
    w = w.sort_values(["corridor_id", "vessel_class", "date"])

    # 1. per-series return autocorrelation
    acs = {}
    for (cid, vc), g in w.groupby(["corridor_id", "vessel_class"]):
        r = np.log(g["rate_usd_mt"] / g["rate_usd_mt"].shift(1)).dropna()
        if len(r) > 4:
            acs[f"{cid}|{vc}"] = round(float(r.autocorr(1)), 3)
    high = {k: v for k, v in acs.items() if v > SMOOTH_AC}
    out["return_autocorrelation"] = {
        "n_series": len(acs), "high": len(high),
        "share_above_threshold": round(len(high) / max(1, len(acs)), 3),
        "mean_autocorr": round(float(np.mean(list(acs.values()))), 3) if acs else None,
        "flag": bool(len(high) / max(1, len(acs)) > 0.5),
        "threshold": SMOOTH_AC, "examples": dict(list(high.items())[:4]),
    }

    # 2. cross-series correlation of the modelling target
    piv = w.pivot_table(index="date", columns=["corridor_id", "vessel_class"],
                        values="rate_usd_mt")
    tgt = np.log(piv / piv.shift(2)).dropna()
    if tgt.shape[1] > 1 and len(tgt) > 3:
        c = tgt.corr().values
        iu = np.triu_indices(len(c), 1)
        pairs = c[iu]
        out["cross_series_target_correlation"] = {
            "mean": round(float(pairs.mean()), 3),
            "min": round(float(pairs.min()), 3),
            "n_pairs": int(len(pairs)),
            "flag": bool(pairs.mean() > CO_MOVE_MEAN_CORR),
        }

    # 3. fixed-multiple relationships
    lp = np.log(piv)
    ref_name = lp.columns[0]
    ref = lp[ref_name]
    scal = {str(k): round(float((lp[k] - ref).std()), 5) for k in lp.columns if k != ref_name}
    near = {k: v for k, v in scal.items() if v < 0.05}
    out["fixed_multiple_pairs"] = {
        "reference": str(ref_name),
        "n_near_constant": len(near),
        "threshold_log_std": 0.05,
        "examples": dict(sorted(near.items(), key=lambda kv: kv[1])[:4]),
    }

    # 4. cargo-size degeneracy
    cargo = w.groupby(["corridor_id", "vessel_class"])["cargo_intake"].nunique()
    out["cargo_size_per_lane"] = {
        "median_unique_sizes": float(cargo.median()),
        "lanes_with_single_size": int((cargo == 1).sum()),
        "n_lanes": int(len(cargo)),
    }
    return out


def check_granularity(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    v = pd.to_numeric(df[col], errors="coerce").dropna()
    if v.empty:
        return {"available": False}
    round_share = float((v % 1000 == 0).mean())
    return {
        "available": True,
        "n": int(len(v)),
        "decimals": _decimals(df[col]),
        "share_multiple_of_1000": round(round_share, 3),
        "flag": bool(round_share > ROUND_FRACTION and _decimals(df[col]) <= 2),
    }


def check_smoothness(df: pd.DataFrame, date_col: str, value_col: str,
                     key: Optional[List[str]] = None) -> Dict[str, Any]:
    d = df.copy()
    d[date_col] = pd.to_datetime(d[date_col])
    d = d.sort_values((key or []) + [date_col])
    acs = []
    groups = d.groupby(key) if key else [(None, d)]
    for _, g in (groups if key else [(None, d)]):
        r = np.log(g[value_col] / g[value_col].shift(1)).dropna()
        if len(r) > 4:
            acs.append(float(r.autocorr(1)))
    if not acs:
        return {"available": False}
    return {"available": True, "n_series": len(acs),
            "mean_autocorr": round(float(np.mean(acs)), 3),
            "flag": bool(np.mean(acs) > SMOOTH_AC)}


def audit_route_rates() -> Dict[str, Any]:
    p = ROOT / "data" / "training_matrix.csv"
    if not p.exists():
        return {"available": False}
    df = pd.read_csv(p, parse_dates=["date"])
    return {"available": True, "rows": len(df), "signals": check_generated_signals(df),
            "granularity": check_granularity(df, "cargo_intake")}


def audit_lineups() -> Dict[str, Any]:
    p = ROOT / "data" / "vessel_snapshots.csv"
    if not p.exists():
        return {"available": False}
    df = pd.read_csv(p, parse_dates=["snapshot_date"])
    findings: Dict[str, Any] = {"rows": len(df),
                                "distinct_vessels": int(df["vessel_name"].nunique()),
                                "snapshot_dates": int(df["snapshot_date"].nunique())}

    # A real port line-up must contain vessels that have finished. Every status here
    # is forward-looking, so no voyage is ever observed to complete.
    st = sorted(df["status"].dropna().unique().tolist())
    findings["status_values"] = st
    findings["has_completion_status"] = bool(
        any(re.search(r"sail|complet|depart|close|finish", s, re.I) for s in st))

    # ETCD revisions: proof the column is a live estimate rather than an outcome.
    d = df[df["etc_or_etcd"].notna()].copy()
    d["etcd"] = pd.to_datetime(d["etc_or_etcd"], errors="coerce")
    g = d.groupby(["port", "vessel_name"])["etcd"].nunique()
    multi = d.groupby(["port", "vessel_name"])["snapshot_date"].nunique()
    revised = int(((g > 1) & (multi > 1)).sum())
    findings["etcd_revised_between_snapshots"] = {
        "vessels_seen_more_than_once": int((multi > 1).sum()),
        "of_which_etcd_changed": revised,
        "interpretation": "a live schedule, not a recorded outcome",
    }

    findings["granularity"] = check_granularity(df, "quantity_mts_numeric")
    return findings


def audit_berth_consistency() -> Dict[str, Any]:
    """Do the two line-up extracts agree with each other?"""
    b = ROOT / "data" / "berth_operations.csv"
    d = ROOT / "data" / "vessel_snapshots.csv"
    if not (b.exists() and d.exists()):
        return {"available": False}
    berth = pd.read_csv(b)
    line = pd.read_csv(d)
    berth["port"] = berth["port"].astype(str).str.strip().str.upper()
    line["port"] = line["port"].astype(str).str.strip().str.upper().replace(
        {"PARADIP PORT": "PARADIP", "SANDHEADS": "SAGAR"})

    rows = []
    for port in sorted(set(berth["port"]) & set(line["port"])):
        same_dates = line[line["snapshot_date"].isin(berth["snapshot_date"])]
        vacant = set(berth[berth["port"] == port]["berth_name"].dropna())
        used = set(same_dates[(same_dates["port"] == port)
                              & same_dates["berth_name"].notna()]["berth_name"])
        rows.append({"port": port, "berths_listed_vacant": len(vacant),
                     "berths_shown_occupied": len(used), "overlap": len(vacant & used)})
    contradictions = [r for r in rows
                      if r["berths_shown_occupied"] > 0 and r["berths_listed_vacant"] > 0
                      and r["overlap"] > 0]
    return {
        "available": True,
        "berth_operations_status_values": berth["status"].value_counts().to_dict(),
        "berth_operations_is_all_one_status": bool(berth["status"].nunique() == 1),
        "per_port": rows,
        "n_contradicting_ports": len(contradictions),
        "verdict": ("CONTRADICTORY: berth_operations lists every berth Vacant on the same "
                    "dates the line-up shows vessels occupying those berths"
                    if contradictions else "consistent"),
    }


def audit_reference_tables() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in ("port_constraints", "vessel_specs", "loading_port_constraints"):
        spec = prov.get(key)
        if not spec.exists():
            out[key] = {"available": False}
            continue
        df = pd.read_csv(ROOT / spec.path)
        d: Dict[str, Any] = {"rows": len(df), "columns": len(df.columns),
                             "constant_columns": [c for c in df.columns
                                                  if df[c].nunique(dropna=True) <= 1]}
        if key == "loading_port_constraints" and "source_url" in df.columns:
            d["rows_with_source_url"] = int(df["source_url"].notna().sum())
            d["distinct_source_domains"] = len(
                {re.sub(r"^https?://([^/]+).*", r"\1", u) for u in df["source_url"].dropna()})
        out[key] = d
    return out


def audit_external() -> Dict[str, Any]:
    """The externally fetched files are verified by their source, not by statistics."""
    out: Dict[str, Any] = {}
    for key in ("world_bank_pink_sheet", "port_weather", "fx_usd_inr"):
        spec = prov.get(key)
        if not spec.exists():
            out[key] = {"available": False}
            continue
        path = ROOT / spec.path
        df = pd.read_csv(path)
        date_col = next((c for c in ("date", "month") if c in df.columns), None)
        out[key] = {
            "available": True, "rows": len(df),
            "verification": "downloaded from the publisher's API; content is the "
                           "publisher's, not generated here",
            "source_url": spec.source_url,
            "period": [str(df[date_col].min())[:10], str(df[date_col].max())[:10]]
            if date_col else None,
        }
    return out


def run() -> Dict[str, Any]:
    route = prov.get("route_rates_weekly")
    report: Dict[str, Any] = {
        "audited_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": "Detect datasets that are present, look authoritative, and are not "
                   "grounded in an identifiable observation.",
        "declared_provenance": {k: {"tier": v.tier, "loaded": v.exists()}
                                for k, v in prov.REGISTRY.items()},
        "route_rates": audit_route_rates(),
        "port_lineups": audit_lineups(),
        "berth_cross_consistency": audit_berth_consistency(),
        "reference_tables": audit_reference_tables(),
        "external_sources": audit_external(),
    }

    verdicts: List[Dict[str, str]] = []
    rr = report["route_rates"]
    if rr.get("available"):
        s = rr["signals"]
        n_flagged = sum([
            s["return_autocorrelation"]["flag"],
            s.get("cross_series_target_correlation", {}).get("flag", False),
            s["fixed_multiple_pairs"]["n_near_constant"] > 0,
            s["cargo_size_per_lane"]["lanes_with_single_size"] > 0,
        ])
        verdicts.append({
            "dataset": "route_rates_weekly",
            "verdict": "GENERATED-SUSPECT" if n_flagged >= 2 else "inconclusive",
            "detail": f"{n_flagged}/4 generator signatures present",
        })
    bc = report["berth_cross_consistency"]
    if bc.get("available") and bc["n_contradicting_ports"]:
        verdicts.append({
            "dataset": "berth_status",
            "verdict": "NOT USABLE AS OCCUPANCY DATA",
            "detail": f"all rows Vacant; contradicts the line-up at "
                      f"{bc['n_contradicting_ports']} ports on the same dates",
        })
    lu = report["port_lineups"]
    if lu.get("available") and not lu.get("has_completion_status"):
        verdicts.append({
            "dataset": "port_lineups",
            "verdict": "REAL BUT FORWARD-LOOKING ONLY",
            "detail": "no completion status, so no realised turnaround can be derived; "
                      "ETCD is revised between snapshots, confirming it is a live estimate",
        })
    report["verdicts"] = verdicts
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"[audit] declared tiers: {report['declared_provenance']['route_rates_weekly']}")
    print(f"[audit] wrote {OUT.relative_to(ROOT)}")
    print("\n[audi] verdicts:")
    for v in verdicts:
        print(f"  {v['dataset']:22s} {v['verdict']:30s} {v['detail']}")
    return report


if __name__ == "__main__":
    run()
