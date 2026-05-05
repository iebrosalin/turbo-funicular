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


# ==========================================
# Схемы для RedCheck сканирований
# ==========================================

class RedCheckScanStatus(str, Enum):
    """Статусы сканирования RedCheck."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RedCheckScanBase(BaseModel):
    """Базовая схема сканирования RedCheck."""
    name: Optional[str] = Field(None, max_length=255, description="Название сканирования")
    scan_type: Optional[str] = Field(None, description="Тип сканирования")
    profile_id: Optional[int] = Field(None, description="ID профиля")
    profile_name: Optional[str] = Field(None, description="Название профиля")
    target_id: Optional[int] = Field(None, description="ID цели")
    target_name: Optional[str] = Field(None, description="Название цели")
    host_group_id: Optional[int] = Field(None, description="ID группы хостов")
    description: Optional[str] = Field(None, description="Описание")


class RedCheckScanCreate(RedCheckScanBase):
    """Схема для создания записи сканирования RedCheck."""
    redcheck_job_id: Optional[int] = None
    redcheck_report_id: Optional[int] = None
    report_format: Optional[str] = None


class RedCheckScanUpdate(BaseModel):
    """Схема для обновления сканирования RedCheck."""
    status: Optional[str] = None
    progress: Optional[int] = None
    redcheck_job_id: Optional[int] = None
    redcheck_report_id: Optional[int] = None
    report_format: Optional[str] = None
    report_status: Optional[str] = None
    vulnerabilities_count: Optional[int] = None
    critical_count: Optional[int] = None
    high_count: Optional[int] = None
    medium_count: Optional[int] = None
    low_count: Optional[int] = None
    hosts_scanned: Optional[int] = None
    hosts_failed: Optional[int] = None
    error_message: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class RedCheckScanResponse(RedCheckScanBase):
    """Схема ответа сканирования RedCheck."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    redcheck_job_id: Optional[int] = None
    status: str
    progress: int
    redcheck_report_id: Optional[int] = None
    report_format: Optional[str] = None
    report_status: Optional[str] = None
    vulnerabilities_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    hosts_scanned: int
    hosts_failed: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None
