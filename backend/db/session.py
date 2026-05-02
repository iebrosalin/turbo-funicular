from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from backend.core.config import settings
from backend.db.base import Base  # Импортируем Base из base.py

# Определяем параметры для SQLite
is_sqlite = "sqlite" in settings.DATABASE_URL

# Движок базы данных
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Отключено логирование SQL запросов
    pool_pre_ping=True,   # Проверка соединения перед использованием
    connect_args={"check_same_thread": False} if is_sqlite else {},  # Для SQLite
)

# Фабрика сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Синхронная сессия для использования в сканерах
sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", "")
sync_engine = create_engine(
    sync_db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in sync_db_url else {},
)
sync_session_maker = sessionmaker(bind=sync_engine)
db = scoped_session(sync_session_maker)


def get_sync_session():
    """Контекстный менеджер для получения синхронной сессии БД."""
    return sync_session_maker()


# Импортируем все модели чтобы они зарегистрировались в Base.metadata
from backend.models import asset, group, service, scan, log

# Определяем таблицу asset_change_logs для Core API (без foreign key для упрощения)
from sqlalchemy import Table, MetaData, Column, Integer, String, DateTime, JSON
from datetime import datetime
metadata = MetaData()

asset_change_logs_table = Table(
    'asset_change_logs',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('asset_id', Integer, nullable=False),  # Без FK для упрощения
    Column('username', String(255)),
    Column('action', String(50), nullable=False),  # create, update, delete
    Column('changed_fields', JSON),
    Column('created_at', DateTime, default=datetime.now)
)

# Экспортируем таблицу для использования в других модулях
import backend.db.base
backend.db.base.asset_change_logs_table = asset_change_logs_table


async def get_db():
    """Dependency для получения сессии БД."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
