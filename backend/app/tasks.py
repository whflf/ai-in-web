# Асинхронная очередь задач — Celery задача генерации текста
# Логирование — время каждого этапа
import logging

from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.config import settings
from app.ml.generator import generator

logger = logging.getLogger(__name__)

# Синхронный движок для использования внутри Celery воркера
_sync_engine = create_engine(settings.DATABASE_SYNC_URL, pool_pre_ping=True)
_SyncSession = sessionmaker(bind=_sync_engine)


@celery_app.task(bind=True, name="app.tasks.generate_text")
def generate_text(self, task_id: str, prompt: str, max_tokens: int, creativity: float) -> dict:
    """
    Асинхронная очередь задач — основная задача генерации текста.
    Логирование — фиксируем начало, выполнение и окончание задачи.
    Stateless архитектура — результат сохраняется в БД, не в памяти воркера.
    """
    from app.models import GenerationRecord

    logger.info("Task started | task_id=%s", task_id)

    # Обновляем статус на STARTED
    with _SyncSession() as session:
        session.execute(
            update(GenerationRecord)
            .where(GenerationRecord.task_id == task_id)
            .values(status="STARTED")
        )
        session.commit()

    try:
        result = generator.generate(prompt=prompt, max_tokens=max_tokens, creativity=creativity)

        # Обновляем запись в БД результатом
        with _SyncSession() as session:
            session.execute(
                update(GenerationRecord)
                .where(GenerationRecord.task_id == task_id)
                .values(
                    status="SUCCESS",
                    result=result.text,
                    inference_time=result.inference_time,
                )
            )
            session.commit()

        logger.info(
            "Task completed | task_id=%s | inference_time=%.3fs", task_id, result.inference_time
        )
        return {"text": result.text, "inference_time": result.inference_time}

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Task failed | task_id=%s | error=%s", task_id, error_msg)

        with _SyncSession() as session:
            session.execute(
                update(GenerationRecord)
                .where(GenerationRecord.task_id == task_id)
                .values(status="FAILURE", error_message=error_msg)
            )
            session.commit()

        # Пробрасываем исключение — Celery сохранит FAILURE в backend
        raise
