"""
Pillar (c): Idle and deadheading risk from observed cargo flow.

The previous version held a REPOSITIONING_NETWORK of hand-written opportunities with
specific numbers in it, e.g. Haldia to Dhamra: bunker 3,800 USD, net profit gain
41,200 USD, "avoids a 4-day Paradip coal waiting queue". None of that was observed or
derivable from any file in the repo. It also imported an ISS traffic parser that
returned hardcoded MMT figures per port.

Neither survives.

What can be computed honestly: the line-up data records, per vessel, whether it is
importing or exporting, the cargo, the tonnage, and the origin. That gives a real
inbound/outbound balance per port per snapshot, and it is the quantity the deadheading
question actually turns on. A vessel that discharges an import cargo at a port with
little outbound cargo is looking for a return parcel.

So this service reports the observed balance, the tonnage at stake, and the modelled
turnaround cost of waiting. Where a repositioning opportunity cannot be evidenced, it
says so rather than inventing a profit figure.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402
from data_pipeline.build_congestion_dataset import (  # noqa: E402
    _dir_class, _norm_for_flow)

SNAPSHOTS = ROOT / "data" / "interim" / "port_congestion_snapshots.csv"
LINEUPS = ROOT / "data" / "vessel_snapshots.csv"

PORT_ALIASES = {"PARADIP PORT": "PARADIP", "SANDHEADS": "SAGAR", "VISAKHAPATNAM": "VISAKHAPATNAM"}
# Business assumptions, surfaced in the response.
HOTEL_BUNKER_USD_PER_DAY = 1800.0
# Outbound to inbound tonnage ratio below which a discharging vessel has a weak
# prospect of finding a return parcel. Policy, not a fitted threshold.
LOW_RETURN_RATIO = 0.75


class IdleManagementService:
    def __init__(self, lineups: Path = LINEUPS, snapshots: Path = SNAPSHOTS) -> None:
        self.lineups_path, self.snapshots_path = lineups, snapshots
        self._flow: Optional[pd.DataFrame] = None
        self._latest: Optional[str] = None

    # ------------------------------------------------------------------ data
    def _load(self) -> pd.DataFrame:
        if self._flow is not None:
            return self._flow
        d = pd.read_csv(self.lineups_path)
        d["snapshot_date"] = pd.to_datetime(d["snapshot_date"])
        d["port"] = d["port"].astype(str).str.strip().str.upper().replace(PORT_ALIASES)
        d["dir_class"] = d["direction"].map(_dir_class)
        d["status_clean"] = d["status"].astype(str).str.strip()
        d["is_working"] = d["status_clean"].str.contains("Working", case=False, na=False).astype(int)
        d["tonnage"] = pd.to_numeric(d["quantity_mts_numeric"], errors="coerce").fillna(0.0)

        # Only vessels actually at the berth are a claim on the port's throughput.
        # Counting vessels merely 'Expected' would overstate demand.
        working = d[d["is_working"] == 1]
        self._latest = working["snapshot_date"].max() if not working.empty else None

        rows = []
        for (port, date), grp in working.groupby(["port", "snapshot_date"]):
            imp = grp[grp["dir_class"] == "import"]
            exp = grp[grp["dir_class"] == "export"]
            both = grp[grp["dir_class"] == "both"]
            imp_t = float(imp["tonnage"].sum())
            exp_t = float(exp["tonnage"].sum())
            rows.append({
                "port": port, "snapshot_date": date,
                "import_vessels": int(len(imp)), "export_vessels": int(len(exp)),
                "both_vessels": int(len(both)),
                "import_tonnage_mt": imp_t, "export_tonnage_mt": exp_t,
                "total_tonnage_mt": imp_t + exp_t,
            })
        self._flow = pd.DataFrame(rows)
        return self._flow

    def _all_ports(self) -> List[str]:
        d = pd.read_csv(self.lineups_path)
        return sorted(d["port"].astype(str).str.strip().str.upper().replace(PORT_ALIASES).unique())

    def _snapshot_counts(self) -> Dict[str, int]:
        d = pd.read_csv(self.lineups_path)
        d["port"] = d["port"].astype(str).str.strip().str.upper().replace(PORT_ALIASES)
        return d.groupby("port")["snapshot_date"].nunique().to_dict()

    # ---------------------------------------------------------------- public
    def analyze(self, discharge_port: str, vessel_class: str = "Supramax",
                day_rate_usd: Optional[float] = None,
                voyage_days: float = 0.0) -> Dict[str, Any]:
        """Idle-cost exposure and return-cargo prospects for a discharge port."""
        flow = self._load()
        p = _norm_for_flow(discharge_port)
        rows = flow[flow["port"] == p]

        if rows.empty:
            # Distinguish "we hold nothing for this port" from "we hold a line-up but no
            # vessel is berthed". Paradip is the second case: all 40 of its listed
            # vessels are 'Waiting & Expected', so there is no throughput to measure.
            reason = f"no observed working line-up for '{p}'"
            detail = None
            if p not in set(flow["port"]) and p in set(self._all_ports()):
                seen = self._snapshot_counts().get(p, 0)
                detail = (f"a line-up exists for {p} on {seen} snapshot dates, but no vessel "
                          f"is recorded as berthed and working on any of them, so there is no "
                          f"observed throughput to compute a return-cargo balance from")
            return {
                "available": False,
                "port": discharge_port,
                "reason": reason,
                "detail": detail,
                "ports_with_data": sorted(flow["port"].unique().tolist()) if not flow.empty else [],
                "provenance": prov.unavailable("port_lineups", reason),
            }

        latest_date = rows["snapshot_date"].max()
        r = rows[rows["snapshot_date"] == latest_date].iloc[-1]
        imp_t, exp_t = float(r["import_tonnage_mt"]), float(r["export_tonnage_mt"])
        ratio = exp_t / imp_t if imp_t > 0 else None

        if ratio is None:
            tier, reading = "unknown", ("No import tonnage observed at this snapshot, so the "
                                        "return-cargo ratio cannot be computed.")
        elif ratio < 0.4:
            tier = "high"
            reading = (f"Export tonnage is {ratio:.2f}x import tonnage. A vessel that has just "
                       f"discharged here has little observed outbound cargo to load.")
        elif ratio < LOW_RETURN_RATIO:
            tier = "moderate"
            reading = (f"Export tonnage is {ratio:.2f}x import tonnage. Some return cargo "
                       f"exists but it is thin relative to what was discharged.")
        else:
            tier = "low"
            reading = (f"Export tonnage is {ratio:.2f}x import tonnage, so return cargo is "
                       f"plentiful relative to the discharge.")

        # Idle cost is a business calculation, not an observation. Both inputs are
        # returned so a reader can substitute their own.
        rate = day_rate_usd if day_rate_usd is not None else 0.0
        rate_source = "supplied by caller" if day_rate_usd is not None else "not supplied"
        scenarios = []
        for days in (7, 14, 21):
            charter = days * rate
            hotel = days * HOTEL_BUNKER_USD_PER_DAY
            scenarios.append({
                "idle_days": days,
                "charter_cost_usd": round(charter, 0),
                "hotel_bunker_usd": round(hotel, 0),
                "total_idle_cost_usd": round(charter + hotel, 0),
                "tonnage_at_stake_mt": round(imp_t, 0),
            })

        out: Dict[str, Any] = {
            "available": True,
            "port": p,
            "vessel_class": vessel_class,
            "as_of": latest_date.strftime("%Y-%m-%d"),
            "observed_flow": {
                "import_vessels": int(r["import_vessels"]),
                "export_vessels": int(r["export_vessels"]),
                "both_direction_vessels": int(r["both_vessels"]),
                "import_tonnage_mt": round(imp_t, 0),
                "export_tonnage_mt": round(exp_t, 0),
                "export_to_import_ratio": round(ratio, 3) if ratio is not None else None,
            },
            "deadhead_risk_tier": tier,
            "assessment": reading,
            "ratio_basis": f"export / import tonnage, working vessels only, as of {latest_date:%Y-%m-%d}",
            "idle_scenarios": scenarios,
            "day_rate_usd": rate,
            "day_rate_source": rate_source,
            "hotel_bunker_usd_per_day": HOTEL_BUNKER_USD_PER_DAY,
            "cost_note": "Idle cost is a business calculation from a day rate. It is not an "
                         "observed figure, and it is only meaningful once a day rate is supplied.",
            "repositioning": {
                "available": False,
                "reason": "No repositioning opportunity is quoted because none can be "
                          "evidenced from the data held. The previous implementation returned "
                          "a fixed list with dollar figures (for example a 41,200 USD net gain "
                          "ballasting Haldia to Dhamra) that appear in no source file and "
                          "cannot be derived from the line-ups. Supply freight-rate and "
                          "distance data for candidate ports and this becomes computable.",
            },
        }
        out["provenance"] = prov.provenance_block(["port_lineups"])
        out["confidence"] = {
            "level": "medium",
            "reasons": [
                f"flow observed on a single snapshot date ({latest_date:%Y-%m-%d}), not a series",
                "direction is read from a free-text field and some rows are ambiguous",
            ],
        }
        return out

    def network_summary(self) -> List[Dict[str, Any]]:
        """Deadhead risk for every port we hold a working line-up for."""
        flow = self._load()
        if flow.empty:
            return []
        out = []
        for port in sorted(flow["port"].unique()):
            rows = flow[flow["port"] == port]
            latest = rows["snapshot_date"].max()
            r = rows[rows["snapshot_date"] == latest].iloc[-1]
            imp_t, exp_t = float(r["import_tonnage_mt"]), float(r["export_tonnage_mt"])
            ratio = exp_t / imp_t if imp_t > 0 else None
            tier = ("unknown" if ratio is None else "high" if ratio < 0.4
                    else "moderate" if ratio < LOW_RETURN_RATIO else "low")
            out.append({
                "port": port,
                "as_of": latest.strftime("%Y-%m-%d"),
                "import_tonnage_mt": round(imp_t, 0),
                "export_tonnage_mt": round(exp_t, 0),
                "export_to_import_ratio": round(ratio, 3) if ratio is not None else None,
                "deadhead_risk_tier": tier,
            })
        return sorted(out, key=lambda x: (x["deadhead_risk_tier"] != "high", x["port"]))


_SERVICE: Optional[IdleManagementService] = None


def get_service() -> IdleManagementService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = IdleManagementService()
    return _SERVICE
