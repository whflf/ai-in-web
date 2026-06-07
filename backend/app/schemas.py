# Валидация данных — строгие Pydantic-схемы с типами и ограничениями
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class GenerateRequest(BaseModel):
    """Запрос на генерацию текста."""

    prompt: str = Field(
        ...,
        min_length=10,
        max_length=4096,
        description="Текст для обработки (суммаризации/продолжения)",
        examples=["Artificial intelligence is transforming industries worldwide..."],
    )
    max_tokens: int = Field(
        default=128,
        ge=10,
        le=512,
        description="Максимальное количество токенов в ответе",
        examples=[128],
    )
    creativity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Уровень креативности: 0.0 — детерминированный, 1.0 — максимально случайный",
        examples=[0.5],
    )

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Prompt cannot be blank or whitespace only")
        return v.strip()


class TaskStatusResponse(BaseModel):
    """Ответ с текущим статусом задачи Celery."""

    task_id: str = Field(description="UUID задачи Celery")
    status: str = Field(description="PENDING | STARTED | SUCCESS | FAILURE")
    result: str | None = Field(default=None, description="Сгенерированный текст")
    inference_time: float | None = Field(default=None, description="Время инференса, сек")
    error: str | None = Field(default=None, description="Описание ошибки при FAILURE")


class GenerateResponse(BaseModel):
    """Ответ при постановке задачи в очередь (202 Accepted)."""

    task_id: str = Field(description="ID задачи для отслеживания статуса")
    message: str = Field(default="Task queued successfully")


class HistoryItem(BaseModel):
    """Одна запись из истории генераций."""

    id: uuid.UUID
    task_id: str
    prompt: str
    result: str | None
    status: str
    max_tokens: int
    creativity: float
    inference_time: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    """Пагинированная история генераций."""

    items: list[HistoryItem]
    total: int
    page: int
    page_size: int


class ComponentHealth(BaseModel):
    """Состояние одного компонента системы."""

    status: str = Field(description="ok | error")
    detail: str | None = None


class HealthResponse(BaseModel):
    """Общее состояние сервиса."""

    status: str = Field(description="ok | degraded | error")
    components: dict[str, ComponentHealth]
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    """Стандартный формат ошибки."""

    error: str
    detail: Any | None = None
    status_code: int
