"""
Модели базы данных для системы управления активами и сканированиями.
Включает модели для активов, групп, сканирований, сервисов и логов активности.
"""
from .base import asset_groups
from .asset import Asset
from .group import AssetGroup
from .service import ServiceInventory
from .scan import ScanJob, ScanResult
from .log import ActivityLog, AssetChangeLog

__all__ = [
    'Asset',
    'AssetGroup',
    'ServiceInventory',
    'ScanJob',
    'ScanResult',
    'ActivityLog',
    'AssetChangeLog',
    'asset_groups'
]