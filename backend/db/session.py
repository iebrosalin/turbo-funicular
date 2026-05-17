from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from backend.core.config import settings
from backend.db.base import Base  # Импортируем Base из base.py
import os
import logging

logger = logging.getLogger(__name__)

# Определяем базовую директорию и путь к файлу БД
is_sqlite = "sqlite" in settings.DATABASE_URL

logger.info(f"🔍 DATABASE_URL: {settings.DATABASE_URL}")
logger.info(f"🔍 is_sqlite: {is_sqlite}")

# Для SQLite: создаём файл БД если не существует перед созданием engine
if is_sqlite:
    # Извлекаем путь к файлу из DATABASE_URL (sqlite+aiosqlite:////workspace/data/app.db)
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite://", "")
    # Убираем ведущий слэш для абсолютного пути
    if db_path.startswith('/'):
        db_path = db_path[1:]
    
    logger.info(f"🔍 Извлечённый путь к БД: {db_path}")
    logger.info(f"🔍 Путь абсолютный: {os.path.isabs(db_path)}")
    logger.info(f"🔍 Директория БД: {os.path.dirname(db_path)}")
    logger.info(f"🔍 Директория существует: {os.path.exists(os.path.dirname(db_path)) if os.path.dirname(db_path) else 'N/A'}")
    logger.info(f"🔍 Файл БД существует: {os.path.exists(db_path)}")
    logger.info(f"🔍 Права на запись в директорию: {os.access(os.path.dirname(db_path), os.W_OK) if os.path.dirname(db_path) else 'N/A'}")
    
    # Создаём директорию если не существует
    db_dir = os.path.dirname(db_path)
    if db_dir:
        logger.info(f"🔍 Попытка создания директории: {db_dir}")
        try:
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"✅ Директория создана/существует: {db_dir}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания директории {db_dir}: {e}")
            raise
    
    # Создаём пустой файл БД если не существует
    if not os.path.exists(db_path):
        logger.info(f"🔍 Файл БД не существует, пытаемся создать: {db_path}")
        try:
            open(db_path, 'a').close()
            logger.info(f"✅ Файл БД создан: {db_path}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания файла БД {db_path}: {e}")
            raise
    else:
        logger.info(f"✅ Файл БД уже существует: {db_path}")
    
    # Проверяем права доступа к файлу
    logger.info(f"🔍 Файл БД теперь существует: {os.path.exists(db_path)}")
    logger.info(f"🔍 Права на чтение файла: {os.access(db_path, os.R_OK)}")
    logger.info(f"🔍 Права на запись в файл: {os.access(db_path, os.W_OK)}")

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
    autoflush=True,  # Включаем autoflush для автоматической отправки изменений перед запросами
)

# Синхронная сессия для использования в сканерах
sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", "")
sync_engine = create_engine(
    sync_db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in sync_db_url else {},
)
sync_session_maker = sessionmaker(bind=sync_engine, autocommit=False, expire_on_commit=False)
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
