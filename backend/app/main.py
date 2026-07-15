import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health_router
from app.core.config import get_settings


settings = get_settings()
logger = structlog.get_logger()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://192.168.0.195:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)


@app.get("/")
def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "health": "/health",
        "readiness": "/ready",
        "documentation": "/docs",
    }


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "control_plane_starting",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_environment,
    )
