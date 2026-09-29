from typing import Annotated

from fastapi import APIRouter, Path

from app.schemas.recommendation import RecommendationRequest
from app.schemas.vessel_opt import VesselOptimizeRequest
from app.schemas.weather import PORT_NAME_PATTERN
from app.services import vessel_service as vs
from app.services.recommendation_service import _operational_risk

router = APIRouter(tags=["risk", "vessel-optimizer"])


@router.get("/risk/{port_name}")
def risk(port_name: Annotated[str, Path(pattern=PORT_NAME_PATTERN, max_length=60)]) -> dict:
    """Operational risk (berth + demand) from vessel snapshots. Internal decision-support score, weather excluded."""
    inputs = vs.risk_inputs(port_name)
    level, reason = _operational_risk(RecommendationRequest(port_name=port_name, **inputs))
    return {"port": port_name, "operational_level": level, "reason": reason, "inputs": inputs,
            "source": "PROXY_FROM_VESSEL_SNAPSHOTS",
            "disclaimer": "Internal FreightIQ heuristic, not a validated risk model."}


@router.post("/vessel/optimize")
def optimize(body: VesselOptimizeRequest) -> dict:
    """Compares a vessel against dimensions/classes actually SEEN at the port.
    True port limits are not in the data, so 'compatible' is never claimed: the
    result is PRECEDENT_EXISTS, NO_PRECEDENT or UNKNOWN."""
    lim = vs.observed_limits(body.port_name)
    checks, warnings, unknown = [], [], []
    for name, val, mx in (("LOA", body.loa_m, lim["max_observed_loa_m"]),
                          ("draft", body.draft_m, lim["max_observed_draft_m"])):
        if val is None:
            unknown.append(f"{name} not provided")
        elif mx is None:
            unknown.append(f"No observed {name} data at this port")
        else:
            ok = val <= mx
            checks.append({"constraint": name, "vessel": val, "max_observed_at_port": mx, "within_observed": ok})
            if not ok:
                warnings.append(f"{name} {val} m exceeds the largest {mx} m seen at {lim['port']}.")
    if body.vessel_class:
        seen = body.vessel_class.upper() in lim["vessel_classes_seen"]
        checks.append({"constraint": "class", "vessel": body.vessel_class.upper(),
                       "classes_seen_at_port": lim["vessel_classes_seen"], "within_observed": seen})
        if not seen:
            warnings.append(f"No {body.vessel_class.upper()} vessel recorded at {lim['port']} in the data.")
    if not checks:
        status = "UNKNOWN"
    else:
        status = "PRECEDENT_EXISTS" if all(c["within_observed"] for c in checks) else "NO_PRECEDENT"
    return {"port": lim["port"], "status": status, "compatible": None, "checks": checks,
            "unknown": unknown, "warnings": warnings, "observed_limits": lim,
            "note": "Based only on vessels recorded in the snapshots (sparse). Confirm actual port limits before chartering."}
