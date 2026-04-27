import logging
from contextlib import asynccontextmanager
from pathlib import Path

from backend.routes import assets, groups
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
from backend.db.base import Base  # Импорт для доступа ко всем моделям
from sqlalchemy import create_engine

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
    # Проверка и инициализация базы данных при старте
    try:
        # Преобразуем async URL в sync для создания таблиц
        db_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", "")
        sync_engine = create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
        )
        
        # Создаем все таблицы, если их нет
        Base.metadata.create_all(bind=sync_engine)
        logger.info("✅ База данных проверена и инициализирована.")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        raise
    
    # Проверка подключения
    try:
        async with engine.begin() as conn:
            pass
        logger.info("✅ Подключение к базе данных установлено.")
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        raise
    
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

# Настройка путей к статике и шаблонам
BASE_DIR = Path(__file__).resolve().parent.parent  # /workspace
BACKEND_DIR = BASE_DIR / "backend"
STATIC_DIR = BASE_DIR / "frontend" / "static"
TEMPLATES_DIR = BACKEND_DIR / "templates"

# Монтирование статических файлов (CSS, JS, изображения)
# Используем check_dir=False чтобы избежать ошибки при старте если директория пуста
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), check_dir=False), name="static")

# Настройка Jinja2 шаблонов
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Подключение маршрутов (Roouters)
app.include_router(assets.router, prefix="/api/assets", tags=["Assets"])
app.include_router(groups.router, prefix="/api/groups", tags=["Groups"])
app.include_router(scans.router, prefix="/api/scans", tags=["Scans"])

@app.get("/health")
async def health_check():
    """Эндпоинт для проверки статуса сервиса (Health Check)."""
    return {"status": "healthy", "environment": settings.ENVIRONMENT}

@app.get("/")
async def root(request: Request):
    """Корневой эндпоинт - рендеринг главной страницы."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard")
async def dashboard(request: Request):
    """Страница Dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/scans")
async def scans_page(request: Request):
    """Страница сканирований."""
    return templates.TemplateResponse("scans.html", {"request": request})

@app.get("/assets/{asset_id}")
async def asset_detail(request: Request, asset_id: int):
    """Страница детали актива."""
    return templates.TemplateResponse("asset_detail.html", {"request": request, "asset_id": asset_id})

@app.get("/assets/{asset_id}/history")
async def asset_history(request: Request, asset_id: int):
    """Страница истории актива."""
    return templates.TemplateResponse("asset_history.html", {"request": request, "asset_id": asset_id})

@app.get("/utilities")
async def utilities(request: Request):
    """Страница утилит."""
    return templates.TemplateResponse("utilities.html", {"request": request})

@app.get("/taxonomy")
async def asset_taxonomy(request: Request):
    """Страница таксономии активов."""
    return templates.TemplateResponse("asset_taxonomy.html", {"request": request})