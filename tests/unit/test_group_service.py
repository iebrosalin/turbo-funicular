import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from backend.services.group_service import GroupService
from backend.schemas.group import GroupCreate, GroupUpdate
from backend.models.group import Group
from sqlalchemy.exc import SQLAlchemyError

pytestmark = pytest.mark.asyncio


class TestGroupService:
    """Тесты для GroupService"""

    async def test_create_group_success(self, async_session_mock):
        """Тест успешного создания группы"""
        # Настраиваем мок для add и flush
        async_session_mock.add = MagicMock()
        async_session_mock.flush = AsyncMock()
        
        service = GroupService(async_session_mock)
        group_data = GroupCreate(name="Test Group", description="Test Desc")
        
        # Мокируем результат query.one_or_none() для проверки уникальности имени
        async_session_mock.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(one_or_none=MagicMock(return_value=None)))))
        
        group = await service.create(group_data)
        
        assert group.name == "Test Group"
        assert group.description == "Test Desc"
        async_session_mock.add.assert_called_once()

    async def test_get_tree_structure(self, async_session_mock):
        """Тест построения дерева групп"""
        service = GroupService(async_session_mock)
        
        # Мокируем выполнение запроса для получения всех групп
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            Group(id=1, name="Parent", parent_id=None),
            Group(id=2, name="Child", parent_id=1)
        ]
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        
        tree = await service.get_tree()
        
        assert len(tree) >= 1

    async def test_cyclic_dependency_prevention(self, async_session_mock):
        """Тест предотвращения циклической зависимости"""
        service = GroupService(async_session_mock)
        
        # Мокируем получение группы
        mock_group = Group(id=1, name="Self Ref")
        async_session_mock.get = AsyncMock(return_value=mock_group)
        
        # Попытка сделать группу родителем самой себя должна вызвать ошибку
        with pytest.raises(ValueError):
            await service.update(1, GroupUpdate(parent_id=1))

    async def test_delete_group_with_cascade(self, async_session_mock):
        """Тест каскадного удаления группы"""
        service = GroupService(async_session_mock)
        
        # Мокируем получение группы через get_by_id (который использует execute)
        mock_group = Group(id=1, name="To Delete")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        async_session_mock.flush = AsyncMock()
        
        result = await service.delete(1)
        assert result is True
        async_session_mock.execute.assert_called()

    async def test_delete_group_db_error(self, async_session_mock):
        """Тест обработки ошибки БД при удалении"""
        service = GroupService(async_session_mock)
        
        mock_group = Group(id=1, name="Error Test")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        async_session_mock.flush = AsyncMock(side_effect=SQLAlchemyError("DB Error"))
        
        with pytest.raises(SQLAlchemyError):
            await service.delete(1)
