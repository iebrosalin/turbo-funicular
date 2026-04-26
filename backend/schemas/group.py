from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class GroupBase(BaseModel):
    """Базовая схема группы."""
    name: str = Field(..., min_length=1, max_length=255, description="Название группы")
    description: Optional[str] = Field(None, description="Описание")
    parent_id: Optional[int] = Field(None, description="ID родительской группы")
    group_type: Optional[str] = Field("manual", description="Тип группы")
    rule: Optional[str] = Field(None, description="Правило для динамических групп")


class GroupCreate(GroupBase):
    """Схема для создания группы."""
    pass


class GroupUpdate(BaseModel):
    """Схема для обновления группы."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    group_type: Optional[str] = None
    rule: Optional[str] = None


class GroupResponse(BaseModel):
    """Схема ответа группы."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    group_type: Optional[str] = "manual"
    rule: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    assets_count: Optional[int] = 0
