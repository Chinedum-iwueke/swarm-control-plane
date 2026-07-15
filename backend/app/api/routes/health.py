from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.db.readiness import check_postgres, check_redis


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()

    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_environment,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ready")
def readiness() -> dict:
    checks: dict[str, bool] = {
        "postgres": False,
        "redis": False,
    }

    errors: dict[str, str] = {}

    try:
        checks["postgres"] = check_postgres()
    except Exception as exc:
        errors["postgres"] = type(exc).__name__

    try:
        checks["redis"] = check_redis()
    except Exception as exc:
        errors["redis"] = type(exc).__name__

    if not all(checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "checks": checks,
                "errors": errors,
            },
        )

    return {
        "status": "ready",
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }
