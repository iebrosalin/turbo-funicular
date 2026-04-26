from pydantic import BaseModel, Field, IPvAnyAddress
from typing import Optional, List
from datetime import datetime


class AssetBase(BaseModel):
    """Базовая схема актива."""
    ip_address: str = Field(..., description="IP адрес")
    hostname: Optional[str] = Field(None, description="Имя хоста")
    os_family: Optional[str] = Field(None, description="Семейство ОС")
    group_id: Optional[int] = Field(None, description="ID группы")
    status: Optional[str] = Field("active", description="Статус")
    location: Optional[str] = Field(None, description="Расположение")


class AssetCreate(AssetBase):
    """Схема для создания актива."""
    pass


class AssetUpdate(BaseModel):
    """Схема для обновления актива."""
    hostname: Optional[str] = None
    os_family: Optional[str] = None
    group_id: Optional[int] = None
    status: Optional[str] = None
    location: Optional[str] = None


class AssetResponse(AssetBase):
    """Схема ответа актива."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
