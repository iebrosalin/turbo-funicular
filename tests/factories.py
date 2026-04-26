"""
Фабрики для создания тестовых данных.
Используются для генерации объектов Asset, Group, Scan в тестах.
"""
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from backend.schemas.asset import AssetCreate
from backend.schemas.group import GroupCreate
from backend.schemas.scan import ScanCreate


def random_string(length: int = 8) -> str:
    """Генерирует случайную строку."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def create_test_asset_data(
    ip: Optional[str] = None,
    hostname: Optional[str] = None,
    group_id: Optional[int] = None,
    mac_address: Optional[str] = None,
    os_type: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> AssetCreate:
    """
    Создает данные для нового актива.
    """
    if ip is None:
        ip = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
    
    if hostname is None:
        hostname = f"host-{random_string()}"
    
    if mac_address is None:
        mac_address = ":".join([f"{random.randint(0, 255):02x}" for _ in range(6)])
    
    if os_type is None:
        os_type = random.choice(["Linux", "Windows", "macOS", "Unknown"])
    
    return AssetCreate(
        ip=ip,
        hostname=hostname,
        group_id=group_id,
        mac_address=mac_address,
        os_type=os_type,
        extra_data=extra_data or {}
    )


def create_test_group_data(
    name: Optional[str] = None,
    parent_id: Optional[int] = None,
    description: Optional[str] = None,
    group_type: str = "manual"
) -> GroupCreate:
    """
    Создает данные для новой группы.
    """
    if name is None:
        name = f"Group-{random_string()}"
    
    if description is None:
        description = f"Test group {name}"
    
    return GroupCreate(
        name=name,
        parent_id=parent_id,
        description=description,
        group_type=group_type
    )


def create_test_scan_data(
    target: Optional[str] = None,
    scan_type: str = "nmap",
    profile: str = "basic",
    status: str = "pending"
) -> Dict[str, Any]:
    """
    Создает данные для задачи сканирования.
    Возвращает словарь, так как схема может быть гибкой.
    """
    if target is None:
        target = f"192.168.1.{random.randint(1, 254)}"
    
    return {
        "target": target,
        "scan_type": scan_type,
        "profile": profile,
        "status": status,
        "started_at": datetime.now(),
        "finished_at": None,
        "results": None
    }
