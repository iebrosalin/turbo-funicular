"""
Модуль унифицированных функций для управления активами при сканировании.
Используется всеми типами сканеров (Nmap, Rustscan, Dig).
"""
import logging
from datetime import datetime
from typing import Optional, List, Set, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.asset import Asset
from backend.models.service import ServiceInventory
from backend.utils import MOSCOW_TZ

logger = logging.getLogger(__name__)


async def upsert_asset(
    db: AsyncSession,
    ip_address: str,
    hostname: Optional[str] = None,
    mac_address: Optional[str] = None,
    vendor: Optional[str] = None,
    os_family: Optional[str] = None,
    os_version: Optional[str] = None,
    status: str = "up",
    scanner_name: str = "unknown",
    group_ids: Optional[List[int]] = None,
    open_ports: Optional[List[int]] = None
) -> Asset:
    """
    Создать или обновить актив.
    
    :param db: Сессия базы данных
    :param ip_address: IP адрес актива
    :param hostname: Имя хоста (опционально)
    :param mac_address: MAC адрес (опционально)
    :param vendor: Производитель (опционально)
    :param os_family: Семейство ОС (опционально)
    :param os_version: Версия ОС (опционально)
    :param status: Статус актива
    :param scanner_name: Имя сканера для логирования
    :param group_ids: Список ID групп для добавления актива (опционально)
    :param open_ports: Список открытых портов для определения активности (опционально)
    :return: Объект актива
    """
    # Явно загружаем актив со связями чтобы избежать ленивой загрузки
    stmt = select(Asset).options(selectinload(Asset.groups)).where(Asset.ip_address == ip_address)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    
    now = datetime.now(MOSCOW_TZ)
    
    # Определяем активность по наличию открытых портов
    has_open_ports = open_ports is not None and len(open_ports) > 0
    
    if not asset:
        logger.info(f"[{scanner_name}] Создание нового актива: {ip_address}")
        # Новый актив: статус зависит от наличия открытых портов
        asset_status = 'active' if has_open_ports else 'inactive'
        asset = Asset(
            ip_address=ip_address,
            hostname=hostname,
            mac_address=mac_address,
            vendor=vendor,
            os_family=os_family,
            os_version=os_version,
            status=asset_status,
            open_ports=open_ports or [],
            rustscan_ports=open_ports if scanner_name.lower() == 'rustscan' else [],
            nmap_ports=open_ports if scanner_name.lower() == 'nmap' else []
        )
        asset.last_seen = now
        # Устанавливаем временную метку для соответствующего сканера
        if scanner_name.lower() == 'rustscan':
            asset.last_rustscan = now
        elif scanner_name.lower() == 'nmap':
            asset.last_nmap = now
        elif scanner_name.lower() == 'dig':
            asset.last_dns_scan = now
        db.add(asset)
        logger.info(f"[{scanner_name}] Актив {ip_address} создан со статусом {asset_status}")
    else:
        updated_fields = []
        
        if hostname and not asset.hostname:
            asset.hostname = hostname
            updated_fields.append(f"hostname={hostname}")
        
        if mac_address and asset.mac_address != mac_address:
            asset.mac_address = mac_address
            updated_fields.append(f"mac={mac_address}")
        
        if vendor and asset.vendor != vendor:
            asset.vendor = vendor
            updated_fields.append(f"vendor={vendor}")
        
        if os_family and not asset.os_family:
            asset.os_family = os_family
            updated_fields.append(f"os_family={os_family}")
        
        if os_version and not asset.os_version:
            asset.os_version = os_version
            updated_fields.append(f"os_version={os_version}")
        
        # Обновляем открытые порты если переданы (rustscan_ports и nmap_ports)
        if open_ports is not None:
            # Определяем какой тип портов обновлять на основе имени сканера
            if scanner_name.lower() == 'rustscan':
                asset.rustscan_ports = open_ports
                asset.last_rustscan = now
                updated_fields.append(f"rustscan_ports={len(open_ports)}")
                updated_fields.append(f"last_rustscan={now}")
            elif scanner_name.lower() == 'nmap':
                asset.nmap_ports = open_ports
                asset.last_nmap = now
                updated_fields.append(f"nmap_ports={len(open_ports)}")
                updated_fields.append(f"last_nmap={now}")
            elif scanner_name.lower() == 'dig':
                asset.last_dns_scan = now
                updated_fields.append(f"last_dns_scan={now}")
        
        # Обновляем статус актива на основе наличия открытых портов
        if has_open_ports:
            asset.status = 'active'
        else:
            asset.status = 'inactive'
        updated_fields.append(f"status={asset.status}")
        
        asset.last_seen = now  # Обновляем дату последнего сканирования
        updated_fields.append(f"last_seen={now}")
        
        if updated_fields:
            logger.info(f"[{scanner_name}] Обновление актива {ip_address}: {', '.join(updated_fields)}")
        else:
            logger.debug(f"[{scanner_name}] Актив {ip_address} проверен, изменений нет")
    
    # Добавляем актив в группы если указаны group_ids
    if group_ids:
        from backend.models.group import Group
        stmt = select(Group).where(Group.id.in_(group_ids))
        result = await db.execute(stmt)
        groups = result.scalars().all()
        
        # Получаем текущие группы актива
        current_group_ids = {g.id for g in asset.groups}
        
        # Добавляем только те группы, в которых актива ещё нет
        for group in groups:
            if group.id not in current_group_ids:
                asset.groups.append(group)
                logger.info(f"[{scanner_name}] Актив {ip_address} добавлен в группу {group.name}")
    
    await db.flush()
    return asset


async def upsert_service(
    db: AsyncSession,
    asset: Asset,
    port: int,
    protocol: str,
    state: str = "open",
    service_name: str = "unknown",
    product: str = "",
    version: str = "",
    extra_info: str = "",
    script_output: str = "",
    ssl_subject: Optional[str] = None,
    ssl_issuer: Optional[str] = None,
    scanner_name: str = "unknown"
) -> ServiceInventory:
    """
    Создать или обновить сервис на порту.
    
    :param db: Сессия базы данных
    :param asset: Объект актива
    :param port: Номер порта
    :param protocol: Протокол (tcp/udp)
    :param state: Состояние порта
    :param service_name: Имя сервиса
    :param product: Продукт
    :param version: Версия
    :param extra_info: Дополнительная информация
    :param script_output: Вывод скриптов
    :param ssl_subject: Subject SSL сертификата
    :param ssl_issuer: Issuer SSL сертификата
    :param scanner_name: Имя сканера для логирования
    :return: Объект сервиса
    """
    stmt = select(ServiceInventory).where(
        ServiceInventory.asset_id == asset.id,
        ServiceInventory.port == port,
        ServiceInventory.protocol == protocol
    )
    result = await db.execute(stmt)
    service = result.scalar_one_or_none()
    
    if not service:
        logger.info(
            f"[{scanner_name}] Создание сервиса {service_name} на {asset.ip_address}:{port}/{protocol}"
        )
        
        # Обработка скриптов (преобразование строки JSON в список, если нужно)
        scripts_data = []
        if script_output:
            try:
                if isinstance(script_output, str):
                    scripts_data = json.loads(script_output)
                else:
                    scripts_data = script_output
            except (json.JSONDecodeError, TypeError):
                scripts_data = script_output
        
        service = ServiceInventory(
            asset_id=asset.id,
            port=port,
            protocol=protocol,
            state=state,
            service_name=service_name,
            product=product,
            version=version,
            extra_info=extra_info,
            scripts=scripts_data,
            ssl_cert_subject=ssl_subject,
            ssl_cert_issuer=ssl_issuer,
            last_seen=datetime.now(MOSCOW_TZ)
        )
        db.add(service)
    else:
        updated_fields = []
        
        if service.state != state:
            service.state = state
            updated_fields.append(f"state={state}")
        
        if service.service_name != service_name:
            service.service_name = service_name
            updated_fields.append(f"service={service_name}")
        
        if service.product != product:
            service.product = product
            updated_fields.append(f"product={product}")
        
        if service.version != version:
            service.version = version
            updated_fields.append(f"version={version}")
        
        service.extra_info = extra_info
        
        # Обработка скриптов (преобразование строки JSON в список, если нужно)
        if script_output:
            try:
                if isinstance(script_output, str):
                    service.scripts = json.loads(script_output)
                else:
                    service.scripts = script_output
            except (json.JSONDecodeError, TypeError):
                service.scripts = script_output
        else:
            service.scripts = []
            
        service.ssl_cert_subject = ssl_subject
        service.ssl_cert_issuer = ssl_issuer
        service.last_seen = datetime.now(MOSCOW_TZ)
        
        if updated_fields:
            logger.info(
                f"[{scanner_name}] Обновление сервиса {service_name} на {asset.ip_address}:{port}/{protocol}: "
                f"{', '.join(updated_fields)}"
            )
        else:
            logger.debug(
                f"[{scanner_name}] Сервис {service_name} на {asset.ip_address}:{port}/{protocol} проверен, изменений нет"
            )
    
    await db.flush()
    return service


def update_asset_ports(
    asset: Asset,
    scanner_type: str,
    ports: List[int],
    scanner_name: str = "unknown"
) -> Set[int]:
    """
    Обновить список портов актива для указанного типа сканера.
    
    :param asset: Объект актива
    :param scanner_type: Тип порта ('nmap', 'rustscan')
    :param ports: Список найденных портов
    :param scanner_name: Имя сканера для логирования
    :return: Обновленное множество портов
    """
    current_ports = set(getattr(asset, f'{scanner_type}_ports') or [])
    new_ports = set(ports)
    
    added_ports = new_ports - current_ports
    if added_ports:
        logger.info(
            f"[{scanner_name}] Найдены новые порты для {asset.ip_address}: {sorted(added_ports)}"
        )
    
    all_ports = current_ports | new_ports
    
    # Обновляем соответствующий атрибут
    if scanner_type == 'nmap':
        asset.nmap_ports = list(all_ports)
    elif scanner_type == 'rustscan':
        asset.rustscan_ports = list(all_ports)
    else:
        # Для неизвестного типа используем nmap_ports как fallback
        asset.nmap_ports = list(all_ports)
    
    # Обновляем объединенный список open_ports
    all_source_ports = set(asset.nmap_ports or []) | set(asset.rustscan_ports or [])
    asset.open_ports = sorted(list(all_source_ports))
    
    # Обновляем статус актива на основе наличия открытых портов
    if len(all_source_ports) > 0:
        asset.status = 'active'
    else:
        asset.status = 'inactive'
    
    return all_ports


async def create_asset_if_not_exists(
    db: AsyncSession,
    ip_address: str,
    hostname: Optional[str] = None,
    scanner_name: str = "unknown"
) -> Optional[Asset]:
    """
    Устаревшая функция-обертка для обратной совместимости.
    Используйте upsert_asset для новой функциональности.
    """
    return await upsert_asset(
        db=db,
        ip_address=ip_address,
        hostname=hostname,
        scanner_name=scanner_name
    )
