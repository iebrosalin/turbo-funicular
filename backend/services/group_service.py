from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
from backend.models.group import Group
from backend.schemas.group import GroupCreate, GroupUpdate


class GroupService:
    """Сервис для управления группами."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all(self) -> List[Group]:
        """Получить все группы с иерархией."""
        query = select(Group).options(selectinload(Group.parent))
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
        
        # Проверка на циклическую ссылку
        if 'parent_id' in update_data and update_data['parent_id'] == group_id:
            raise ValueError("Группа не может быть родителем самой себя")
        
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
            
            # Проверка: нельзя переместить группу в её собственного потомка
            # Это создало бы циклическую зависимость
            if await self._is_descendant_of(group_id, new_parent_id):
                return None
        
        group.parent_id = new_parent_id
        await self.db.flush()
        await self.db.refresh(group)
        return group
    
    async def _is_descendant_of(self, potential_ancestor_id: int, potential_descendant_id: int) -> bool:
        """Проверить, является ли potential_ancestor_id потомком potential_descendant_id."""
        current_id = potential_descendant_id
        
        while current_id is not None:
            if current_id == potential_ancestor_id:
                return True
            # Получаем родителя текущей группы
            parent = await self.get_by_id(current_id)
            if parent:
                current_id = parent.parent_id
            else:
                break
        
        return False
    
    async def update_dynamic_group_members(self, group_id: int, filter_rules_json: str) -> int:
        """
        Обновить состав динамической группы на основе правил фильтрации.
        Возвращает количество обновленных активов.
        """
        import json
        from backend.models.asset import Asset, asset_groups
        from sqlalchemy import select
        
        # Парсим правила
        try:
            rules = json.loads(filter_rules_json)
        except (json.JSONDecodeError, TypeError):
            return 0
        
        if not rules:
            return 0
        
        # Получаем все активы
        query = select(Asset).options(selectinload(Asset.groups))
        result = await self.db.execute(query)
        all_assets = list(result.scalars().unique().all())
        
        # Фильтруем активы по правилам (та же логика что в AssetService)
        matching_asset_ids = []
        for asset in all_assets:
            match = True
            for rule in rules:
                field = rule.get('field', '')
                operation = rule.get('operation', '')
                value = str(rule.get('value', '')).lower()
                
                # Получаем значение поля из актива
                field_value = getattr(asset, field, None)
                
                # Маппинг альтернативных имен полей
                if field_value is None:
                    if field == 'ip':
                        field_value = getattr(asset, 'ip_address', None)
                    elif field == 'hostname':
                        field_value = getattr(asset, 'hostname', None)
                    elif field == 'os':
                        field_value = getattr(asset, 'os_family', None)
                    elif field == 'device_role':
                        field_value = getattr(asset, 'device_type', None)
                    elif field == 'ports':
                        field_value = getattr(asset, 'open_ports', None)
                    elif field == 'status':
                        field_value = getattr(asset, 'status', None)
                    elif field == 'source':
                        field_value = getattr(asset, 'source', None)
                    elif field == 'group_id':
                        # Для группы проверяем наличие связи
                        if asset.groups and len(asset.groups) > 0:
                            field_value = str(asset.groups[0].id)
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
                matching_asset_ids.append(asset.id)
        
        # Получаем группу
        group = await self.get_by_id(group_id)
        if not group:
            return 0
        
        # Очищаем текущие связи и добавляем новые
        # Сначала получаем текущие ID активов в группе
        current_query = select(asset_groups.c.asset_id).where(asset_groups.c.group_id == group_id)
        current_result = await self.db.execute(current_query)
        current_asset_ids = set(row[0] for row in current_result.all())
        
        new_asset_ids = set(matching_asset_ids)
        
        # Активы для добавления (есть в новых, но нет в текущих)
        to_add = new_asset_ids - current_asset_ids
        # Активы для удаления (есть в текущих, но нет в новых)
        to_remove = current_asset_ids - new_asset_ids
        
        # Добавляем новые связи
        for asset_id in to_add:
            insert_stmt = asset_groups.insert().values(asset_id=asset_id, group_id=group_id)
            await self.db.execute(insert_stmt)
        
        # Удаляем старые связи
        if to_remove:
            delete_stmt = delete(asset_groups).where(
                asset_groups.c.asset_id.in_(to_remove),
                asset_groups.c.group_id == group_id
            )
            await self.db.execute(delete_stmt)
        
        await self.db.flush()
        
        return len(to_add) + len(to_remove)
