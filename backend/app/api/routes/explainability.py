from fastapi import APIRouter

from app.api.routes.recommendation import recommendation
from app.schemas.recommendation import RecommendationRequest
from app.services.explainability_service import build_evidence

router = APIRouter(prefix="/explainability", tags=["explainability"])


@router.post("")
async def explain(body: RecommendationRequest) -> dict:
    return build_evidence(await recommendation(body))
