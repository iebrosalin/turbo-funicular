"""
Модели базы данных.
Импортируем все модели здесь, чтобы они были зарегистрированы в SQLAlchemy до создания таблиц.
"""

from models.asset import Asset, asset_groups
from models.group import Group
from models.scan import Scan, ScanJob, ScanResult
from models.log import ActivityLog, AssetChangeLog
from models.service import ServiceInventory

__all__ = [
    'Asset',
    'asset_groups',
    'Group',
    'Scan',
    'ScanJob',
    'ScanResult',
    'ActivityLog',
    'AssetChangeLog',
    'ServiceInventory',
]
