from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
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


class Base(DeclarativeBase):
    """Базовый класс для моделей."""
    pass


# Импортируем все модели чтобы они зарегистрировались в Base.metadata
from backend.models import asset, group, service, scan, log

# Инициализируем таблицу логов изменений после регистрации всех моделей
from backend.db.base import init_change_log_table
init_change_log_table()


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
