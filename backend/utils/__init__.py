"""
Утилиты для работы с сетевыми активами.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
import json

logger = logging.getLogger(__name__)

# Московский часовой пояс (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))


def get_moscow_time() -> datetime:
    """Получить текущее время в московском часовом поясе."""
    return datetime.now(MOSCOW_TZ)


def to_moscow_time(dt: datetime) -> datetime:
    """Конвертировать datetime в московское время."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MOSCOW_TZ)


def format_moscow_time(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Форматировать datetime в строку с московским временем."""
    moscow_dt = to_moscow_time(dt)
    return moscow_dt.strftime(fmt)


async def create_asset_if_not_exists(
    db: AsyncSession,
    ip_address: str,
    hostname: Optional[str] = None,
    mac_address: Optional[str] = None,
    group_id: Optional[int] = None
) -> Any:
    """
    Создать актив если он не существует, иначе вернуть существующий.
    
    Args:
        db: Сессия базы данных
        ip_address: IP адрес актива
        hostname: Имя хоста (опционально)
        mac_address: MAC адрес (опционально)
        group_id: ID группы (опционально)
    
    Returns:
        Экземпляр модели Asset
    """
    from backend.models.asset import Asset
    
    # Проверяем существование
    query = select(Asset).where(Asset.ip_address == ip_address)
    result = await db.execute(query)
    asset = result.scalar_one_or_none()
    
    if asset:
        logger.info(f"[AssetManager] Найден существующий актив {asset.id} для IP: {ip_address}, обновление не требуется")
        return asset
    
    # Создаём новый
    logger.info(f"[AssetManager] Создание нового актива для IP: {ip_address}")
    asset = Asset(
        ip_address=ip_address,
        hostname=hostname,
        mac_address=mac_address,
        group_id=group_id
    )
    db.add(asset)
    await db.flush()
    await db.refresh(asset)
    logger.info(f"[AssetManager] Успешно создан актив {asset.id} для IP: {ip_address} (hostname: {hostname})")
    return asset


async def update_asset_dns_names(
    db: AsyncSession,
    asset: Any,
    dns_names: List[str]
) -> bool:
    """
    Обновить DNS имена актива.
    
    Args:
        db: Сессия базы данных
        asset: Экземпляр модели Asset
        dns_names: Список DNS имен
    
    Returns:
        True если обновлено, False если нет изменений
    """
    from backend.models.log import AssetChangeLog
    
    current_dns = asset.dns_names or []
    if set(current_dns) == set(dns_names):
        return False
    
    old_value = current_dns
    asset.dns_names = dns_names
    asset.last_dns_scan = get_moscow_time()
    
    # Логируем изменение
    await log_asset_change(
        db=db,
        asset=asset,
        field_name="dns_names",
        old_value=json.dumps(old_value),
        new_value=json.dumps(dns_names)
    )
    
    await db.flush()
    logger.info(f"Обновлены DNS имена для {asset.ip_address}: {dns_names}")
    return True


async def log_asset_change(
    db: AsyncSession,
    asset: Any,
    field_name: str,
    old_value: str,
    new_value: str
):
    """
    Записать изменение актива в лог.
    
    Args:
        db: Сессия базы данных
        asset: Экземпляр модели Asset
        field_name: Имя изменённого поля
        old_value: Старое значение (JSON строка)
        new_value: Новое значение (JSON строка)
    """
    from backend.models.log import AssetChangeLog
    
    # Если asset=None (например, при создании группы), пропускаем логирование
    if asset is None:
        return
    
    change_log = AssetChangeLog(
        asset_id=asset.id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value
    )
    db.add(change_log)
    await db.flush()
    logger.debug(f"Записано изменение {field_name} для актива {asset.id}")


def detect_device_role_and_tags(asset: Any) -> Dict[str, Any]:
    """
    Определить роль устройства и теги на основе открытых портов.
    
    Args:
        asset: Экземпляр модели Asset
    
    Returns:
        Словарь с ролью и тегами
    """
    ports = asset.open_ports or []
    tags = []
    role = "unknown"
    
    # Определение по портам
    web_ports = [80, 443, 8080, 8443]
    ssh_ports = [22]
    db_ports = [3306, 5432, 1433, 27017, 6379, 1521]
    mail_ports = [25, 465, 587, 993, 995, 110, 143]
    file_sharing_ports = [445, 139, 21, 20]
    monitoring_ports = [161, 162, 10050, 10051]
    
    has_web = any(p in ports for p in web_ports)
    has_ssh = any(p in ports for p in ssh_ports)
    has_db = any(p in ports for p in db_ports)
    has_mail = any(p in ports for p in mail_ports)
    has_file_sharing = any(p in ports for p in file_sharing_ports)
    has_monitoring = any(p in ports for p in monitoring_ports)
    
    if has_db:
        role = "database_server"
        tags.append("database")
    elif has_web and has_db:
        role = "web_application_server"
        tags.extend(["web", "database"])
    elif has_web:
        role = "web_server"
        tags.append("web")
    elif has_mail:
        role = "mail_server"
        tags.append("mail")
    elif has_file_sharing:
        role = "file_server"
        tags.append("file_sharing")
    elif has_monitoring:
        role = "monitoring_server"
        tags.append("monitoring")
    elif has_ssh and len(ports) > 10:
        role = "server"
        tags.append("server")
    elif has_ssh:
        role = "linux_host"
        tags.append("linux")
    elif 445 in ports or 139 in ports:
        role = "windows_host"
        tags.append("windows")
    
    # Дополнительные теги
    if 22 in ports:
        tags.append("ssh")
    if 3389 in ports:
        tags.append("rdp")
        if role == "unknown":
            role = "windows_host"
    if 80 in ports or 443 in ports:
        tags.append("http")
    if 21 in ports:
        tags.append("ftp")
    
    return {"role": role, "tags": list(set(tags))}


def build_group_tree(groups: List[Any]) -> List[Dict]:
    """
    Построить дерево групп из плоского списка.
    
    Args:
        groups: Список объектов Group
    
    Returns:
        Список словарей с древовидной структурой
    """
    def group_to_dict(g):
        if hasattr(g, 'to_dict'):
            return g.to_dict()
        return {'id': g.id, 'name': g.name, 'assets_count': getattr(g, 'assets_count', 0)}
    
    groups_dict = {}
    for g in groups:
        data = group_to_dict(g)
        data['children'] = []
        groups_dict[g.id] = data
    
    tree = []
    
    for group in groups:
        group_data = groups_dict[group.id]
        if group.parent_id is None:
            tree.append(group_data)
        else:
            parent = groups_dict.get(group.parent_id)
            if parent:
                parent['children'].append(group_data)
            else:
                # Если родитель не найден, добавляем в корень
                tree.append(group_data)
    
    return tree


def build_complex_query(
    base_query,
    filters: Optional[Dict[str, Any]] = None,
    search: Optional[str] = None,
    group_id: Optional[int] = None,
    ungrouped: bool = False
):
    """
    Построить сложный запрос с фильтрами.
    
    Args:
        base_query: Базовый SQLAlchemy запрос
        filters: Словарь фильтров {поле: значение}
        search: Поисковая строка
        group_id: ID группы для фильтрации
        ungrouped: Фильтровать только активы без группы
    
    Returns:
        Модифицированный запрос
    """
    from backend.models.asset import Asset
    from backend.models.group import AssetGroup
    
    query = base_query
    
    if filters:
        for field, value in filters.items():
            if hasattr(Asset, field):
                column = getattr(Asset, field)
                if isinstance(value, list):
                    query = query.where(column.in_(value))
                else:
                    query = query.where(column == value)
    
    if search:
        query = query.where(
            (Asset.ip_address.ilike(f"%{search}%")) |
            (Asset.hostname.ilike(f"%{search}%")) |
            (Asset.mac_address.ilike(f"%{search}%")) |
            (Asset.fqdn.ilike(f"%{search}%"))
        )
    
    if ungrouped:
        # Активы без группы
        query = query.where(Asset.group_id.is_(None))
    elif group_id is not None:
        # Включая подгруппы
        from sqlalchemy.orm import aliased
        sub_group = aliased(AssetGroup)
        query = query.join(
            sub_group,
            (Asset.group_id == sub_group.id) | 
            (sub_group.path.like(f"%/{group_id}/%"))
        )
    
    return query


def generate_asset_taxonomy(asset: Any) -> Dict[str, Any]:
    """
    Сгенерировать таксономию актива (классификацию).
    
    Args:
        asset: Экземпляр модели Asset
    
    Returns:
        Словарь с таксономией
    """
    taxonomy = {
        'ip_version': 'ipv6' if ':' in asset.ip_address else 'ipv4',
        'has_hostname': bool(asset.hostname or asset.fqdn),
        'has_mac': bool(asset.mac_address),
        'port_count': len(asset.open_ports) if hasattr(asset, 'open_ports') and asset.open_ports else 0,
        'status': asset.status,
        'device_type': asset.device_type,
        'group_name': asset.group.name if hasattr(asset, 'group') and asset.group else None,
    }
    
    # Классификация по портам
    if hasattr(asset, 'open_ports') and asset.open_ports:
        ports = asset.open_ports
        taxonomy['has_web'] = any(p in [80, 443, 8080, 8443] for p in ports)
        taxonomy['has_ssh'] = 22 in ports
        taxonomy['has_rdp'] = 3389 in ports
        taxonomy['has_database'] = any(p in [3306, 5432, 1433, 27017, 6379] for p in ports)
        taxonomy['has_mail'] = any(p in [25, 465, 587, 993, 995] for p in ports)
        taxonomy['has_ftp'] = 21 in ports
        taxonomy['has_smb'] = any(p in [445, 139] for p in ports)
        
        # Определение роли
        role_info = detect_device_role_and_tags(asset)
        taxonomy['detected_role'] = role_info['role']
        taxonomy['detected_tags'] = role_info['tags']
    
    return taxonomy