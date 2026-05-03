import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from backend.routes import assets, groups
from fastapi import FastAPI, Request, Depends
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
from backend.models.asset import Asset, asset_groups
from backend.models.group import Group
from backend.db.session import engine, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from sqlalchemy import create_engine, select, func
from backend.services.scan_queue_manager import scan_queue_manager

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Подавляем излишне подробные логи aiosqlite, чтобы видеть только важные сообщения
logging.getLogger('aiosqlite').setLevel(logging.WARNING)


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
        
        # Создаем таблицу asset_change_logs если её нет
        from backend.db.session import asset_change_logs_table
        asset_change_logs_table.create(bind=sync_engine, checkfirst=True)
        logger.info("✅ Таблица asset_change_logs создана/проверена.")
        
        # Добавляем отсутствующие колонки в существующие таблицы (миграция)
        from sqlalchemy import text, inspect
        inspector = inspect(sync_engine)
        
        # Проверяем наличие колонки username в таблице asset_change_logs
        if "asset_change_logs" in inspector.get_table_names():
            log_columns = [col['name'] for col in inspector.get_columns('asset_change_logs')]
            
            # Добавляем колонку username если её нет
            if 'username' not in log_columns:
                logger.info("🔧 Добавление колонки username в таблицу asset_change_logs...")
                with sync_engine.begin() as conn:
                    if "sqlite" in db_url:
                        conn.execute(text("ALTER TABLE asset_change_logs ADD COLUMN username VARCHAR(100)"))
                    else:
                        conn.execute(text("ALTER TABLE asset_change_logs ADD COLUMN username VARCHAR(100)"))
                logger.info("✅ Колонка username успешно добавлена.")
            
            # Добавляем колонку action если её нет
            if 'action' not in log_columns:
                logger.info("🔧 Добавление колонки action в таблицу asset_change_logs...")
                with sync_engine.begin() as conn:
                    if "sqlite" in db_url:
                        conn.execute(text("ALTER TABLE asset_change_logs ADD COLUMN action VARCHAR(50) NOT NULL DEFAULT 'update'"))
                    else:
                        conn.execute(text("ALTER TABLE asset_change_logs ADD COLUMN action VARCHAR(50) NOT NULL DEFAULT 'update'"))
                logger.info("✅ Колонка action успешно добавлена.")
            
            # Добавляем колонку changed_fields если её нет
            if 'changed_fields' not in log_columns:
                logger.info("🔧 Добавление колонки changed_fields в таблицу asset_change_logs...")
                with sync_engine.begin() as conn:
                    if "sqlite" in db_url:
                        conn.execute(text("ALTER TABLE asset_change_logs ADD COLUMN changed_fields JSON"))
                    else:
                        conn.execute(text("ALTER TABLE asset_change_logs ADD COLUMN changed_fields JSON"))
                logger.info("✅ Колонка changed_fields успешно добавлена.")
        
        # Проверяем наличие колонки last_seen в таблице assets
        if "assets" in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('assets')]
            
            # Добавляем колонку last_seen если её нет
            if 'last_seen' not in columns:
                logger.info("🔧 Добавление колонки last_seen в таблицу assets...")
                with sync_engine.begin() as conn:
                    if "sqlite" in db_url:
                        conn.execute(text("ALTER TABLE assets ADD COLUMN last_seen DATETIME"))
                    else:
                        conn.execute(text("ALTER TABLE assets ADD COLUMN last_seen TIMESTAMP WITH TIME ZONE"))
                logger.info("✅ Колонка last_seen успешно добавлена.")
            
            # Добавляем колонку source если её нет
            if 'source' not in columns:
                logger.info("🔧 Добавление колонки source в таблицу assets...")
                with sync_engine.begin() as conn:
                    if "sqlite" in db_url:
                        conn.execute(text("ALTER TABLE assets ADD COLUMN source VARCHAR(20) DEFAULT 'manual'"))
                    else:
                        conn.execute(text("ALTER TABLE assets ADD COLUMN source VARCHAR(20) DEFAULT 'manual'"))
                logger.info("✅ Колонка source успешно добавлена.")
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
    
    # Запускаем менеджер очереди сканирований
    await scan_queue_manager.start()
    
    yield
    logger.info("🛑 Остановка приложения...")
    
    # Останавливаем менеджер очереди сканирований
    await scan_queue_manager.stop()

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

# Обработчики HTTP ошибок 404 и 500 для рендеринга страниц
@app.exception_handler(404)
async def http_404_handler(request: Request, exc):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

@app.exception_handler(500)
async def http_500_handler(request: Request, exc):
    return templates.TemplateResponse("500.html", {"request": request}, status_code=500)

# Middleware для логирования запросов к сканированиям (для отладки)
@app.middleware("http")
async def log_scan_requests_middleware(request: Request, call_next):
    """Логирование всех POST-запросов к /api/scans/ для отладки."""
    if request.url.path.startswith('/api/scans/') and request.method == 'POST':
        logger.info("=" * 80)
        logger.info(f"📥 ВХОДЯЩИЙ ЗАПРОС: {request.method} {request.url.path}")
        logger.info(f"   Client: {request.client.host}:{request.client.port if request.client.port else 'unknown'}")
        logger.info(f"   Headers: {dict(request.headers)}")
        try:
            body = await request.body()
            logger.info(f"   Body: {body.decode('utf-8')}")
        except Exception as e:
            logger.warning(f"   Не удалось прочитать тело запроса: {e}")
        logger.info("=" * 80)
    response = await call_next(request)
    return response

# Настройка путей к статике и шаблонам
BASE_DIR = Path(__file__).resolve().parent.parent  # /workspace
BACKEND_DIR = BASE_DIR / "backend"
STATIC_DIR = BASE_DIR / "frontend" / "static"
TEMPLATES_DIR = BACKEND_DIR / "templates"

# Custom JSON encoder for Jinja2 templates to handle datetime objects
import json
from datetime import datetime, date
from decimal import Decimal

class CustomJSONEncoder(json.JSONEncoder):
    """Кастомный JSON энкодер для обработки datetime и других специальных типов."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, '__dict__'):
            # Для SQLAlchemy моделей и других объектов
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):
                    try:
                        # Рекурсивно обрабатываем вложенные объекты
                        json.dumps(value, cls=CustomJSONEncoder)
                        result[key] = value
                    except (TypeError, ValueError):
                        # Пропускаем поля, которые нельзя сериализовать
                        pass
            return result
        return super().default(obj)

# Монтирование статических файлов (CSS, JS, изображения)
# Используем check_dir=False чтобы избежать ошибки при старте если директория пуста
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), check_dir=False), name="static")

# Настройка Jinja2 шаблонов с кастомным фильтром tojson
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.policies['json.dumps_function'] = lambda obj, **kw: json.dumps(obj, cls=CustomJSONEncoder, **kw)

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
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/dashboard")
async def dashboard(request: Request):
    """Страница Dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/scans")
async def scans_page(request: Request):
    """Страница сканирований."""
    return templates.TemplateResponse("scans.html", {"request": request})

@app.get("/scan-history")
async def scan_history_page(request: Request):
    """Страница истории сканирований."""
    return templates.TemplateResponse("scan_history.html", {"request": request})

@app.get("/assets/{asset_id}")
async def asset_detail(request: Request, asset_id: int, db: AsyncSession = Depends(get_db)):
    """Страница детали актива."""
    from backend.services.asset_service import AssetService
    service = AssetService(db)
    
    # Явно загружаем актив со всеми связями
    asset = await service.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")
    
    # Загружаем историю изменений
    change_logs = await service.get_change_logs(asset_id, limit=50)
    
    return templates.TemplateResponse("asset_detail.html", {
        "request": request, 
        "asset": asset,
        "change_logs": change_logs
    })


@app.get("/asset/view/{asset_id}")
async def asset_view_page(request: Request, asset_id: int, db: AsyncSession = Depends(get_db)):
    """Страница просмотра актива (альтернативный маршрут для совместимости)."""
    from backend.services.asset_service import AssetService
    service = AssetService(db)
    asset = await service.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")
    
    return templates.TemplateResponse("asset_detail.html", {
        "request": request,
        "asset": asset
    })

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

@app.get("/ui-kit")
async def ui_kit(request: Request):
    """Страница UI Kit для демонстрации компонентов."""
    return templates.TemplateResponse("ui_kit.html", {"request": request})

@app.get("/settings")
async def settings_page(request: Request):
    """Страница настроек приложения."""
    return templates.TemplateResponse("settings.html", {"request": request})