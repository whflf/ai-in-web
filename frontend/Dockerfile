# Оптимизация сборок — многоэтапная сборка
# Кэширование слоёв — зависимости отдельно от кода
# uv менеджер зависимостей

FROM python:3.11-slim AS builder

# uv менеджер зависимостей
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Кэширование слоёв — только файл зависимостей
COPY pyproject.toml .

RUN uv venv /opt/venv && \
    VIRTUAL_ENV=/opt/venv uv pip install --no-cache -r pyproject.toml

FROM python:3.11-slim AS runtime

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Оптимизация сборок — код последним
COPY app.py .

EXPOSE 8501

# Graceful Shutdown — Streamlit корректно завершается по SIGTERM
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
