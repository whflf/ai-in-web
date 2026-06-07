# Версионирование данных — Alembic env.py для миграций через синхронный psycopg2
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import settings
from app.database import Base
from app.models import GenerationRecord  # noqa: F401 — регистрирует таблицы в metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные всех таблиц для автогенерации миграций
target_metadata = Base.metadata

# Используем sync URL для alembic
config.set_main_option("sqlalchemy.url", settings.DATABASE_SYNC_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
