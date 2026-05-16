import asyncio
import logging
import os
import tempfile
import shutil
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, List, Literal, Protocol, runtime_checkable
from backend.models.target import Target

logger = logging.getLogger(__name__)


class ScanResult(Dict[str, Any]):
    """Типизированный словарь результатов сканирования"""
    pass


@runtime_checkable
class SingleTargetScanner(Protocol):
    """
    Протокол для сканеров, работающих с одиночными целями.
    
    Атрибуты:
        SUPPORTS_MULTIPLE_TARGETS: Должен быть False
    """
    SCANNER_NAME: str
    SUPPORTS_MULTIPLE_TARGETS: bool  # Проверка значения делается вручную
    DEFAULT_TIMEOUT: int
    
    async def scan(self) -> ScanResult:
        """Выполняет сканирование одиночной цели"""
        ...
    
    def _parse_output(self, stdout: str, stderr: str = "") -> ScanResult:
        """Парсит вывод утилиты сканирования"""
        ...


@runtime_checkable
class MultiTargetScanner(Protocol):
    """
    Протокол для сканеров, работающих с множественными целями.
    
    Атрибуты:
        SUPPORTS_MULTIPLE_TARGETS: Должен быть True
    """
    SCANNER_NAME: str
    SUPPORTS_MULTIPLE_TARGETS: bool  # Проверка значения делается вручную
    DEFAULT_TIMEOUT: int
    
    async def scan(self, targets: Optional[List[Union[str, Target]]] = None) -> ScanResult:
        """
        Выполняет сканирование множества целей.
        
        Args:
            targets: Список целей для сканирования. Если None, используется цель из конструктора.
        """
        ...
    
    def _parse_output(self, stdout: str, stderr: str = "") -> ScanResult:
        """Парсит вывод утилиты сканирования"""
        ...


def is_single_target_scanner(scanner) -> bool:
    """
    Проверяет, является ли сканер одиночным (SingleTarget).
    
    Args:
        scanner: Экземпляр сканера
        
    Returns:
        bool: True если сканер работает с одиночными целями
    """
    return (
        isinstance(scanner, BaseScanner) and
        not scanner.SUPPORTS_MULTIPLE_TARGETS and
        hasattr(scanner, 'scan') and
        hasattr(scanner, '_parse_output')
    )


def is_multi_target_scanner(scanner) -> bool:
    """
    Проверяет, является ли сканер множественным (MultiTarget).
    
    Args:
        scanner: Экземпляр сканера
        
    Returns:
        bool: True если сканер работает с множественными целями
    """
    return (
        isinstance(scanner, BaseScanner) and
        scanner.SUPPORTS_MULTIPLE_TARGETS and
        hasattr(scanner, 'scan') and
        hasattr(scanner, '_parse_output')
    )


class BaseScanner(ABC):
    """
    Абстрактный базовый класс для всех сканеров.
    
    Определяет единый интерфейс и общую логику для:
    - Работы с одиночными и множественными целями
    - Управления временными файлами
    - Логирования
    - Парсинга результатов
    
    Подклассы должны реализовать:
    - SCANNER_NAME: str - имя сканера
    - SUPPORTS_MULTIPLE_TARGETS: bool - поддержка множественных целей
    - scan() - метод выполнения сканирования
    - _parse_output() - метод парсинга вывода
    """
    
    # Конфигурация сканера (должна быть переопределена в подклассах)
    SCANNER_NAME: str = "base"
    SUPPORTS_MULTIPLE_TARGETS: bool = False
    DEFAULT_TIMEOUT: int = 300
    
    def __init__(
        self, 
        job_id: int, 
        target: Union[str, Target], 
        output_dir: Optional[str] = None
    ):
        """
        Инициализация базового сканера.
        
        Args:
            job_id: ID задачи сканирования
            target: Цель сканирования (строка или объект Target)
            output_dir: Директория для вывода (опционально, используется только для временных файлов)
        """
        self.job_id = job_id
        
        # Директория для временных файлов результатов
        self.output_dir = output_dir or os.getenv('SCANNER_OUTPUT_DIR', '/app/scanner_output')
        self.temp_dir: Optional[str] = None
        
        # Конвертируем строку в Target если нужно
        if isinstance(target, str):
            self.target_obj = Target.from_string(target)
        elif isinstance(target, Target):
            self.target_obj = target
        else:
            raise ValueError(f"target должен быть str или Target, получен {type(target)}")
        
        # Для обратной совместимости оставляем target как строку
        self.target = self.target_obj.value
    
    @abstractmethod
    async def scan(self) -> ScanResult:
        """
        Выполняет сканирование цели.
        
        Returns:
            ScanResult: Словарь с результатами сканирования
            
        Raises:
            NotImplementedError: Если метод не реализован в наследнике
            Exception: Ошибка выполнения сканирования
        """
        raise NotImplementedError("Метод scan должен быть реализован в наследнике")
    
    @abstractmethod
    def _parse_output(self, stdout: str, stderr: str = "") -> ScanResult:
        """
        Парсит вывод утилиты сканирования.
        
        Args:
            stdout: Вывод stdout утилиты
            stderr: Вывод stderr утилиты
            
        Returns:
            ScanResult: Распарсенные результаты
            
        Raises:
            NotImplementedError: Если метод не реализован в наследнике
        """
        raise NotImplementedError("Метод _parse_output должен быть реализован в наследнике")
    
    def _create_temp_dir(self, prefix: Optional[str] = None) -> str:
        """
        Создает временную директорию для файлов результатов.
        
        Args:
            prefix: Префикс имени директории
            
        Returns:
            str: Путь к созданной директории
        """
        if prefix is None:
            prefix = f"{self.SCANNER_NAME}_job_{self.job_id}_"
        
        self.temp_dir = tempfile.mkdtemp(prefix=prefix)
        logger.info(f"[{self.__class__.__name__}] Создана временная директория: {self.temp_dir}")
        return self.temp_dir
    
    def _cleanup_temp_dir(self):
        """Очищает временную директорию с файлами результатов"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"[{self.__class__.__name__}] Временная директория удалена: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"[{self.__class__.__name__}] Не удалось удалить временную директорию: {e}")
    
    def _read_file_content(self, file_path: str, label: str = "Файл") -> str:
        """
        Читает содержимое файла.
        
        Args:
            file_path: Путь к файлу
            label: Метка для логирования
            
        Returns:
            str: Содержимое файла или пустая строка
        """
        if not os.path.exists(file_path):
            logger.error(f"[{self.__class__.__name__}] Файл {label} не найден: {file_path}")
            return ""
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            file_size = os.path.getsize(file_path)
            logger.info(f"[{self.__class__.__name__}] Прочитан {label}, размер: {file_size} байт")
            
            if file_size == 0:
                logger.warning(f"[{self.__class__.__name__}] Файл {label} пустой!")
            
            return content
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Ошибка чтения файла {label}: {e}", exc_info=True)
            raise
    
    def get_target_info(self) -> Dict[str, Any]:
        """Возвращает информацию о цели сканирования"""
        return self.target_obj.to_dict()
    
    def get_scanner_info(self) -> Dict[str, Any]:
        """Возвращает информацию о сканере"""
        return {
            "name": self.SCANNER_NAME,
            "class": self.__class__.__name__,
            "supports_multiple_targets": self.SUPPORTS_MULTIPLE_TARGETS,
            "default_timeout": self.DEFAULT_TIMEOUT,
            "protocol": "MultiTargetScanner" if self.SUPPORTS_MULTIPLE_TARGETS else "SingleTargetScanner"
        }
    
    async def __aenter__(self):
        """Контекстный менеджер: вход"""
        self._create_temp_dir()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: выход с очисткой"""
        self._cleanup_temp_dir()


def create_scanner_from_protocol(scanner_instance: BaseScanner):
    """
    Фабричная функция для определения типа сканера и приведения к протоколу.
    
    Args:
        scanner_instance: Экземпляр сканера
        
    Returns:
        Union[SingleTargetScanner, MultiTargetScanner]: Приведенный экземпляр
        
    Raises:
        TypeError: Если сканер не соответствует ни одному протоколу
    """
    if isinstance(scanner_instance, BaseScanner):
        if scanner_instance.SUPPORTS_MULTIPLE_TARGETS:
            # Проверяем соответствие протоколу MultiTargetScanner
            if hasattr(scanner_instance, 'scan') and hasattr(scanner_instance, '_parse_output'):
                return scanner_instance  # type: ignore
            raise TypeError(f"Сканер {scanner_instance.SCANNER_NAME} объявлен как MultiTarget, но не имеет необходимых методов")
        else:
            # Проверяем соответствие протоколу SingleTargetScanner
            if hasattr(scanner_instance, 'scan') and hasattr(scanner_instance, '_parse_output'):
                return scanner_instance  # type: ignore
            raise TypeError(f"Сканер {scanner_instance.SCANNER_NAME} объявлен как SingleTarget, но не имеет необходимых методов")
    
    raise TypeError(f"Неизвестный тип сканера: {type(scanner_instance)}")
