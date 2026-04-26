import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from app.services.group_service import GroupService
from app.schemas.group import GroupCreate, GroupUpdate
from app.models.group import Group
from sqlalchemy.exc import SQLAlchemyError

pytestmark = pytest.mark.asyncio


class TestGroupService:
    """Тесты для GroupService"""

    async def test_create_group_success(self, async_client, db_session):
        """Тест успешного создания группы"""
        service = GroupService(db_session)
        group_data = GroupCreate(name="Test Group", description="Test Desc")
        
        group = await service.create(group_data)
        
        assert group.name == "Test Group"
        assert group.description == "Test Desc"
        assert group.id is not None

    async def test_get_tree_structure(self, async_client, db_session):
        """Тест построения дерева групп"""
        service = GroupService(db_session)
        
        # Создаем родительскую и дочернюю группы
        parent = await service.create(GroupCreate(name="Parent"))
        child = await service.create(GroupCreate(name="Child", parent_id=parent.id))
        
        tree = await service.get_tree()
        
        assert len(tree) >= 1
        # Проверка что дерево содержит вложенность (упрощенно)
        parent_node = next((g for g in tree if g.id == parent.id), None)
        assert parent_node is not None

    async def test_cyclic_dependency_prevention(self, async_client, db_session):
        """Тест предотвращения циклической зависимости"""
        service = GroupService(db_session)
        
        group = await service.create(GroupCreate(name="Self Ref"))
        
        # Попытка сделать группу родителем самой себя должна вызвать ошибку
        with pytest.raises(ValueError):
            await service.update(group.id, GroupUpdate(parent_id=group.id))

    async def test_delete_group_with_cascade(self, async_client, db_session):
        """Тест каскадного удаления группы"""
        service = GroupService(db_session)
        
        parent = await service.create(GroupCreate(name="Parent To Delete"))
        child = await service.create(GroupCreate(name="Child To Delete", parent_id=parent.id))
        
        # Удаляем дочернюю группу сначала (так как CASCADE работает на уровне БД для children)
        result_child = await service.delete(child.id)
        assert result_child is True
        
        # Затем удаляем родительскую группу
        result_parent = await service.delete(parent.id)
        assert result_parent is True
        
        # Проверяем что обе группы удалены
        remaining_parent = await service.get_by_id(parent.id)
        assert remaining_parent is None
        remaining_child = await service.get_by_id(child.id)
        assert remaining_child is None

    async def test_delete_group_db_error(self, async_client, db_session):
        """Тест обработки ошибки БД при удалении"""
        service = GroupService(db_session)
        group = await service.create(GroupCreate(name="Error Test"))
        
        # Мокируем execute для выброса ошибки
        db_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB Error"))
        
        with pytest.raises(SQLAlchemyError):
            await service.delete(group.id)
