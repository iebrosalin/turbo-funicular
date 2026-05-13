"""
RedCheck Integration API Routes
Интеграция с системой RedCheck для управления уязвимостями и соответствием
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
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

async def get_redcheck_token(settings: RedCheckSettings) -> Optional[str]:
    """
    Получение JWT токена для доступа к RedCheck API
    """
    if settings.auth_type != "basic" or not settings.username or not settings.password:
        return None
    
    token_url = f"{settings.api_url}/api/{settings.api_version}/accounts/token"
    
    async with httpx.AsyncClient(
        timeout=settings.timeout,
        verify=settings.verify_ssl
    ) as client:
        try:
            response = await client.post(
                token_url,
                json={
                    "username": settings.username,
                    "password": settings.password
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                # Токен может быть в разных полях в зависимости от версии API
                token = data.get("token") or data.get("access_token") or data.get("result", {}).get("token")
                return token
            else:
                logger.error(f"Ошибка получения токена: {response.status_code} - {response.text}")
                return None
                
        except httpx.RequestError as e:
            logger.error(f"Ошибка запроса к RedCheck API: {e}")
            return None
    
    return None


async def redcheck_request(
    method: str,
    endpoint: str,
    settings: RedCheckSettings,
    token: Optional[str] = None,
    json_data: Optional[Dict] = None,
    params: Optional[Dict] = None
) -> Optional[Dict]:
    """
    Выполнение запроса к RedCheck API
    """
    url = f"{settings.api_url}/api/{settings.api_version}/{endpoint.lstrip('/')}"
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers["Content-Type"] = "application/json"
    
    async with httpx.AsyncClient(
        timeout=settings.timeout,
        verify=settings.verify_ssl,
        headers=headers
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
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка RedCheck API ({method} {endpoint}): {response.status_code} - {response.text}")
                return None
                
        except httpx.RequestError as e:
            logger.error(f"Ошибка запроса к RedCheck API: {e}")
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
async def test_connection(settings: RedCheckSettings):
    """
    Проверка подключения к RedCheck API
    """
    logger.info(f"Проверка подключения к RedCheck: {settings.api_url}")
    
    # Сначала пробуем получить токен
    token = None
    token_received = False
    
    if settings.auth_type == "basic" and settings.username and settings.password:
        token = await get_redcheck_token(settings)
        if token:
            token_received = True
            logger.info("✅ Токен успешно получен")
        else:
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
        token=token
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
    # Здесь должна быть логика сохранения в БД или конфиг
    # Для примера просто возвращаем успех
    logger.info(f"Сохранение настроек RedCheck: {settings.api_url}")
    
    # TODO: Реализовать сохранение в базу данных или зашифрованное хранилище
    
    return {
        "success": True,
        "message": "Настройки успешно сохранены",
        "settings": {
            "api_url": settings.api_url,
            "api_version": settings.api_version,
            "auth_type": settings.auth_type,
            "timeout": settings.timeout,
            "verify_ssl": settings.verify_ssl
        }
    }


@router.get("/settings")
async def get_current_settings(db: AsyncSession = Depends(get_db)):
    """
    Получение текущих настроек подключения
    """
    # TODO: Реализовать получение из БД
    # Для примера возвращаем пустые настройки
    return {
        "api_url": "",
        "api_version": "v1.0",
        "auth_type": "basic",
        "timeout": 30,
        "verify_ssl": True
    }


@router.get("/info")
async def get_integration_info(db: AsyncSession = Depends(get_db)):
    """
    Общая информация об интеграции с RedCheck
    """
    # TODO: Реализовать получение статистики из БД
    return {
        "enabled": False,
        "last_sync": None,
        "total_scans": 0,
        "total_hosts": 0,
        "status": "not_configured"
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
    Синхронизация сканирований из RedCheck API
    """
    # TODO: Получить настройки из БД
    # settings = await get_stored_settings(db)
    
    # Для примера используем заглушку
    settings = RedCheckSettings(
        api_url="http://localhost:8080",
        api_version="v1.0",
        username="admin",
        password="password"
    )
    
    # Получаем токен
    token = await get_redcheck_token(settings)
    if not token:
        raise HTTPException(status_code=401, detail="Не удалось получить токен")
    
    # Получаем список задач (jobs) из RedCheck
    jobs_data = await redcheck_request(
        method="GET",
        endpoint="jobs",
        settings=settings,
        token=token,
        params={"per_page": 100}
    )
    
    if not jobs_data:
        raise HTTPException(status_code=500, detail="Ошибка получения данных из RedCheck")
    
    # Обрабатываем данные
    jobs = jobs_data.get("items", []) or jobs_data.get("result", {}).get("items", [])
    
    added_count = 0
    updated_count = 0
    
    from backend.models.scan import RedCheckScan
    
    for job in jobs:
        job_id = job.get("id")
        if not job_id:
            continue
        
        # Проверяем существует ли запись
        existing = await db.execute(
            select(RedCheckScan).where(RedCheckScan.external_id == str(job_id))
        )
        scan = existing.scalar_one_or_none()
        
        scan_data = {
            "external_id": str(job_id),
            "name": job.get("name", "Unknown"),
            "description": job.get("description", ""),
            "scan_type": map_scan_type(job.get("type")),
            "status": map_scan_status(job.get("status")),
            "profile_name": job.get("profile_name", ""),
            "target_name": job.get("target_name", ""),
            "progress": job.get("progress", 0),
            "created_at": parse_datetime(job.get("created_at")),
            "started_at": parse_datetime(job.get("started_at")),
            "completed_at": parse_datetime(job.get("completed_at")),
            "vulnerabilities_critical": job.get("vulnerabilities", {}).get("critical", 0),
            "vulnerabilities_high": job.get("vulnerabilities", {}).get("high", 0),
            "vulnerabilities_medium": job.get("vulnerabilities", {}).get("medium", 0),
            "vulnerabilities_low": job.get("vulnerabilities", {}).get("low", 0),
            "has_report": job.get("report_id") is not None,
            "report_id": job.get("report_id")
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
        "total": added_count + updated_count
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
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    os_type: Optional[str] = None,
    group: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список хостов (активов) из RedCheck
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
    
    # Пагинация
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    result = await db.execute(query)
    hosts = result.scalars().all()
    
    # Получаем общее количество
    from sqlalchemy import func
    count_query = select(func.count()).select_from(RedCheckHost)
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    return {
        "hosts": [host.to_dict() for host in hosts],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


@router.post("/hosts/sync")
async def sync_hosts(db: AsyncSession = Depends(get_db)):
    """
    Синхронизация хостов из RedCheck API
    """
    # TODO: Получить настройки из БД
    settings = RedCheckSettings(
        api_url="http://localhost:8080",
        api_version="v1.0",
        username="admin",
        password="password"
    )
    
    # Получаем токен
    token = await get_redcheck_token(settings)
    if not token:
        raise HTTPException(status_code=401, detail="Не удалось получить токен")
    
    # Получаем список хостов из RedCheck
    hosts_data = await redcheck_request(
        method="GET",
        endpoint="targets/hosts",
        settings=settings,
        token=token,
        params={"per_page": 100}
    )
    
    if not hosts_data:
        raise HTTPException(status_code=500, detail="Ошибка получения данных из RedCheck")
    
    # Обрабатываем данные
    hosts = hosts_data.get("items", []) or hosts_data.get("result", {}).get("items", [])
    
    added_count = 0
    updated_count = 0
    
    from backend.models.asset import RedCheckHost
    
    for host in hosts:
        host_id = host.get("id")
        if not host_id:
            continue
        
        # Проверяем существует ли запись
        existing = await db.execute(
            select(RedCheckHost).where(RedCheckHost.external_id == str(host_id))
        )
        db_host = existing.scalar_one_or_none()
        
        host_data = {
            "external_id": str(host_id),
            "hostname": host.get("hostname", ""),
            "ip_address": host.get("ip", "") or host.get("ip_address", ""),
            "os_type": host.get("os", "") or host.get("os_type", ""),
            "os_version": host.get("os_version", ""),
            "status": "active" if host.get("is_active", True) else "inactive",
            "groups": ",".join(host.get("groups", [])),
            "mac_address": host.get("mac", ""),
            "last_seen": parse_datetime(host.get("last_seen")),
            "vulnerabilities_count": host.get("vulnerabilities_count", 0),
            "critical_vulnerabilities": host.get("critical_vulnerabilities", 0),
            "compliance_score": host.get("compliance_score", 0)
        }
        
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
        "total": added_count + updated_count
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
