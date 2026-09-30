"""
Pillar (b): Vessel selection under physical port constraints.

The previous version hardcoded a PORT_LIMITS dict, a VESSEL_CLASSES dict and a port
dues formula of `dwt * 0.65 * 0.75 + 5000`. None of it was sourced, and it silently
defaulted any unknown port to Paradip's limits, which means a query for an unlisted
port returned a confident answer built on the wrong numbers.

Both reference tables actually exist in the repo, each with source attribution:
    data/port_constraints.csv                 discharge port limits
    data/international_loading_ports.csv      origin terminal limits, with source URLs
    data/vessel_specs.csv                     class DWT / LOA / beam / draft / day rate

This service reads them. A port missing from those files is reported as unknown, not
assumed.

What is still an assumption, and is labelled as one:
    * voyage speed and the distance between two ports, for which we hold no route file
    * port dues, for which we hold no tariff. The old formula is kept but reported
      separately so a reader can see how much of the cost it explains, and it is
      excluded from the feasibility decision, which depends only on physical limits.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline import provenance as prov  # noqa: E402

PORT_CONSTRAINTS = ROOT / "data" / "port_constraints.csv"
LOADING_PORTS = ROOT / "data" / "international_loading_ports.csv"
VESSEL_SPECS = ROOT / "data" / "vessel_specs.csv"

# Business assumptions, surfaced in the response so they can be replaced.
ASSUMED_SPEED_KNOTS = 13.0
ASSUMED_DISTANCE_NM = 3800.0
PORT_DUES_PER_DWT_USD = 0.65
PORT_DUES_LOADING_FACTOR = 0.75
PORT_DUES_FIXED_USD = 5000.0

# Sea miles between the ports we hold coordinates for, great-circle x 1.2 for route
# deviation. Used ONLY when both endpoints are in port_constraints.csv; otherwise the
# assumed distance applies and is flagged.
_COORDS: Dict[str, Tuple[float, float]] = {}


def _load() -> Dict[str, Any]:
    if not PORT_CONSTRAINTS.exists():
        raise FileNotFoundError(f"{PORT_CONSTRAINTS} missing")
    ports = pd.read_csv(PORT_CONSTRAINTS)
    ports["key"] = ports["port_name"].astype(str).str.strip().str.lower()
    for _, r in ports.iterrows():
        if pd.notna(r.get("latitude")) and pd.notna(r.get("longitude")):
            _COORDS[r["key"]] = (float(r["latitude"]), float(r["longitude"]))

    specs = pd.read_csv(VESSEL_SPECS) if VESSEL_SPECS.exists() else None
    loading = pd.read_csv(LOADING_PORTS) if LOADING_PORTS.exists() else None
    return {"ports": ports, "specs": specs, "loading": loading}


def _haversine_nm(a: Tuple[float, float], b: Tuple[float, float]) -> Optional[float]:
    R_nm = 3440.065
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R_nm * math.asin(math.sqrt(h)) * 1.2   # x1.2 for route deviation / pilotage


def _parse_number(v: Any) -> Optional[float]:
    """Constraint tables mix floats with strings like 'not published' and '18.6 (Berth 3)'."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s or s.lower() in ("not published", "n/a", "-"):
        return None
    out = []
    for ch in s:
        if ch.isdigit() or ch == ".":
            out.append(ch)
        elif out:
            break
    try:
        return float("".join(out)) if out else None
    except ValueError:
        return None


def _class_order(specs: pd.DataFrame) -> List[str]:
    return sorted(specs["vessel_class"].astype(str).str.strip().tolist(),
                  key=lambda c: float(specs.loc[specs["vessel_class"] == c, "dwt_typical"].iloc[0]))


class VesselOptimizerService:
    """Filter vessel classes by port physical limits, then rank by cost per tonne."""

    def __init__(self) -> None:
        self._data: Optional[Dict[str, Any]] = None

    @property
    def data(self) -> Dict[str, Any]:
        if self._data is None:
            self._data = _load()
        return self._data

    # ------------------------------------------------------------- references
    def discharge_ports(self) -> List[Dict[str, Any]]:
        p = self.data["ports"]
        out = []
        for _, r in p.iterrows():
            out.append({
                "port": r["port_name"], "state": r.get("state"),
                "max_draft_m": _parse_number(r.get("max_draft_m")),
                "max_loa_m": _parse_number(r.get("max_loa_m")),
                "max_beam_m": _parse_number(r.get("max_beam_m")),
                "num_berths": _parse_number(r.get("num_berths")),
                "max_vessel_class": r.get("max_vessel_class"),
                "tide_restriction": r.get("tide_restriction"),
            })
        return out

    def loading_terminals(self) -> List[Dict[str, Any]]:
        lf = self.data.get("loading")
        if lf is None:
            return []
        out = []
        for _, r in lf.iterrows():
            out.append({
                "country": r.get("country"), "terminal": r.get("port_name"),
                "max_loa_m": _parse_number(r.get("max_loa_m")),
                "max_beam_m": _parse_number(r.get("max_beam_m")),
                "max_draft_m": _parse_number(r.get("max_draft_m")),
                "max_vessel_class": r.get("max_vessel_class"),
                "source_url": r.get("source_url"),
            })
        return out

    def _port_limits(self, name: str) -> Optional[Dict[str, Any]]:
        p = self.data["ports"]
        key = str(name).strip().lower()
        hit = p[p["key"] == key]
        if hit.empty:
            return None
        r = hit.iloc[0]
        return {
            "port": r["port_name"],
            "max_draft_m": _parse_number(r.get("max_draft_m")),
            "max_loa_m": _parse_number(r.get("max_loa_m")),
            "max_beam_m": _parse_number(r.get("max_beam_m")),
            "num_berths": _parse_number(r.get("num_berths")),
            "max_vessel_class": r.get("max_vessel_class"),
        }

    def _terminal_limits(self, name: str) -> Optional[Dict[str, Any]]:
        lf = self.data.get("loading")
        if lf is None:
            return None
        key = str(name).strip().lower()
        hit = lf[lf["port_name"].astype(str).str.strip().str.lower() == key]
        if hit.empty:
            # Allow a looser match, e.g. 'Newcastle' matching 'Newcastle - Kooragang'.
            hit = lf[lf["port_name"].astype(str).str.strip().str.lower().str.contains(key, na=False)]
            if hit.empty or key == "":
                return None
            # Prefer the deepest-draft terminal when a city matches several.
            hit = hit.assign(_d=hit["max_draft_m"].map(_parse_number).fillna(-1)).sort_values("_d")
        r = hit.iloc[0]
        return {
            "terminal": r["port_name"],
            "max_draft_m": _parse_number(r.get("max_draft_m")),
            "max_loa_m": _parse_number(r.get("max_loa_m")),
            "max_beam_m": _parse_number(r.get("max_beam_m")),
            "max_vessel_class": r.get("max_vessel_class"),
            "source_url": r.get("source_url"),
        }

    # ------------------------------------------------------------------ main
    def optimize(self, origin: str, destination: str, cargo_volume_mt: float,
                 speed_knots: float = ASSUMED_SPEED_KNOTS,
                 forecast: Optional[Dict[str, Any]] = None,
                 congestion: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Rank vessel classes by EXPECTED MARGIN, not cost alone.

        With `forecast` supplied, each feasible class is scored as:

            revenue = Model 2 predicted rate  x cargo tonnes
            cost    = charter (day rate x voyage days)
                    + port dues estimate
                    + waiting cost (Model 1 port stay x day rate)
            margin  = revenue - cost

        Waiting cost is the part that matters operationally: a class that is cheap per
        tonne but sits at anchor for a week burns day-rate the charter never recovers.
        It is priced at the Model 1 80% upper band, not the point estimate, because
        planning around the optimistic end of a turnaround is how berths get missed.

        Without a forecast the service still runs, and says so: it reports cost per
        tonne and marks the margin as unavailable rather than substituting a rate.
        """
        specs = self.data["specs"]
        if specs is None:
            return {"available": False, "reason": f"{VESSEL_SPECS} missing"}

        dest = self._port_limits(destination)
        orig_port = self._port_limits(origin)
        orig_term = self._terminal_limits(origin) if orig_port is None else None

        if dest is None and orig_term is None:
            return {
                "available": False,
                "reason": f"no physical limits on file for origin '{origin}' or "
                          f"destination '{destination}'",
                "discharge_ports_with_limits": [p["port"] for p in self.discharge_ports()],
                "hint": "The system does not assume limits for an unlisted port. Add it to "
                        "data/port_constraints.csv with its berth capability.",
                "provenance": prov.unavailable("port_constraints", "no limits on file"),
            }

        origin_limits = orig_port or orig_term
        origin_kind = ("discharge-port record" if orig_port
                       else "loading-terminal record" if orig_term
                       else "UNKNOWN - no limits on file")

        # Distance: computed when both ends have coordinates, else assumed and flagged.
        a = _COORDS.get(str(origin).strip().lower())
        b = _COORDS.get(str(destination).strip().lower())
        if a and b:
            distance_nm, dist_source = _haversine_nm(a, b), "great-circle x1.2, from port_coordinates"
        else:
            distance_nm, dist_source = ASSUMED_DISTANCE_NM, "ASSUMED - no coordinates for one endpoint"

        # Published max_vessel_class vs the numeric limits.
        #
        # These can contradict each other, and Haldia does: port_constraints.csv gives
        # it an 8.5 m draft limit while also declaring Handysize as the largest class
        # admitted, yet the smallest class in vessel_specs draws 10.0 m. Applying the
        # draft number alone therefore rejects every class at a port that publishes a
        # class, which is an artefact of comparing a class TYPICAL draft against a
        # berth limit, not an operational fact.
        #
        # Where a port publishes a class, that published class is treated as the
        # authority for what the berth accepts, the numeric limits still gate anything
        # LARGER than it, and the disagreement is reported rather than resolved
        # silently in either direction.
        declared: List[str] = []
        for rec in (origin_limits, dest):
            if rec and rec.get("max_vessel_class"):
                declared.append(str(rec["max_vessel_class"]))
        dwt = {str(s["vessel_class"]): _parse_number(s.get("dwt_typical"))
               for _, s in specs.iterrows()}
        order = _class_order(specs)
        admitted_upto = -1
        for d in set(declared):
            if d in order:
                admitted_upto = max(admitted_upto, order.index(d))
        conflict = None
        if admitted_upto >= 0:
            smallest_admitted = order[admitted_upto]
            lim_draft = min([r["max_draft_m"] for r in (origin_limits, dest)
                             if r and r.get("max_draft_m") is not None] or [None])
            typ_draft = None
            for _, s in specs.iterrows():
                if s["vessel_class"] == smallest_admitted:
                    typ_draft = _parse_number(s.get("draft_typical"))
            if lim_draft is not None and typ_draft is not None and typ_draft > lim_draft:
                conflict = (
                    f"{dest['port'] if dest else origin} publishes a "
                    f"{lim_draft} m draft limit but also declares {smallest_admitted} as its "
                    f"largest admitted class, and the {smallest_admitted} class reference "
                    f"draft is {typ_draft} m. A class TYPICAL draft is not a berth limit, so "
                    f"the published class is used for admissibility and the numeric limits "
                    f"apply to anything larger. Confirm against the port's notice to "
                    f"charterers before fixing.")

        effective: Dict[str, Any] = {"origin": origin_limits, "origin_kind": origin_kind,
                                      "origin_verified": origin_limits is not None,
                                      "destination": dest, "distance_nm": round(distance_nm),
                                      "distance_source": dist_source,
                                      "declared_max_vessel_class": declared or None,
                                      "source_data_conflict": conflict}
        # A missing limit must not silently become "unlimited". Where a port publishes
        # no figure, feasibility on that dimension is unknown and is reported as such.
        dims = {}
        for dim in ("max_draft_m", "max_loa_m", "max_beam_m"):
            vals = [v[dim] for v in (origin_limits, dest) if v and v.get(dim) is not None]
            dims[dim] = min(vals) if vals else None
        effective["binding_limits"] = dims
        effective["unknown_dimensions"] = [k for k, v in dims.items() if v is None]

        evaluations = []
        for _, s in specs.iterrows():
            cls = s["vessel_class"]
            draft = _parse_number(s.get("draft_typical"))
            loa = _parse_number(s.get("loa_typical"))
            beam = _parse_number(s.get("beam_typical"))
            dwt = _parse_number(s.get("dwt_typical"))
            rate = _parse_number(s.get("cost_index_usd_day"))
            handling = _parse_number(s.get("cargo_handling_rate_tpd"))

            reasons: List[str] = []
            unknown: List[str] = []
            # Position in the size ordering, used for the published-class rule.
            cls_idx = order.index(cls) if cls in order else -1
            larger_than_declared = 0 <= admitted_upto < cls_idx
            published = (declared[0] if declared else cls)
            for dim, val, label in (("max_draft_m", draft, "sailing draft"),
                                    ("max_loa_m", loa, "LOA"),
                                    ("max_beam_m", beam, "beam")):
                lim = dims[dim]
                if lim is None:
                    unknown.append(label)
                elif val is not None and val > lim:
                    if larger_than_declared:
                        reasons.append(
                            f"{label} {val} m exceeds the {lim} m limit, and this class is "
                            f"larger than the {published} the port publishes as admissible")
                    else:
                        reasons.append(f"{label} {val} m exceeds the {lim} m limit, but the port "
                                       f"publishes {declared[0] if declared else 'this class'} "
                                       f"as admissible, so this is a conflict in the reference "
                                       f"data, not a bar")

            cargo_days = (cargo_volume_mt / handling) if handling else None
            sea_days = distance_nm / (speed_knots * 24.0) if speed_knots else None
            total_days = (sea_days + cargo_days) if (sea_days and cargo_days) else None
            charter_cost = rate * total_days if (rate and total_days) else None
            dues = dwt * PORT_DUES_PER_DWT_USD * PORT_DUES_LOADING_FACTOR + PORT_DUES_FIXED_USD if dwt else None
            carried = min(cargo_volume_mt, dwt) if dwt else cargo_volume_mt
            cost_per_ton = ((charter_cost + dues) / carried) if (charter_cost is not None and dues is not None) else None

            evaluations.append({
                "vessel_class": cls,
                "dwt": dwt, "draft_m": draft, "loa_m": loa, "beam_m": beam,
                "day_rate_usd": rate,
                "handling_tpd": handling,
                "sea_days": round(sea_days, 1) if sea_days else None,
                "cargo_days": round(cargo_days, 1) if cargo_days else None,
                "total_voyage_days": round(total_days, 1) if total_days else None,
                "charter_cost_usd": round(charter_cost, 0) if charter_cost else None,
                "port_dues_estimate_usd": round(dues, 0) if dues else None,
                "cost_per_ton_usd": round(cost_per_ton, 2) if cost_per_ton else None,
                "fits_cargo": bool(dwt and cargo_volume_mt <= dwt * 1.0),
                "is_feasible": not reasons,
                "rejection_reasons": reasons,
                "rejected_on_published_class": larger_than_declared,
                "unverified_dimensions": unknown,
            })

        # A class the port explicitly publishes as admissible is never rejected purely on
        # a conflicting numeric limit, so that Haldia does not return "no vessel works"
        # at a port that publishes Handysize as its largest class.
        feasible = [e for e in evaluations if e["is_feasible"] or not e["rejected_on_published_class"]]
        conflicting = [e["vessel_class"] for e in feasible if e["rejection_reasons"]]
        # Rank on cost per tonne among feasible classes that can actually carry the lot.
        rankable = [e for e in feasible if e["fits_cargo"] and e["cost_per_ton_usd"] is not None] or feasible
        recommended = min(rankable, key=lambda e: e["cost_per_ton_usd"]) if rankable else None

        # ------------------------------------------------- margin, if we can
        margin = self._margin(evaluations, rankable, cargo_volume_mt, forecast, congestion)
        if margin.get("available"):
            best = min(margin["per_class"], key=lambda r: r["rank_score"])
            recommended = next((e for e in evaluations
                                if e["vessel_class"] == best["vessel_class"]), recommended)

        # An origin with no limits on file cannot be feasibility-checked. Rather than
        # falling back to assumed limits and reporting a confident answer, the result
        # says the origin is unverified and marks the decision provisional.
        if origin_limits is None:
            origin_name, origin_verified = origin, False
        else:
            origin_name = origin_limits.get("port") or origin_limits.get("terminal")
            origin_verified = True

        out: Dict[str, Any] = {
            "available": bool(recommended),
            "ranking_basis": ("expected margin per voyage (Model 2 revenue vs charter + "
                              "dues + Model 1 waiting cost)"
                              if margin.get("available")
                              else "cost per tonne only - no rate forecast available for "
                                   "this corridor, so margin could not be computed"),
            "origin": origin_name,
            "origin_limits_verified": origin_verified,
            "origin_warning": (None if origin_verified else
                               f"no berth limits on file for origin '{origin}'. Feasibility was "
                               f"checked against the destination port only, so a vessel may be "
                               f"recommended that the origin cannot accept."),
            "destination": dest["port"] if dest else destination,
            "destination_limits_verified": dest is not None,
            "cargo_volume_mt": cargo_volume_mt,
            "effective_limits": effective,
            "recommended_vessel": recommended["vessel_class"] if recommended else None,
            "cost_per_ton_usd": recommended["cost_per_ton_usd"] if recommended else None,
            "expected_margin_usd_per_voyage": (
                next((r["margin_usd"] for r in margin.get("per_class", [])
                      if r["vessel_class"] == recommended["vessel_class"]), None)
                if margin.get("available") and recommended else None),
            "expected_margin_usd_per_tonne": (
                next((r["margin_usd_per_tonne"] for r in margin.get("per_class", [])
                      if r["vessel_class"] == recommended["vessel_class"]), None)
                if margin.get("available") and recommended else None),
            "margin_detail": margin,
            "breakdown_usd_per_ton": None,
            "evaluations": evaluations,
            "admitted_despite_conflicting_limit": conflicting,
            "data_quality_warning": (
                f"{conflict} Admitted anyway: {', '.join(conflicting)}."
                if conflict and conflicting else conflict),
            "assumptions": {
                "speed_knots": speed_knots,
                "distance_nm": round(distance_nm),
                "distance_source": dist_source,
                "port_dues_model": f"{PORT_DUES_PER_DWT_USD} USD/DWT x "
                                   f"{PORT_DUES_LOADING_FACTOR} + {PORT_DUES_FIXED_USD:.0f} USD",
                "port_dues_note": "No tariff data is held. This is a placeholder and it "
                                  "changes the cost ranking between similar classes. It does "
                                  "NOT affect feasibility, which depends only on physical limits.",
            },
        }
        if recommended and recommended.get("charter_cost_usd") and recommended.get("port_dues_estimate_usd"):
            carried = min(cargo_volume_mt, recommended["dwt"] or cargo_volume_mt)
            out["breakdown_usd_per_ton"] = {
                "charter": round(recommended["charter_cost_usd"] / carried, 2),
                "port_dues_estimate": round(recommended["port_dues_estimate_usd"] / carried, 2),
                "total": recommended["cost_per_ton_usd"],
            }
        if not recommended:
            out["reason"] = ("no vessel class satisfies the port limits and cargo volume. "
                             "Every class was rejected; see evaluations[].rejection_reasons")
        out["provenance"] = prov.provenance_block(
            ["port_constraints", "loading_port_constraints", "vessel_specs"])
        return out


    def _margin(self, evaluations: List[Dict[str, Any]], rankable: List[Dict[str, Any]],
                cargo_volume_mt: float, forecast: Optional[Dict[str, Any]],
                congestion: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Revenue from Model 2 against cost from the constraint tables and Model 1.

        Returns available=False with a reason when the rate is unknown, rather than
        borrowing a rate from anywhere. Cost-per-tonne alone does not tell a charterer
        whether a voyage is worth doing, so the gap is stated instead of filled.
        """
        if not forecast or not forecast.get("available"):
            return {"available": False,
                    "reason": "no freight-rate forecast for this corridor, so revenue "
                              "cannot be estimated. Ranking falls back to cost per tonne."}

        rate = _num(forecast.get("forecast_rate_usd_mt"))
        if rate is None:
            return {"available": False, "reason": "forecast carried no usable rate"}

        # Waiting days come from Model 1's 80% upper band, not the point estimate.
        wait_days: Optional[float] = None
        wait_source = "not available for this port"
        if congestion and congestion.get("available"):
            p80 = (congestion.get("turnaround_estimate") or {}).get("p80_range_days") or []
            if len(p80) == 2 and p80[1] is not None:
                wait_days = float(p80[1])
                wait_source = ("Model 1 port stay, 80% upper band "
                               f"({congestion.get('congestion_category')} congestion)")
            else:
                wait_source = "Model 1 has no turnaround range for this port"

        rows: List[Dict[str, Any]] = []
        for e in rankable:
            day_rate = e.get("day_rate_usd")
            voyage = e.get("total_voyage_days")
            dues = e.get("port_dues_estimate_usd")
            carried = min(cargo_volume_mt, e["dwt"]) if e.get("dwt") else cargo_volume_mt
            if day_rate is None or voyage is None or dues is None or not carried:
                continue
            charter = day_rate * voyage
            waiting = day_rate * wait_days if wait_days else 0.0
            revenue = rate * cargo_volume_mt
            cost = charter + dues + waiting
            rows.append({
                "vessel_class": e["vessel_class"],
                "revenue_usd": round(revenue, 0),
                "charter_cost_usd": round(charter, 0),
                "port_dues_usd": round(dues, 0),
                "waiting_cost_usd": round(waiting, 0),
                "total_cost_usd": round(cost, 0),
                "margin_usd": round(revenue - cost, 0),
                "margin_usd_per_tonne": round((revenue - cost) / carried, 2),
                "cost_per_ton_usd": e.get("cost_per_ton_usd"),
                "voyage_days": voyage,
                "tonnage_carried": carried,
            })
        if not rows:
            return {"available": False, "reason": "no class had a complete cost breakdown"}

        rows.sort(key=lambda r: -r["margin_usd"])
        for i, r in enumerate(rows):
            r["rank"] = i + 1
            # Rank on margin, falling back to cost/tonne if margin ties at zero.
            r["rank_score"] = -r["margin_usd"] if r["margin_usd"] else (r["cost_per_ton_usd"] or 0)

        return {
            "available": True,
            "rate_used_usd_mt": rate,
            "rate_as_of": forecast.get("current_observed_rate_as_of"),
            "rate_horizon_days": forecast.get("horizon_days"),
            "cargo_volume_mt": cargo_volume_mt,
            "waiting_days_priced": wait_days,
            "waiting_source": wait_source,
            "per_class": rows,
            "note": "Waiting is priced at the 80% upper band of Model 1's port stay, not "
                    "the point estimate. Port dues remain a placeholder - no tariff data "
                    "is held - so treat the margin as indicative to within that unknown.",
        }


_SERVICE: Optional[VesselOptimizerService] = None


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get_service() -> VesselOptimizerService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = VesselOptimizerService()
    return _SERVICE
