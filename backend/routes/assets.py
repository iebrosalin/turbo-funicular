from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
from backend.db.session import get_db
from backend.services.asset_service import AssetService
from backend.schemas.asset import AssetCreate, AssetUpdate, AssetResponse
from backend.models.asset import Asset

router = APIRouter(tags=["assets"])
assets_router = router  # Алиас для совместимости импортов


@router.get("", response_model=List[AssetResponse])
async def get_assets(
    db: AsyncSession = Depends(get_db),
    group_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None)
):
    """Получить список активов с фильтрацией."""
    service = AssetService(db)
    assets = await service.get_all(group_id=group_id, search=search)
    return assets


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    """Получить актив по ID."""
    service = AssetService(db)
    asset = await service.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")
    return asset


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
async def update_asset(asset_id: int, asset_data: AssetUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить актив."""
    service = AssetService(db)
    asset = await service.update(asset_id, asset_data)
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")
    
    # Явно загружаем связи для ответа
    await db.refresh(asset, attribute_names=['groups'])
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить актив."""
    service = AssetService(db)
    success = await service.delete(asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Актив не найден")


@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bulk_assets(asset_ids: List[int], db: AsyncSession = Depends(get_db)):
    """Удалить несколько активов."""
    service = AssetService(db)
    deleted_count = await service.delete_batch(asset_ids)
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Активы не найдены")
