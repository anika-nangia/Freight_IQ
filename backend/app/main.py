import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (congestion, explainability, forecast, freight, health,
                            history, ports, recommendation, risk_vessel, vessels, weather)
from app.config import get_settings
from app.errors import AppError, PortNotFoundError

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(title="FreightIQ Backend", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(weather.router)
    api.include_router(freight.router)
    api.include_router(forecast.router)
    api.include_router(recommendation.router)
    api.include_router(ports.router)
    api.include_router(vessels.router)
    api.include_router(risk_vessel.router)
    api.include_router(congestion.router)
    api.include_router(history.router)
    api.include_router(explainability.router)
    app.include_router(api)

    @app.exception_handler(PortNotFoundError)
    async def port_not_found(_: Request, exc: PortNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": "PORT_NOT_FOUND", "message": "Destination port was not found."},
        )

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("%s: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code, content={"error": exc.code, "message": exc.message}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"error": "VALIDATION_ERROR", "message": "Invalid request.", "details": details},
        )

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
        )

    return app


app = create_app()
