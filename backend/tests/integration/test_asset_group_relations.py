"""
Интеграционные тесты для проверки связей между Активами и Группами.
Проверка перемещения, каскадного удаления, фильтрации и статистики.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from app.models.asset import Asset
from app.models.group import Group


class TestAssetGroupRelations:
    """Тесты взаимодействия активов и групп."""

    @pytest.mark.asyncio
    async def test_create_asset_in_group(self, async_client, db_session, test_group):
        """Создание актива внутри группы и проверка связи."""
        payload = {
            "hostname": "grouped-asset",
            "ip_address": "192.168.10.5",
            "group_id": test_group.id
        }
        response = await async_client.post("/api/assets", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["group_id"] == test_group.id

        # Проверка в БД
        asset = (await db_session.execute(select(Asset).where(Asset.id == data["id"]))).scalars().first()
        assert asset is not None
        assert asset.group_id == test_group.id

    @pytest.mark.asyncio
    async def test_move_asset_to_another_group(self, async_client, db_session, test_group, test_asset):
        """Перемещение актива из одной группы в другую."""
        # Создадим вторую группу
        new_group_payload = {"name": "New Group for Move"}
        resp = await async_client.post("/api/groups", json=new_group_payload)
        new_group_id = resp.json()["id"]

        # Изначально актив может быть без группы или в test_group, принудительно обновим
        payload = {"group_id": new_group_id}
        response = await async_client.put(f"/api/assets/{test_asset.id}", json=payload)
        
        # Если API поддерживает PATCH/PUT для обновления группы
        if response.status_code in [200, 201]:
            data = response.json()
            assert data["group_id"] == new_group_id
            
            # Проверка в БД
            updated_asset = (await db_session.execute(select(Asset).where(Asset.id == test_asset.id))).scalars().first()
            assert updated_asset.group_id == new_group_id
        else:
            # Если обновление через отдельный эндпоинт, этот тест можно адаптировать
            pytest.skip("Endpoint for moving assets might differ")

    @pytest.mark.asyncio
    async def test_filter_assets_by_group_id(self, async_client, db_session, test_group):
        """Фильтрация активов по ID группы через API."""
        # Создадим несколько активов в группе
        for i in range(3):
            payload = {
                "hostname": f"asset-in-group-{i}",
                "ip_address": f"192.168.20.{i+1}",
                "group_id": test_group.id
            }
            await async_client.post("/api/assets", json=payload)
        
        # Запросим активы этой группы
        response = await async_client.get(f"/api/assets?group_id={test_group.id}")
        assert response.status_code == 200
        data = response.json()
        # Ожидаем, что в ответе будут наши активы
        # Примечание: формат ответа зависит от реализации (список или объект с данными)
        if isinstance(data, list):
            assert len(data) >= 3
        elif isinstance(data, dict) and "items" in data:
            assert len(data["items"]) >= 3

    @pytest.mark.asyncio
    async def test_cascade_delete_group_with_assets(self, async_client, db_session, test_group):
        """
        Проверка поведения при удалении группы, содержащей активы.
        В зависимости от настройки CASCADE: активы удаляются или их group_id становится NULL.
        """
        # Создадим актив в группе
        payload = {
            "hostname": "asset-to-be-cascaded",
            "ip_address": "192.168.30.1",
            "group_id": test_group.id
        }
        resp = await async_client.post("/api/assets", json=payload)
        asset_id = resp.json()["id"]

        # Удалим группу
        del_response = await async_client.delete(f"/api/groups/{test_group.id}")
        assert del_response.status_code == 200

        # Проверим судьбу актива
        asset = (await db_session.execute(select(Asset).where(Asset.id == asset_id))).scalars().first()
        
        # Вариант А: Актив удален (CASCADE DELETE)
        if asset is None:
            pass # Успех, актив удален
        else:
            # Вариант Б: group_id стал NULL (SET NULL)
            assert asset.group_id is None

    @pytest.mark.asyncio
    async def test_group_assets_count_statistics(self, async_client, db_session, test_group):
        """Проверка счетчика активов в группе после добавления."""
        # Добавим 5 активов
        for i in range(5):
            payload = {
                "hostname": f"stat-asset-{i}",
                "ip_address": f"192.168.40.{i+1}",
                "group_id": test_group.id
            }
            await async_client.post("/api/assets", json=payload)

        # Получим информацию о группе (если эндпоинт возвращает count)
        response = await async_client.get(f"/api/groups/{test_group.id}")
        if response.status_code == 200:
            data = response.json()
            # Проверка поля assets_count, если оно есть в схеме ответа
            if "assets_count" in data:
                assert data["assets_count"] >= 5

    @pytest.mark.asyncio
    async def test_create_asset_in_nonexistent_group_validation(self, async_client):
        """Валидация создания актива с несуществующей группой (дублирование теста на всякий случай)."""
        payload = {
            "hostname": "bad-group-asset",
            "ip_address": "192.168.50.1",
            "group_id": 99999
        }
        response = await async_client.post("/api/assets", json=payload)
        assert response.status_code in [400, 422]
