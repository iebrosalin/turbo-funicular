"""
Модели базы данных.
Импортируем все модели здесь, чтобы они были зарегистрированы в SQLAlchemy до создания таблиц.
"""

from backend.models.asset import Asset, asset_groups
from backend.models.group import Group
from backend.models.scan import Scan, ScanJob, ScanResult
from backend.models.log import ActivityLog
from backend.models.service import ServiceInventory
from backend.models.integration_settings import IntegrationSettings

__all__ = [
    'Asset',
    'asset_groups',
    'Group',
    'Scan',
    'ScanJob',
    'ScanResult',
    'ActivityLog',
    'ServiceInventory',
    'IntegrationSettings',
]
