# Асинхронная очередь задач — Celery с Redis как брокером и бэкендом
from celery import Celery

from app.config import settings

celery_app = Celery(
    "ml_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    task_track_started=True,
    # Graceful Shutdown — мягкое завершение текущей задачи перед остановкой
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
