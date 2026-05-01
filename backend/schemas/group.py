from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Union, Any
from datetime import datetime
import json


class GroupBase(BaseModel):
    """Базовая схема группы."""
    name: str = Field(..., min_length=1, max_length=255, description="Название группы")
    description: Optional[str] = Field(None, description="Описание")
    parent_id: Optional[int] = Field(None, description="ID родительской группы")
    group_type: Optional[str] = Field("manual", description="Тип группы")
    is_dynamic: Optional[bool] = Field(False, description="Флаг динамической группы")
    rule: Optional[str] = Field(None, description="Правило для динамических групп")
    filter_rules: Optional[Union[str, List[Any]]] = Field(None, description="JSON правила фильтрации или массив правил")

    @field_validator('filter_rules', mode='before')
    @classmethod
    def serialize_filter_rules(cls, v):
        """Сериализуем filter_rules в JSON строку если это массив."""
        if v is None:
            return None
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return json.dumps(v)
        return str(v)


class GroupCreate(GroupBase):
    """Схема для создания группы."""
    pass


class GroupUpdate(BaseModel):
    """Схема для обновления группы."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    group_type: Optional[str] = None
    is_dynamic: Optional[bool] = None
    rule: Optional[str] = None
    filter_rules: Optional[Union[str, List[Any]]] = None

    @field_validator('filter_rules', mode='before')
    @classmethod
    def serialize_filter_rules(cls, v):
        """Сериализуем filter_rules в JSON строку если это массив."""
        if v is None:
            return None
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return json.dumps(v)
        return str(v)


class GroupResponse(BaseModel):
    """Схема ответа группы."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uuid: str
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    group_type: Optional[str] = "manual"
    is_dynamic: Optional[bool] = False
    rule: Optional[str] = None
    filter_rules: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    assets_count: Optional[int] = 0
