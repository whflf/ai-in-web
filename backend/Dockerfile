# Оптимизация сборок — многоэтапная сборка: builder отдельно от runtime
# Кэширование слоёв — зависимости копируются и устанавливаются до копирования кода
# uv менеджер зависимостей — uv вместо pip для быстрой установки пакетов

# ── Этап 1: установка зависимостей ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

# uv менеджер зависимостей — устанавливаем uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Кэширование слоёв — сначала только файлы зависимостей
COPY pyproject.toml .

# uv менеджер зависимостей — устанавливаем в изолированное виртуальное окружение
RUN uv venv /opt/venv && \
    VIRTUAL_ENV=/opt/venv uv pip install --no-cache -r pyproject.toml

# ── Этап 2: runtime образ ──────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Кэширование слоёв — копируем только виртуальное окружение из builder
COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Оптимизация сборок — код копируется последним, изменения не инвалидируют слой зависимостей
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/

EXPOSE 8000

# Graceful Shutdown — uvicorn перехватывает SIGTERM и завершает активные запросы
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]
