"""
Абстрактные классы и интерфейсы для сохранения результатов сканирований.
Обеспечивают единую структуру для хранения и отдачи результатов через API.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ScanResultData(BaseModel):
    """Базовая модель данных результата сканирования."""
    ip_address: str
    hostname: Optional[str] = None
    ports: List[Any] = Field(default_factory=list)
    services: Dict[str, Any] = Field(default_factory=dict)
    os_info: Optional[str] = None
    status: str = "pending"
    raw_output: Optional[str] = None
    scanned_at: Optional[datetime] = None


class NmapScanResult(ScanResultData):
    """Результат сканирования Nmap с дополнительными полями."""
    output_xml: Optional[str] = None
    output_gnmap: Optional[str] = None
    output_normal: Optional[str] = None


class RustscanScanResult(ScanResultData):
    """Результат сканирования Rustscan."""
    pass


class DigScanResult(ScanResultData):
    """Результат сканирования Dig."""
    record_type: Optional[str] = None
    dns_records: List[Dict[str, Any]] = Field(default_factory=list)


class FpingScanResult(ScanResultData):
    """Результат сканирования Fping."""
    packets_sent: int = 0
    packets_received: int = 0
    packet_loss: float = 0.0
    avg_rtt: float = 0.0
    min_rtt: float = 0.0
    max_rtt: float = 0.0


class IScanResultStorage(ABC):
    """Интерфейс для хранилища результатов сканирований."""
    
    @abstractmethod
    async def save_result(self, scan_id: int, result_data: ScanResultData) -> int:
        """
        Сохранить результат сканирования.
        
        Args:
            scan_id: ID сканирования
            result_data: Данные результата
            
        Returns:
            ID сохраненного результата
        """
        pass
    
    @abstractmethod
    async def get_result(self, result_id: int) -> Optional[ScanResultData]:
        """
        Получить результат по ID.
        
        Args:
            result_id: ID результата
            
        Returns:
            Данные результата или None
        """
        pass
    
    @abstractmethod
    async def get_results_by_scan(self, scan_id: int) -> List[ScanResultData]:
        """
        Получить все результаты для сканирования.
        
        Args:
            scan_id: ID сканирования
            
        Returns:
            Список результатов
        """
        pass
    
    @abstractmethod
    async def update_result(self, result_id: int, **kwargs) -> bool:
        """
        Обновить результат.
        
        Args:
            result_id: ID результата
            **kwargs: Поля для обновления
            
        Returns:
            True если успешно
        """
        pass
    
    @abstractmethod
    async def delete_result(self, result_id: int) -> bool:
        """
        Удалить результат.
        
        Args:
            result_id: ID результата
            
        Returns:
            True если успешно
        """
        pass


class IScanResultFormatter(ABC):
    """Интерфейс для форматирования результатов сканирований."""
    
    @abstractmethod
    def format_raw(self, results: List[ScanResultData]) -> str:
        """Форматировать в сырой текст."""
        pass
    
    @abstractmethod
    def format_json(self, results: List[ScanResultData]) -> str:
        """Форматировать в JSON."""
        pass
    
    @abstractmethod
    def format_xml(self, results: List[ScanResultData]) -> str:
        """Форматировать в XML."""
        pass
    
    @abstractmethod
    def format_gnmap(self, results: List[ScanResultData]) -> str:
        """Форматировать в Grepable/Nmap формат."""
        pass
    
    @abstractmethod
    def format_normal(self, results: List[ScanResultData]) -> str:
        """Форматировать в Normal формат."""
        pass


class BaseScanResultStorage(IScanResultStorage):
    """Базовый класс для хранилища результатов сканирований."""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    async def save_result(self, scan_id: int, result_data: ScanResultData) -> int:
        """Реализация по умолчанию - выбрасывает NotImplementedError."""
        raise NotImplementedError("Метод save_result должен быть реализован в подклассе")
    
    async def get_result(self, result_id: int) -> Optional[ScanResultData]:
        """Реализация по умолчанию - выбрасывает NotImplementedError."""
        raise NotImplementedError("Метод get_result должен быть реализован в подклассе")
    
    async def get_results_by_scan(self, scan_id: int) -> List[ScanResultData]:
        """Реализация по умолчанию - выбрасывает NotImplementedError."""
        raise NotImplementedError("Метод get_results_by_scan должен быть реализован в подклассе")
    
    async def update_result(self, result_id: int, **kwargs) -> bool:
        """Реализация по умолчанию - выбрасывает NotImplementedError."""
        raise NotImplementedError("Метод update_result должен быть реализован в подклассе")
    
    async def delete_result(self, result_id: int) -> bool:
        """Реализация по умолчанию - выбрасывает NotImplementedError."""
        raise NotImplementedError("Метод delete_result должен быть реализован в подклассе")


class BaseScanResultFormatter(IScanResultFormatter):
    """Базовый класс для форматирования результатов сканирований."""
    
    def format_raw(self, results: List[ScanResultData]) -> str:
        """Форматировать в сырой текст."""
        raw_output = ""
        for result in results:
            if result.raw_output:
                raw_output += f"# Host: {result.ip_address}\n"
                raw_output += result.raw_output
                raw_output += "\n\n"
        return raw_output
    
    def format_json(self, results: List[ScanResultData]) -> str:
        """Форматировать в JSON."""
        import json
        data = []
        for r in results:
            item = {
                "ip_address": r.ip_address,
                "hostname": r.hostname,
                "ports": r.ports,
                "services": r.services,
                "os_info": r.os_info,
                "status": r.status,
            }
            if r.raw_output:
                item["raw_output"] = r.raw_output
            data.append(item)
        return json.dumps(data, indent=2)
    
    def format_xml(self, results: List[ScanResultData]) -> str:
        """Форматировать в XML."""
        # Реализация по умолчанию - пустая строка
        return ""
    
    def format_gnmap(self, results: List[ScanResultData]) -> str:
        """Форматировать в Grepable/Nmap формат."""
        # Реализация по умолчанию - пустая строка
        return ""
    
    def format_normal(self, results: List[ScanResultData]) -> str:
        """Форматировать в Normal формат."""
        # Реализация по умолчанию - пустая строка
        return ""
