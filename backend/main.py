import logging
import os
import sys
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

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
    http_exception_handler,
    generic_exception_handler
)
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
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

# ============================================================================
# Расширенная настройка логирования
# ============================================================================

# Создаем директорию для логов
LOG_DIR = Path("/workspace/logs")
LOG_DIR.mkdir(exist_ok=True)

# Формат детального логирования
DETAILED_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(funcName)s | %(message)s"

# Настраиваем корневой logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Очищаем существующие handlers
root_logger.handlers.clear()

# Handler для вывода в консоль (INFO уровень и выше)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
root_logger.addHandler(console_handler)

# Handler для записи в файл (DEBUG уровень и выше) с ротацией
file_handler = RotatingFileHandler(
    LOG_DIR / "app.log",
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
root_logger.addHandler(file_handler)

# Handler для ошибок (ERROR и CRITICAL) в отдельный файл
error_handler = RotatingFileHandler(
    LOG_DIR / "error.log",
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
root_logger.addHandler(error_handler)

logger = logging.getLogger(__name__)
logger.info("🔧 Система логирования инициализирована")
logger.info(f"📁 Логи записываются в: {LOG_DIR}")

# Подавляем излишне подробные логи aiosqlite, чтобы видеть только важные сообщения
logging.getLogger('aiosqlite').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


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
        
        # Создаем таблицу asset_change_logs если её нет (используем определение из session.py)
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
                    conn.execute(text("ALTER TABLE asset_change_logs ADD COLUMN username VARCHAR(255)"))
                logger.info("✅ Колонка username успешно добавлена.")
            
            # Добавляем колонку action если её нет
            if 'action' not in log_columns:
                logger.info("🔧 Добавление колонки action в таблицу asset_change_logs...")
                with sync_engine.begin() as conn:
                    conn.execute(text("ALTER TABLE asset_change_logs ADD COLUMN action VARCHAR(50) NOT NULL DEFAULT 'update'"))
                logger.info("✅ Колонка action успешно добавлена.")
            
            # Добавляем колонку changed_fields если её нет
            if 'changed_fields' not in log_columns:
                logger.info("🔧 Добавление колонки changed_fields в таблицу asset_change_logs...")
                with sync_engine.begin() as conn:
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
        logger.error(f"🔍 DATABASE_URL: {settings.DATABASE_URL}")
        logger.error(f"🔍 Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"🔍 Полный traceback:\n{traceback.format_exc()}")
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
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Обработчики HTTP ошибок 404 и 500 для рендеринга страниц
@app.exception_handler(404)
async def http_404_handler(request: Request, exc):
    return templates.TemplateResponse(request, "404.html", status_code=404)

@app.exception_handler(500)
async def http_500_handler(request: Request, exc: Exception):
    """Обработчик HTTP 500 ошибок с логированием."""
    logger.error("=" * 80)
    logger.error(f"🚨 HTTP 500 Error | Status: 500")
    logger.error(f"   URL: {request.method} {request.url}")
    logger.error(f"   Client: {request.client.host if request.client else 'unknown'}")
    logger.error(f"   Exception Type: {type(exc).__name__}")
    logger.error(f"   Message: {str(exc)}")
    logger.error(f"   Full Traceback:\n{traceback.format_exc()}")
    logger.error("=" * 80)
    return templates.TemplateResponse(request, "500.html", status_code=500)

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

def tojson_filter(obj, **kwargs):
    """Кастомный фильтр tojson для обработки datetime и других специальных типов."""
    return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)

templates.env.filters['tojson'] = tojson_filter

# Подключение маршрутов (Roouters)
app.include_router(assets.router, prefix="/api/assets", tags=["Assets"])
app.include_router(groups.router, prefix="/api/groups", tags=["Groups"])
app.include_router(scans.router, prefix="/api/scans", tags=["Scans"])

# RedCheck Integration Router
try:
    from backend.routes import redcheck
    app.include_router(redcheck.router, prefix="/api", tags=["RedCheck"])
    logger.info("✅ RedCheck integration router подключён")
except ImportError as e:
    logger.warning(f"⚠️ RedCheck integration router не подключён: {e}")

# Projects Router
try:
    from backend.routes import projects
    app.include_router(projects.router, tags=["Projects"])
    logger.info("✅ Projects router подключён")
except ImportError as e:
    logger.warning(f"⚠️ Projects router не подключён: {e}")

@app.get("/health")
async def health_check():
    """Эндпоинт для проверки статуса сервиса (Health Check)."""
    return {"status": "healthy", "environment": settings.ENVIRONMENT}

@app.get("/")
async def root(request: Request):
    """Корневой эндпоинт - рендеринг главной страницы."""
    return templates.TemplateResponse(request, "components/dashboard.html")

@app.get("/dashboard")
async def dashboard(request: Request):
    """Страница Dashboard."""
    return templates.TemplateResponse(request, "components/dashboard.html")

@app.get("/scans")
async def scans_page(request: Request):
    """Страница сканирований."""
    return templates.TemplateResponse(request, "scans/scans.html")

@app.get("/scan-history")
async def scan_history_page(request: Request):
    """Страница истории сканирований."""
    return templates.TemplateResponse(request, "scans/scan_history.html")

@app.get("/import-nmap")
async def import_nmap_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Страница импорта Nmap XML."""
    from backend.services.group_service import GroupService
    group_service = GroupService(db)
    groups = await group_service.get_all()
    
    return templates.TemplateResponse(request, "scans/import_nmap.html", {
        "groups": groups
    })

@app.get("/assets/{asset_id}")
async def asset_detail(request: Request, asset_id: int, db: AsyncSession = Depends(get_db)):
    """Страница детали актива."""
    from backend.services.asset_service import AssetService
    service = AssetService(db)
    
    # Явно загружаем актив со всеми связями
    asset = await service.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")
    
    # Загружаем историю изменений (без ограничений)
    change_logs = await service.get_change_logs(asset_id)
    
    return templates.TemplateResponse(request, "assets/asset_detail.html", {
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
    
    return templates.TemplateResponse(request, "assets/asset_detail.html", {
        "asset": asset
    })

@app.get("/assets/{asset_id}/history")
async def asset_history(request: Request, asset_id: int):
    """Страница истории актива."""
    return templates.TemplateResponse(request, "assets/asset_history.html", {"asset_id": asset_id})

@app.get("/utilities")
async def utilities(request: Request):
    """Страница утилит."""
    return templates.TemplateResponse(request, "scans/utilities.html")

@app.get("/taxonomy")
async def asset_taxonomy(request: Request):
    """Страница таксономии активов."""
    return templates.TemplateResponse(request, "assets/asset_taxonomy.html")

@app.get("/ui-kit")
async def ui_kit(request: Request):
    """Страница UI Kit для демонстрации компонентов."""
    return templates.TemplateResponse(request, "components/ui_kit.html")

@app.get("/settings")
async def settings_page(request: Request):
    """Страница настроек приложения."""
    return templates.TemplateResponse(request, "components/settings.html")


# ============================================================================
# Projects Pages
# ============================================================================

@app.get("/projects")
async def projects_page(request: Request):
    """Страница управления проектами."""
    return templates.TemplateResponse(request, "projects/projects.html")


@app.get("/projects/{project_id}")
async def project_detail_page(request: Request, project_id: int):
    """Страница деталей проекта."""
    return templates.TemplateResponse(request, "projects/project_detail.html", {
        "project_id": project_id
    })


# ============================================================================
# RedCheck Integration Pages
# ============================================================================

@app.get("/integrations/redcheck")
async def redcheck_integration_page(request: Request):
    """Страница настройки интеграции с RedCheck."""
    return templates.TemplateResponse(request, "redcheck/redcheck_integration.html")

@app.get("/integrations/redcheck/scans")
async def redcheck_scans_page(request: Request):
    """Страница сканирований RedCheck."""
    return templates.TemplateResponse(request, "redcheck/redcheck_scans.html")

@app.get("/integrations/redcheck/hosts")
async def redcheck_hosts_page(request: Request):
    """Страница хостов (активов) RedCheck."""
    return templates.TemplateResponse(request, "redcheck/redcheck_hosts.html")


@app.get("/assets-manager")
async def assets_manager_page(request: Request):
    """Единая страница управления активами и группами."""
    return templates.TemplateResponse(request, "assets/assets_table.html")

# Альтернативные представления активов
@app.get("/assets-cards")
async def assets_cards_page(request: Request):
    """Представление активов в виде карточек."""
    return templates.TemplateResponse(request, "assets/assets_cards.html")

@app.get("/assets-table")
async def assets_table_page(request: Request):
    """Представление активов в виде таблицы."""
    return templates.TemplateResponse(request, "assets/assets_table.html")

@app.get("/groups-manager")
async def groups_manager_page(request: Request):
    """Страница управления группами."""
    return templates.TemplateResponse(request, "groups/groups_manager.html")