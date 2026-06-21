from sqlalchemy import select, delete, insert, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from backend.models.asset import Asset
from backend.models.group import Group
from backend.db.base import asset_change_logs_table
from backend.schemas.asset import AssetCreate, AssetUpdate
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AssetService:
    """Сервис для управления активами."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all(self, group_id: Optional[int] = None, search: Optional[str] = None, ungrouped: Optional[bool] = None, source: Optional[str] = None, rules: Optional[List[dict]] = None, include_services: bool = False) -> List[Asset]:
        """Получить все активы с фильтрацией."""
        # Загружаем связанные данные если нужно
        options = [selectinload(Asset.groups)]
        if include_services:
            options.append(selectinload(Asset.services))
        
        query = select(Asset).options(*options)
        
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
                # Конвертируем ORM-объект в словарь для фильтрации
                asset_dict = self._asset_to_dict(asset)
                match = True
                for rule in rules:
                    field = rule.get('field', '')
                    # Поддерживаем оба формата: 'operation' (фронтенд) и 'op' (бэкенд)
                    operation = rule.get('operation') or rule.get('op', '')
                    value = str(rule.get('value', '')).lower()
                    
                    # Получаем значение поля из актива (asset_dict теперь dict)
                    field_value = AssetService.get_nested_value(asset_dict, field)
                    
                    # Маппинг альтернативных имен полей
                    if field_value is None:
                        if field == 'ip_address' or field == 'ip':
                            field_value = asset_dict.get('ip_address')
                        elif field == 'hostname':
                            field_value = asset_dict.get('hostname')
                        elif field == 'os_family' or field == 'os':
                            field_value = asset_dict.get('os_info') or asset_dict.get('os_name')
                        elif field == 'device_role' or field == 'role':
                            field_value = asset_dict.get('device_type')
                        elif field == 'open_ports' or field == 'ports':
                            # open_ports теперь вычисляемое свойство, объединяем rustscan и nmap порты
                            rustscan_ports = asset_dict.get('rustscan_ports', []) or []
                            nmap_ports = asset_dict.get('nmap_ports', []) or []
                            field_value = sorted(list(set(rustscan_ports) | set(nmap_ports)))
                        elif field == 'status':
                            field_value = asset_dict.get('status')
                        elif field == 'source':
                            field_value = asset_dict.get('source')
                        elif field == 'group_name' or field == 'group':
                            # Для группы берем имя первой группы
                            groups = asset_dict.get('groups', [])
                            if groups and len(groups) > 0:
                                field_value = groups[0].get('name', '')
                            else:
                                field_value = ''
                        elif field == 'notes' or field == 'description':
                            field_value = asset_dict.get('notes') or asset_dict.get('description')
                        elif field == 'tags':
                            tags = asset_dict.get('tags', [])
                            field_value = ','.join(tags) if tags else ''
                        elif field == 'mac_address' or field == 'mac':
                            field_value = asset_dict.get('mac_address')
                        elif field == 'vendor':
                            field_value = asset_dict.get('vendor')
                    
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
                    # Возвращаем ORM-объект, а не словарь, чтобы caller мог работать с ним как с ORM
                    filtered.append(asset)
            
            return filtered
        
        # Возвращаем ORM-объекты, конвертация будет выполнена вызывающим кодом
        return assets
    
    async def get_by_id(self, asset_id: int) -> Optional[dict]:
        """Получить актив по ID и вернуть как словарь с предзагруженными данными."""
        query = select(Asset).options(
            selectinload(Asset.groups),
            selectinload(Asset.services)
        ).where(Asset.id == asset_id)
        result = await self.db.execute(query)
        asset = result.scalar_one_or_none()
        
        if not asset:
            return None
        
        # Конвертируем в словарь пока сессия активна - это гарантирует загрузку всех данных
        return self._asset_to_dict(asset)
    
    def _asset_to_dict(self, asset: Asset) -> dict:
        """Конвертировать ORM-объект в словарь с предзагрузкой всех полей и связей."""
        # Явный доступ ко всем JSON-полям для их загрузки
        dns_names = list(asset.dns_names) if asset.dns_names else []
        
        # Корректная обработка dns_records: может быть списком словарей или списком списков
        dns_records_data = asset.dns_records
        if dns_records_data:
            if isinstance(dns_records_data, list) and len(dns_records_data) > 0:
                # Если это список словарей - оставляем как есть
                if isinstance(dns_records_data[0], dict):
                    dns_records = dns_records_data
                # Если это список списков (старый формат [name, type, data]) - конвертируем в словари
                elif isinstance(dns_records_data[0], (list, tuple)):
                    dns_records = []
                    for record in dns_records_data:
                        if len(record) >= 3:
                            dns_records.append({
                                "name": record[0],
                                "type": record[1],
                                "data": record[2],
                                "ttl": record[3] if len(record) > 3 else None
                            })
                else:
                    dns_records = dns_records_data
            else:
                dns_records = dns_records_data
        else:
            dns_records = []
            
        open_ports = list(asset.open_ports) if asset.open_ports else []
        rustscan_ports = list(asset.rustscan_ports) if asset.rustscan_ports else []
        nmap_ports = list(asset.nmap_ports) if asset.nmap_ports else []
        
        # Предзагрузка связанных объектов services
        services_data = []
        try:
            if 'services' not in inspect(asset).unloaded:
                for service in asset.services:
                    services_data.append({
                        'id': service.id,
                        'port': service.port,
                        'protocol': service.protocol,
                        'state': service.state,
                        'service_name': service.service_name,
                        'product': service.product,
                        'version': service.version,
                        'extra_info': service.extra_info,
                        'ssl_subject': service.ssl_cert_subject,
                        'ssl_issuer': service.ssl_cert_issuer,
                        'ssl_not_before': service.ssl_cert_not_before.isoformat() if service.ssl_cert_not_before else None,
                        'ssl_not_after': service.ssl_cert_not_after.isoformat() if service.ssl_cert_not_after else None,
                        'script_output': service.scripts,
                        'scripts': service.scripts  # Добавлено для совместимости с шаблоном
                    })
        except Exception:
            services_data = []
        
        # Предзагрузка групп
        groups_data = [{'id': g.id, 'name': g.name} for g in asset.groups]
        
        return {
            'id': asset.id,
            'uuid': asset.uuid,
            'ip_address': asset.ip_address,
            'hostname': asset.hostname,
            'mac_address': asset.mac_address,
            'vendor': asset.vendor,
            'fqdn': asset.fqdn,
            'device_type': asset.device_type,
            'status': asset.status,
            'os_family': asset.os_family,
            'os_version': asset.os_version,
            'owner': asset.owner,
            'location': asset.location,
            'source': asset.source,
            'last_rustscan': asset.last_rustscan.isoformat() if asset.last_rustscan else None,
            'last_nmap': asset.last_nmap.isoformat() if asset.last_nmap else None,
            'last_dns_scan': asset.last_dns_scan.isoformat() if asset.last_dns_scan else None,
            'last_seen': asset.last_seen.isoformat() if asset.last_seen else None,
            'created_at': asset.created_at.isoformat() if asset.created_at else None,
            'updated_at': asset.updated_at.isoformat() if asset.updated_at else None,
            'dns_names': dns_names,
            'dns_records': dns_records,
            'open_ports': open_ports,
            'rustscan_ports': rustscan_ports,
            'nmap_ports': nmap_ports,
            'services': services_data,
            'groups': groups_data
        }
    
    async def create(self, asset_data: AssetCreate) -> Asset:
        """Создать новый актив."""
        data = asset_data.model_dump()
        group_ids = data.pop('groups', None)
        
        asset = Asset(**data)
        
        # Если указаны группы, добавляем связи
        if group_ids is not None and len(group_ids) > 0:
            for gid in group_ids:
                group_query = select(Group).where(Group.id == gid)
                group_result = await self.db.execute(group_query)
                group = group_result.scalar_one_or_none()
                if group:
                    asset.groups.append(group)
                else:
                    # Группа не найдена - выбрасываем ошибку
                    from fastapi import HTTPException
                    raise HTTPException(status_code=400, detail=f"Группа с ID {gid} не найдена")
        
        self.db.add(asset)
        await self.db.flush()
        await self.db.refresh(asset, attribute_names=['groups'])  # Явно обновляем связь groups
        return asset
    
    async def update(self, asset_id: int, asset_data: AssetUpdate, username: Optional[str] = None) -> Optional[dict]:
        """Обновить актив с записью в лог изменений."""
        # Для обновления нам нужно получить ORM-объект с предзагруженными связями
        query = select(Asset).options(
            selectinload(Asset.groups),
            selectinload(Asset.services)
        ).where(Asset.id == asset_id)
        result = await self.db.execute(query)
        asset = result.scalar_one_or_none()
        
        if not asset:
            return None
        
        # Собираем изменения для логирования (текущие значения)
        changed_fields = {}
        
        update_data = asset_data.model_dump(exclude_unset=True)
        group_ids = update_data.pop('groups', None)
        
        for field, value in update_data.items():
            old_value = getattr(asset, field, None)
            if old_value != value:
                changed_fields[field] = {'old': old_value, 'new': value}
            setattr(asset, field, value)
        
        # Обновляем связи с группами
        if group_ids is not None:
            # Получаем текущие группы для логирования
            old_group_ids = [g.id for g in asset.groups]
            old_group_names = [g.name for g in asset.groups]
            
            # Очищаем текущие группы
            asset.groups.clear()
            
            # Добавляем новые группы если указаны
            new_group_names = []
            if group_ids and len(group_ids) > 0:
                for gid in group_ids:
                    group_query = select(Group).where(Group.id == gid)
                    group_result = await self.db.execute(group_query)
                    group = group_result.scalar_one_or_none()
                    if group:
                        asset.groups.append(group)
                        new_group_names.append(group.name)
            
            # Логируем изменение группы
            if old_group_names != new_group_names:
                changed_fields['groups'] = {'old': old_group_names, 'new': new_group_names}
        
        await self.db.flush()
        
        # Записываем в лог изменений если были изменения
        if changed_fields:
            # Используем прямую вставку через Core API
            stmt = insert(asset_change_logs_table).values(
                asset_id=asset_id,
                username=username,
                action='update',
                changed_fields=changed_fields,
                created_at=datetime.now()
            )
            await self.db.execute(stmt)
            await self.db.flush()
        
        # После flush и коммита связанных данных, заново получаем актив со всеми связями
        # Это гарантирует, что все данные загружены в рамках активной сессии
        refresh_query = select(Asset).options(
            selectinload(Asset.groups),
            selectinload(Asset.services)
        ).where(Asset.id == asset_id)
        refresh_result = await self.db.execute(refresh_query)
        refreshed_asset = refresh_result.scalar_one_or_none()
        
        if not refreshed_asset:
            return None
        
        # Возвращаем обновленные данные как словарь
        return self._asset_to_dict(refreshed_asset)
    
    async def delete(self, asset_id: int, username: Optional[str] = None) -> bool:
        """Удалить актив с записью в лог."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Сначала получаем данные для лога
        query = select(Asset).options(
            selectinload(Asset.groups),
            selectinload(Asset.services)
        ).where(Asset.id == asset_id)
        result = await self.db.execute(query)
        asset = result.scalar_one_or_none()
        
        if not asset:
            logger.warning(f"[DELETE] Актив {asset_id} не найден")
            return False
        
        logger.info(f"[DELETE] Найден актив {asset_id}: IP={asset.ip_address}, hostname={asset.hostname}")
        
        # Конвертируем в dict пока сессия активна
        asset_dict = self._asset_to_dict(asset)
        logger.info(f"[DELETE] Актив {asset_id} конвертирован в dict, ключи: {asset_dict.keys()}")
        
        # Теперь удаляем
        del_query = delete(Asset).where(Asset.id == asset_id)
        del_result = await self.db.execute(del_query)
        logger.info(f"[DELETE] DELETE выполнен, rowcount={del_result.rowcount}")
        
        # Записываем в лог ДО коммита удаления в той же транзакции
        if del_result.rowcount > 0 and asset_dict:
            logger.info(f"[DELETE] Запись в asset_change_logs для актива {asset_id}")
            stmt = insert(asset_change_logs_table).values(
                asset_id=asset_id,
                username=username,
                action='delete',
                changed_fields={'asset': asset_dict},
                created_at=datetime.utcnow()
            )
            log_result = await self.db.execute(stmt)
            logger.info(f"[DELETE] Лог изменений вставлен, rowcount={log_result.rowcount}")
        
        # Коммитим всё вместе (удаление + лог)
        logger.info(f"[DELETE] Выполняем commit...")
        await self.db.commit()
        logger.info(f"[DELETE] Commit успешен для актива {asset_id}")
        
        return del_result.rowcount > 0
    
    async def delete_batch(self, asset_ids: List[int], username: Optional[str] = None) -> int:
        """Удалить несколько активов с записью в лог."""
        if not asset_ids:
            return 0
        
        # Получаем данные для лога перед удалением
        assets_data = []
        for aid in asset_ids:
            asset_dict = await self.get_by_id(aid)
            if asset_dict:
                # get_by_id уже возвращает словарь, используем его напрямую
                assets_data.append(asset_dict)
        
        # Удаляем все активы одним запросом
        query = delete(Asset).where(Asset.id.in_(asset_ids))
        result = await self.db.execute(query)
        
        # Записываем в лог все удаленные активы одним bulk-запросом
        if assets_data:
            log_entries = [
                {
                    'asset_id': asset_dict['id'],
                    'username': username,
                    'action': 'delete',
                    'changed_fields': {'asset': asset_dict},
                    'created_at': datetime.utcnow()
                }
                for asset_dict in assets_data
            ]
            stmt = insert(asset_change_logs_table).values(log_entries)
            await self.db.execute(stmt)
        
        await self.db.commit()
        
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
    
    @staticmethod
    def get_nested_value(data: dict, key: str):
        """Получить значение из словаря по ключу (для обработки вложенных ключей через точку)."""
        keys = key.split('.')
        value = data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        return value
    
    async def get_change_logs(self, asset_id: int, limit: Optional[int] = None) -> List[dict]:
        """Получить историю изменений актива (без ограничений по умолчанию)."""
        query = select(asset_change_logs_table).where(
            asset_change_logs_table.c.asset_id == asset_id
        ).order_by(asset_change_logs_table.c.id.desc())
        
        if limit is not None:
            query = query.limit(limit)
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        return [
            {
                'id': row.id,
                'asset_id': row.asset_id,
                'username': row.username,
                'action': row.action,
                'changed_fields': row.changed_fields,
                'created_at': row.created_at.isoformat() if row.created_at else None
            }
            for row in rows
        ]

    async def get_assets_from_groups(self, group_ids: List[int]) -> List[Asset]:
        """
        Получить все активы из указанных групп.
        
        Args:
            group_ids: Список ID групп
            
        Returns:
            Список активов из всех указанных групп
        """
        if not group_ids:
            return []
        
        # Получаем активы, которые состоят в указанных группах
        query = select(Asset).join(Asset.groups).where(Group.id.in_(group_ids))
        result = await self.db.execute(query)
        assets = list(result.scalars().unique().all())
        
        logger = logging.getLogger(__name__)
        logger.info(f"Получено {len(assets)} активов из {len(group_ids)} групп")
        
        return assets
