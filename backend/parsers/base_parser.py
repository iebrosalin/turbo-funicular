"""
Абстрактные классы и интерфейсы для парсеров результатов сканирования.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic
from pathlib import Path

from ..models.target import Target
from ..models.scan import ScanResult

T = TypeVar('T')


class BaseParser(ABC, Generic[T]):
    """
    Абстрактный базовый класс для парсеров результатов сканирования.
    
    Все парсеры должны наследовать этот класс и реализовать методы
    для преобразования сырых данных в структурированные результаты.
    """
    
    @abstractmethod
    def parse(self, raw_data: T) -> List[ScanResult]:
        """
        Парсинг сырых данных в список результатов сканирования.
        
        Args:
            raw_data: Сырые данные для парсинга (строка, байты, XML, JSON и т.д.)
            
        Returns:
            Список объектов ScanResult
        """
        pass
    
    @abstractmethod
    def parse_file(self, file_path: Path) -> List[ScanResult]:
        """
        Парсинг результатов из файла.
        
        Args:
            file_path: Путь к файлу с результатами
            
        Returns:
            Список объектов ScanResult
        """
        pass
    
    @abstractmethod
    def validate(self, raw_data: T) -> bool:
        """
        Валидация формата входных данных.
        
        Args:
            raw_data: Данные для валидации
            
        Returns:
            True если данные валидны, False иначе
        """
        pass
    
    @property
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """
        Список поддерживаемых форматов данных.
        
        Returns:
            Список расширений или MIME-типов
        """
        pass


class TextParser(BaseParser[str]):
    """Базовый класс для парсеров текстового вывода."""
    
    def validate(self, raw_data: str) -> bool:
        """Проверка что данные являются непустой строкой."""
        return isinstance(raw_data, str) and len(raw_data.strip()) > 0


class FileParser(BaseParser[Path]):
    """Базовый класс для парсеров файлов."""
    
    def validate(self, file_path: Path) -> bool:
        """Проверка существования файла и его читаемости."""
        return file_path.exists() and file_path.is_file()
