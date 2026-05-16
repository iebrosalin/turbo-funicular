"""
Интерфейсы для источников данных (targets).
Поддерживает различные способы получения целей: CSV, файлы, группы активов.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Union, AsyncIterator
from pathlib import Path

from ..models.target import Target


class ITargetSource(ABC):
    """
    Интерфейс для источников целей.
    
    Позволяет унифицировать получение целей из различных источников:
    - CSV текст
    - CSV файлы
    - Группы активов
    - Комбинации источников
    """
    
    @abstractmethod
    async def get_targets(self) -> List[Target]:
        """
        Получение списка целей из источника.
        
        Returns:
            Список объектов Target
        """
        pass
    
    @abstractmethod
    async def get_targets_stream(self) -> AsyncIterator[Target]:
        """
        Потоковое получение целей (для больших списков).
        
        Yields:
            Объекты Target по одному
        """
        pass
    
    @property
    @abstractmethod
    def source_type(self) -> str:
        """Тип источника (csv_text, csv_file, groups, mixed)."""
        pass
    
    @property
    @abstractmethod
    def target_count(self) -> Optional[int]:
        """Количество целей (если известно заранее)."""
        pass


class ITargetValidator(ABC):
    """Интерфейс для валидаторов целей."""
    
    @abstractmethod
    def validate(self, target: str) -> bool:
        """Проверка валидности цели."""
        pass
    
    @abstractmethod
    def classify(self, target: str) -> str:
        """Определение типа цели (ipv4, ipv6, domain)."""
        pass


class ITargetTransformer(ABC):
    """Интерфейс для трансформеров целей."""
    
    @abstractmethod
    def transform(self, targets: List[str]) -> List[Target]:
        """Трансформация сырых строк в объекты Target."""
        pass
    
    @abstractmethod
    def deduplicate(self, targets: List[Target]) -> List[Target]:
        """Удаление дубликатов."""
        pass
