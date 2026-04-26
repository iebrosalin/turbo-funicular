from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker
from sqlalchemy import create_engine
from backend.core.config import settings

# Определяем параметры для SQLite
is_sqlite = "sqlite" in settings.DATABASE_URL

# Движок базы данных
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Логирование SQL запросов в режиме отладки
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
    echo=settings.DEBUG,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in sync_db_url else {},
)
sync_session_maker = sessionmaker(bind=sync_engine)
db = scoped_session(sync_session_maker)


class Base(DeclarativeBase):
    """Базовый класс для моделей."""
    pass


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
