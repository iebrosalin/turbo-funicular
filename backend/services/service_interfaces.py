"""
Абстрактные классы для сервисов.
Определяют контракты бизнес-логики приложения.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import uuid

from ..models.target import Target
from ..models.scan import ScanResult, Scan
from ..models.asset import Asset
from ..models.group import Group


class IAssetService(ABC):
    """Интерфейс сервиса управления активами."""
    
    @abstractmethod
    async def get_assets_from_groups(self, group_ids: List[int]) -> List[Asset]:
        """Получение активов из указанных групп."""
        pass
    
    @abstractmethod
    async def get_asset_by_id(self, asset_id: int) -> Optional[Asset]:
        """Получение актива по ID."""
        pass
    
    @abstractmethod
    async def get_assets_by_filter(self, **filters) -> List[Asset]:
        """Получение активов по фильтрам."""
        pass
    
    @abstractmethod
    async def create_asset(self, asset_data: Dict[str, Any]) -> Asset:
        """Создание нового актива."""
        pass
    
    @abstractmethod
    async def update_asset(self, asset_id: int, asset_data: Dict[str, Any]) -> Optional[Asset]:
        """Обновление актива."""
        pass
    
    @abstractmethod
    async def delete_asset(self, asset_id: int) -> bool:
        """Удаление актива."""
        pass


class IScanService(ABC):
    """Интерфейс сервиса сканирования."""
    
    @abstractmethod
    async def create_scan(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создание новой задачи сканирования."""
        pass
    
    @abstractmethod
    async def get_scan_status(self, scan_id: uuid.UUID) -> Dict[str, Any]:
        """Получение статуса сканирования."""
        pass
    
    @abstractmethod
    async def get_scan_results(self, scan_id: uuid.UUID) -> List[ScanResult]:
        """Получение результатов сканирования."""
        pass
    
    @abstractmethod
    async def cancel_scan(self, scan_id: uuid.UUID) -> bool:
        """Отмена сканирования."""
        pass
    
    @abstractmethod
    async def scan_from_csv_text(self, csv_text: str, scan_params: Dict[str, Any]) -> Dict[str, Any]:
        """Сканирование целей из CSV текста."""
        pass
    
    @abstractmethod
    async def scan_from_csv_file(self, file_path: Path, scan_params: Dict[str, Any]) -> Dict[str, Any]:
        """Сканирование целей из CSV файла."""
        pass
    
    @abstractmethod
    async def scan_from_groups(self, group_ids: List[int], scan_params: Dict[str, Any]) -> Dict[str, Any]:
        """Сканирование активов из групп."""
        pass


class IGroupService(ABC):
    """Интерфейс сервиса управления группами."""
    
    @abstractmethod
    async def get_group_by_id(self, group_id: int) -> Optional[Group]:
        """Получение группы по ID."""
        pass
    
    @abstractmethod
    async def get_all_groups(self) -> List[Group]:
        """Получение всех групп."""
        pass
    
    @abstractmethod
    async def create_group(self, group_data: Dict[str, Any]) -> Group:
        """Создание новой группы."""
        pass
    
    @abstractmethod
    async def update_group(self, group_id: int, group_data: Dict[str, Any]) -> Optional[Group]:
        """Обновление группы."""
        pass
    
    @abstractmethod
    async def delete_group(self, group_id: int) -> bool:
        """Удаление группы."""
        pass
    
    @abstractmethod
    async def add_assets_to_group(self, group_id: int, asset_ids: List[int]) -> bool:
        """Добавление активов в группу."""
        pass
    
    @abstractmethod
    async def remove_assets_from_group(self, group_id: int, asset_ids: List[int]) -> bool:
        """Удаление активов из группы."""
        pass


class IQueueManager(ABC):
    """Интерфейс менеджера очереди сканирований."""
    
    @abstractmethod
    async def enqueue_scan(self, scan_id: uuid.UUID) -> uuid.UUID:
        """Добавление сканирования в очередь."""
        pass
    
    @abstractmethod
    async def dequeue_scan(self) -> Optional[uuid.UUID]:
        """Извлечение сканирования из очереди."""
        pass
    
    @abstractmethod
    async def get_queue_status(self) -> Dict[str, Any]:
        """Получение статуса очереди."""
        pass
    
    @abstractmethod
    async def cancel_queued_scan(self, scan_id: uuid.UUID) -> bool:
        """Отмена сканирования в очереди."""
        pass
    
    @abstractmethod
    async def get_position_in_queue(self, scan_id: uuid.UUID) -> Optional[int]:
        """Получение позиции сканирования в очереди."""
        pass
