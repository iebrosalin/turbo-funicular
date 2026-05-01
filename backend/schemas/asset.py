from pydantic import BaseModel, Field, IPvAnyAddress, ConfigDict
from typing import Optional, List
from datetime import datetime


class AssetBase(BaseModel):
    """Базовая схема актива."""
    ip_address: str = Field(..., description="IP адрес")
    hostname: Optional[str] = Field(None, description="Имя хоста")
    os_name: Optional[str] = Field(None, description="Название ОС (например, Ubuntu 22.04)")
    os_family: Optional[str] = Field(None, description="Семейство ОС")
    os_version: Optional[str] = Field(None, description="Версия ОС")
    description: Optional[str] = Field(None, description="Описание/комментарии")
    tags: Optional[List[str]] = Field(None, description="Теги")
    group_id: Optional[int] = Field(None, description="ID группы")
    status: Optional[str] = Field("active", description="Статус")
    location: Optional[str] = Field(None, description="Расположение")


class AssetCreate(AssetBase):
    """Схема для создания актива."""
    pass


class AssetUpdate(BaseModel):
    """Схема для обновления актива."""
    hostname: Optional[str] = None
    os_name: Optional[str] = None
    os_family: Optional[str] = None
    os_version: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    group_id: Optional[int] = None
    status: Optional[str] = None
    location: Optional[str] = None


class AssetResponse(BaseModel):
    """Схема ответа актива."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    ip_address: str
    hostname: Optional[str] = None
    os_name: Optional[str] = None
    os_family: Optional[str] = None
    os_version: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = "active"
    location: Optional[str] = None
    group_id: Optional[int] = None  # Возвращаем ID первой группы для совместимости
    group_name: Optional[str] = None  # Добавляем имя группы для отображения
    groups: Optional[List[dict]] = None  # Добавляем полную информацию о группах
    created_at: datetime
    updated_at: Optional[datetime] = None
