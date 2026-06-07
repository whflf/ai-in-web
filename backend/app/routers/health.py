# API Health Check — проверка доступности PostgreSQL, Redis и ML-модели
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.ml.generator import generator
from app.schemas import ComponentHealth, HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Состояние всех компонентов сервиса",
)
async def health_check() -> HealthResponse:
    """
    API Health Check — проверяет PostgreSQL, Redis и готовность ML-модели.
    Возвращает статус каждого компонента отдельно.
    """
    components: dict[str, ComponentHealth] = {}

    # Проверка PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        components["postgres"] = ComponentHealth(status="ok")
    except Exception as exc:
        logger.error("Health check: postgres failed: %s", exc)
        components["postgres"] = ComponentHealth(status="error", detail=str(exc))

    # Проверка Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        components["redis"] = ComponentHealth(status="ok")
    except Exception as exc:
        logger.error("Health check: redis failed: %s", exc)
        components["redis"] = ComponentHealth(status="error", detail=str(exc))

    # Проверка готовности ML-модели
    if generator.is_ready:
        components["ml_model"] = ComponentHealth(
            status="ok", detail=f"ollama/{settings.OLLAMA_MODEL}"
        )
    else:
        components["ml_model"] = ComponentHealth(status="error", detail="Model not ready")

    overall = (
        "ok"
        if all(c.status == "ok" for c in components.values())
        else "degraded"
        if any(c.status == "ok" for c in components.values())
        else "error"
    )

    logger.info("Health check complete | status=%s", overall)
    return HealthResponse(status=overall, components=components)
