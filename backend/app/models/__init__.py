"""
Модели базы данных.
Импортируем все модели здесь, чтобы они были зарегистрированы в SQLAlchemy до создания таблиц.
"""

from app.models.asset import Asset, asset_groups
from app.models.group import Group
from app.models.scan import Scan, ScanJob, ScanResult
from app.models.log import ActivityLog, AssetChangeLog
from app.models.service import ServiceInventory

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
