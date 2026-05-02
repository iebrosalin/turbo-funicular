from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
from backend.models.asset import Asset
from backend.models.group import Group
from backend.schemas.asset import AssetCreate, AssetUpdate


class AssetService:
    """Сервис для управления активами."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all(self, group_id: Optional[int] = None, search: Optional[str] = None, ungrouped: Optional[bool] = None, source: Optional[str] = None, rules: Optional[List[dict]] = None) -> List[Asset]:
        """Получить все активы с фильтрацией."""
        query = select(Asset).options(selectinload(Asset.groups))
        
        if ungrouped is True:
            # Активы без групп (нет записей в asset_groups)
            query = query.outerjoin(Asset.groups).where(Group.id.is_(None))
        elif group_id is not None:
            # Фильтрация по many-to-many связи через таблицу asset_groups
            query = query.join(Asset.groups).where(Group.id == group_id)
        
        # Фильтрация по источнику
        if source and source != 'all':
            query = query.where(Asset.source == source)
        
        if search:
            query = query.where(
                (Asset.ip_address.ilike(f"%{search}%")) |
                (Asset.hostname.ilike(f"%{search}%"))
            )
        
        result = await self.db.execute(query)
        assets = list(result.scalars().unique().all())
        
        # Применяем сложные правила фильтрации на уровне Python
        if rules:
            filtered = []
            for asset in assets:
                match = True
                for rule in rules:
                    field = rule.get('field', '')
                    operation = rule.get('operation', '')
                    value = str(rule.get('value', '')).lower()
                    
                    # Получаем значение поля из актива
                    field_value = getattr(asset, field, None)
                    
                    # Маппинг альтернативных имен полей
                    if field_value is None:
                        if field == 'ip_address':
                            field_value = getattr(asset, 'ip_address', None)
                        elif field == 'hostname':
                            field_value = getattr(asset, 'hostname', None)
                        elif field == 'os_family':
                            field_value = getattr(asset, 'os_family', None)
                        elif field == 'device_role':
                            field_value = getattr(asset, 'device_type', None)
                        elif field == 'open_ports':
                            field_value = getattr(asset, 'open_ports', None)
                        elif field == 'status':
                            field_value = getattr(asset, 'status', None)
                        elif field == 'source':
                            field_value = getattr(asset, 'source', None)
                        elif field == 'group_name':
                            # Для группы берем имя первой группы
                            if asset.groups and len(asset.groups) > 0:
                                field_value = asset.groups[0].name
                            else:
                                field_value = ''
                    
                    if field_value is None:
                        field_value = ''
                    elif isinstance(field_value, list):
                        # Для списков (порты) конвертируем в строку
                        field_value = ','.join(map(str, field_value)).lower()
                    else:
                        field_value = str(field_value).lower()
                    
                    # Применяем операцию
                    if operation == 'eq':
                        if field_value != value:
                            match = False
                    elif operation == 'neq':
                        if field_value == value:
                            match = False
                    elif operation == 'contains':
                        if value not in field_value:
                            match = False
                    elif operation == 'in':
                        values_list = [v.strip().lower() for v in value.split(',')]
                        if field_value not in values_list:
                            match = False
                    
                    if not match:
                        break
                
                if match:
                    filtered.append(asset)
            
            return filtered
        
        return assets
    
    async def get_by_id(self, asset_id: int) -> Optional[Asset]:
        """Получить актив по ID."""
        query = select(Asset).options(
            selectinload(Asset.groups),
            selectinload(Asset.services)
        ).where(Asset.id == asset_id)
        result = await self.db.execute(query)
        asset = result.scalar_one_or_none()
        
        # Явно загружаем JSON поля и связи пока сессия активна
        if asset:
            # Доступ к JSON полям для триггеринга загрузки
            try:
                _ = list(asset.dns_names) if asset.dns_names else []
                _ = list(asset.dns_records) if asset.dns_records else []
                _ = list(asset.open_ports) if asset.open_ports else []
                _ = list(asset.rustscan_ports) if asset.rustscan_ports else []
                _ = list(asset.nmap_ports) if asset.nmap_ports else []
                _ = dict(asset.os_info) if asset.os_info else {}
                _ = list(asset.mac_addresses) if asset.mac_addresses else []
            except Exception:
                pass
            
            # Принудительно загружаем связанные объекты services
            try:
                for service in asset.services:
                    _ = service.port
                    _ = service.protocol
                    _ = service.state
                    _ = service.service_name
                    _ = service.version
            except Exception:
                pass
            
        return asset
    
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
            else:
                # Группа не найдена - выбрасываем ошибку
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail=f"Группа с ID {group_id} не найдена")
        
        self.db.add(asset)
        await self.db.flush()
        await self.db.refresh(asset, attribute_names=['groups'])  # Явно обновляем связь groups
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
    
    async def move_to_group_batch(self, asset_ids: List[int], group_id: Optional[int]) -> int:
        """Переместить несколько активов в другую группу."""
        if not asset_ids:
            return 0
        
        # Получаем все активы
        query = select(Asset).options(selectinload(Asset.groups)).where(Asset.id.in_(asset_ids))
        result = await self.db.execute(query)
        assets = list(result.scalars().unique().all())
        
        if not assets:
            return 0
        
        # Если указана группа, проверяем её существование
        group = None
        if group_id is not None:
            group_query = select(Group).where(Group.id == group_id)
            group_result = await self.db.execute(group_query)
            group = group_result.scalar_one_or_none()
            if not group:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail=f"Группа с ID {group_id} не найдена")
        
        # Обновляем связи для каждого актива
        for asset in assets:
            asset.groups.clear()
            if group:
                asset.groups.append(group)
        
        await self.db.flush()
        return len(assets)
