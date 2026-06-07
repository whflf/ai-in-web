# Асинхронная очередь задач — эндпоинты постановки задачи и проверки статуса
# WebSocket статус задачи — WS эндпоинт вместо polling
# Stateless архитектура — состояние задачи хранится в Redis (Celery backend)
import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.database import get_db
from app.models import GenerationRecord
from app.schemas import GenerateRequest, GenerateResponse, TaskStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["generation"])


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=202,
    summary="Поставить задачу генерации текста в очередь",
)
async def enqueue_generation(
    request: GenerateRequest, db: AsyncSession = Depends(get_db)
) -> GenerateResponse:
    """
    Принимает промпт, создаёт запись в БД и ставит задачу в Celery очередь.
    Возвращает task_id для отслеживания статуса (202 Accepted).
    """
    task_id = str(uuid.uuid4())

    # ORM — сохраняем запись в PostgreSQL
    record = GenerationRecord(
        task_id=task_id,
        prompt=request.prompt,
        max_tokens=request.max_tokens,
        creativity=request.creativity,
        status="PENDING",
    )
    db.add(record)
    await db.commit()

    # Асинхронная очередь задач — отправляем задачу воркеру
    from app.tasks import generate_text
    generate_text.apply_async(
        args=[task_id, request.prompt, request.max_tokens, request.creativity],
        task_id=task_id,
    )

    logger.info("Task enqueued | task_id=%s | prompt_len=%d", task_id, len(request.prompt))
    return GenerateResponse(task_id=task_id)


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="Получить статус задачи (polling)",
)
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_db)) -> TaskStatusResponse:
    """Polling-эндпоинт: возвращает текущий статус задачи из БД."""
    result = await db.execute(
        select(GenerationRecord).where(GenerationRecord.task_id == task_id)
    )
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=record.task_id,
        status=record.status,
        result=record.result,
        inference_time=record.inference_time,
        error=record.error_message,
    )


@router.websocket("/ws/tasks/{task_id}")
async def task_status_websocket(websocket: WebSocket, task_id: str) -> None:
    """
    WebSocket статус задачи — клиент получает обновления без polling.
    Отправляет статус каждую секунду до завершения задачи.
    """
    await websocket.accept()
    logger.info("WebSocket connected | task_id=%s", task_id)

    try:
        while True:
            celery_result = celery_app.AsyncResult(task_id)
            state = celery_result.state

            payload: dict = {"task_id": task_id, "status": state}

            if state == "SUCCESS":
                payload["result"] = celery_result.result.get("text") if celery_result.result else None
                payload["inference_time"] = celery_result.result.get("inference_time") if celery_result.result else None
                await websocket.send_json(payload)
                break

            if state == "FAILURE":
                payload["error"] = str(celery_result.info)
                await websocket.send_json(payload)
                break

            await websocket.send_json(payload)
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected | task_id=%s", task_id)
    except Exception as exc:
        logger.error("WebSocket error | task_id=%s | error=%s", task_id, exc)
        await websocket.close(code=1011)
    finally:
        logger.info("WebSocket closed | task_id=%s", task_id)
