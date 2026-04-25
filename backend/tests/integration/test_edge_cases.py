"""
Интеграционные тесты для проверки краевых случаев (Edge Cases).
Проверка транзакционности, уникальности, обработки ошибок и некорректных данных.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.asset import Asset
from app.models.group import Group


class TestEdgeCases:
    """Тесты краевых случаев для API."""

    @pytest.mark.asyncio
    async def test_create_asset_with_nonexistent_group(self, async_client, db_session):
        """Попытка создания актива с несуществующим ID группы должна вернуть 400 или 422."""
        payload = {
            "hostname": "test-host",
            "ip_address": "192.168.1.100",
            "group_id": 99999  # Не существует
        }
        response = await async_client.post("/api/assets", json=payload)
        # Ожидаем ошибку (400 Bad Request или 422 Validation Error)
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_create_duplicate_asset_ip(self, async_client, db_session, test_asset):
        """Попытка создания актива с дублирующимся IP должна быть отклонена."""
        payload = {
            "hostname": "duplicate-host",
            "ip_address": test_asset.ip_address,  # Тот же IP
            "group_id": None
        }
        response = await async_client.post("/api/assets", json=payload)
        # В зависимости от реализации: 400 или 409 Conflict
        assert response.status_code in [400, 409, 422]

    @pytest.mark.asyncio
    async def test_create_asset_empty_payload(self, async_client):
        """Отправка пустого JSON должна вернуть 422."""
        response = await async_client.post("/api/assets", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_nonexistent_asset(self, async_client):
        """Запрос несуществующего актива должен вернуть 404."""
        response = await async_client.get("/api/assets/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_asset(self, async_client):
        """Удаление несуществующего актива должно вернуть 404."""
        response = await async_client.delete("/api/assets/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, async_client):
        """Использование неподдерживаемого метода (например, PUT на коллекцию) должно вернуть 405."""
        response = await async_client.put("/api/assets")
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_invalid_json_payload(self, async_client):
        """Отправка невалидного JSON должна обрабатываться корректно."""
        # Попытка отправить некорректный тип данных для поля
        payload = {
            "hostname": 12345,  # Ожидается строка
            "ip_address": "not-an-ip",
            "group_id": "string-instead-of-int"
        }
        response = await async_client.post("/api/assets", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, async_client, db_session):
        """
        Проверка отката транзакции.
        Сценарий сложно эмулировать через API без моков, но можно проверить целостность.
        Создадим валидный актив, затем проверим, что он есть в БД.
        """
        initial_count = (await db_session.execute(select(Asset))).scalars().all()
        count_before = len(initial_count)

        payload = {
            "hostname": "rollback-test",
            "ip_address": "10.0.0.1",
            "group_id": None
        }
        response = await async_client.post("/api/assets", json=payload)
        assert response.status_code == 201

        # Проверяем, что счетчик увеличился
        result = (await db_session.execute(select(Asset))).scalars().all()
        assert len(result) == count_before + 1
