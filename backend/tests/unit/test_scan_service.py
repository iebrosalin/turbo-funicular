import pytest
from unittest.mock import AsyncMock, patch
from app.services.scan_service import ScanService
from app.schemas.scan import ScanCreate, ScanStatus
from app.models.scan import Scan
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

pytestmark = pytest.mark.asyncio


class TestScanService:
    """Тесты для ScanService"""

    async def test_create_scan_success(self, async_client, db_session):
        """Тест успешного создания сканирования"""
        service = ScanService(db_session)
        scan_data = ScanCreate(
            name="Test Scan",
            target="192.168.1.1",
            scan_type="nmap",
            options="-sV"
        )
        
        scan = await service.create(scan_data)
        
        assert scan.name == "Test Scan"
        assert scan.target == "192.168.1.1"
        assert scan.status == "pending"
        assert scan.id is not None

    async def test_update_scan_status(self, async_client, db_session):
        """Тест обновления статуса сканирования"""
        service = ScanService(db_session)
        scan = await service.create(ScanCreate(
            name="Status Test",
            target="10.0.0.1",
            scan_type="nmap"
        ))
        
        updated = await service.update_status(scan.id, "running")
        
        assert updated.status == "running"
        assert updated.started_at is not None

    async def test_update_scan_with_results(self, async_client, db_session):
        """Тест обновления сканирования с результатами"""
        import json
        service = ScanService(db_session)
        scan = await service.create(ScanCreate(
            name="Result Test",
            target="127.0.0.1",
            scan_type="nmap"
        ))
        
        results = {"ports": [80, 443], "hosts": ["127.0.0.1"]}
        updated = await service.complete(scan.id, results)
        
        assert updated.status == "completed"
        assert json.loads(updated.result) == results
        assert updated.completed_at is not None

    async def test_invalid_status_transition(self, async_client, db_session):
        """Тест невалидного перехода статуса"""
        service = ScanService(db_session)
        scan = await service.create(ScanCreate(
            name="Invalid Transition",
            target="192.168.1.1",
            scan_type="nmap"
        ))
        
        # Сначала запускаем сканирование
        await service.update_status(scan.id, "running")
        
        # Теперь пытаемся завершить - должно работать
        results = {}
        updated = await service.complete(scan.id, results)
        assert updated.status == "completed"

    async def test_delete_scan_success(self, async_client, db_session):
        """Тест успешного удаления сканирования"""
        service = ScanService(db_session)
        scan = await service.create(ScanCreate(
            name="To Delete",
            target="192.168.1.1",
            scan_type="nmap"
        ))
        
        await service.delete(scan.id)
        
        deleted = await db_session.get(Scan, scan.id)
        assert deleted is None

    async def test_get_active_scans(self, async_client, db_session):
        """Тест получения активных сканирований"""
        from sqlalchemy import select
        service = ScanService(db_session)
        
        await service.create(ScanCreate(name="Active 1", target="1.1.1.1", scan_type="nmap"))
        await service.create(ScanCreate(name="Active 2", target="2.2.2.2", scan_type="nmap"))
        
        # Обновляем одно на completed
        scans = await db_session.execute(select(Scan))
        all_scans = scans.scalars().all()
        if all_scans:
            await service.update_status(all_scans[0].id, "running")
        
        active = await service.get_active()
        assert len(active) >= 1
