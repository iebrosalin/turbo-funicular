from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import logging

from app.core.config import settings
from app.core.exceptions import (
    validation_exception_handler,
    sqlalchemy_exception_handler,
    generic_exception_handler,
)
from app.db.session import engine, Base
from app.routes import assets, groups, scans

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Создание приложения
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене ограничить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Регистрация обработчиков исключений
app.add_exception_handler(Exception, generic_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
# Примечание: RequestValidationError обрабатывается автоматически в FastAPI

# Подключение роутеров
app.include_router(assets.router)
app.include_router(groups.router)
app.include_router(scans.router)

# Статические файлы
static_path = Path(__file__).parent.parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Проверка состояния сервиса."""
    return {"status": "healthy", "version": settings.VERSION}


# Главная страница
@app.get("/")
async def root():
    """Отдаем главную страницу."""
    index_path = Path(__file__).parent.parent.parent / "templates" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "API работает. Используйте /docs для документации."}


# Событие при запуске
@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске."""
    logger.info("Запуск приложения...")
    # Создаем таблицы если их нет (для разработки, в проде используем миграции)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("База данных инициализирована.")


# Событие при остановке
@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при остановке."""
    logger.info("Остановка приложения...")
    await engine.dispose()
