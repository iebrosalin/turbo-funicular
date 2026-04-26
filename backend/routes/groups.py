from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional, Dict, Any
from backend.db.session import get_db
from backend.models.group import Group as AssetGroup
from backend.schemas.group import GroupCreate, GroupUpdate, GroupResponse
from backend.services.group_service import GroupService
from backend.utils import build_group_tree, build_complex_query, log_asset_change, get_moscow_time
import json

router = APIRouter(tags=["groups"])
groups_router = router  # Алиас для совместимости импортов


@router.get("", response_model=List[GroupResponse])
async def get_groups(
    db: AsyncSession = Depends(get_db),
    include_assets_count: bool = True
):
    """Получить все группы."""
    service = GroupService(db)
    groups = await service.get_all()
    
    if include_assets_count:
        # Подсчёт активов для каждой группы
        from backend.models.asset import Asset
        for group in groups:
            query = select(func.count()).select_from(Asset).where(Asset.group_id == group.id)
            result = await db.execute(query)
            group.assets_count = result.scalar()
    
    return groups


@router.get("/tree", response_model=List[Dict])
async def get_group_tree(db: AsyncSession = Depends(get_db)):
    """Получить дерево групп с подсчётом активов."""
    from backend.models.asset import Asset
    
    # Получаем все группы
    query = select(AssetGroup).order_by(AssetGroup.name)
    result = await db.execute(query)
    groups = list(result.scalars().all())
    
    # Подсчитываем активы для каждой группы
    for group in groups:
        count_query = select(func.count()).select_from(Asset).where(Asset.group_id == group.id)
        count_result = await db.execute(count_query)
        group.assets_count = count_result.scalar()
    
    tree = build_group_tree(groups)
    return tree


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """Получить группу по ID."""
    service = GroupService(db)
    group = await service.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return group


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Создать новую группу.
    Поддерживает статические и динамические группы (с filter_rules).
    """
    service = GroupService(db)
    
    # Проверка на дубликат имени
    existing = await service.get_all()
    if any(g.name == group_data.name for g in existing):
        raise HTTPException(status_code=400, detail="Группа с таким именем уже существует")
    
    # Создание группы
    group = await service.create(group_data)
    
    # Логирование
    await log_asset_change(
        db=db,
        asset=None,  # Группа не актив
        field_name="group_created",
        old_value="null",
        new_value=json.dumps({"group_id": group.id, "name": group.name})
    )
    
    # Если это динамическая группа с filter_rules, обновляем состав
    if hasattr(group_data, 'filter_rules') and group_data.filter_rules:
        await service.update_dynamic_group_members(group.id, group_data.filter_rules)
    
    return group


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    group_data: GroupUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить группу."""
    service = GroupService(db)
    
    # Проверка на дубликат имени (если имя меняется)
    if group_data.name:
        existing = await service.get_all()
        if any(g.name == group_data.name and g.id != group_id for g in existing):
            raise HTTPException(status_code=400, detail="Группа с таким именем уже существует")
    
    group = await service.update(group_id, group_data)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
    # Если это динамическая группа, обновляем состав
    if hasattr(group_data, 'filter_rules') and group_data.filter_rules is not None:
        await service.update_dynamic_group_members(group.id, group_data.filter_rules)
    
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить группу."""
    service = GroupService(db)
    success = await service.delete(group_id)
    if not success:
        raise HTTPException(status_code=404, detail="Группа не найдена")


@router.post("/{group_id}/move", response_model=GroupResponse)
async def move_group(
    group_id: int,
    new_parent_id: Optional[int],
    db: AsyncSession = Depends(get_db)
):
    """Переместить группу в другую родительскую группу."""
    service = GroupService(db)
    group = await service.move(group_id, new_parent_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена или недопустимый родитель")
    return group


@router.get("/ungrouped/count", response_model=Dict[str, int])
async def get_ungrouped_count(db: AsyncSession = Depends(get_db)):
    """Получить количество активов без группы."""
    from backend.models.asset import Asset
    
    query = select(func.count()).select_from(Asset).where(Asset.group_id.is_(None))
    result = await db.execute(query)
    count = result.scalar()
    
    return {"ungrouped_count": count}


@router.post("/cidr/auto-create", response_model=List[GroupResponse])
async def create_cidr_groups(
    cidr_list: List[str],
    parent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Автоматически создать группы для CIDR подсетей.
    
    Args:
        cidr_list: Список CIDR нотаций (например, ["192.168.1.0/24"])
        parent_id: ID родительской группы (опционально)
    """
    from backend.utils.network_utils import create_cidr_groups
    
    groups = await create_cidr_groups(
        db=db,
        cidr_list=cidr_list,
        parent_id=parent_id
    )
    
    return groups
