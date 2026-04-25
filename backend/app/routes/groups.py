from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.db.session import get_db
from app.services.group_service import GroupService
from app.schemas.group import GroupCreate, GroupUpdate, GroupResponse

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("", response_model=List[GroupResponse])
async def get_groups(db: AsyncSession = Depends(get_db)):
    """Получить все группы."""
    service = GroupService(db)
    groups = await service.get_all()
    return groups


@router.get("/tree", response_model=List[GroupResponse])
async def get_group_tree(db: AsyncSession = Depends(get_db)):
    """Получить дерево групп."""
    service = GroupService(db)
    tree = await service.get_tree()
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
async def create_group(group_data: GroupCreate, db: AsyncSession = Depends(get_db)):
    """Создать новую группу."""
    service = GroupService(db)
    
    # Проверка на дубликат имени
    existing = await service.get_all()
    if any(g.name == group_data.name for g in existing):
        raise HTTPException(status_code=400, detail="Группа с таким именем уже существует")
    
    group = await service.create(group_data)
    return group


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(group_id: int, group_data: GroupUpdate, db: AsyncSession = Depends(get_db)):
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
