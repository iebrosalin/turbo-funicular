"""
RedCheck Integration API Routes
Интеграция с системой RedCheck для управления уязвимостями и соответствием
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from pydantic import BaseModel, Field
import httpx

from backend.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/redcheck", tags=["RedCheck Integration"])

# ============================================================================
# Модели данных
# ============================================================================

class RedCheckSettings(BaseModel):
    """Настройки подключения к RedCheck API"""
    api_url: str = Field(..., description="URL RedCheck API")
    api_version: str = Field(default="v1.0", description="Версия API")
    username: Optional[str] = Field(None, description="Имя пользователя")
    password: Optional[str] = Field(None, description="Пароль")
    auth_type: str = Field(default="basic", description="Тип аутентификации")
    timeout: int = Field(default=30, description="Таймаут запросов в секундах")
    verify_ssl: bool = Field(default=True, description="Проверка SSL сертификата")


class RedCheckTokenResponse(BaseModel):
    """Ответ с токеном аутентификации"""
    token: str
    expires_at: Optional[datetime] = None


class ConnectionTestResult(BaseModel):
    """Результат проверки подключения"""
    success: bool
    message: str
    token_received: bool = False
    error_details: Optional[str] = None


class RedCheckEndpoint(BaseModel):
    """Информация об эндпоинте API"""
    path: str
    method: str
    summary: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []


# ============================================================================
# Вспомогательные функции
# ============================================================================

async def get_redcheck_token(settings: RedCheckSettings, db: Optional[AsyncSession] = None, settings_id: Optional[int] = None, force_refresh: bool = False) -> Optional[str]:
    """
    Получение JWT токена для доступа к RedCheck API
    
    Формат данных для настройки интеграции:
    {
        "api_url": "https://10.250.95.14:444",  // URL сервера RedCheck
        "api_version": "v1.0",                   // Версия API (обычно v1.0)
        "username": "your_username",             // Имя пользователя
        "password": "your_password",             // Пароль
        "auth_type": "basic",                    // Тип аутентификации (basic)
        "timeout": 30,                           // Таймаут запросов в секундах
        "verify_ssl": false                      // Проверка SSL сертификата (false для самоподписанных)
    }
    
    Args:
        force_refresh: Если True, игнорируем сохранённый токен и запрашиваем новый
    """
    if settings.auth_type != "basic" or not settings.username or not settings.password:
        return None
    
    # Проверяем, есть ли сохранённый токен в БД и не истёк ли он (только если не force_refresh)
    if db and settings_id and not force_refresh:
        from sqlalchemy import select
        from backend.models.integration_settings import IntegrationSettings
        from datetime import datetime, timedelta
        
        query = select(IntegrationSettings).where(IntegrationSettings.id == settings_id)
        result = await db.execute(query)
        settings_record = result.scalar_one_or_none()
        
        if settings_record and settings_record.token:
            # Проверяем, не истёк ли токен
            if settings_record.token_expires_at:
                # Добавляем буфер 5 минут для безопасного обновления
                effective_expiry = settings_record.token_expires_at - timedelta(minutes=5)
                if datetime.utcnow() < effective_expiry:
                    logger.info(f"[DEBUG] Используем сохранённый токен (истекает: {settings_record.token_expires_at})")
                    return settings_record.token
                else:
                    logger.info(f"[DEBUG] Токен истёк или истекает скоро (истекает: {settings_record.token_expires_at}), запрашиваем новый")
            else:
                # Если нет времени истечения, считаем токен действующим
                logger.info(f"[DEBUG] Используем сохранённый токен (время истечения не установлено)")
                return settings_record.token
    
    # Если force_refresh=True, пропускаем проверку БД и сразу запрашиваем новый токен
    if force_refresh:
        logger.info("[DEBUG] Принудительное обновление токена (force_refresh=True)")
    
    token_url = f"{settings.api_url}/api/{settings.api_version}/accounts/token"
    
    logger.info(f"[DEBUG] Получение токена RedCheck:")
    logger.info(f"  URL: {token_url}")
    logger.info(f"  Username: {settings.username}")
    logger.info(f"  Password: {'*' * len(settings.password)}")
    logger.info(f"  Timeout: {settings.timeout}s")
    logger.info(f"  Verify SSL: {settings.verify_ssl}")
    
    async with httpx.AsyncClient(
        timeout=settings.timeout,
        verify=settings.verify_ssl,
        follow_redirects=True  # Разрешить редиректы для корректной работы с API
    ) as client:
        try:
            # RedCheck API требует поля userName и userPassword (camelCase)
            request_payload = {
                "userName": settings.username,
                "userPassword": settings.password
            }
            logger.info(f"  Request payload: {request_payload}")
            
            response = await client.post(
                token_url,
                json=request_payload,
                headers={"Content-Type": "application/json"}
            )
            
            logger.info(f"  Response status: {response.status_code}")
            logger.info(f"  Response headers: {dict(response.headers)}")
            logger.info(f"  Response body: {response.text[:500] if response.text else 'empty'}")
            
            # RedCheck API может возвращать токен как plain text (status 201) или как JSON (status 200)
            if response.status_code in [200, 201]:
                # Пробуем распарсить как JSON, если не получится - берём как текст
                token = None
                try:
                    data = response.json()
                    logger.info(f"  Response JSON: {data}")
                    # Токен может быть в разных полях в зависимости от версии API
                    token = data.get("token") or data.get("access_token") or data.get("result", {}).get("token")
                    if token:
                        logger.info(f"  ✅ Токен получен успешно из JSON (длина: {len(token)})")
                    else:
                        logger.warning(f"  ⚠️ Токен не найден в JSON ответе. Доступные ключи: {list(data.keys())}")
                except Exception:
                    # Если не JSON, берём тело ответа как есть (plain text токен)
                    token = response.text.strip()
                    if token:
                        logger.info(f"  ✅ Токен получен успешно как plain text (длина: {len(token)})")
                    else:
                        logger.warning(f"  ⚠️ Пустой ответ")
                
                # Сохраняем токен в БД, если предоставлена сессия
                if token and db and settings_id:
                    from sqlalchemy import select
                    from backend.models.integration_settings import IntegrationSettings
                    from datetime import datetime, timedelta
                    
                    query = select(IntegrationSettings).where(IntegrationSettings.id == settings_id)
                    result = await db.execute(query)
                    settings_record = result.scalar_one_or_none()
                    
                    if settings_record:
                        settings_record.token = token
                        # Устанавливаем время истечения токена (по умолчанию 1 час)
                        # Сервер RedCheck может иметь своё время истечения, поэтому используем меньший срок
                        settings_record.token_expires_at = datetime.utcnow() + timedelta(hours=1)
                        await db.commit()
                        await db.refresh(settings_record)
                        logger.info(f"[DEBUG] Токен сохранён в БД для интеграции id={settings_id}, длина токена: {len(token)}, истекает: {settings_record.token_expires_at}")
                
                return token
            elif response.status_code == 302:
                location = response.headers.get("Location", "unknown")
                logger.error(f"  ❌ Ошибка получения токена: 302 - Перенаправление на {location}")
                logger.error(f"  Возможная причина: Неверный URL API или требуется другая аутентификация")
                return None
            elif response.status_code == 400:
                logger.error(f"  ❌ Ошибка получения токена: 400 - Bad Request")
                logger.error(f"  Возможная причина: Неверный формат запроса или учётных данных")
                logger.error(f"  Ответ сервера: {response.text}")
                return None
            elif response.status_code == 401:
                logger.error(f"  ❌ Ошибка получения токена: 401 - Unauthorized")
                logger.error(f"  Возможная причина: Неверное имя пользователя или пароль, либо сервер требует Negotiate-аутентификацию")
                logger.error(f"  Заголовок WWW-Authenticate: {response.headers.get('www-authenticate', 'не указан')}")
                return None
            else:
                logger.error(f"  ❌ Ошибка получения токена: {response.status_code} - {response.text}")
                return None
                
        except httpx.RequestError as e:
            logger.error(f"  ❌ Ошибка запроса к RedCheck API: {type(e).__name__}: {e}")
            return None
    
    return None


async def redcheck_request(
    method: str,
    endpoint: str,
    settings: RedCheckSettings,
    token: Optional[str] = None,
    json_data: Optional[Dict] = None,
    params: Optional[Dict] = None,
    db: Optional[AsyncSession] = None,
    settings_id: Optional[int] = None
) -> Optional[Dict]:
    """
    Выполнение запроса к RedCheck API с автоматическим обновлением токена при 401 ошибке
    """
    url = f"{settings.api_url}/api/{settings.api_version}/{endpoint.lstrip('/')}"
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers["Content-Type"] = "application/json"
    
    logger.info(f"[DEBUG] Запрос к RedCheck API:")
    logger.info(f"  Method: {method.upper()}")
    logger.info(f"  URL: {url}")
    logger.info(f"  Headers: {headers}")
    if json_data:
        logger.info(f"  JSON data: {json_data}")
    if params:
        logger.info(f"  Params: {params}")
    
    async with httpx.AsyncClient(
        timeout=settings.timeout,
        verify=settings.verify_ssl,
        headers=headers,
        follow_redirects=True  # Разрешить редиректы для корректной работы с API
    ) as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, json=json_data, params=params)
            elif method.upper() == "PUT":
                response = await client.put(url, json=json_data, params=params)
            elif method.upper() == "DELETE":
                response = await client.delete(url, params=params)
            else:
                raise ValueError(f"Неподдерживаемый метод: {method}")
            
            logger.info(f"  Response status: {response.status_code}")
            logger.info(f"  Response headers: {dict(response.headers)}")
            logger.info(f"  Response body: {response.text[:500] if response.text else 'empty'}")
            
            # Если получили 401 и есть возможность обновить токен
            if response.status_code == 401 and db and settings_id:
                logger.info(f"[DEBUG] Получена 401 ошибка, пытаемся обновить токен...")
                # При 401 ошибке всегда запрашиваем новый токен, игнорируя сохранённый
                new_token = await get_redcheck_token(settings, db=db, settings_id=settings_id, force_refresh=True)
                
                if new_token:
                    logger.info(f"[DEBUG] Токен обновлён, повторяем запрос...")
                    # Повторяем запрос с новым токеном
                    headers["Authorization"] = f"Bearer {new_token}"
                    
                    async with httpx.AsyncClient(
                        timeout=settings.timeout,
                        verify=settings.verify_ssl,
                        headers=headers,
                        follow_redirects=True
                    ) as retry_client:
                        if method.upper() == "GET":
                            response = await retry_client.get(url, params=params)
                        elif method.upper() == "POST":
                            response = await retry_client.post(url, json=json_data, params=params)
                        elif method.upper() == "PUT":
                            response = await retry_client.put(url, json=json_data, params=params)
                        elif method.upper() == "DELETE":
                            response = await retry_client.delete(url, params=params)
                        
                        logger.info(f"  Retry response status: {response.status_code}")
                        logger.info(f"  Retry response headers: {dict(response.headers)}")
                        logger.info(f"  Retry response body: {response.text[:500] if response.text else 'empty'}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"  ✅ Успешный ответ: {result}")
                return result
            elif response.status_code == 302:
                location = response.headers.get("Location", "unknown")
                logger.error(f"  ❌ Ошибка RedCheck API ({method} {endpoint}): 302 - Перенаправление на {location}")
                logger.error(f"  Возможная причина: Требуется аутентификация или неверный URL")
                return None
            elif response.status_code == 401:
                logger.error(f"  ❌ Ошибка RedCheck API ({method} {endpoint}): 401 - Неавторизовано")
                logger.error(f"  Возможная причина: Неверный или истёкший токен")
                logger.error(f"  Заголовок WWW-Authenticate: {response.headers.get('www-authenticate', 'не указан')}")
                return None
            elif response.status_code == 403:
                logger.error(f"  ❌ Ошибка RedCheck API ({method} {endpoint}): 403 - Доступ запрещён")
                logger.error(f"  Возможная причина: Недостаточно прав доступа")
                return None
            elif response.status_code == 404:
                logger.error(f"  ❌ Ошибка RedCheck API ({method} {endpoint}): 404 - Ресурс не найден")
                logger.error(f"  Возможная причина: Неверный эндпоинт или ресурс не существует")
                return None
            else:
                logger.error(f"  ❌ Ошибка RedCheck API ({method} {endpoint}): {response.status_code} - {response.text}")
                return None
                
        except httpx.RequestError as e:
            logger.error(f"  ❌ Ошибка запроса к RedCheck API: {type(e).__name__}: {e}")
            return None
    
    return None


def parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Парсинг даты из строки в различных форматах"""
    if not date_str:
        return None
    
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def map_scan_type(type_str: Optional[str]) -> str:
    """Маппинг типов сканирований RedCheck"""
    if not type_str:
        return "unknown"
    
    type_lower = type_str.lower()
    
    mapping = {
        "vulnerability": "vulnerability_scan",
        "compliance": "compliance_check",
        "inventory": "inventory",
        "discovery": "discovery",
        "audit": "audit",
        "pentest": "pentest",
        "bruteforce": "bruteforce",
        "docker": "docker_scan",
        "hostdiscovery": "host_discovery"
    }
    
    for key, value in mapping.items():
        if key in type_lower:
            return value
    
    return "unknown"


def map_scan_status(status_str: Optional[str]) -> str:
    """Маппинг статусов сканирований"""
    if not status_str:
        return "unknown"
    
    status_lower = status_str.lower()
    
    mapping = {
        "pending": "pending",
        "running": "running",
        "inprogress": "running",
        "completed": "completed",
        "success": "completed",
        "failed": "failed",
        "error": "failed",
        "cancelled": "cancelled",
        "stopped": "cancelled"
    }
    
    return mapping.get(status_lower, "unknown")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/endpoints")
async def get_endpoints():
    """
    Получить список всех доступных эндпоинтов RedCheck API
    """
    try:
        with open("backend/redcheck_api.json", "r", encoding="utf-8") as f:
            spec = __import__("json").load(f)
        
        endpoints = []
        paths = spec.get("paths", {})
        
        for path, methods in paths.items():
            for method, details in methods.items():
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": details.get("summary", ""),
                    "description": details.get("description", ""),
                    "tags": details.get("tags", [])
                })
        
        return {"endpoints": endpoints, "total": len(endpoints)}
        
    except Exception as e:
        logger.error(f"Ошибка чтения спецификации API: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения спецификации: {str(e)}")


@router.post("/test-connection", response_model=ConnectionTestResult)
async def test_connection(settings: RedCheckSettings, db: AsyncSession = Depends(get_db)):
    """
    Проверка подключения к RedCheck API
    При проверке подключения всегда запрашиваем новый токен, игнорируя сохранённый
    """
    logger.info(f"Проверка подключения к RedCheck: {settings.api_url}")
    
    # При проверке подключения всегда запрашиваем новый токен
    token = None
    token_received = False
    
    from sqlalchemy import select
    from backend.models.integration_settings import IntegrationSettings
    
    query = select(IntegrationSettings).where(IntegrationSettings.name == "redcheck")
    result = await db.execute(query)
    existing_settings = result.scalar_one_or_none()
    
    settings_id = None
    if existing_settings:
        settings_id = existing_settings.id
        # Обновляем существующие настройки переданными значениями
        existing_settings.api_url = settings.api_url
        existing_settings.api_version = settings.api_version
        existing_settings.username = settings.username
        existing_settings.password = settings.password
        existing_settings.auth_type = settings.auth_type
        existing_settings.timeout = settings.timeout
        existing_settings.verify_ssl = settings.verify_ssl
    else:
        # Создаем новую запись для сохранения токена
        new_settings = IntegrationSettings(
            name="redcheck",
            api_url=settings.api_url,
            api_version=settings.api_version,
            username=settings.username,
            password=settings.password,
            auth_type=settings.auth_type,
            timeout=settings.timeout,
            verify_ssl=settings.verify_ssl,
            enabled=False  # Пока не включаем, только тестируем
        )
        db.add(new_settings)
        await db.flush()  # Получаем ID но не делаем коммит
        settings_id = new_settings.id
    
    # При тестировании подключения всегда запрашиваем новый токен (force_refresh=True)
    if settings.auth_type == "basic" and settings.username and settings.password:
        token = await get_redcheck_token(settings, db=db, settings_id=settings_id, force_refresh=True)
        if token:
            token_received = True
            logger.info("✅ Токен успешно получен и сохранён в БД")
            # Делаем коммит только если токен получен успешно
            await db.commit()
        else:
            await db.rollback()
            return ConnectionTestResult(
                success=False,
                message="Не удалось получить токен аутентификации",
                token_received=False,
                error_details="Проверьте учётные данные"
            )
    
    # Пробуем выполнить тестовый запрос к API
    test_endpoint = "info"  # Эндпоинт получения информации о системе
    
    result = await redcheck_request(
        method="GET",
        endpoint=test_endpoint,
        settings=settings,
        token=token,
        db=db,
        settings_id=settings_id if 'settings_id' in locals() else None
    )
    
    if result is not None:
        return ConnectionTestResult(
            success=True,
            message="Подключение успешно установлено",
            token_received=token_received
        )
    else:
        return ConnectionTestResult(
            success=False,
            message="Не удалось подключиться к RedCheck API",
            token_received=token_received,
            error_details="Проверьте URL и параметры подключения"
        )


@router.post("/settings")
async def save_settings(settings: RedCheckSettings, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Сохранение настроек подключения к RedCheck
    """
    from sqlalchemy import select, update
    from backend.models.integration_settings import IntegrationSettings
    
    logger.info(f"Сохранение настроек RedCheck: {settings.api_url}")
    
    # Проверяем существующие настройки
    query = select(IntegrationSettings).where(IntegrationSettings.name == "redcheck")
    result = await db.execute(query)
    existing_settings = result.scalar_one_or_none()
    
    if existing_settings:
        # Обновляем существующие настройки
        existing_settings.api_url = settings.api_url
        existing_settings.api_version = settings.api_version
        existing_settings.username = settings.username
        existing_settings.password = settings.password
        existing_settings.auth_type = settings.auth_type
        existing_settings.timeout = settings.timeout
        existing_settings.verify_ssl = settings.verify_ssl
        existing_settings.enabled = True
        logger.info(f"[DEBUG] Настройки RedCheck обновлены в БД (id={existing_settings.id})")
        saved_settings = existing_settings
    else:
        # Создаем новые настройки
        new_settings = IntegrationSettings(
            name="redcheck",
            api_url=settings.api_url,
            api_version=settings.api_version,
            username=settings.username,
            password=settings.password,
            auth_type=settings.auth_type,
            timeout=settings.timeout,
            verify_ssl=settings.verify_ssl,
            enabled=True
        )
        db.add(new_settings)
        logger.info(f"[DEBUG] Настройки RedCheck созданы в БД")
        saved_settings = new_settings
    
    await db.commit()
    await db.refresh(saved_settings)
    logger.info(f"[DEBUG] Настройки RedCheck закоммичены в БД")
    
    return {
        "success": True,
        "message": "Настройки успешно сохранены",
        "settings": {
            "api_url": saved_settings.api_url or "",
            "api_version": saved_settings.api_version or "v1.0",
            "username": saved_settings.username or "",
            "auth_type": saved_settings.auth_type or "basic",
            "timeout": saved_settings.timeout or 30,
            "verify_ssl": saved_settings.verify_ssl if saved_settings.verify_ssl is not None else True,
            "enabled": saved_settings.enabled if saved_settings.enabled is not None else False
        }
    }


@router.get("/settings")
async def get_current_settings(db: AsyncSession = Depends(get_db)):
    """
    Получение текущих настроек подключения
    """
    from sqlalchemy import select
    from backend.models.integration_settings import IntegrationSettings
    
    query = select(IntegrationSettings).where(IntegrationSettings.name == "redcheck")
    result = await db.execute(query)
    settings_record = result.scalar_one_or_none()
    
    if settings_record:
        logger.info(f"[DEBUG] Настройки RedCheck найдены в БД (id={settings_record.id})")
        return {
            "api_url": settings_record.api_url or "",
            "api_version": settings_record.api_version or "v1.0",
            "username": settings_record.username or "",
            "password": settings_record.password or "",
            "auth_type": settings_record.auth_type or "basic",
            "timeout": settings_record.timeout or 30,
            "verify_ssl": settings_record.verify_ssl if settings_record.verify_ssl is not None else True,
            "enabled": settings_record.enabled if settings_record.enabled is not None else False,
            "token_saved": bool(settings_record.token),
            "token_expires_at": settings_record.token_expires_at.isoformat() if settings_record.token_expires_at else None
        }
    else:
        logger.info(f"[DEBUG] Настройки RedCheck не найдены в БД")
        return {
            "api_url": "",
            "api_version": "v1.0",
            "auth_type": "basic",
            "timeout": 30,
            "verify_ssl": True,
            "enabled": False
        }


@router.get("/info")
async def get_integration_info(db: AsyncSession = Depends(get_db)):
    """
    Общая информация об интеграции с RedCheck
    """
    from sqlalchemy import select, func
    from backend.models.integration_settings import IntegrationSettings
    
    # Получаем настройки
    query = select(IntegrationSettings).where(IntegrationSettings.name == "redcheck")
    result = await db.execute(query)
    settings_record = result.scalar_one_or_none()
    
    enabled = False
    last_sync = None
    token_saved = False
    token_expires_at = None
    if settings_record:
        enabled = settings_record.enabled if settings_record.enabled is not None else False
        # В будущем можно добавить поле last_sync в модель IntegrationSettings
        token_saved = bool(settings_record.token)
        token_expires_at = settings_record.token_expires_at.isoformat() if settings_record.token_expires_at else None
    
    return {
        "enabled": enabled,
        "last_sync": last_sync,
        "total_scans": 0,  # В будущем можно получить из БД
        "total_hosts": 0,  # В будущем можно получить из БД
        "status": "configured" if enabled else "not_configured",
        "api_url": settings_record.api_url if settings_record else None,
        "token_saved": token_saved,
        "token_expires_at": token_expires_at
    }


# ============================================================================
# Scans API
# ============================================================================

@router.get("/scans")
async def get_scans(
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    scan_type: Optional[str] = None,
    profile: Optional[str] = None,
    target: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список сканирований RedCheck
    """
    # TODO: Реализовать получение из БД с фильтрацией
    from backend.models.scan import RedCheckScan
    
    query = select(RedCheckScan)
    
    # Применяем фильтры
    if status:
        query = query.where(RedCheckScan.status == status)
    if scan_type:
        query = query.where(RedCheckScan.scan_type == scan_type)
    if profile:
        query = query.where(RedCheckScan.profile_name.contains(profile))
    if target:
        query = query.where(RedCheckScan.target_name.contains(target))
    if search:
        query = query.where(
            (RedCheckScan.name.contains(search)) |
            (RedCheckScan.description.contains(search))
        )
    
    # Пагинация
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    result = await db.execute(query)
    scans = result.scalars().all()
    
    # Получаем общее количество
    count_query = select(func.count()).select_from(RedCheckScan)
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    return {
        "scans": [scan.to_dict() for scan in scans],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


@router.post("/scans/sync")
async def sync_scans(db: AsyncSession = Depends(get_db)):
    """
    Синхронизация сканирований из RedCheck API (все страницы)
    """
    # Получаем настройки из БД
    from sqlalchemy import select
    from backend.models.integration_settings import IntegrationSettings
    
    query = select(IntegrationSettings).where(IntegrationSettings.name == "redcheck")
    result = await db.execute(query)
    settings_record = result.scalar_one_or_none()
    
    if not settings_record or not settings_record.api_url:
        raise HTTPException(status_code=400, detail="Настройки RedCheck не найдены")
    
    # Создаём объект настроек из записи БД
    settings = RedCheckSettings(
        api_url=settings_record.api_url,
        api_version=settings_record.api_version or "v1.0",
        username=settings_record.username,
        password=settings_record.password,
        auth_type=settings_record.auth_type or "basic",
        timeout=settings_record.timeout or 30,
        verify_ssl=settings_record.verify_ssl if settings_record.verify_ssl is not None else True
    )
    
    # Получаем токен (с передачей db и settings_id для сохранения)
    token = await get_redcheck_token(settings, db=db, settings_id=settings_record.id)
    if not token:
        raise HTTPException(status_code=401, detail="Не удалось получить токен")
    
    # Получаем все сканирования из RedCheck (проходим по всем страницам)
    all_jobs = []
    page = 1
    per_page = 100
    
    while True:
        jobs_data = await redcheck_request(
            method="GET",
            endpoint="jobs",
            settings=settings,
            token=token,
            params={"page": page, "per_page": per_page},
            db=db,
            settings_id=settings_record.id
        )
        
        if not jobs_data:
            raise HTTPException(status_code=500, detail="Ошибка получения данных из RedCheck")
        
        # Извлекаем задания из разных возможных форматов ответа
        jobs = jobs_data.get("items", []) or jobs_data.get("result", {}).get("items", []) or []
        all_jobs.extend(jobs)
        
        logger.info(f"[DEBUG] Страница {page}: получено {len(jobs)} сканирований")
        
        # Если получили меньше чем per_page или пустой список - это последняя страница
        if len(jobs) < per_page:
            break
        
        page += 1
    
    logger.info(f"[DEBUG] Всего получено {len(all_jobs)} сканирований из RedCheck")
    
    # Обрабатываем данные
    added_count = 0
    updated_count = 0
    
    from backend.models.scan import RedCheckScan
    
    for job in all_jobs:
        job_id = job.get("id")
        if not job_id:
            continue
        
        # Проверяем существует ли запись
        existing = await db.execute(
            select(RedCheckScan).where(RedCheckScan.external_id == str(job_id))
        )
        scan = existing.scalar_one_or_none()
        
        # Парсим поля с учётом различных форматов ответа RedCheck
        vuln_info = job.get("vulnerabilities", {}) or job.get("vulns", {}) or {}
        scan_data = {
            "external_id": str(job_id),
            "name": job.get("name", "") or job.get("title", "Unknown"),
            "description": job.get("description", "") or job.get("desc", ""),
            "scan_type": map_scan_type(job.get("type") or job.get("scan_type")),
            "status": map_scan_status(job.get("status") or job.get("state")),
            "profile_name": job.get("profile_name", "") or job.get("profile", "") or job.get("policy_name", ""),
            "target_name": job.get("target_name", "") or job.get("target", "") or job.get("host_name", ""),
            "progress": job.get("progress", 0) or job.get("percent", 0) or 0,
            "created_at": parse_datetime(job.get("created_at") or job.get("createdAt") or job.get("create_time")),
            "started_at": parse_datetime(job.get("started_at") or job.get("startedAt") or job.get("start_time")),
            "completed_at": parse_datetime(job.get("completed_at") or job.get("completedAt") or job.get("end_time") or job.get("finish_time")),
            "vulnerabilities_critical": vuln_info.get("critical", 0) or vuln_info.get("Critical", 0) or 0,
            "vulnerabilities_high": vuln_info.get("high", 0) or vuln_info.get("High", 0) or 0,
            "vulnerabilities_medium": vuln_info.get("medium", 0) or vuln_info.get("Medium", 0) or 0,
            "vulnerabilities_low": vuln_info.get("low", 0) or vuln_info.get("Low", 0) or 0,
            "has_report": job.get("report_id") is not None or job.get("reportId") is not None or job.get("has_report", False),
            "report_id": job.get("report_id") or job.get("reportId")
        }
        
        if scan:
            # Обновляем существующую запись
            for key, value in scan_data.items():
                setattr(scan, key, value)
            updated_count += 1
        else:
            # Создаём новую запись
            scan = RedCheckScan(**scan_data)
            db.add(scan)
            added_count += 1
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Синхронизация завершена",
        "added": added_count,
        "updated": updated_count,
        "total": added_count + updated_count,
        "pages_processed": page
    }


@router.get("/scans/columns")
async def get_scan_columns():
    """
    Получить доступные колонки для таблицы сканирований
    """
    columns = [
        {"key": "id", "label": "ID", "default": True},
        {"key": "name", "label": "Название", "default": True},
        {"key": "scan_type", "label": "Тип", "default": True},
        {"key": "status", "label": "Статус", "default": True},
        {"key": "progress", "label": "Прогресс", "default": True},
        {"key": "profile_name", "label": "Профиль", "default": True},
        {"key": "target_name", "label": "Цель", "default": True},
        {"key": "created_at", "label": "Создано", "default": True},
        {"key": "started_at", "label": "Начато", "default": False},
        {"key": "completed_at", "label": "Завершено", "default": False},
        {"key": "vulnerabilities_critical", "label": "Критические", "default": True},
        {"key": "vulnerabilities_high", "label": "Высокие", "default": False},
        {"key": "vulnerabilities_medium", "label": "Средние", "default": False},
        {"key": "vulnerabilities_low", "label": "Низкие", "default": False},
        {"key": "has_report", "label": "Отчёт", "default": True},
        {"key": "description", "label": "Описание", "default": False},
        {"key": "external_id", "label": "Внешний ID", "default": False},
        {"key": "actions", "label": "Действия", "default": True}
    ]
    return {"columns": columns}


# ============================================================================
# Hosts API
# ============================================================================

@router.get("/hosts")
async def get_hosts(
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    status: Optional[str] = None,
    os_type: Optional[str] = None,
    group: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список хостов (активов) из RedCheck
    
    Если page и per_page не указаны - возвращаются ВСЕ хосты без пагинации.
    """
    from backend.models.asset import RedCheckHost
    
    query = select(RedCheckHost)
    
    # Применяем фильтры
    if status:
        query = query.where(RedCheckHost.status == status)
    if os_type:
        query = query.where(RedCheckHost.os_type.contains(os_type))
    if group:
        query = query.where(RedCheckHost.groups.contains(group))
    if search:
        query = query.where(
            (RedCheckHost.hostname.contains(search)) |
            (RedCheckHost.ip_address.contains(search))
        )
    
    # Пагинация только если указаны параметры
    if page is not None and per_page is not None:
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        # Получаем общее количество для пагинации
        count_query = select(func.count()).select_from(RedCheckHost)
        # Применяем те же фильтры к count запросу
        if status:
            count_query = count_query.where(RedCheckHost.status == status)
        if os_type:
            count_query = count_query.where(RedCheckHost.os_type.contains(os_type))
        if group:
            count_query = count_query.where(RedCheckHost.groups.contains(group))
        if search:
            count_query = count_query.where(
                (RedCheckHost.hostname.contains(search)) |
                (RedCheckHost.ip_address.contains(search))
            )
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        result = await db.execute(query)
        hosts = result.scalars().all()
        
        return {
            "hosts": [host.to_dict() for host in hosts],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page
        }
    else:
        # Возвращаем все хосты без пагинации
        result = await db.execute(query)
        hosts = result.scalars().all()
        
        return {
            "hosts": [host.to_dict() for host in hosts],
            "total": len(hosts),
            "page": 1,
            "per_page": len(hosts),
            "pages": 1
        }


@router.post("/hosts/sync")
async def sync_hosts(db: AsyncSession = Depends(get_db)):
    """
    Синхронизация хостов из RedCheck API (все страницы)
    """
    # Получаем настройки из БД
    from sqlalchemy import select
    from backend.models.integration_settings import IntegrationSettings
    
    query = select(IntegrationSettings).where(IntegrationSettings.name == "redcheck")
    result = await db.execute(query)
    settings_record = result.scalar_one_or_none()
    
    if not settings_record or not settings_record.api_url:
        raise HTTPException(status_code=400, detail="Настройки RedCheck не найдены")
    
    # Создаём объект настроек из записи БД
    settings = RedCheckSettings(
        api_url=settings_record.api_url,
        api_version=settings_record.api_version or "v1.0",
        username=settings_record.username,
        password=settings_record.password,
        auth_type=settings_record.auth_type or "basic",
        timeout=settings_record.timeout or 30,
        verify_ssl=settings_record.verify_ssl if settings_record.verify_ssl is not None else True
    )
    
    # Получаем токен (с передачей db и settings_id для сохранения)
    token = await get_redcheck_token(settings, db=db, settings_id=settings_record.id)
    if not token:
        raise HTTPException(status_code=401, detail="Не удалось получить токен")
    
    # Получаем все хосты из RedCheck (проходим по всем страницам)
    all_hosts = []
    page = 1
    per_page = 100
    
    while True:
        hosts_data = await redcheck_request(
            method="GET",
            endpoint="targets/hosts",
            settings=settings,
            token=token,
            params={"page": page, "per_page": per_page},
            db=db,
            settings_id=settings_record.id
        )
        
        if not hosts_data:
            raise HTTPException(status_code=500, detail="Ошибка получения данных из RedCheck")
        
        # Извлекаем хосты из разных возможных форматов ответа
        hosts = hosts_data.get("items", []) or hosts_data.get("result", {}).get("items", []) or []
        all_hosts.extend(hosts)
        
        logger.info(f"[DEBUG] Страница {page}: получено {len(hosts)} хостов")
        
        # Если получили меньше чем per_page или пустой список - это последняя страница
        if len(hosts) < per_page:
            break
        
        page += 1
    
    logger.info(f"[DEBUG] Всего получено {len(all_hosts)} хостов из RedCheck")
    
    # Обрабатываем данные
    added_count = 0
    updated_count = 0
    
    from backend.models.asset import RedCheckHost
    
    for host in all_hosts:
        host_id = host.get("id")
        if not host_id:
            continue
        
        # Проверяем существует ли запись
        existing = await db.execute(
            select(RedCheckHost).where(RedCheckHost.external_id == str(host_id))
        )
        db_host = existing.scalar_one_or_none()
        
        # Парсим поля с учётом различных форматов ответа RedCheck
        host_data = {
            "external_id": str(host_id),
            "hostname": host.get("hostname", "") or host.get("name", ""),
            "ip_address": host.get("ip", "") or host.get("ip_address", "") or host.get("address", ""),
            "os_type": host.get("os", "") or host.get("os_type", "") or host.get("platform", ""),
            "os_version": host.get("os_version", "") or host.get("osver", "") or "",
            "status": "active" if host.get("is_active", True) else "inactive",
            "groups": ",".join(host.get("groups", []) or []) if isinstance(host.get("groups"), list) else str(host.get("groups", "")),
            "mac_address": host.get("mac", "") or host.get("mac_address", "") or "",
            "last_seen": parse_datetime(host.get("last_seen") or host.get("lastSeen") or host.get("last_update")),
            "vulnerabilities_count": host.get("vulnerabilities_count", 0) or host.get("vuln_count", 0) or 0,
            "critical_vulnerabilities": host.get("critical_vulnerabilities", 0) or host.get("critical", 0) or 0,
            "high_vulnerabilities": host.get("high_vulnerabilities", 0) or host.get("high", 0) or 0,
            "open_ports_count": len(host.get("open_ports", []) or host.get("ports", []) or []),
            "compliance_score": host.get("compliance_score", 0) or host.get("compliance", 0) or 0
        }
        
        # Если нет открытых портов, помечаем как неактивный
        if host_data["open_ports_count"] == 0:
            host_data["status"] = "inactive"
            host_data["is_active"] = False
        
        if db_host:
            # Обновляем существующую запись
            for key, value in host_data.items():
                setattr(db_host, key, value)
            updated_count += 1
        else:
            # Создаём новую запись
            db_host = RedCheckHost(**host_data)
            db.add(db_host)
            added_count += 1
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"Синхронизация хостов завершена",
        "added": added_count,
        "updated": updated_count,
        "total": added_count + updated_count,
        "pages_processed": page
    }


@router.get("/hosts/columns")
async def get_host_columns():
    """
    Получить доступные колонки для таблицы хостов
    """
    columns = [
        {"key": "id", "label": "ID", "default": True},
        {"key": "hostname", "label": "Имя хоста", "default": True},
        {"key": "ip_address", "label": "IP адрес", "default": True},
        {"key": "os_type", "label": "ОС", "default": True},
        {"key": "os_version", "label": "Версия ОС", "default": False},
        {"key": "status", "label": "Статус", "default": True},
        {"key": "groups", "label": "Группы", "default": True},
        {"key": "mac_address", "label": "MAC адрес", "default": False},
        {"key": "last_seen", "label": "Последний раз", "default": False},
        {"key": "vulnerabilities_count", "label": "Уязвимости", "default": True},
        {"key": "critical_vulnerabilities", "label": "Критические", "default": True},
        {"key": "compliance_score", "label": "Соответствие", "default": False},
        {"key": "external_id", "label": "Внешний ID", "default": False},
        {"key": "actions", "label": "Действия", "default": True}
    ]
    return {"columns": columns}


@router.get("/hosts/{host_id}")
async def get_host(host_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить информацию о хосте по ID
    """
    from backend.models.asset import RedCheckHost
    
    result = await db.execute(
        select(RedCheckHost).where(RedCheckHost.id == host_id)
    )
    host = result.scalar_one_or_none()
    
    if not host:
        raise HTTPException(status_code=404, detail="Хост не найден")
    
    return host.to_dict()


@router.delete("/hosts/{host_id}")
async def delete_host(host_id: int, db: AsyncSession = Depends(get_db)):
    """
    Удаление хоста из локальной базы
    """
    from backend.models.asset import RedCheckHost
    
    await db.execute(
        delete(RedCheckHost).where(RedCheckHost.id == host_id)
    )
    await db.commit()
    
    return {"success": True, "message": "Хост удалён"}


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить информацию о сканировании по ID
    """
    from backend.models.scan import RedCheckScan
    
    result = await db.execute(
        select(RedCheckScan).where(RedCheckScan.id == scan_id)
    )
    scan = result.scalar_one_or_none()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Сканирование не найдено")
    
    return scan.to_dict()


@router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: int, db: AsyncSession = Depends(get_db)):
    """
    Удаление сканирования из локальной базы
    """
    from backend.models.scan import RedCheckScan
    
    await db.execute(
        delete(RedCheckScan).where(RedCheckScan.id == scan_id)
    )
    await db.commit()
    
    return {"success": True, "message": "Сканирование удалено"}
