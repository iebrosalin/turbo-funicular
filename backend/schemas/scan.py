from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ScanStatus(str, Enum):
    """Статусы сканирования."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanResultItem(BaseModel):
    """Схема результата сканирования по хосту."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    ip_address: str
    status: str
    ports: Optional[List[Any]] = None
    services: Optional[Dict[str, Any]] = None
    hostname: Optional[str] = None
    os_info: Optional[str] = None
    raw_output: Optional[str] = None
    scanned_at: Optional[datetime] = None


class ScanBase(BaseModel):
    """Базовая схема сканирования."""
    name: str = Field(..., min_length=1, max_length=255, description="Название сканирования")
    target: str = Field(..., description="Цель сканирования (IP, диапазон)")
    scan_type: Optional[str] = Field("nmap", description="Тип сканирования")
    group_id: Optional[int] = Field(None, description="ID группы")


class ScanCreate(ScanBase):
    """Схема для создания сканирования."""
    pass


class ScanUpdate(BaseModel):
    """Схема для обновления сканирования."""
    name: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None
    result: Optional[str] = None
    error_message: Optional[str] = None


class ScanResponse(ScanBase):
    """Схема ответа сканирования."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    status: str
    progress: int
    result: Optional[str] = None
    raw_output: Optional[str] = None  # Вывод утилиты
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    error_message: Optional[str] = None
