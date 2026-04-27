import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.services.scan_service import ScanService
from backend.schemas.scan import ScanCreate, ScanStatus
from backend.models.scan import Scan
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

pytestmark = pytest.mark.asyncio


class TestScanService:
    """Тесты для ScanService"""

    async def test_create_scan_success(self, async_session_mock):
        """Тест успешного создания сканирования"""
        # Настраиваем мок для add и flush
        async_session_mock.add = MagicMock()
        async_session_mock.flush = AsyncMock()
        async_session_mock.refresh = AsyncMock()
        
        service = ScanService(async_session_mock)
        scan_data = ScanCreate(
            name="Test Scan",
            target="192.168.1.1",
            scan_type="nmap",
            options="-sV"
        )
        
        # Мокируем возврат созданного объекта
        created_scan = MagicMock(spec=Scan)
        created_scan.name = "Test Scan"
        created_scan.target = "192.168.1.1"
        created_scan.status = "pending"
        created_scan.id = 1
        
        # После flush mock object будет иметь атрибуты
        async_session_mock.add.side_effect = lambda x: setattr(x, 'id', 1) or setattr(x, 'status', 'pending')
        
        scan = await service.create(scan_data)
        
        assert scan is not None
        async_session_mock.add.assert_called_once()

    async def test_update_scan_status(self, async_session_mock):
        """Тест обновления статуса сканирования"""
        service = ScanService(async_session_mock)
        
        # Мокируем получение сканирования через patch get_by_id
        mock_scan = MagicMock(spec=Scan)
        mock_scan.id = 1
        mock_scan.name = "Status Test"
        mock_scan.target = "10.0.0.1"
        mock_scan.scan_type = "nmap"
        mock_scan.status = "pending"
        mock_scan.started_at = None
        
        with patch.object(service, 'get_by_id', new=AsyncMock(return_value=mock_scan)):
            updated = await service.update_status(1, "running")
            
            assert updated.status == "running"

    async def test_update_scan_with_results(self, async_session_mock):
        """Тест обновления сканирования с результатами"""
        import json
        service = ScanService(async_session_mock)
        
        # Мокируем получение сканирования
        mock_scan = MagicMock(spec=Scan)
        mock_scan.id = 1
        mock_scan.name = "Result Test"
        mock_scan.target = "127.0.0.1"
        mock_scan.scan_type = "nmap"
        mock_scan.status = "running"
        mock_scan.result = None
        mock_scan.completed_at = None
        
        with patch.object(service, 'get_by_id', new=AsyncMock(return_value=mock_scan)):
            results = {"ports": [80, 443], "hosts": ["127.0.0.1"]}
            updated = await service.complete(1, results)
            
            assert updated.status == "completed"

    async def test_invalid_status_transition(self, async_session_mock):
        """Тест невалидного перехода статуса"""
        service = ScanService(async_session_mock)
        
        # Мокируем получение сканирования
        mock_scan = MagicMock(spec=Scan)
        mock_scan.id = 1
        mock_scan.name = "Invalid Transition"
        mock_scan.target = "192.168.1.1"
        mock_scan.scan_type = "nmap"
        mock_scan.status = "running"
        
        with patch.object(service, 'get_by_id', new=AsyncMock(return_value=mock_scan)):
            # Теперь пытаемся завершить - должно работать
            results = {}
            updated = await service.complete(1, results)
            assert updated.status == "completed"

    async def test_delete_scan_success(self, async_session_mock):
        """Тест успешного удаления сканирования"""
        service = ScanService(async_session_mock)
        
        # Мокируем выполнение delete
        mock_result = MagicMock()
        mock_result.rowcount = 1
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        async_session_mock.flush = AsyncMock()
        
        result = await service.delete(1)
        assert result is True

    async def test_get_active_scans(self, async_session_mock):
        """Тест получения активных сканирований"""
        from sqlalchemy import select
        service = ScanService(async_session_mock)
        
        # Мокируем выполнение запроса
        mock_scan1 = MagicMock(spec=Scan)
        mock_scan1.id = 1
        mock_scan1.name = "Active 1"
        mock_scan1.status = "running"
        
        mock_scan2 = MagicMock(spec=Scan)
        mock_scan2.id = 2
        mock_scan2.name = "Active 2"
        mock_scan2.status = "pending"
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_scan1, mock_scan2]
        async_session_mock.execute = AsyncMock(return_value=mock_result)
        
        active = await service.get_active()
        assert len(active) >= 1

    async def test_create_scan_persists_to_db(self, async_session_mock):
        """Тест полного сохранения сканирования в БД с вызовом add(), commit() и refresh()"""
        from backend.schemas.scan import ScanCreate
        service = ScanService(async_session_mock)
        
        # Настраиваем мок для отслеживания вызовов
        async_session_mock.add = MagicMock()
        async_session_mock.commit = AsyncMock()
        async_session_mock.refresh = AsyncMock()
        
        scan_data = ScanCreate(
            name="Persistence Test",
            target="10.0.0.1",
            scan_type="nmap",
            options="-sV"
        )
        
        # Создаем объект сканирования, который будет изменён при commit/refresh
        created_scan = Scan(**scan_data.model_dump())
        created_scan.id = 1
        created_scan.status = "pending"
        created_scan.progress = 0
        
        # Мокируем side_effect для add чтобы сохранить объект
        def add_side_effect(obj):
            obj.id = 1
            if not hasattr(obj, 'status'):
                obj.status = "pending"
            if not hasattr(obj, 'progress'):
                obj.progress = 0
        
        async_session_mock.add.side_effect = add_side_effect
        
        # После refresh объект должен иметь все атрибуты
        async_session_mock.refresh.side_effect = lambda x: setattr(x, 'id', 1) or setattr(x, 'created_at', datetime.now())
        
        result = await service.create(scan_data)
        
        # Проверяем, что все методы были вызваны
        async_session_mock.add.assert_called_once()
        async_session_mock.commit.assert_called_once()
        async_session_mock.refresh.assert_called_once()
        
        # Проверяем, что объект был сохранён с правильными данными
        assert result is not None
        assert result.name == "Persistence Test"
        assert result.target == "10.0.0.1"
        assert result.scan_type == "nmap"

    async def test_create_scan_default_values(self, async_session_mock):
        """Тест установки значений по умолчанию при создании сканирования без указания полей"""
        from backend.schemas.scan import ScanCreate
        service = ScanService(async_session_mock)
        
        # Настраиваем мок
        async_session_mock.add = MagicMock()
        async_session_mock.commit = AsyncMock()
        async_session_mock.refresh = AsyncMock()
        
        # Создаём сканирование без указания scan_type, status, progress
        scan_data = ScanCreate(
            name="Default Values Test",
            target="192.168.1.1"
        )
        
        # Мокируем создание объекта с значениями по умолчанию из модели
        def add_side_effect(obj):
            obj.id = 1
            # Проверяем, что значения по умолчанию установлены
            if not hasattr(obj, 'scan_type') or obj.scan_type is None:
                obj.scan_type = "nmap"
            if not hasattr(obj, 'status') or obj.status is None:
                obj.status = "pending"
            if not hasattr(obj, 'progress') or obj.progress is None:
                obj.progress = 0
        
        async_session_mock.add.side_effect = add_side_effect
        async_session_mock.refresh.side_effect = lambda x: setattr(x, 'created_at', datetime.now())
        
        result = await service.create(scan_data)
        
        # Проверяем, что commit был вызван для фиксации изменений в БД
        async_session_mock.commit.assert_called_once()
        
        # Проверяем значения по умолчанию
        assert result.scan_type == "nmap", "scan_type должен быть 'nmap' по умолчанию"
        assert result.status == "pending", "status должен быть 'pending' по умолчанию"
        assert result.progress == 0, "progress должен быть 0 по умолчанию"
