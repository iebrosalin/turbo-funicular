from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
import json
import os

from backend.db.session import get_db
from backend.services.asset_service import AssetService
from backend.schemas.asset import AssetCreate, AssetUpdate, AssetResponse
from backend.models.asset import Asset
from backend.utils.query_parser import parse_query, QueryParserError
from backend.utils import generate_asset_taxonomy

router = APIRouter(tags=["assets"])
assets_router = router  # Алиас для совместимости импортов

# Инициализация шаблонов
templates_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_path)


class FilterRule(BaseModel):
    field: str
    operation: str
    value: str


class FilterRequest(BaseModel):
    rules: List[FilterRule]


# Кэш схемы полей
_asset_schema_cache: Optional[List[Dict[str, Any]]] = None

@router.get("/schema")
async def get_asset_schema(db: AsyncSession = Depends(get_db)):
    """Возвращает список доступных полей для фильтрации с типами и операторами."""
    global _asset_schema_cache
    
    if _asset_schema_cache is None:
        columns = []
        for column in Asset.__table__.columns:
            col_type = str(column.type).lower()
            ops = ["=", "like", "reg_match"]
            if "int" in col_type or "integer" in col_type:
                ops.append("in")
            elif "string" in col_type or "text" in col_type or "varchar" in col_type:
                ops.append("in")
            
            # Исключаем служебные поля
            if column.name not in ['id', 'created_at', 'updated_at']:
                columns.append({
                    "field": column.name,
                    "type": col_type,
                    "operators": ops,
                    "label": column.name.replace("_", " ").title()
                })
        _asset_schema_cache = columns
    
    return {"schema": _asset_schema_cache}


@router.post("/count", response_model=dict)
async def count_assets_by_filter(
    filter_request: FilterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Подсчитать количество активов по правилам фильтрации."""
    service = AssetService(db)
    
    # Получаем все активы и фильтруем на уровне Python (упрощенно)
    # В будущем можно оптимизировать через SQL запросы
    assets = await service.get_all()
    
    filtered = []
    for asset in assets:
        match = True
        for rule in filter_request.rules:
            field_value = getattr(asset, rule.field, None)
            if field_value is None:
                # Поле не найдено в модели, пробуем альтернативные имена
                if rule.field == 'ip_address':
                    field_value = getattr(asset, 'ip', None)
                elif rule.field == 'os_info':
                    field_value = getattr(asset, 'os_family', None)
                elif rule.field == 'device_role':
                    field_value = getattr(asset, 'role', None)
                elif rule.field == 'scanners_used':
                    field_value = getattr(asset, 'scanners', None)
            
            if field_value is None:
                field_value = ''
            else:
                field_value = str(field_value).lower()
            
            search_value = rule.value.lower()
            
            if rule.operation == 'eq':
                if field_value != search_value:
                    match = False
            elif rule.operation == 'neq':
                if field_value == search_value:
                    match = False
            elif rule.operation == 'contains':
                if search_value not in field_value:
                    match = False
            elif rule.operation == 'in':
                values_list = [v.strip().lower() for v in search_value.split(',')]
                if field_value not in values_list:
                    match = False
            
            if not match:
                break
        
        if match:
            filtered.append(asset)
    
    return {"count": len(filtered)}


@router.get("", response_model=List[AssetResponse])
async def get_assets(
    db: AsyncSession = Depends(get_db),
    group_id: Optional[str] = Query(None, alias="group_id"),
    search: Optional[str] = Query(None),
    ungrouped: Optional[bool] = Query(None),
    source: Optional[str] = Query(None),
    rules: Optional[str] = Query(None),  # JSON строка с правилами фильтрации
    include_taxonomy: Optional[bool] = Query(False)  # Включить таксономию в ответ
):
    """Получить список активов с фильтрацией."""
    service = AssetService(db)
    
    # Преобразуем group_id в int или None
    group_id_int: Optional[int] = None
    
    # Специальная обработка для значения "ungrouped" - активы без группы
    if group_id == "ungrouped":
        group_id_int = None
        ungrouped = True
    elif group_id is not None and group_id != "null":
        try:
            group_id_int = int(group_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный формат group_id")
    
    # Если передан ungrouped=true, игнорируем group_id
    if ungrouped is True:
        group_id_int = None
    
    # Парсим правила фильтрации если переданы
    filter_rules = None
    if rules:
        try:
            import json
            filter_rules = json.loads(rules)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Некорректный формат правил фильтрации")
    
    assets = await service.get_all(
        group_id=group_id_int, 
        search=search, 
        ungrouped=ungrouped, 
        source=source,
        rules=filter_rules
    )
    
    # Если запрошена таксономия, добавляем её к каждому активу
    if include_taxonomy:
        result = []
        for asset in assets:
            asset_dict = asset.model_dump() if hasattr(asset, 'model_dump') else asset.__dict__
            taxonomy = generate_asset_taxonomy(asset)
            asset_dict['taxonomy'] = taxonomy
            result.append(asset_dict)
        return result
    
    return assets


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    """Получить актив по ID."""
    service = AssetService(db)
    asset = await service.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"error": "Актив не найден", "code": "ASSET_NOT_FOUND"})
    return asset


@router.get("/view/{asset_id}", response_class=HTMLResponse)
async def get_asset_page(request: Request, asset_id: int, db: AsyncSession = Depends(get_db)):
    """Отобразить страницу детали актива."""
    from fastapi.responses import JSONResponse
    
    service = AssetService(db)
    asset = await service.get_by_id(asset_id)
    if not asset:
        # Возвращаем JSON ошибку вместо HTML 404 страницы
        return JSONResponse(
            status_code=404,
            content={"detail": "Актив не найден", "code": "ASSET_NOT_FOUND"}
        )
    
    # Получаем историю изменений
    change_logs = await service.get_change_logs(asset_id, limit=50)
    
    return templates.TemplateResponse("asset_detail.html", {
        "request": request,
        "asset": asset,
        "change_logs": change_logs
    })


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(asset_data: AssetCreate, db: AsyncSession = Depends(get_db)):
    """Создать новый актив."""
    service = AssetService(db)
    
    # Проверка на дубликат IP
    existing = await service.get_all(search=asset_data.ip_address)
    if any(a.ip_address == asset_data.ip_address for a in existing):
        raise HTTPException(status_code=400, detail="Актив с таким IP уже существует")
    
    asset = await service.create(asset_data)
    
    # Создаем ответ вручную, чтобы корректно установить group_id
    from backend.schemas.asset import AssetResponse
    group_id = None
    if asset.groups and len(asset.groups) > 0:
        group_id = asset.groups[0].id
    
    return AssetResponse(
        id=asset.id,
        ip_address=asset.ip_address,
        hostname=asset.hostname,
        os_family=asset.os_family,
        status=asset.status,
        location=asset.location,
        group_id=group_id,
        created_at=asset.created_at,
        updated_at=asset.updated_at
    )


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: int, asset_data: AssetUpdate, db: AsyncSession = Depends(get_db), username: Optional[str] = None):
    """Обновить актив."""
    service = AssetService(db)
    asset = await service.update(asset_id, asset_data, username=username)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")
    
    # Явно загружаем связи для ответа
    await db.refresh(asset, attribute_names=['groups'])
    
    # Создаем ответ вручную, чтобы корректно установить group_id
    group_id = None
    if asset.groups and len(asset.groups) > 0:
        group_id = asset.groups[0].id
    
    return AssetResponse(
        id=asset.id,
        ip_address=asset.ip_address,
        hostname=asset.hostname,
        os_family=asset.os_family,
        status=asset.status,
        location=asset.location,
        group_id=group_id,
        created_at=asset.created_at,
        updated_at=asset.updated_at
    )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(asset_id: int, db: AsyncSession = Depends(get_db), username: Optional[str] = None):
    """Удалить актив."""
    service = AssetService(db)
    success = await service.delete(asset_id, username=username)
    if not success:
        raise HTTPException(status_code=404, detail="Актив не найден")


class BulkDeleteRequest(BaseModel):
    ids: List[int]


@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bulk_assets(request: BulkDeleteRequest, db: AsyncSession = Depends(get_db), username: Optional[str] = None):
    """Удалить несколько активов."""
    service = AssetService(db)
    deleted_count = await service.delete_batch(request.ids, username=username)
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Активы не найдены")


class BulkMoveRequest(BaseModel):
    ids: List[int]
    group_id: Optional[int] = None


@router.post("/bulk-move", status_code=status.HTTP_200_OK)
async def bulk_move_assets(
    request: BulkMoveRequest,
    db: AsyncSession = Depends(get_db)
):
    """Переместить несколько активов в другую группу."""
    service = AssetService(db)
    moved_count = await service.move_to_group_batch(request.ids, request.group_id)
    return {"message": f"Перемещено активов: {moved_count}", "count": moved_count}
