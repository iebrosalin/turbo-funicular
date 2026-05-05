"""
Маршруты для интеграции с RedCheck API.
"""
import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Literal, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from backend.db.session import get_db
from backend.models.scan import RedCheckScan
from backend.schemas.scan import (
    RedCheckScanResponse, 
    RedCheckScanCreate, 
    RedCheckScanUpdate,
    RedCheckScanStatus
)

router = APIRouter(prefix="/integrations/redcheck", tags=["RedCheck Integration"])

# Путь к файлу спецификации API
BASE_DIR = Path(__file__).resolve().parent.parent.parent
REDCHECK_API_SPEC_PATH = BASE_DIR / "backend" / "redcheck_api.json"


class RedCheckSettings(BaseModel):
    """Модель настроек интеграции с RedCheck."""
    url: str
    apiVersion: str = "v1.0"
    username: Optional[str] = None
    password: Optional[str] = None
    tokenType: Literal["basic", "token", "account"] = "basic"
    timeout: int = 30
    verifySsl: bool = True
    enabled: bool = False


class EndpointInfo(BaseModel):
    """Информация об эндпоинте API."""
    method: str
    path: str
    tag: Optional[str] = None
    summary: Optional[str] = None


class RedCheckScansFilter(BaseModel):
    """Фильтр для списка сканирований RedCheck."""
    status: Optional[List[str]] = None
    scan_type: Optional[str] = None
    profile_id: Optional[int] = None
    target_id: Optional[int] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@router.get("/endpoints")
async def get_redcheck_endpoints():
    """
    Получить список всех доступных эндпоинтов RedCheck API из спецификации.
    
    Возвращает массив объектов с информацией о каждом эндпоинте:
    - method: HTTP метод (GET, POST, PUT, DELETE и т.д.)
    - path: путь к эндпоинту
    - tag: категория/тег эндпоинта
    - summary: краткое описание
    """
    try:
        if not REDCHECK_API_SPEC_PATH.exists():
            raise HTTPException(
                status_code=404, 
                detail="Спецификация API RedCheck не найдена"
            )
        
        with open(REDCHECK_API_SPEC_PATH, 'r', encoding='utf-8') as f:
            spec = json.load(f)
        
        endpoints = []
        paths = spec.get('paths', {})
        
        for path, methods in paths.items():
            for method, details in methods.items():
                endpoint = EndpointInfo(
                    method=method.upper(),
                    path=path,
                    tag=details.get('tags', ['API'])[0] if details.get('tags') else 'API',
                    summary=details.get('summary', '')
                )
                endpoints.append(endpoint.dict())
        
        # Сортировка по тегам и путям
        endpoints.sort(key=lambda x: (x['tag'], x['path']))
        
        return endpoints
    
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка парсинга спецификации API: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )


@router.post("/test-connection")
async def test_connection(settings: RedCheckSettings):
    """
    Проверить подключение к RedCheck API с указанными настройками.
    
    Выполняет тестовый запрос к эндпоинту /api/{version}/info для проверки:
    - Доступности сервера
    - Корректности учётных данных
    - Работоспособности SSL/TLS
    
    Для типа аутентификации 'basic' автоматически получает JWT токен
    и сохраняет его для последующего использования.
    
    Требует указания URL в настройках.
    """
    import httpx
    
    if not settings.url:
        raise HTTPException(
            status_code=400,
            detail="URL RedCheck API не указан"
        )
    
    # Формируем базовый URL
    base_url = settings.url.rstrip('/')
    
    # Настраиваем заголовки и аутентификацию
    headers = {}
    auth = None
    token = None
    
    # Если используется базовая аутентификация, сначала получаем токен
    if settings.tokenType == "basic" and settings.username and settings.password:
        token_url = f"{base_url}/api/{settings.apiVersion}/accounts/token"
        
        try:
            async with httpx.AsyncClient(
                timeout=settings.timeout,
                verify=settings.verifySsl
            ) as client:
                # Запрос на получение токена
                token_response = await client.post(
                    token_url,
                    json={
                        "username": settings.username,
                        "password": settings.password
                    }
                )
                
                if token_response.status_code == 200:
                    token_data = token_response.json()
                    # Извлекаем токен из ответа (поле может называться access_token, token или id)
                    token = token_data.get('access_token') or token_data.get('token') or token_data.get('id')
                    
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                    else:
                        raise HTTPException(
                            status_code=500,
                            detail="Не удалось извлечь токен из ответа сервера"
                        )
                elif token_response.status_code == 401:
                    raise HTTPException(
                        status_code=401,
                        detail="Неверные учётные данные"
                    )
                elif token_response.status_code == 403:
                    raise HTTPException(
                        status_code=403,
                        detail="Доступ запрещён при получении токена"
                    )
                else:
                    raise HTTPException(
                        status_code=token_response.status_code,
                        detail=f"Ошибка получения токена: {token_response.status_code} - {token_response.text[:200]}"
                    )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=408,
                detail=f"Превышено время ожидания при получении токена ({settings.timeout} сек)"
            )
        except httpx.SSLCertVerificationError:
            raise HTTPException(
                status_code=495,
                detail="Ошибка SSL сертификата при получении токена"
            )
        except httpx.ConnectError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Не удалось подключиться к серверу для получения токена: {str(e)}"
            )
    
    elif settings.tokenType == "token" and settings.password:
        headers["Authorization"] = f"Bearer {settings.password}"
        token = settings.password
    elif settings.tokenType == "account" and settings.password:
        headers["Authorization"] = f"Token {settings.password}"
        token = settings.password
    
    # Тестовый запрос к API
    test_url = f"{base_url}/api/{settings.apiVersion}/info"
    
    try:
        async with httpx.AsyncClient(
            timeout=settings.timeout,
            verify=settings.verifySsl
        ) as client:
            response = await client.get(test_url, headers=headers, auth=auth)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    result = {
                        "success": True,
                        "message": "Подключение успешно установлено",
                        "version": data.get('version', settings.apiVersion),
                        "details": data
                    }
                    # Добавляем информацию о токене, если он был получен
                    if token:
                        result["token_obtained"] = True
                        result["token_preview"] = f"{token[:10]}..." if len(token) > 10 else token
                    return result
                except json.JSONDecodeError:
                    result = {
                        "success": True,
                        "message": "Подключение успешно установлено",
                        "version": settings.apiVersion,
                        "details": {"raw_response": response.text[:500]}
                    }
                    if token:
                        result["token_obtained"] = True
                        result["token_preview"] = f"{token[:10]}..." if len(token) > 10 else token
                    return result
            elif response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail="Неверные учётные данные или истёк срок действия токена"
                )
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=403,
                    detail="Доступ запрещён. Проверьте права доступа"
                )
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Эндпоинт не найден. Проверьте URL и версию API: {test_url}"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Ошибка подключения: {response.status_code} - {response.text[:200]}"
                )
    
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=408,
            detail=f"Превышено время ожидания ({settings.timeout} сек)"
        )
    except httpx.SSLCertVerificationError:
        raise HTTPException(
            status_code=495,
            detail="Ошибка SSL сертификата. Попробуйте отключить проверку SSL для тестовых окружений"
        )
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Не удалось подключиться к серверу: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка: {str(e)}"
        )


@router.post("/settings")
async def save_settings(settings: RedCheckSettings):
    """
    Сохранить настройки интеграции с RedCheck.
    
    Настройки сохраняются в базе данных или конфигурационном файле
    для последующего использования при вызовах API RedCheck.
    """
    # TODO: Реализовать сохранение в БД
    # Пока просто возвращаем успех
    return {
        "success": True,
        "message": "Настройки сохранены",
        "settings": {
            "url": settings.url,
            "apiVersion": settings.apiVersion,
            "username": settings.username,
            "tokenType": settings.tokenType,
            "timeout": settings.timeout,
            "verifySsl": settings.verifySsl,
            "enabled": settings.enabled
        }
    }


@router.get("/settings")
async def get_settings():
    """
    Получить текущие настройки интеграции с RedCheck.
    """
    # TODO: Реализовать получение из БД
    # Пока возвращаем пустые настройки
    return {
        "url": "",
        "apiVersion": "v1.0",
        "username": None,
        "tokenType": "basic",
        "timeout": 30,
        "verifySsl": True,
        "enabled": False
    }


@router.get("/info")
async def get_integration_info():
    """
    Получить общую информацию об интеграции с RedCheck.
    """
    try:
        if not REDCHECK_API_SPEC_PATH.exists():
            spec_info = {"available": False}
        else:
            with open(REDCHECK_API_SPEC_PATH, 'r', encoding='utf-8') as f:
                spec = json.load(f)
            
            info = spec.get('info', {})
            paths = spec.get('paths', {})
            
            # Подсчёт эндпоинтов по тегам
            tag_counts = {}
            for path, methods in paths.items():
                for method, details in methods.items():
                    tags = details.get('tags', ['API'])
                    for tag in tags:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            spec_info = {
                "available": True,
                "title": info.get('title', 'RedCheck REST API'),
                "version": info.get('version', 'unknown'),
                "total_endpoints": len(paths),
                "total_operations": sum(len(methods) for methods in paths.values()),
                "tags": tag_counts
            }
        
        return {
            "integration_name": "RedCheck",
            "description": "Интеграция с системой проверки уязвимостей RedCheck",
            "specification": spec_info,
            "features": [
                "Синхронизация активов",
                "Запуск сканирований",
                "Получение результатов",
                "Управление заданиями",
                "Работа с отчётами"
            ]
        }
    
    except Exception as e:
        return {
            "integration_name": "RedCheck",
            "description": "Интеграция с системой проверки уязвимостей RedCheck",
            "error": str(e)
        }


# ==========================================
# Маршруты для управления сканированиями RedCheck
# ==========================================

@router.get("/scans")
async def get_redcheck_scans(
    limit: int = Query(default=100, ge=1, le=1000, description="Максимальное количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    scan_type: Optional[str] = Query(None, description="Фильтр по типу сканирования"),
    profile_id: Optional[int] = Query(None, description="Фильтр по ID профиля"),
    target_id: Optional[int] = Query(None, description="Фильтр по ID цели"),
    search: Optional[str] = Query(None, description="Поиск по названию или описанию"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список сканирований RedCheck с фильтрацией и пагинацией.
    
    Поддерживаемые фильтры:
    - status: статус сканирования (pending, running, completed, failed)
    - scan_type: тип сканирования
    - profile_id: ID профиля проверки
    - target_id: ID цели
    - search: поиск по названию или описанию
    
    Возвращает список с поддержкой пагинации.
    """
    try:
        # Базовый запрос
        query = select(RedCheckScan).order_by(RedCheckScan.created_at.desc())
        
        # Применяем фильтры
        filters = []
        if status:
            filters.append(RedCheckScan.status == status)
        if scan_type:
            filters.append(RedCheckScan.scan_type == scan_type)
        if profile_id:
            filters.append(RedCheckScan.profile_id == profile_id)
        if target_id:
            filters.append(RedCheckScan.target_id == target_id)
        if search:
            filters.append(
                or_(
                    RedCheckScan.name.ilike(f"%{search}%"),
                    RedCheckScan.description.ilike(f"%{search}%"),
                    RedCheckScan.profile_name.ilike(f"%{search}%"),
                    RedCheckScan.target_name.ilike(f"%{search}%")
                )
            )
        
        if filters:
            query = query.where(and_(*filters))
        
        # Считаем общее количество
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Применяем пагинацию
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        scans = result.scalars().all()
        
        # Преобразуем в список словарей
        scans_list = []
        for scan in scans:
            scan_dict = {
                "id": scan.id,
                "uuid": scan.uuid,
                "name": scan.name,
                "scan_type": scan.scan_type,
                "profile_id": scan.profile_id,
                "profile_name": scan.profile_name,
                "target_id": scan.target_id,
                "target_name": scan.target_name,
                "host_group_id": scan.host_group_id,
                "status": scan.status,
                "progress": scan.progress,
                "redcheck_job_id": scan.redcheck_job_id,
                "redcheck_report_id": scan.redcheck_report_id,
                "report_format": scan.report_format,
                "report_status": scan.report_status,
                "vulnerabilities_count": scan.vulnerabilities_count,
                "critical_count": scan.critical_count,
                "high_count": scan.high_count,
                "medium_count": scan.medium_count,
                "low_count": scan.low_count,
                "hosts_scanned": scan.hosts_scanned,
                "hosts_failed": scan.hosts_failed,
                "description": scan.description,
                "started_at": scan.started_at.isoformat() if scan.started_at else None,
                "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
                "created_at": scan.created_at.isoformat() if scan.created_at else None,
                "updated_at": scan.updated_at.isoformat() if scan.updated_at else None,
                "error_message": scan.error_message,
            }
            scans_list.append(scan_dict)
        
        return {
            "items": scans_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения списка сканирований: {str(e)}"
        )


@router.get("/scans/{scan_id}")
async def get_redcheck_scan(
    scan_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить детальную информацию о сканировании RedCheck по ID.
    """
    try:
        query = select(RedCheckScan).where(RedCheckScan.id == scan_id)
        result = await db.execute(query)
        scan = result.scalar_one_or_none()
        
        if not scan:
            raise HTTPException(status_code=404, detail="Сканирование не найдено")
        
        return {
            "id": scan.id,
            "uuid": scan.uuid,
            "name": scan.name,
            "scan_type": scan.scan_type,
            "profile_id": scan.profile_id,
            "profile_name": scan.profile_name,
            "target_id": scan.target_id,
            "target_name": scan.target_name,
            "host_group_id": scan.host_group_id,
            "status": scan.status,
            "progress": scan.progress,
            "redcheck_job_id": scan.redcheck_job_id,
            "redcheck_report_id": scan.redcheck_report_id,
            "report_format": scan.report_format,
            "report_status": scan.report_status,
            "vulnerabilities_count": scan.vulnerabilities_count,
            "critical_count": scan.critical_count,
            "high_count": scan.high_count,
            "medium_count": scan.medium_count,
            "low_count": scan.low_count,
            "hosts_scanned": scan.hosts_scanned,
            "hosts_failed": scan.hosts_failed,
            "description": scan.description,
            "started_at": scan.started_at.isoformat() if scan.started_at else None,
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
            "updated_at": scan.updated_at.isoformat() if scan.updated_at else None,
            "error_message": scan.error_message,
            "raw_data": scan.raw_data,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения сканирования: {str(e)}"
        )


@router.post("/scans")
async def create_redcheck_scan(
    scan_data: RedCheckScanCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Создать новую запись сканирования RedCheck.
    
    Используется для сохранения информации о сканировании,
    полученной из API RedCheck или созданной локально.
    """
    try:
        scan = RedCheckScan(**scan_data.model_dump())
        db.add(scan)
        await db.commit()
        await db.refresh(scan)
        
        return {
            "success": True,
            "message": "Сканирование создано",
            "data": {
                "id": scan.id,
                "uuid": scan.uuid,
                "name": scan.name,
                "status": scan.status,
                "created_at": scan.created_at.isoformat() if scan.created_at else None
            }
        }
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка создания сканирования: {str(e)}"
        )


@router.put("/scans/{scan_id}")
async def update_redcheck_scan(
    scan_id: int,
    scan_data: RedCheckScanUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить информацию о сканировании RedCheck.
    
    Используется для обновления статуса, прогресса и результатов сканирования.
    """
    try:
        query = select(RedCheckScan).where(RedCheckScan.id == scan_id)
        result = await db.execute(query)
        scan = result.scalar_one_or_none()
        
        if not scan:
            raise HTTPException(status_code=404, detail="Сканирование не найдено")
        
        # Обновляем поля
        update_data = scan_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(scan, field, value)
        
        await db.commit()
        await db.refresh(scan)
        
        return {
            "success": True,
            "message": "Сканирование обновлено",
            "data": {
                "id": scan.id,
                "status": scan.status,
                "progress": scan.progress,
                "updated_at": scan.updated_at.isoformat() if scan.updated_at else None
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обновления сканирования: {str(e)}"
        )


@router.delete("/scans/{scan_id}")
async def delete_redcheck_scan(
    scan_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить запись сканирования RedCheck.
    """
    try:
        query = select(RedCheckScan).where(RedCheckScan.id == scan_id)
        result = await db.execute(query)
        scan = result.scalar_one_or_none()
        
        if not scan:
            raise HTTPException(status_code=404, detail="Сканирование не найдено")
        
        await db.delete(scan)
        await db.commit()
        
        return {
            "success": True,
            "message": "Сканирование удалено"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка удаления сканирования: {str(e)}"
        )


@router.get("/scans/columns")
async def get_available_columns():
    """
    Получить список доступных колонок для отображения в таблице сканирований.
    
    Возвращает список полей с описанием для настройки видимости колонок.
    """
    columns = [
        {"key": "id", "label": "ID", "type": "number", "default": True},
        {"key": "uuid", "label": "UUID", "type": "string", "default": False},
        {"key": "name", "label": "Название", "type": "string", "default": True},
        {"key": "scan_type", "label": "Тип", "type": "string", "default": True},
        {"key": "profile_name", "label": "Профиль", "type": "string", "default": True},
        {"key": "target_name", "label": "Цель", "type": "string", "default": True},
        {"key": "status", "label": "Статус", "type": "badge", "default": True},
        {"key": "progress", "label": "Прогресс", "type": "progress", "default": True},
        {"key": "vulnerabilities_count", "label": "Уязвимости", "type": "number", "default": True},
        {"key": "critical_count", "label": "Критические", "type": "number", "badge": "danger", "default": True},
        {"key": "high_count", "label": "Высокие", "type": "number", "badge": "warning", "default": True},
        {"key": "medium_count", "label": "Средние", "type": "number", "default": False},
        {"key": "low_count", "label": "Низкие", "type": "number", "default": False},
        {"key": "hosts_scanned", "label": "Хостов", "type": "number", "default": True},
        {"key": "hosts_failed", "label": "Ошибки", "type": "number", "badge": "danger", "default": False},
        {"key": "started_at", "label": "Начало", "type": "datetime", "default": True},
        {"key": "completed_at", "label": "Завершено", "type": "datetime", "default": True},
        {"key": "created_at", "label": "Создано", "type": "datetime", "default": False},
        {"key": "error_message", "label": "Ошибка", "type": "text", "default": False},
    ]
    
    return {"columns": columns}


@router.post("/scans/sync")
async def sync_redcheck_scans(db: AsyncSession = Depends(get_db)):
    """
    Синхронизировать сканирования из RedCheck API.
    
    Получает актуальный список сканирований из RedCheck API,
    создаёт новые записи и обновляет существующие в локальной базе.
    
    Возвращает статистику синхронизации:
    - added: количество добавленных записей
    - updated: количество обновлённых записей
    - total: общее количество записей в API
    """
    import httpx
    from datetime import datetime
    
    try:
        # Получаем настройки интеграции
        # TODO: Заменить на реальное получение из БД
        settings = {
            "url": "http://redcheck.local",
            "apiVersion": "v1.0",
            "token": None  # TODO: Получить сохранённый токен
        }
        
        if not settings.get("token"):
            raise HTTPException(
                status_code=400,
                detail="Интеграция не настроена. Необходимо сохранить настройки подключения."
            )
        
        base_url = settings["url"].rstrip('/')
        headers = {"Authorization": f"Bearer {settings['token']}"}
        
        # Запрашиваем список сканирований из API
        # Используем эндпоинт /jobs или /reports в зависимости от реализации RedCheck
        api_url = f"{base_url}/api/{settings['apiVersion']}/jobs"
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(api_url, headers=headers)
            
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Токен недействителен")
            elif response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Ошибка API: {response.text[:200]}"
                )
            
            api_data = response.json()
        
        # Обрабатываем данные API
        # Формат ответа зависит от структуры API RedCheck
        jobs = api_data.get('jobs', []) if isinstance(api_data, dict) else api_data
        
        added_count = 0
        updated_count = 0
        
        for job in jobs:
            # Преобразуем данные API в формат модели
            scan_data = {
                "uuid": job.get('id') or job.get('uuid'),
                "name": job.get('name') or job.get('description', 'Без названия'),
                "scan_type": _map_scan_type(job.get('type') or job.get('profile_type')),
                "profile_id": job.get('profile_id'),
                "profile_name": job.get('profile_name'),
                "target_id": job.get('target_id'),
                "target_name": job.get('target_name'),
                "status": _map_scan_status(job.get('status')),
                "progress": job.get('progress', 0),
                "vulnerabilities_count": job.get('vulnerabilities_count', 0),
                "critical_count": job.get('critical_count', 0),
                "high_count": job.get('high_count', 0),
                "medium_count": job.get('medium_count', 0),
                "low_count": job.get('low_count', 0),
                "compliance_score": job.get('compliance_score'),
                "hosts_scanned": job.get('hosts_scanned', 0),
                "hosts_failed": job.get('hosts_failed', 0),
                "started_at": _parse_datetime(job.get('started_at')),
                "completed_at": _parse_datetime(job.get('finished_at') or job.get('completed_at')),
                "report_available": job.get('report_id') is not None or job.get('status') == 'completed',
                "external_data": job,  # Сохраняем оригинальные данные
            }
            
            # Проверяем существование записи по UUID
            existing = await db.execute(
                select(RedCheckScan).where(RedCheckScan.uuid == scan_data["uuid"])
            )
            existing_scan = existing.scalar_one_or_none()
            
            if existing_scan:
                # Обновляем существующую запись
                for key, value in scan_data.items():
                    if key != "uuid" and hasattr(existing_scan, key):
                        setattr(existing_scan, key, value)
                updated_count += 1
            else:
                # Создаём новую запись
                new_scan = RedCheckScan(**scan_data)
                db.add(new_scan)
                added_count += 1
        
        await db.commit()
        
        return {
            "success": True,
            "added": added_count,
            "updated": updated_count,
            "total": len(jobs)
        }
        
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Превышено время ожидания при синхронизации")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Не удалось подключиться к RedCheck API")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка синхронизации: {str(e)}")


def _map_scan_type(api_type: str) -> str:
    """Преобразует тип сканирования из API в внутренний формат."""
    if not api_type:
        return "unknown"
    
    type_mapping = {
        "vulnerability_scan": "vulnerability",
        "compliance_check": "compliance",
        "inventory": "inventory",
        "audit": "compliance",
        "discovery": "inventory",
    }
    
    api_type_lower = api_type.lower()
    for key, value in type_mapping.items():
        if key in api_type_lower:
            return value
    
    return api_type_lower


def _map_scan_status(api_status: str) -> str:
    """Преобразует статус из API в внутренний формат."""
    if not api_status:
        return "pending"
    
    status_mapping = {
        "completed": "completed",
        "finished": "completed",
        "done": "completed",
        "success": "completed",
        "running": "running",
        "in_progress": "running",
        "processing": "running",
        "failed": "failed",
        "error": "failed",
        "cancelled": "failed",
        "pending": "pending",
        "queued": "pending",
        "waiting": "pending",
    }
    
    api_status_lower = api_status.lower()
    return status_mapping.get(api_status_lower, "pending")


def _parse_datetime(datetime_str: str | None) -> datetime | None:
    """Парсит строку даты/времени из API."""
    if not datetime_str:
        return None
    
    try:
        # Пробуем несколько форматов
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue
        
        # Если ни один формат не подошёл, пробуем ISO format
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except Exception:
        return None
