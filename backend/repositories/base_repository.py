"""
Абстрактные классы для репозиториев.
Определяют контракты доступа к данным.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, TypeVar, Generic, Union
from datetime import datetime
import uuid

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """
    Абстрактный базовый класс для репозиториев.
    
    Реализует паттерн Repository для абстракции доступа к базе данных.
    """
    
    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        """Получение записи по ID."""
        pass
    
    @abstractmethod
    async def get_all(self, limit: int = 100000, offset: int = 0) -> List[T]:
        """Получение всех записей с пагинацией (лимит увеличен для поддержки больших выборок)."""
        pass
    
    @abstractmethod
    async def get_by_filter(self, **filters) -> List[T]:
        """Получение записей по фильтрам."""
        pass
    
    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> T:
        """Создание новой записи."""
        pass
    
    @abstractmethod
    async def update(self, id: int, data: Dict[str, Any]) -> Optional[T]:
        """Обновление записи."""
        pass
    
    @abstractmethod
    async def delete(self, id: int) -> bool:
        """Удаление записи."""
        pass
    
    @abstractmethod
    async def exists(self, id: int) -> bool:
        """Проверка существования записи."""
        pass
    
    @abstractmethod
    async def count(self, **filters) -> int:
        """Подсчет количества записей."""
        pass


class IAssetRepository(BaseRepository[Any], ABC):
    """Интерфейс репозитория активов."""
    
    @abstractmethod
    async def get_by_ip(self, ip: str) -> Optional[Any]:
        """Поиск актива по IP адресу."""
        pass
    
    @abstractmethod
    async def get_by_hostname(self, hostname: str) -> Optional[Any]:
        """Поиск актива по имени хоста."""
        pass
    
    @abstractmethod
    async def get_by_groups(self, group_ids: List[int]) -> List[Any]:
        """Получение активов из указанных групп."""
        pass
    
    @abstractmethod
    async def add_to_group(self, asset_id: int, group_id: int) -> bool:
        """Добавление актива в группу."""
        pass
    
    @abstractmethod
    async def remove_from_group(self, asset_id: int, group_id: int) -> bool:
        """Удаление актива из группы."""
        pass


class IScanRepository(BaseRepository[Any], ABC):
    """Интерфейс репозитория сканирований."""
    
    @abstractmethod
    async def get_by_status(self, status: str) -> List[Any]:
        """Получение сканирований по статусу."""
        pass
    
    @abstractmethod
    async def get_running_scans(self) -> List[Any]:
        """Получение активных сканирований."""
        pass
    
    @abstractmethod
    async def update_status(self, scan_id: uuid.UUID, status: str) -> bool:
        """Обновление статуса сканирования."""
        pass
    
    @abstractmethod
    async def add_result(self, scan_id: uuid.UUID, result: Dict[str, Any]) -> bool:
        """Добавление результата сканирования."""
        pass
    
    @abstractmethod
    async def get_results(self, scan_id: uuid.UUID) -> List[Any]:
        """Получение результатов сканирования."""
        pass
    
    @abstractmethod
    async def cancel(self, scan_id: uuid.UUID) -> bool:
        """Отмена сканирования."""
        pass


class IGroupRepository(BaseRepository[Any], ABC):
    """Интерфейс репозитория групп."""
    
    @abstractmethod
    async def get_with_assets(self, group_id: int) -> Optional[Any]:
        """Получение группы с активами."""
        pass
    
    @abstractmethod
    async def get_all_with_asset_counts(self) -> List[Dict[str, Any]]:
        """Получение всех групп с количеством активов."""
        pass
    
    @abstractmethod
    async def add_asset(self, group_id: int, asset_id: int) -> bool:
        """Добавление актива в группу."""
        pass
    
    @abstractmethod
    async def remove_asset(self, group_id: int, asset_id: int) -> bool:
        """Удаление актива из группы."""
        pass
    
    @abstractmethod
    async def get_assets(self, group_id: int) -> List[Any]:
        """Получение активов группы."""
        pass


class IQueueRepository(BaseRepository[Any], ABC):
    """Интерфейс репозитория очереди."""
    
    @abstractmethod
    async def enqueue(self, scan_id: uuid.UUID, priority: int = 0) -> bool:
        """Добавление сканирования в очередь."""
        pass
    
    @abstractmethod
    async def dequeue(self) -> Optional[uuid.UUID]:
        """Извлечение сканирования из очереди."""
        pass
    
    @abstractmethod
    async def get_position(self, scan_id: uuid.UUID) -> Optional[int]:
        """Получение позиции в очереди."""
        pass
    
    @abstractmethod
    async def remove(self, scan_id: uuid.UUID) -> bool:
        """Удаление сканирования из очереди."""
        pass
    
    @abstractmethod
    async def get_queue_length(self) -> int:
        """Получение длины очереди."""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """Очистка очереди."""
        pass
