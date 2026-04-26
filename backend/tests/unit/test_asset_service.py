"""
Unit tests for AssetService.
Tests business logic without HTTP layer.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.services.asset_service import AssetService
from app.schemas.asset import AssetCreate, AssetUpdate
from app.models.asset import Asset


class TestAssetService:
    """Tests for AssetService CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_asset_success(self, async_session_mock, test_asset_data):
        """Test successful asset creation."""
        service = AssetService(async_session_mock)
        
        # Mock DB commit and refresh
        async_session_mock.add = AsyncMock()
        async_session_mock.commit = AsyncMock()
        async_session_mock.refresh = AsyncMock()
        
        asset_data = AssetCreate(**test_asset_data)
        result = await service.create(asset_data)
        
        assert result is not None
        assert result.ip_address == test_asset_data["ip_address"]
        assert result.hostname == test_asset_data["hostname"]
        async_session_mock.add.assert_called_once()
        async_session_mock.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_asset_by_id_exists(self, async_session_mock, test_asset_instance):
        """Test getting an existing asset by ID."""
        service = AssetService(async_session_mock)
        
        # Mock query result with scalar_one_or_none
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_asset_instance
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        
        result = await service.get_by_id(1)
        
        assert result is not None
        assert result.id == 1
        assert result.ip_address == "192.168.1.10"

    @pytest.mark.asyncio
    async def test_get_asset_by_id_not_found(self, async_session_mock):
        """Test getting a non-existent asset."""
        service = AssetService(async_session_mock)
        
        # Mock None result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        
        result = await service.get_by_id(999)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_update_asset_success(self, async_session_mock, test_asset_instance):
        """Test successful asset update."""
        service = AssetService(async_session_mock)
        
        # Mock existing asset retrieval via get_by_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [test_asset_instance, None]  # First call returns asset, second (group lookup) returns None
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        async_session_mock.flush = AsyncMock()
        async_session_mock.refresh = AsyncMock()
        
        update_data = AssetUpdate(hostname="new-hostname")
        result = await service.update(1, update_data)
        
        assert result is not None
        assert result.hostname == "new-hostname"

    @pytest.mark.asyncio
    async def test_update_asset_not_found(self, async_session_mock):
        """Test updating a non-existent asset."""
        service = AssetService(async_session_mock)
        
        # Mock None result for get_by_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        
        update_data = AssetUpdate(hostname="new-hostname")
        result = await service.update(999, update_data)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_asset_success(self, async_session_mock, test_asset_instance):
        """Test successful asset deletion."""
        service = AssetService(async_session_mock)
        
        # Mock delete result
        mock_result = MagicMock()
        mock_result.rowcount = 1
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        async_session_mock.flush = AsyncMock()
        
        result = await service.delete(1)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_asset_not_found(self, async_session_mock):
        """Test deleting a non-existent asset."""
        service = AssetService(async_session_mock)
        
        # Mock delete result with 0 rows
        mock_result = MagicMock()
        mock_result.rowcount = 0
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        async_session_mock.flush = AsyncMock()
        
        result = await service.delete(999)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_filter_assets_by_search(self, async_session_mock, test_asset_instance):
        """Test filtering assets by search term using get_all."""
        service = AssetService(async_session_mock)
        
        # Mock execute and scalars
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.return_value.all.return_value = [test_asset_instance]
        mock_result.scalars.return_value = mock_scalars
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        
        results = await service.get_all(search="192.168")
        
        assert len(results) == 1
        assert results[0].ip_address == "192.168.1.10"

    @pytest.mark.asyncio
    async def test_db_error_handling(self, async_session_mock, test_asset_data):
        """Test handling of database errors during creation."""
        service = AssetService(async_session_mock)
        
        # Mock DB error
        async_session_mock.add = AsyncMock(side_effect=SQLAlchemyError("DB Error"))
        
        asset_data = AssetCreate(**test_asset_data)
        
        with pytest.raises(SQLAlchemyError):
            await service.create(asset_data)
