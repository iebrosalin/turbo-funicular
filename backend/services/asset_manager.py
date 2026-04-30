"""
Модуль унифицированных функций для управления активами при сканировании.
Используется всеми типами сканеров (Nmap, Rustscan, Dig).
"""
import logging
from datetime import datetime
from typing import Optional, List, Set, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
    scanner_name: str = "unknown"
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
    :return: Объект актива
    """
    stmt = select(Asset).where(Asset.ip_address == ip_address)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    
    now = datetime.now(MOSCOW_TZ)
    
    if not asset:
        logger.info(f"[{scanner_name}] Создание нового актива: {ip_address}")
        asset = Asset(
            ip_address=ip_address,
            hostname=hostname,
            mac_address=mac_address,
            vendor=vendor,
            os_family=os_family,
            os_version=os_version,
            status=status,
            last_seen=now
        )
        db.add(asset)
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
        
        asset.status = status
        asset.last_seen = now  # Обновляем дату последнего сканирования
        updated_fields.append(f"last_seen={now}")
        
        if updated_fields:
            logger.info(f"[{scanner_name}] Обновление актива {ip_address}: {', '.join(updated_fields)}")
        else:
            logger.debug(f"[{scanner_name}] Актив {ip_address} проверен, изменений нет")
    
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
        service = ServiceInventory(
            asset_id=asset.id,
            port=port,
            protocol=protocol,
            state=state,
            service_name=service_name,
            product=product,
            version=version,
            extra_info=extra_info,
            script_output=script_output,
            ssl_subject=ssl_subject,
            ssl_issuer=ssl_issuer,
            discovered_at=datetime.now(MOSCOW_TZ)
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
        service.script_output = script_output
        service.ssl_subject = ssl_subject
        service.ssl_issuer = ssl_issuer
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
    :param scanner_type: Тип порта ('nmap', 'rustscan', 'masscan')
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
    elif scanner_type == 'masscan':
        asset.masscan_ports = list(all_ports)
    else:
        # Для неизвестного типа используем open_ports как fallback
        asset.open_ports = list(all_ports)
    
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
