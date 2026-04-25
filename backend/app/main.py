import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import AppException, global_exception_handler
from app.core.test_integrity import verify_test_integrity, SecurityError
from app.db.session import engine
from app.routes import assets, groups, scans

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
    Выполняет критическую проверку целостности тестов перед стартом.
    """
    logger.info("🔍 Проверка целостности тестов...")
    try:
        verify_test_integrity()
        logger.info("✅ Проверка целостности тестов пройдена.")
    except FileNotFoundError:
        logger.warning("⚠️  Файл эталонного хеша не найден. Пропуск проверки (первый запуск).")
    except SecurityError as e:
        logger.error(f"🚫 БЛОКИРОВКА ЗАПУСКА: {e}")
        # В режиме разработки выбрасываем ошибку, останавливая сервер
        if settings.ENVIRONMENT == "development":
            raise RuntimeError(f"Security Check Failed: {e}") from e
        else:
            # В продакшене тоже лучше остановиться, если тесты изменены
            logger.critical("Запуск невозможен: нарушена целостность тестов.")
            raise RuntimeError("Startup blocked: Test integrity compromised") from e
    except Exception as e:
        logger.error(f"Неожиданная ошибка при проверке тестов: {e}")

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
app.add_exception_handler(Exception, global_exception_handler)

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