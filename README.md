# ML Text Generation Service

Сервис генерации и суммаризации текста на базе **Ollama** (локальный LLM, без внешних API).
Модель по умолчанию: `tinyllama` (~637 MB, работает на CPU).

## Архитектурная схема

```
                        ┌────────────────────────────────���───────────┐
                        │               frontend_net                   │
[Пользователь :80] ──→ [Nginx] ──→ [Streamlit :8501]               │
                          │                                            │
                          └──────────→ [FastAPI :8000] x2 ─────────→ │
                                            │         backend_net      │
                                 ┌──────────┼──────────┐              │
                             [PostgreSQL] [Redis]   [Ollama :11434]   │
                                 │           │          │              │
                                 └── [Celery Worker x2] ──────────────┘

Мониторинг: [FastAPI /metrics] → [Prometheus] → [Grafana :3000]
```

## Стек технологий

| Компонент       | Технология                              |
|-----------------|-----------------------------------------|
| Backend         | Python 3.11, FastAPI, SQLAlchemy async  |
| LLM             | Ollama (`tinyllama`, работает локально) |
| Task Queue      | Celery + Redis                          |
| Database        | PostgreSQL 16 + Alembic                 |
| UI              | Streamlit + Plotly                      |
| Reverse Proxy   | Nginx 1.25                              |
| Monitoring      | Prometheus + Grafana                    |
| Packaging       | Docker Compose, uv                      |

## Быстрый старт

### 1. Настройте переменные окружения

```bash
cp .env.example .env
# При необходимости измените OLLAMA_MODEL (например, на phi3:mini)
```

### 2. Запустите сервис

```bash
docker compose up --build -d
```

При первом запуске Docker автоматически:
- Соберёт образы (~2–3 мин)
- Скачает модель `tinyllama` (~637 MB)
- Применит миграции БД

Готовность можно отслеживать:
```bash
docker compose logs -f ollama_setup   # прогресс загрузки модели
docker compose ps                     # статус всех сервисов
```

### 3. Откройте в браузере

| Сервис      | URL                       |
|-------------|---------------------------|
| UI          | http://localhost          |
| API Docs    | http://localhost/api/docs |
| Grafana     | http://localhost:3000     |

Grafana: логин `admin` / пароль `admin`.

## Примеры cURL-запросов

### Health Check

```bash
curl http://localhost/api/health
```

```json
{
  "status": "ok",
  "components": {
    "postgres":  {"status": "ok"},
    "redis":     {"status": "ok"},
    "ml_model":  {"status": "ok", "detail": "ollama/tinyllama"}
  },
  "version": "1.0.0"
}
```

### Поставить задачу в очередь

```bash
curl -X POST http://localhost/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Artificial intelligence is transforming how businesses operate. Companies are investing billions in AI research and development, hoping to automate repetitive tasks and gain competitive advantages.",
    "max_tokens": 128,
    "creativity": 0.5
  }'
```

```json
{"task_id": "9a97fb3c-...", "message": "Task queued successfully"}
```

### Проверить статус задачи (polling)

```bash
curl http://localhost/api/tasks/9a97fb3c-...
```

```json
{
  "task_id": "9a97fb3c-...",
  "status": "SUCCESS",
  "result": "AI is changing how businesses operate...",
  "inference_time": 2.65,
  "error": null
}
```

### История генераций

```bash
curl "http://localhost/api/history?page=1&page_size=10"
```

### WebSocket статус задачи

```bash
# npm install -g wscat
wscat -c ws://localhost/api/ws/tasks/9a97fb3c-...
```

## Смена модели

Любая модель из [ollama.com/library](https://ollama.com/library) — меняется без пересборки образов:

```bash
# 1. Изменить в .env
OLLAMA_MODEL=phi3:mini

# 2. Скачать новую модель
docker exec ai_in_web-ollama-1 ollama pull phi3:mini

# 3. Перезапустить воркеры
docker compose restart api celery_worker
```

Рекомендуемые модели для CPU:

| Модель       | Размер | Качество |
|--------------|--------|----------|
| `tinyllama`  | 637 MB | базовое  |
| `phi3:mini`  | 2.3 GB | хорошее  |
| `gemma:2b`   | 1.4 GB | среднее  |

## Остановка

```bash
docker compose down        # остановить контейнеры
docker compose down -v     # + удалить все данные и веса модели
```

## Переменные окружения

| Переменная          | Описание                        | По умолчанию              |
|---------------------|---------------------------------|---------------------------|
| `OLLAMA_MODEL`      | Название модели Ollama          | `tinyllama`               |
| `OLLAMA_URL`        | URL Ollama сервиса              | `http://ollama:11434`     |
| `MAX_NEW_TOKENS`    | Максимум токенов в ответе       | `256`                     |
| `INFERENCE_TIMEOUT` | Таймаут инференса (сек)         | `120`                     |
| `POSTGRES_*`        | Настройки PostgreSQL            | см. `.env.example`        |
