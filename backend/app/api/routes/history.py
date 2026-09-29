from typing import Annotated

from fastapi import APIRouter, Query

from app.errors import NotFoundError
from app.repositories import history_repository as repo
from app.schemas.history import HistoryCreate, HistoryRecord

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[HistoryRecord])
def list_history(limit: Annotated[int, Query(ge=1, le=500)] = 100, port: str | None = None):
    return repo.list_all(limit, port)


@router.post("", response_model=HistoryRecord, status_code=201)
def add_history(body: HistoryCreate):
    return repo.create(body.port, body.vessel, body.inputs, body.recommendation)


@router.delete("")
def clear_history() -> dict:
    return {"deleted": repo.clear()}


@router.get("/{rec_id}", response_model=HistoryRecord)
def get_history(rec_id: str):
    rec = repo.get(rec_id)
    if rec is None:
        raise NotFoundError("History entry was not found.")
    return rec


@router.delete("/{rec_id}")
def delete_history(rec_id: str) -> dict:
    if not repo.delete(rec_id):
        raise NotFoundError("History entry was not found.")
    return {"deleted": rec_id}
