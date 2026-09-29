from typing import Any

from pydantic import BaseModel, Field

from app.schemas.weather import PORT_NAME_PATTERN


class HistoryCreate(BaseModel):
    port: str = Field(pattern=PORT_NAME_PATTERN)
    vessel: str | None = Field(default=None, max_length=100)
    inputs: dict[str, Any] = Field(default_factory=dict, description="What the user entered.")
    recommendation: dict[str, Any] | None = None


class HistoryRecord(BaseModel):
    id: str
    created_at: str
    port: str
    vessel: str | None
    inputs: dict[str, Any]
    recommendation: dict[str, Any] | None
