from typing import Annotated

from fastapi import APIRouter, Path

from app.config import get_settings
from app.data.ports import list_ports
from app.schemas.weather import (
    PORT_NAME_PATTERN,
    PortInfo,
    PortWeatherRequest,
    PortWeatherResponse,
)
from app.services.weather_service import get_port_weather

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/ports", response_model=list[PortInfo])
async def supported_ports() -> list[PortInfo]:
    allowed = get_settings().supported_ports_list
    return [
        PortInfo(name=p.name, state=p.state, latitude=p.latitude, longitude=p.longitude)
        for p in list_ports(allowed)
    ]


@router.get("/port/{port_name}", response_model=PortWeatherResponse)
async def weather_for_port(
    port_name: Annotated[str, Path(pattern=PORT_NAME_PATTERN, max_length=60)],
) -> PortWeatherResponse:
    return await get_port_weather(port_name)


@router.post("/port", response_model=PortWeatherResponse)
async def weather_for_port_post(body: PortWeatherRequest) -> PortWeatherResponse:
    return await get_port_weather(body.port)
