from pydantic import BaseModel, Field

from app.schemas.weather import PORT_NAME_PATTERN


class VesselOptimizeRequest(BaseModel):
    port_name: str = Field(pattern=PORT_NAME_PATTERN)
    vessel_class: str | None = Field(default=None, pattern=r"^(?i:panamax|handimax|cape)$")
    loa_m: float | None = Field(default=None, gt=0, le=500)
    draft_m: float | None = Field(default=None, gt=0, le=30)
