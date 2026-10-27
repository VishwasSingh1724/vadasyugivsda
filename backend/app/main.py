import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.auth import router as auth_router
from app.api.middleware import RequestContextMiddleware, register_error_handlers
from app.api.routes import data, router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.repository import CsvRepository
from app.services.analytics import AnalyticsService

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # Built eagerly (not in a lifespan hook): serverless runtimes may skip ASGI lifespan events.
    service = AnalyticsService(CsvRepository(settings.data_dir), settings)
    log.info("service ready", extra={"data_version": service.version})

    app = FastAPI(
        title="WindWatch API",
        version="1.0.0",
        description="Day-ahead wind forecast decision support for GB (Elexon FUELHH / WINDFOR).",
    )
    app.state.service = service
    app.state.settings = settings
    app.state.data_version = service.version
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(data)
    return app


app = create_app()
