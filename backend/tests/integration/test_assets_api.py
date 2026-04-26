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
            "hostname": "Test Server",
            "ip_address": "192.168.1.100",
            "os_family": "Linux",
            "group_id": None
        }
        
        response = await async_client.post("/api/assets", json=asset_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["hostname"] == "Test Server"
        assert data["ip_address"] == "192.168.1.100"
        assert "id" in data

    async def test_create_asset_validation_error(self, async_client: AsyncClient):
        """Тест валидации при создании актива"""
        # Отсутствует обязательное поле ip_address
        asset_data = {
            "hostname": "test-host"
        }
        
        response = await async_client.post("/api/assets", json=asset_data)
        
        assert response.status_code == 422  # Validation Error

    async def test_get_single_asset(self, async_client: AsyncClient, db_session, test_asset_data):
        """Тест получения одного актива по ID"""
        # Создаем тестовый актив через API
        create_response = await async_client.post("/api/assets", json=test_asset_data)
        asset_id = create_response.json()["id"]
        
        response = await async_client.get(f"/api/assets/{asset_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == asset_id
        assert data["hostname"] == test_asset_data["hostname"]

    async def test_update_asset_success(self, async_client: AsyncClient, db_session, test_asset_data):
        """Тест успешного обновления актива"""
        # Создаем тестовый актив
        create_response = await async_client.post("/api/assets", json=test_asset_data)
        asset_id = create_response.json()["id"]
        
        update_data = {
            "hostname": "Updated Server",
            "os_family": "Windows"
        }
        
        response = await async_client.put(
            f"/api/assets/{asset_id}", 
            json=update_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["hostname"] == "Updated Server"
        assert data["os_family"] == "Windows"

    async def test_delete_asset_success(self, async_client: AsyncClient, db_session, test_asset_data):
        """Тест успешного удаления актива"""
        # Создаем тестовый актив
        create_response = await async_client.post("/api/assets", json=test_asset_data)
        asset_id = create_response.json()["id"]
        
        response = await async_client.delete(f"/api/assets/{asset_id}")
        
        assert response.status_code == 204
        
        # Проверяем что актив удален
        get_response = await async_client.get(f"/api/assets/{asset_id}")
        assert get_response.status_code == 404

    async def test_filter_assets_by_search(self, async_client: AsyncClient, db_session, test_asset_data):
        """Тест фильтрации активов по поиску"""
        # Создаем тестовый актив
        await async_client.post("/api/assets", json=test_asset_data)
        
        response = await async_client.get(f"/api/assets?search={test_asset_data['hostname'][:5]}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(asset["hostname"] == test_asset_data["hostname"] for asset in data)
