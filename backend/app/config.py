from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://mluser:mlpassword@postgres:5432/mldb"
    DATABASE_SYNC_URL: str = "postgresql+psycopg2://mluser:mlpassword@postgres:5432/mldb"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # Ollama — локальный LLM без зависимости от внешней сети
    OLLAMA_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "tinyllama"

    # Управление ресурсами — ограничения инференса
    MAX_NEW_TOKENS: int = 256
    INFERENCE_TIMEOUT: int = 120
    MAX_BATCH_SIZE: int = 4

    # App
    APP_ENV: str = "production"
    LOG_LEVEL: str = "INFO"


settings = Settings()
