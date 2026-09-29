from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.schemas.weather import PORT_NAME_PATTERN
from app.services import congestion_service as cs

router = APIRouter(prefix="/congestion", tags=["congestion"])
PortPath = Annotated[str, Path(pattern=PORT_NAME_PATTERN, max_length=60)]


@router.get("")
def scoreboard() -> dict:
    return cs.scoreboard()


@router.get("/{port_name}")
def port_congestion(port_name: PortPath) -> dict:
    return cs.port_latest(port_name)


@router.get("/{port_name}/history")
def port_history(port_name: PortPath, limit: Annotated[int | None, Query(ge=1, le=5000)] = None) -> dict:
    return cs.port_history(port_name, limit)
