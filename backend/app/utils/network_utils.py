"""
Утилиты для работы с сетью.
"""
import ipaddress
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)


async def create_cidr_groups(
    db: AsyncSession,
    cidr_list: List[str],
    parent_id: Optional[int] = None
) -> List[Any]:
    """
    Создать группы для CIDR подсетей.
    
    Args:
        db: Сессия базы данных
        cidr_list: Список CIDR нотаций (например, ["192.168.1.0/24"])
        parent_id: ID родительской группы (опционально)
    
    Returns:
        Список созданных групп
    """
    from app.models.group import AssetGroup
    
    created_groups = []
    
    for cidr in cidr_list:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            group_name = str(network)
            
            # Проверяем, существует ли уже группа
            query = select(AssetGroup).where(AssetGroup.name == group_name)
            result = await db.execute(query)
            existing_group = result.scalar_one_or_none()
            
            if existing_group:
                logger.debug(f"Группа {group_name} уже существует")
                created_groups.append(existing_group)
                continue
            
            # Создаём новую группу
            group = AssetGroup(
                name=group_name,
                description=f"CIDR группа для {cidr}",
                parent_id=parent_id,
                is_dynamic=False
            )
            db.add(group)
            await db.flush()
            await db.refresh(group)
            
            created_groups.append(group)
            logger.info(f"Создана CIDR группа: {group_name}")
            
        except ValueError as e:
            logger.error(f"Неверный CIDR формат {cidr}: {e}")
            continue
    
    await db.commit()
    return created_groups


def ip_in_cidr(ip_address: str, cidr: str) -> bool:
    """
    Проверить, принадлежит ли IP адрес к CIDR подсети.
    
    Args:
        ip_address: IP адрес
        cidr: CIDR нотация
    
    Returns:
        True если IP принадлежит подсети
    """
    try:
        ip = ipaddress.ip_address(ip_address)
        network = ipaddress.ip_network(cidr, strict=False)
        return ip in network
    except ValueError:
        return False


def get_network_info(cidr: str) -> Optional[Dict[str, Any]]:
    """
    Получить информацию о сети.
    
    Args:
        cidr: CIDR нотация
    
    Returns:
        Словарь с информацией о сети или None если ошибка
    """
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        return {
            'network': str(network),
            'netmask': str(network.netmask),
            'broadcast': str(network.broadcast_address),
            'num_hosts': network.num_addresses,
            'first_host': str(network[1]) if network.num_addresses > 1 else str(network[0]),
            'last_host': str(network[-2]) if network.num_addresses > 1 else str(network[0]),
            'version': network.version
        }
    except ValueError as e:
        logger.error(f"Ошибка при получении информации о сети {cidr}: {e}")
        return None
