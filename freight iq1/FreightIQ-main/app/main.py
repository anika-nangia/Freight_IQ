from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import Base, engine

# Import ORM models so Base.metadata knows about them before create_all.
from app.models import vessel as _vessel_models  # noqa: F401
from app.models import freight as _freight_models  # noqa: F401
from app.models import trade as _trade_models  # noqa: F401
from app.models import risk as _risk_models  # noqa: F401

from app.api.routes import (
    vessels, ports, freight, trade, risk, forecast, recommend, dashboard,
   
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only relevant for the local SQLite fallback — once DATABASE_URL points
    # at the real Postgres/Supabase instance, that DB's own migrations own
    # table creation and this becomes a no-op (create_all is idempotent and
    # skips existing tables).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(vessels.router)
app.include_router(ports.router)
app.include_router(freight.router)
app.include_router(trade.router)
app.include_router(risk.router)
app.include_router(forecast.router)
app.include_router(recommend.router)
app.include_router(dashboard.router)



@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}