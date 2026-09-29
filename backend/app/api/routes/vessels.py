from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.schemas.weather import PORT_NAME_PATTERN
from app.services import vessel_service as vs

router = APIRouter(tags=["vessels"])
PortPath = Annotated[str, Path(pattern=PORT_NAME_PATTERN, max_length=60)]


@router.get("/vessels")
def vessels(port: str | None = None, status: str | None = None,
            snapshot: Annotated[str, Query(pattern="^(latest|all)$")] = "latest",
            limit: Annotated[int, Query(ge=1, le=1000)] = 200) -> dict:
    return {"vessels": vs.list_vessels(port, status, snapshot, limit)}


@router.get("/vessels/port/{port_name}")
def vessels_at_port(port_name: PortPath, status: str | None = None) -> dict:
    return {"port": port_name, "vessels": vs.list_vessels(port_name, status)}


@router.get("/vessels/{vessel_id}")
def vessel(vessel_id: Annotated[str, Path(pattern=r"^v\d{1,7}$")]) -> dict:
    return vs.get_vessel(vessel_id)


@router.get("/ports/{port_name}/operations")
def operations(port_name: PortPath) -> dict:
    return vs.port_operations(port_name)


@router.get("/ports/{port_name}/queue-history")
def queue_history(port_name: PortPath) -> dict:
    return {"port": port_name, "history": vs.port_queue_history(port_name)}
