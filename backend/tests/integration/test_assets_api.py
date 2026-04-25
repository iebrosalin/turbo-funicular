import pytest
from httpx import AsyncClient
from app.main import app

pytestmark = pytest.mark.asyncio


class TestAssetsAPI:
    """Интеграционные тесты для API активов"""

    async def test_get_assets_empty(self, async_client: AsyncClient):
        """Тест получения пустого списка активов"""
        response = await async_client.get("/api/assets")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_create_asset_success(self, async_client: AsyncClient):
        """Тест успешного создания актива"""
        asset_data = {
            "name": "Test Server",
            "ip_address": "192.168.1.100",
            "description": "Test Description",
            "group_id": None
        }
        
        response = await async_client.post("/api/assets", json=asset_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Server"
        assert data["ip_address"] == "192.168.1.100"
        assert "id" in data

    async def test_create_asset_validation_error(self, async_client: AsyncClient):
        """Тест валидации при создании актива"""
        # Отсутствует обязательное поле name
        asset_data = {
            "ip_address": "192.168.1.101"
        }
        
        response = await async_client.post("/api/assets", json=asset_data)
        
        assert response.status_code == 422  # Validation Error

    async def test_get_single_asset(self, async_client: AsyncClient, test_asset):
        """Тест получения одного актива по ID"""
        response = await async_client.get(f"/api/assets/{test_asset.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_asset.id
        assert data["name"] == test_asset.name

    async def test_get_asset_not_found(self, async_client: AsyncClient):
        """Тест получения несуществующего актива"""
        response = await async_client.get("/api/assets/99999")
        
        assert response.status_code == 404

    async def test_update_asset_success(self, async_client: AsyncClient, test_asset):
        """Тест успешного обновления актива"""
        update_data = {
            "name": "Updated Server",
            "description": "Updated Description"
        }
        
        response = await async_client.put(
            f"/api/assets/{test_asset.id}", 
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Server"
        assert data["description"] == "Updated Description"

    async def test_delete_asset_success(self, async_client: AsyncClient, test_asset):
        """Тест успешного удаления актива"""
        response = await async_client.delete(f"/api/assets/{test_asset.id}")
        
        assert response.status_code == 200
        
        # Проверяем что актив удален
        get_response = await async_client.get(f"/api/assets/{test_asset.id}")
        assert get_response.status_code == 404

    async def test_filter_assets_by_search(self, async_client: AsyncClient, test_asset):
        """Тест фильтрации активов по поиску"""
        response = await async_client.get(f"/api/assets?search={test_asset.name[:5]}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(asset["name"] == test_asset.name for asset in data)
