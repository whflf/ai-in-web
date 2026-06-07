import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.database import close_db, init_db
from app.ml.generator import generator
from app.routers import generate, health, history
from app.schemas import ErrorResponse

# Логирование — формат с timestamp и уровнем
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Управление жизненным циклом — инициализация и завершение работы приложения.
    Startup: подключение к БД, Redis, прогрев ML-модели.
    Shutdown: graceful закрытие всех соединений.
    """
    # Startup
    logger.info("Application startup | env=%s | model=%s", settings.APP_ENV, settings.OLLAMA_MODEL)

    await init_db()
    logger.info("Database pool initialized")

    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=5)
        await r.ping()
        await r.aclose()
        logger.info("Redis connection verified")
    except Exception as exc:
        logger.warning("Redis not available at startup: %s", exc)

    # Загрузка ML-модели в память — прогрев
    generator.warmup()

    # Graceful Shutdown — регистрируем обработчик SIGTERM
    def _handle_sigterm(signum, frame):
        logger.info("SIGTERM received — initiating graceful shutdown")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    logger.info("Application ready")
    yield

    # Shutdown
    logger.info("Application shutdown initiated")
    await close_db()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="ML Text Generation Service",
    description="Сервис генерации текста на базе HuggingFace Inference API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Метрики Prometheus — инструментация FastAPI
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Роутеры
app.include_router(generate.router)
app.include_router(history.router)
app.include_router(health.router)


# Обработка ошибок — кастомный handler для ошибок валидации (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Validation error | path=%s | errors=%s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Validation failed",
            detail=exc.errors(),
            status_code=422,
        ).model_dump(),
    )


# Обработка ошибок — handler для непредвиденных ошибок (500)
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception | path=%s | error=%s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if settings.APP_ENV != "production" else None,
            status_code=500,
        ).model_dump(),
    )


@app.get("/", tags=["root"])
async def root():
    return {"service": "ML Text Generation API", "docs": "/docs", "health": "/api/health"}
