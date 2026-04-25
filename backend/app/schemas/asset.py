from pydantic import BaseModel, Field, IPvAnyAddress
from typing import Optional, List
from datetime import datetime


class AssetBase(BaseModel):
    """Базовая схема актива."""
    ip_address: str = Field(..., description="IP адрес")
    hostname: Optional[str] = Field(None, description="Имя хоста")
    mac_address: Optional[str] = Field(None, description="MAC адрес")
    os_info: Optional[str] = Field(None, description="Информация об ОС")
    group_id: Optional[int] = Field(None, description="ID группы")
    status: Optional[str] = Field("active", description="Статус")
    notes: Optional[str] = Field(None, description="Заметки")


class AssetCreate(AssetBase):
    """Схема для создания актива."""
    pass


class AssetUpdate(BaseModel):
    """Схема для обновления актива."""
    hostname: Optional[str] = None
    mac_address: Optional[str] = None
    os_info: Optional[str] = None
    group_id: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class AssetResponse(AssetBase):
    """Схема ответа актива."""
    id: int
    last_seen: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
