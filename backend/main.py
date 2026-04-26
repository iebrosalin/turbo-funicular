import logging
from contextlib import asynccontextmanager

from backend.routes import assets, groups
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.core.exceptions import (
    AppException, 
    global_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    generic_exception_handler
)
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from backend.db.session import engine
from backend.routes import scans

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    """
    # Инициализация соединения с БД (если требуется)
    try:
        async with engine.begin() as conn:
            # Здесь можно добавить логику проверки подключения
            pass
        logger.info("✅ Подключение к базе данных установлено.")
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        # Не блокируем старт, если БД еще не готова (retry logic может быть в драйвере)
    
    logger.info("🚀 Приложение успешно запущено.")
    yield
    logger.info("🛑 Остановка приложения...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Network Asset Manager API with Test Integrity Protection",
    lifespan=lifespan
)

# Настройка CORS (необходимо для работы фронтенда на отдельном порту/домене)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене заменить на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Регистрация глобальных обработчиков исключений
app.add_exception_handler(AppException, global_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Подключение маршрутов (Roouters)
app.include_router(assets.router, prefix="/api/assets", tags=["Assets"])
app.include_router(groups.router, prefix="/api/groups", tags=["Groups"])
app.include_router(scans.router, prefix="/api/scans", tags=["Scans"])

@app.get("/health")
async def health_check():
    """Эндпоинт для проверки статуса сервиса (Health Check)."""
    return {"status": "healthy", "environment": settings.ENVIRONMENT}

@app.get("/")
async def root():
    """Корневой эндпоинт."""
    return {
        "message": "Welcome to Network Asset Manager API",
        "documentation": "/docs",
        "health": "/health"
    }