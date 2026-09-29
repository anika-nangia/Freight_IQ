import logging

from fastapi import APIRouter

from app.errors import DatasetError, PortNotFoundError
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.freight_service import apply_bdi_market_data
from app.services.recommendation_service import build_recommendation
from app.services.vessel_service import risk_inputs
from app.services.weather_service import get_port_weather

logger = logging.getLogger(__name__)
router = APIRouter(tags=["recommendation"])


@router.post("/recommendation", response_model=RecommendationResponse)
async def recommendation(body: RecommendationRequest) -> RecommendationResponse:
    weather = await get_port_weather(body.port_name)
    derived: dict[str, str] = {}
    if body.use_bdi_market_data:
        try:
            body, derived = apply_bdi_market_data(body)
        except DatasetError as exc:
            logger.warning("BDI market data unavailable: %s", exc.message)
    if body.use_vessel_snapshot_data:
        try:
            inputs = risk_inputs(body.port_name)
            fill = {}
            for k, v in inputs.items():
                if v is not None and getattr(body, k) is None:
                    fill[k] = v
                    derived[k] = "PROXY_FROM_VESSEL_SNAPSHOTS"
            body = body.model_copy(update=fill)
        except (DatasetError, PortNotFoundError) as exc:
            logger.warning("Vessel snapshot data unavailable: %s", exc.message)
    return build_recommendation(body, weather, derived)
