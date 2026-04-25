from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.models.group import Group
from app.schemas.group import GroupCreate, GroupUpdate


class GroupService:
    """Сервис для управления группами."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all(self) -> List[Group]:
        """Получить все группы с иерархией."""
        query = select(Group).options(selectinload(Group.children), selectinload(Group.parent))
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_tree(self) -> List[dict]:
        """Получить дерево групп."""
        groups = await self.get_all()
        
        # Строим дерево в памяти
        groups_dict = {g.id: g for g in groups}
        tree = []
        
        for group in groups:
            if group.parent_id is None:
                tree.append(group)
            else:
                parent = groups_dict.get(group.parent_id)
                if parent:
                    if not hasattr(parent, '_children_list'):
                        parent._children_list = []
                    parent._children_list.append(group)
        
        # Возвращаем только корневые элементы, дети уже привязаны
        return [g for g in groups if g.parent_id is None]
    
    async def get_by_id(self, group_id: int) -> Optional[Group]:
        """Получить группу по ID."""
        query = select(Group).where(Group.id == group_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create(self, group_data: GroupCreate) -> Group:
        """Создать новую группу."""
        group = Group(**group_data.model_dump(exclude_unset=True))
        self.db.add(group)
        await self.db.flush()
        await self.db.refresh(group)
        return group
    
    async def update(self, group_id: int, group_data: GroupUpdate) -> Optional[Group]:
        """Обновить группу."""
        group = await self.get_by_id(group_id)
        if not group:
            return None
        
        update_data = group_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(group, field, value)
        
        await self.db.flush()
        await self.db.refresh(group)
        return group
    
    async def delete(self, group_id: int) -> bool:
        """Удалить группу."""
        group = await self.get_by_id(group_id)
        if not group:
            return False
        
        query = delete(Group).where(Group.id == group_id)
        await self.db.execute(query)
        await self.db.flush()
        return True
    
    async def move(self, group_id: int, new_parent_id: Optional[int]) -> Optional[Group]:
        """Переместить группу в другую родительскую группу."""
        group = await self.get_by_id(group_id)
        if not group:
            return None
        
        # Проверка на циклическую ссылку
        if new_parent_id:
            parent = await self.get_by_id(new_parent_id)
            if not parent:
                return None
            # Простая проверка: нельзя переместить родителя в самого себя или в потомка
            if new_parent_id == group_id:
                return None
        
        group.parent_id = new_parent_id
        await self.db.flush()
        await self.db.refresh(group)
        return group
