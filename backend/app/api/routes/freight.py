from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas.freight import BdiHistoryResponse, BdiSummary, FreightCatalogue
from app.services import freight_service

router = APIRouter(prefix="/freight", tags=["freight"])


@router.get("", response_model=FreightCatalogue)
def catalogue() -> FreightCatalogue:
    return freight_service.get_catalogue()


@router.get("/bdi", response_model=BdiHistoryResponse)
def bdi_history(
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Annotated[int | None, Query(ge=1, le=5000)] = None,
) -> BdiHistoryResponse:
    return freight_service.get_history(start_date, end_date, limit)


@router.get("/bdi/summary", response_model=BdiSummary)
def bdi_summary() -> BdiSummary:
    return freight_service.get_summary()
