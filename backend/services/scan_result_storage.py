"""
Абстрактные классы и интерфейсы для сохранения результатов сканирований.
Поддерживает различные хранилища: файловая система, база данных, облачные хранилища.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union, BinaryIO
from pathlib import Path
from datetime import datetime
import uuid


class ScanResultData:
    """Модель данных результата сканирования."""
    
    def __init__(
        self,
        scan_id: uuid.UUID,
        job_id: Optional[int] = None,
        ip_address: str = "",
        hostname: str = "",
        ports: Optional[List[Dict[str, Any]]] = None,
        services: Optional[List[Dict[str, Any]]] = None,
        os_info: str = "",
        status: str = "up",
        raw_output: str = "",
        output_normal: str = "",
        output_xml: str = "",
        output_gnmap: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.scan_id = scan_id
        self.job_id = job_id
        self.ip_address = ip_address
        self.hostname = hostname
        self.ports = ports or []
        self.services = services or []
        self.os_info = os_info
        self.status = status
        self.raw_output = raw_output
        self.output_normal = output_normal
        self.output_xml = output_xml
        self.output_gnmap = output_gnmap
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "scan_id": str(self.scan_id),
            "job_id": self.job_id,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "ports": self.ports,
            "services": self.services,
            "os_info": self.os_info,
            "status": self.status,
            "raw_output": self.raw_output,
            "output_normal": self.output_normal,
            "output_xml": self.output_xml,
            "output_gnmap": self.output_gnmap,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


class IScanResultStorage(ABC):
    """
    Интерфейс хранилища результатов сканирований.
    
    Определяет контракт для сохранения и извлечения результатов сканирований.
    Поддерживает различные реализации:
    - DatabaseStorage (SQLite/PostgreSQL)
    - FileSystemStorage (файлы на диске)
    - CloudStorage (S3, GCS, Azure Blob)
    - HybridStorage (комбинация подходов)
    """
    
    @abstractmethod
    async def save_result(self, result: ScanResultData) -> bool:
        """
        Сохранение результата сканирования.
        
        Args:
            result: Объект ScanResultData с данными сканирования
            
        Returns:
            True если сохранение успешно
        """
        pass
    
    @abstractmethod
    async def save_results_batch(self, results: List[ScanResultData]) -> int:
        """
        Пакетное сохранение результатов.
        
        Args:
            results: Список объектов ScanResultData
            
        Returns:
            Количество успешно сохранённых записей
        """
        pass
    
    @abstractmethod
    async def get_result(self, scan_id: uuid.UUID, ip_address: str) -> Optional[ScanResultData]:
        """
        Получение результата по ID сканирования и IP адресу.
        
        Args:
            scan_id: UUID сканирования
            ip_address: IP адрес или хост
            
        Returns:
            Объект ScanResultData или None
        """
        pass
    
    @abstractmethod
    async def get_all_results(self, scan_id: uuid.UUID) -> List[ScanResultData]:
        """
        Получение всех результатов для сканирования.
        
        Args:
            scan_id: UUID сканирования
            
        Returns:
            Список объектов ScanResultData
        """
        pass
    
    @abstractmethod
    async def delete_result(self, scan_id: uuid.UUID, ip_address: str) -> bool:
        """
        Удаление результата.
        
        Args:
            scan_id: UUID сканирования
            ip_address: IP адрес или хост
            
        Returns:
            True если удаление успешно
        """
        pass
    
    @abstractmethod
    async def delete_all_results(self, scan_id: uuid.UUID) -> int:
        """
        Удаление всех результатов для сканирования.
        
        Args:
            scan_id: UUID сканирования
            
        Returns:
            Количество удалённых записей
        """
        pass
    
    @abstractmethod
    async def export_results(
        self, 
        scan_id: uuid.UUID, 
        format: str,
        destination: Union[str, Path, BinaryIO]
    ) -> bool:
        """
        Экспорт результатов в файл.
        
        Args:
            scan_id: UUID сканирования
            format: Формат экспорта (json, xml, nmap, gnmap, raw, csv)
            destination: Путь к файлу или file-like объект
            
        Returns:
            True если экспорт успешен
        """
        pass


class IScanResultExporter(ABC):
    """
    Интерфейс экспортера результатов сканирований.
    
    Отвечает за конвертацию результатов в различные форматы.
    """
    
    @property
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """Список поддерживаемых форматов."""
        pass
    
    @abstractmethod
    def export(self, results: List[ScanResultData], format: str) -> Union[str, bytes]:
        """
        Экспорт результатов в указанный формат.
        
        Args:
            results: Список результатов
            format: Формат экспорта
            
        Returns:
            Строка или байты с экспортированными данными
        """
        pass
    
    @abstractmethod
    def get_content_type(self, format: str) -> str:
        """
        Получение MIME типа для формата.
        
        Args:
            format: Формат файла
            
        Returns:
            MIME тип (например, application/json)
        """
        pass
    
    @abstractmethod
    def get_file_extension(self, format: str) -> str:
        """
        Получение расширения файла для формата.
        
        Args:
            format: Формат файла
            
        Returns:
            Расширение файла (например, .json)
        """
        pass


class StorageError(Exception):
    """Исключение ошибки хранилища."""
    pass


class ExportError(Exception):
    """Исключение ошибки экспорта."""
    pass
