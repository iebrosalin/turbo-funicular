from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ProjectStatus(str, Enum):
    """Статусы проекта."""
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectPriority(str, Enum):
    """Приоритеты проекта."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReportType(str, Enum):
    """Типы отчётов."""
    GENERAL = "general"
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    VULNERABILITY = "vulnerability"


class ArtifactType(str, Enum):
    """Типы артефактов."""
    FILE = "file"
    SCREENSHOT = "screenshot"
    LOG = "log"
    EXPORT = "export"
    EVIDENCE = "evidence"


class SessionType(str, Enum):
    """Типы сессий сканирования."""
    MANUAL = "manual"
    AUTOMATED = "automated"
    SCHEDULED = "scheduled"


# ===== Project Schemas =====

class ProjectBase(BaseModel):
    """Базовая схема проекта."""
    name: str = Field(..., min_length=1, max_length=255, description="Название проекта")
    description: Optional[str] = Field(None, description="Описание проекта")
    customer: Optional[str] = Field(None, max_length=255, description="Заказчик")
    project_type: Optional[str] = Field("pentest", description="Тип проекта")
    status: Optional[ProjectStatus] = Field(ProjectStatus.PLANNING, description="Статус проекта")
    priority: Optional[ProjectPriority] = Field(ProjectPriority.MEDIUM, description="Приоритет")
    start_date: Optional[datetime] = Field(None, description="Дата начала")
    end_date: Optional[datetime] = Field(None, description="Дата окончания")
    group_ids: Optional[List[int]] = Field(None, description="ID групп активов")


class ProjectCreate(ProjectBase):
    """Схема для создания проекта."""
    pass


class ProjectUpdate(BaseModel):
    """Схема для обновления проекта."""
    name: Optional[str] = None
    description: Optional[str] = None
    customer: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    group_ids: Optional[List[int]] = None


class ProjectResponse(ProjectBase):
    """Схема ответа проекта."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    groups: Optional[List[str]] = []
    reports_count: int = 0
    artifacts_count: int = 0


# ===== ProjectReport Schemas =====

class ProjectReportBase(BaseModel):
    """Базовая схема отчёта."""
    title: str = Field(..., min_length=1, max_length=255, description="Заголовок отчёта")
    report_type: Optional[ReportType] = Field(ReportType.GENERAL, description="Тип отчёта")
    content: str = Field(..., description="Markdown контент отчёта")
    is_final: Optional[bool] = Field(False, description="Финальная версия")
    tags: Optional[List[str]] = Field(None, description="Теги")
    obsidian_tags: Optional[str] = Field(None, description="Теги в формате Obsidian")


class ProjectReportCreate(ProjectReportBase):
    """Схема для создания отчёта."""
    project_id: int


class ProjectReportUpdate(BaseModel):
    """Схема для обновления отчёта."""
    title: Optional[str] = None
    report_type: Optional[ReportType] = None
    content: Optional[str] = None
    content_html: Optional[str] = None
    version: Optional[int] = None
    is_final: Optional[bool] = None
    tags: Optional[List[str]] = None
    obsidian_tags: Optional[str] = None
    obsidian_links: Optional[List[str]] = None


class ProjectReportResponse(ProjectReportBase):
    """Схема ответа отчёта."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    project_id: int
    content_html: Optional[str] = None
    version: int
    obsidian_links: Optional[List[str]] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None


# ===== ProjectArtifact Schemas =====

class ProjectArtifactBase(BaseModel):
    """Базовая схема артефакта."""
    name: str = Field(..., min_length=1, max_length=255, description="Название артефакта")
    description: Optional[str] = Field(None, description="Описание")
    artifact_type: Optional[ArtifactType] = Field(ArtifactType.FILE, description="Тип артефакта")
    category: Optional[str] = Field(None, description="Категория")
    tags: Optional[List[str]] = Field(None, description="Теги")
    scan_id: Optional[int] = Field(None, description="ID связанного сканирования")


class ProjectArtifactCreate(ProjectArtifactBase):
    """Схема для создания артефакта."""
    project_id: int
    file_path: str = Field(..., description="Путь к файлу")


class ProjectArtifactUpdate(BaseModel):
    """Схема для обновления артефакта."""
    name: Optional[str] = None
    description: Optional[str] = None
    artifact_type: Optional[ArtifactType] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    scan_id: Optional[int] = None


class ProjectArtifactResponse(ProjectArtifactBase):
    """Схема ответа артефакта."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    project_id: int
    file_path: str
    file_size: int
    mime_type: Optional[str] = None
    checksum: Optional[str] = None
    scan_id: Optional[int] = None
    created_at: datetime
    uploaded_at: Optional[datetime] = None


# ===== ProjectScanSession Schemas =====

class ProjectScanSessionBase(BaseModel):
    """Базовая схема сессии сканирования."""
    name: str = Field(..., min_length=1, max_length=255, description="Название сессии")
    description: Optional[str] = Field(None, description="Описание сессии")
    session_type: Optional[SessionType] = Field(SessionType.MANUAL, description="Тип сессии")
    utilities_used: Optional[List[str]] = Field(None, description="Использованные утилиты")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Параметры запуска")
    targets: Optional[List[str]] = Field(None, description="Цели сканирования")
    results_summary: Optional[str] = Field(None, description="Краткое описание результатов")
    scan_ids: Optional[List[int]] = Field(None, description="ID связанных сканирований")


class ProjectScanSessionCreate(ProjectScanSessionBase):
    """Схема для создания сессии сканирования."""
    project_id: int


class ProjectScanSessionUpdate(BaseModel):
    """Схема для обновления сессии сканирования."""
    name: Optional[str] = None
    description: Optional[str] = None
    session_type: Optional[SessionType] = None
    utilities_used: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None
    targets: Optional[List[str]] = None
    results_summary: Optional[str] = None
    scan_ids: Optional[List[int]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ProjectScanSessionResponse(ProjectScanSessionBase):
    """Схема ответа сессии сканирования."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    project_id: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
