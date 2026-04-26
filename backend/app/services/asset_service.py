from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.models.asset import Asset
from app.models.group import Group
from app.schemas.asset import AssetCreate, AssetUpdate


class AssetService:
    """Сервис для управления активами."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all(self, group_id: Optional[int] = None, search: Optional[str] = None) -> List[Asset]:
        """Получить все активы с фильтрацией."""
        query = select(Asset).options(selectinload(Asset.groups))
        
        if group_id is not None:
            # Фильтрация по many-to-many связи через таблицу asset_groups
            query = query.join(Asset.groups).where(Group.id == group_id)
        
        if search:
            query = query.where(
                (Asset.ip_address.ilike(f"%{search}%")) |
                (Asset.hostname.ilike(f"%{search}%"))
            )
        
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())
    
    async def get_by_id(self, asset_id: int) -> Optional[Asset]:
        """Получить актив по ID."""
        query = select(Asset).options(selectinload(Asset.groups)).where(Asset.id == asset_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create(self, asset_data: AssetCreate) -> Asset:
        """Создать новый актив."""
        data = asset_data.model_dump()
        group_id = data.pop('group_id', None)
        
        asset = Asset(**data)
        
        # Если указана группа, добавляем связь
        if group_id is not None:
            group_query = select(Group).where(Group.id == group_id)
            group_result = await self.db.execute(group_query)
            group = group_result.scalar_one_or_none()
            if group:
                asset.groups.append(group)
        
        self.db.add(asset)
        await self.db.flush()
        await self.db.refresh(asset)
        return asset
    
    async def update(self, asset_id: int, asset_data: AssetUpdate) -> Optional[Asset]:
        """Обновить актив."""
        asset = await self.get_by_id(asset_id)
        if not asset:
            return None
        
        update_data = asset_data.model_dump(exclude_unset=True)
        group_id = update_data.pop('group_id', None)
        
        for field, value in update_data.items():
            setattr(asset, field, value)
        
        # Обновляем связи с группами
        if group_id is not None:
            # Очищаем текущие группы
            asset.groups.clear()
            
            # Добавляем новую группу если указана
            if group_id:
                group_query = select(Group).where(Group.id == group_id)
                group_result = await self.db.execute(group_query)
                group = group_result.scalar_one_or_none()
                if group:
                    asset.groups.append(group)
        
        await self.db.flush()
        await self.db.refresh(asset)
        return asset
    
    async def delete(self, asset_id: int) -> bool:
        """Удалить актив."""
        query = delete(Asset).where(Asset.id == asset_id)
        result = await self.db.execute(query)
        await self.db.flush()
        return result.rowcount > 0
    
    async def delete_batch(self, asset_ids: List[int]) -> int:
        """Удалить несколько активов."""
        query = delete(Asset).where(Asset.id.in_(asset_ids))
        result = await self.db.execute(query)
        await self.db.flush()
        return result.rowcount
