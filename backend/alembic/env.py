from logging.config import fileConfig
import os

from sqlalchemy import pool, create_engine
from sqlalchemy import engine_from_config

from alembic import context

# это объект Alembic Config, который предоставляет доступ к файлу .ini
config = context.config

# Интерпретация конфигурации логирования из файла alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# добавляем MetaData наших моделей для автогенерации миграций
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.db.base import Base
from backend.models.asset import Asset  # noqa
from backend.models.group import Group  # noqa
from backend.models.scan import Scan, ScanJob, ScanResult  # noqa

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск миграций в 'офлайн' режиме."""
    # Получаем URL из переменной окружения или используем значение по умолчанию
    db_url = os.getenv("DATABASE_URL", "sqlite:////app/instance/app.db")
    # Преобразуем async URL в sync для миграций
    db_url = db_url.replace("+aiosqlite", "").replace("+asyncpg", "")
    
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в 'онлайн' режиме."""
    # Получаем URL из переменной окружения или используем значение по умолчанию
    db_url = os.getenv("DATABASE_URL", "sqlite:////app/instance/app.db")
    # Преобразуем async URL в sync для миграций
    db_url = db_url.replace("+aiosqlite", "").replace("+asyncpg", "")
    
    connectable = create_engine(
        db_url,
        poolclass=pool.NullPool,
        echo=False,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
