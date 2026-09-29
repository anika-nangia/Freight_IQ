from typing import Annotated

from fastapi import APIRouter, Path

from app.config import get_settings
from app.data.ports import find_port, list_ports
from app.errors import PortNotFoundError
from app.schemas.weather import PORT_NAME_PATTERN, PortInfo

router = APIRouter(prefix="/ports", tags=["ports"])


def _info(p) -> PortInfo:
    return PortInfo(name=p.name, state=p.state, latitude=p.latitude, longitude=p.longitude)


@router.get("", response_model=list[PortInfo])
def ports() -> list[PortInfo]:
    return [_info(p) for p in list_ports(get_settings().supported_ports_list)]


@router.get("/{port_name}", response_model=PortInfo)
def port(port_name: Annotated[str, Path(pattern=PORT_NAME_PATTERN, max_length=60)]) -> PortInfo:
    p = find_port(port_name, get_settings().supported_ports_list)
    if p is None:
        raise PortNotFoundError(port_name)
    return _info(p)
