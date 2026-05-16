"""
Репозитории для доступа к данным.
"""

from .base_repository import (
    BaseRepository,
    IAssetRepository,
    IScanRepository,
    IGroupRepository,
    IQueueRepository,
)

__all__ = [
    'BaseRepository',
    'IAssetRepository',
    'IScanRepository',
    'IGroupRepository',
    'IQueueRepository',
]
