"""
Headless E2E тесты для полного цикла сканирования БЕЗ Playwright.
Использует только:
- requests для HTTP запросов к API
- SQLAlchemy для прямого доступа к БД
- subprocess для запуска утилит сканирования

Тестовые данные:
- Цели: ya.ru, 1.1.1.1, 8.8.8.8
- Группы: test1, test1-2, тест (разный уровень вложенности)

ВАЖНО: 
- Последний шаг теста - полное удаление всех созданных тестовых данных!
- Активы проверяются только ПОСЛЕ завершения сканирования
- Реальное ожидание утилит сканирования через опрос статуса
- Все результаты хранятся в БД и отдаются через API
"""

import pytest
import requests
import time
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from backend.db.session import async_session_maker
from backend.models.group import Group
from backend.models.asset import Asset
from backend.models.scan import Scan, ScanJob, ScanResult

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestScanUtilitiesE2E:
    """E2E тесты для всех утилит сканирования через HTTP API + БД."""
    
    BASE_URL = "http://localhost:8000"
    API_URL = f"{BASE_URL}/api"
    
    # Хранилище ID созданных ресурсов для последующего удаления
    created_group_ids = []
    created_asset_ids = []
    created_scan_ids = []
    created_job_ids = []
    
    @pytest.fixture(scope="class", autouse=True)
    def setup_and_cleanup(self):
        """Setup: очистка старых тестовых данных. Cleanup: удаление новых."""
        logger.info("=" * 80)
        logger.info("SETUP: Очистка возможных старых тестовых данных")
        
        # Сначала удаляем любые существующие тестовые данные
        self._cleanup_test_data_by_name()
        
        # Создаем тестовые группы через API
        self._create_test_groups()
        
        yield
        
        # Cleanup - удаление всех созданных тестовых данных
        logger.info("=" * 80)
        logger.info("CLEANUP: Удаление всех созданных тестовых данных")
        self._cleanup_all_data()
        logger.info("✓ Все тестовые данные удалены")
    
    def _cleanup_test_data_by_name(self):
        """Удаление любых существующих тестовых данных по именам."""
        async def cleanup():
            async with async_session_maker() as db:
                try:
                    # Находим тестовые группы по именам
                    group_names = ["test1", "test1-2", "тест"]
                    for name in group_names:
                        query = select(Group).where(Group.name == name)
                        result = await db.execute(query)
                        groups = result.scalars().all()
                        for group in groups:
                            # Сначала удаляем активы в этой группе
                            assets_query = select(Asset).where(Asset.group_id == group.id)
                            assets_result = await db.execute(assets_query)
                            assets = assets_result.scalars().all()
                            for asset in assets:
                                await db.execute(delete(Asset).where(Asset.id == asset.id))
                                logger.info(f"✓ Удален актив {asset.id} из старой группы")
                            
                            # Удаляем группу
                            await db.execute(delete(Group).where(Group.id == group.id))
                            logger.info(f"✓ Удалена старая группа {name} (ID: {group.id})")
                    
                    # Находим тестовые активы по IP/DNS
                    test_targets = ["ya.ru", "1.1.1.1", "8.8.8.8"]
                    for target in test_targets:
                        # По DNS
                        query = select(Asset).where(Asset.dns_name.contains(target))
                        result = await db.execute(query)
                        assets = result.scalars().all()
                        for asset in assets:
                            await db.execute(delete(Asset).where(Asset.id == asset.id))
                            logger.info(f"✓ Удален старый актив {asset.id} ({target})")
                        
                        # По IP
                        query = select(Asset).where(Asset.ip_address == target)
                        result = await db.execute(query)
                        assets = result.scalars().all()
                        for asset in assets:
                            await db.execute(delete(Asset).where(Asset.id == asset.id))
                            logger.info(f"✓ Удален старый актив {asset.id} ({target})")
                    
                    # Находим тестовые сканирования
                    for target in test_targets:
                        query = select(Scan).where(Scan.target.contains(target))
                        result = await db.execute(query)
                        scans = result.scalars().all()
                        for scan in scans:
                            # Удаляем результаты
                            await db.execute(delete(ScanResult).where(ScanResult.scan_id == scan.id))
                            # Удаляем задачи
                            await db.execute(delete(ScanJob).where(ScanJob.scan_id == scan.id))
                            # Удаляем сканирование
                            await db.execute(delete(Scan).where(Scan.id == scan.id))
                            logger.info(f"✓ Удалено старое сканирование {scan.id} ({target})")
                    
                    await db.commit()
                    logger.info("✓ Транзакция очистки закоммичена")
                    
                except Exception as e:
                    logger.error(f"✗ Ошибка при очистке: {e}")
                    await db.rollback()
        
        asyncio.run(cleanup())
    
    def _create_test_groups(self):
        """Создание тестовых групп с разной вложенностью через API."""
        logger.info("Создание тестовых групп...")
        
        # Создаем группу test1 (без родителя)
        group1_id = self._create_group_api("test1", None)
        logger.info(f"✓ Группа test1 создана (ID: {group1_id})")
        
        # Создаем группу test1-2 внутри test1
        group2_id = self._create_group_api("test1-2", group1_id)
        logger.info(f"✓ Группа test1-2 создана (ID: {group2_id})")
        
        # Создаем группу тест (кириллица, без родителя)
        group3_id = self._create_group_api("тест", None)
        logger.info(f"✓ Группа тест создана (ID: {group3_id})")
    
    def _create_group_api(self, name: str, parent_id: int = None) -> int:
        """Создание группы через API."""
        payload = {"name": name}
        if parent_id:
            payload["parent_id"] = parent_id
        
        response = requests.post(f"{self.API_URL}/groups", json=payload)
        assert response.status_code == 200 or response.status_code == 201, \
            f"Не удалось создать группу {name}: {response.text}"
        
        group_data = response.json()
        group_id = group_data.get("id")
        self.created_group_ids.append(group_id)
        return group_id
    
    def _cleanup_all_data(self):
        """Полное удаление всех созданных тестовых данных из БД."""
        async def cleanup():
            async with async_session_maker() as db:
                try:
                    # Удаляем результаты сканирований
                    for scan_id in self.created_scan_ids:
                        await db.execute(delete(ScanResult).where(ScanResult.scan_id == scan_id))
                        logger.info(f"✓ Удалены результаты сканирования {scan_id}")
                    
                    # Удаляем задачи сканирований
                    for job_id in self.created_job_ids:
                        await db.execute(delete(ScanJob).where(ScanJob.id == job_id))
                        logger.info(f"✓ Удалена задача сканирования {job_id}")
                    
                    # Удаляем сканирования
                    for scan_id in self.created_scan_ids:
                        await db.execute(delete(Scan).where(Scan.id == scan_id))
                        logger.info(f"✓ Удалено сканирование {scan_id}")
                    
                    # Удаляем активы
                    for asset_id in self.created_asset_ids:
                        await db.execute(delete(Asset).where(Asset.id == asset_id))
                        logger.info(f"✓ Удален актив {asset_id}")
                    
                    # Удаляем группы (в обратном порядке чтобы не было проблем с FK)
                    for group_id in reversed(self.created_group_ids):
                        await db.execute(delete(Group).where(Group.id == group_id))
                        logger.info(f"✓ Удалена группа {group_id}")
                    
                    await db.commit()
                    logger.info("✓ Транзакция очистки закоммичена")
                    
                except Exception as e:
                    logger.error(f"✗ Ошибка при очистке: {e}")
                    await db.rollback()
        
        asyncio.run(cleanup())
    
    def _wait_for_scan_completion(self, target: str, timeout_seconds: int = 120) -> bool:
        """Ожидание завершения сканирования через опрос БД."""
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            async def check_status():
                async with async_session_maker() as db:
                    query = select(Scan).where(Scan.target.contains(target)).order_by(Scan.created_at.desc())
                    result = await db.execute(query)
                    scan = result.scalar_one_or_none()
                    
                    if scan:
                        if scan.status in ['completed', 'failed', 'stopped', 'cancelled']:
                            # Сохраняем ID сканирования и задач
                            if scan.id not in self.created_scan_ids:
                                self.created_scan_ids.append(scan.id)
                            
                            # Получаем связанные задачи
                            jobs_query = select(ScanJob).where(ScanJob.scan_id == scan.id)
                            jobs_result = await db.execute(jobs_query)
                            jobs = jobs_result.scalars().all()
                            for job in jobs:
                                if job.id not in self.created_job_ids:
                                    self.created_job_ids.append(job.id)
                            
                            return scan.status == 'completed'
                    
                    return False
            
            if asyncio.run(check_status()):
                return True
            
            logger.info(f"⏳ Ожидание завершения сканирования {target}...")
            time.sleep(5)
        
        logger.warning(f"⚠ Таймаут ожидания сканирования {target}")
        return False
    
    def test_01_nmap_scan_ya_ru_and_check_assets_appear_after(self):
        """Тест 1: Nmap сканирование ya.ru - активы появляются ПОСЛЕ сканирования."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 1: Nmap сканирование ya.ru")
        
        # Проверяем что нет активов до сканирования
        async def check_no_assets_before():
            async with async_session_maker() as db:
                query = select(Asset).where(Asset.dns_name.contains("ya.ru") | Asset.ip_address.contains("ya.ru"))
                result = await db.execute(query)
                assets = result.scalars().all()
                return len(assets)
        
        assets_before = asyncio.run(check_no_assets_before())
        logger.info(f"✓ Активов для ya.ru до сканирования: {assets_before}")
        
        # Запускаем Nmap сканирование через API
        payload = {
            "target": "ya.ru",
            "utility": "nmap",
            "group_id": self.created_group_ids[0] if self.created_group_ids else None
        }
        
        response = requests.post(f"{self.API_URL}/scans/start", json=payload)
        assert response.status_code == 200 or response.status_code == 201, \
            f"Не удалось запустить Nmap сканирование: {response.text}"
        
        scan_data = response.json()
        logger.info(f"✓ Nmap сканирование ya.ru запущено (ID: {scan_data.get('id')})")
        
        # Ждем завершения сканирования через опрос статуса
        completed = self._wait_for_scan_completion("ya.ru", timeout_seconds=120)
        assert completed, f"Nmap сканирование ya.ru не завершилось успешно"
        
        logger.info("✓ Nmap сканирование ya.ru завершено")
        
        # Проверяем что активы появились в БД ПОСЛЕ сканирования
        async def check_assets_after():
            async with async_session_maker() as db:
                query = select(Asset).where(Asset.dns_name.contains("ya.ru") | Asset.ip_address.contains("ya.ru"))
                result = await db.execute(query)
                assets = result.scalars().all()
                for asset in assets:
                    if asset.id not in self.created_asset_ids:
                        self.created_asset_ids.append(asset.id)
                return len(assets)
        
        assets_after = asyncio.run(check_assets_after())
        assert assets_after > 0, "Активы не появились в БД после Nmap сканирования ya.ru"
        logger.info(f"✓ Найдено активов для ya.ru после сканирования: {assets_after}")
    
    def test_02_rustscan_ip_addresses(self):
        """Тест 2: Rustscan сканирование IP адресов 1.1.1.1 и 8.8.8.8."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 2: Rustscan сканирование IP адресов")
        
        for ip in ["1.1.1.1", "8.8.8.8"]:
            logger.info(f"Запуск Rustscan сканирования {ip}...")
            
            # Проверяем что нет активов до сканирования
            async def check_no_assets_before():
                async with async_session_maker() as db:
                    query = select(Asset).where(Asset.ip_address == ip)
                    result = await db.execute(query)
                    return len(list(result.scalars().all()))
            
            assets_before = asyncio.run(check_no_assets_before())
            logger.info(f"✓ Активов для {ip} до сканирования: {assets_before}")
            
            # Запускаем Rustscan через API
            payload = {
                "target": ip,
                "utility": "rustscan",
                "group_id": self.created_group_ids[0] if self.created_group_ids else None
            }
            
            response = requests.post(f"{self.API_URL}/scans/start", json=payload)
            assert response.status_code == 200 or response.status_code == 201, \
                f"Не удалось запустить Rustscan сканирование {ip}: {response.text}"
            
            scan_data = response.json()
            logger.info(f"✓ Rustscan сканирование {ip} запущено (ID: {scan_data.get('id')})")
            
            # Ждем завершения сканирования
            completed = self._wait_for_scan_completion(ip, timeout_seconds=60)
            assert completed, f"Rustscan сканирование {ip} не завершилось успешно"
            
            logger.info(f"✓ Rustscan сканирование {ip} завершено")
            
            # Проверяем что активы появились в БД
            async def check_assets_after():
                async with async_session_maker() as db:
                    query = select(Asset).where(Asset.ip_address == ip)
                    result = await db.execute(query)
                    assets = result.scalars().all()
                    for asset in assets:
                        if asset.id not in self.created_asset_ids:
                            self.created_asset_ids.append(asset.id)
                    return len(assets)
            
            assets_after = asyncio.run(check_assets_after())
            assert assets_after > 0, f"Активы не появились в БД после Rustscan сканирования {ip}"
            logger.info(f"✓ Найдено активов для {ip} после сканирования: {assets_after}")
    
    def test_03_dig_dns_scan(self):
        """Тест 3: Dig DNS сканирование."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 3: Dig DNS сканирование")
        
        target = "ya.ru"
        
        # Запускаем Dig сканирование
        payload = {
            "target": target,
            "utility": "dig",
            "group_id": self.created_group_ids[0] if self.created_group_ids else None
        }
        
        response = requests.post(f"{self.API_URL}/scans/start", json=payload)
        assert response.status_code == 200 or response.status_code == 201, \
            f"Не удалось запустить Dig сканирование: {response.text}"
        
        logger.info(f"✓ Dig сканирование {target} запущено")
        
        # Ждем завершения
        completed = self._wait_for_scan_completion(target, timeout_seconds=60)
        assert completed, "Dig сканирование не завершилось успешно"
        
        logger.info("✓ Dig сканирование завершено")
        
        # Проверяем наличие результатов в БД
        async def check_results():
            async with async_session_maker() as db:
                query = select(ScanResult).join(Scan).where(Scan.target.contains(target))
                result = await db.execute(query)
                results = result.scalars().all()
                return len(results)
        
        results_count = asyncio.run(check_results())
        assert results_count > 0, "Результаты Dig сканирования не найдены в БД"
        logger.info(f"✓ Найдено результатов Dig сканирования: {results_count}")
    
    def test_04_fping_scan(self):
        """Тест 4: Fping сканирование."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 4: Fping сканирование")
        
        target = "8.8.8.8"
        
        # Запускаем Fping сканирование
        payload = {
            "target": target,
            "utility": "fping",
            "group_id": self.created_group_ids[0] if self.created_group_ids else None
        }
        
        response = requests.post(f"{self.API_URL}/scans/start", json=payload)
        assert response.status_code == 200 or response.status_code == 201, \
            f"Не удалось запустить Fping сканирование: {response.text}"
        
        logger.info(f"✓ Fping сканирование {target} запущено")
        
        # Ждем завершения
        completed = self._wait_for_scan_completion(target, timeout_seconds=60)
        assert completed, "Fping сканирование не завершилось успешно"
        
        logger.info("✓ Fping сканирование завершено")
        
        # Проверяем наличие результатов
        async def check_results():
            async with async_session_maker() as db:
                query = select(ScanResult).join(Scan).where(Scan.target.contains(target))
                result = await db.execute(query)
                results = result.scalars().all()
                return len(results)
        
        results_count = asyncio.run(check_results())
        assert results_count > 0, "Результаты Fping сканирования не найдены в БД"
        logger.info(f"✓ Найдено результатов Fping сканирования: {results_count}")


class TestScanResultsDownloadE2E:
    """E2E тесты для скачивания результатов сканирования через API."""
    
    BASE_URL = "http://localhost:8000"
    API_URL = f"{BASE_URL}/api"
    
    def test_05_download_scan_results_from_db(self):
        """Тест 5: Скачивание результатов сканирования через API (из БД)."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 5: Скачивание результатов сканирования через API")
        
        # Находим последнее завершенное сканирование
        async def get_completed_scan():
            async with async_session_maker() as db:
                query = select(Scan).where(Scan.status == 'completed').order_by(Scan.created_at.desc())
                result = await db.execute(query)
                return result.scalar_one_or_none()
        
        scan = asyncio.run(get_completed_scan())
        assert scan is not None, "Нет завершенных сканирований для тестирования скачивания"
        
        logger.info(f"✓ Найдено сканирование ID: {scan.id}, цель: {scan.target}")
        
        # Тестируем скачивание в формате JSON
        response_json = requests.get(f"{self.API_URL}/scans/{scan.id}/download/json")
        assert response_json.status_code == 200, \
            f"Не удалось скачать результаты в JSON: {response_json.status_code} - {response_json.text}"
        
        # Проверяем что это JSON
        try:
            data = response_json.json()
            assert "results" in data or isinstance(data, list), "Ответ не содержит результатов сканирования"
            logger.info(f"✓ Результаты в JSON формате скачаны успешно (размер: {len(response_json.content)} байт)")
        except Exception as e:
            pytest.fail(f"Ответ не является корректным JSON: {e}")
        
        # Тестируем скачивание в формате Raw
        response_raw = requests.get(f"{self.API_URL}/scans/{scan.id}/download/raw")
        assert response_raw.status_code == 200, \
            f"Не удалось скачать результаты в Raw: {response_raw.status_code} - {response_raw.text}"
        
        assert len(response_raw.content) > 0, "Raw результат пустой"
        logger.info(f"✓ Результаты в Raw формате скачаны успешно (размер: {len(response_raw.content)} байт)")
    
    def test_06_download_different_formats(self):
        """Тест 6: Проверка различных форматов скачивания."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 6: Проверка различных форматов скачивания")
        
        # Находим сканирование
        async def get_completed_scan():
            async with async_session_maker() as db:
                query = select(Scan).where(Scan.status == 'completed').order_by(Scan.created_at.desc())
                result = await db.execute(query)
                return result.scalar_one_or_none()
        
        scan = asyncio.run(get_completed_scan())
        assert scan is not None, "Нет завершенных сканирований"
        
        formats_to_test = ["json", "raw"]
        
        for fmt in formats_to_test:
            logger.info(f"Тестирование формата {fmt}...")
            
            response = requests.get(f"{self.API_URL}/scans/{scan.id}/download/{fmt}")
            assert response.status_code == 200, \
                f"Формат {fmt}: ошибка скачивания {response.status_code}"
            
            assert len(response.content) > 0, f"Формат {fmt}: пустой результат"
            logger.info(f"✓ Формат {fmt}: скачано {len(response.content)} байт")


class TestGroupsAndAssetsE2E:
    """E2E тесты для групп и активов."""
    
    BASE_URL = "http://localhost:8000"
    API_URL = f"{BASE_URL}/api"
    
    def test_07_groups_hierarchy(self):
        """Тест 7: Проверка иерархии групп."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 7: Проверка иерархии групп")
        
        # Получаем все группы
        response = requests.get(f"{self.API_URL}/groups")
        assert response.status_code == 200, f"Не удалось получить список групп: {response.text}"
        
        groups = response.json()
        assert isinstance(groups, list), "Ответ API не является списком групп"
        
        # Ищем наши тестовые группы
        test_group_names = ["test1", "test1-2", "тест"]
        found_groups = {}
        
        for group in groups:
            name = group.get("name")
            if name in test_group_names:
                found_groups[name] = group
                logger.info(f"✓ Найдена группа: {name} (ID: {group.get('id')})")
        
        # Проверяем что все группы созданы
        for name in test_group_names:
            assert name in found_groups, f"Группа {name} не найдена"
        
        # Проверяем иерархию: test1-2 должна иметь родителя test1
        if "test1" in found_groups and "test1-2" in found_groups:
            test1_id = found_groups["test1"].get("id")
            test1_2_parent_id = found_groups["test1-2"].get("parent_id")
            
            if test1_2_parent_id:
                assert test1_2_parent_id == test1_id, \
                    f"Группа test1-2 должна иметь родителя test1, но имеет parent_id={test1_2_parent_id}"
                logger.info("✓ Иерархия групп проверена: test1-2 является дочерней test1")
    
    def test_08_assets_in_groups_after_scan(self):
        """Тест 8: Активы в группах появляются после сканирования."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 8: Активы в группах после сканирования")
        
        # Получаем активы из БД
        async def get_assets_with_groups():
            async with async_session_maker() as db:
                query = select(Asset, Group).join(Group, isouter=True)
                result = await db.execute(query)
                rows = result.all()
                
                assets_data = []
                for asset, group in rows:
                    assets_data.append({
                        "id": asset.id,
                        "dns_name": asset.dns_name,
                        "ip_address": asset.ip_address,
                        "group_id": asset.group_id,
                        "group_name": group.name if group else None
                    })
                return assets_data
        
        assets = asyncio.run(get_assets_with_groups())
        
        # Проверяем что есть активы с тестовыми целями
        test_targets = ["ya.ru", "1.1.1.1", "8.8.8.8"]
        found_assets = []
        
        for asset in assets:
            dns = asset.get("dns_name", "")
            ip = asset.get("ip_address", "")
            
            for target in test_targets:
                if target in dns or target == ip:
                    found_assets.append(asset)
                    logger.info(f"✓ Найден актив: {dns or ip}, группа: {asset.get('group_name')}")
        
        assert len(found_assets) > 0, "Активы с тестовыми целями не найдены после сканирования"
        logger.info(f"✓ Всего найдено активов с тестовыми целями: {len(found_assets)}")


class TestAssetsCRUDE2E:
    """E2E тесты для CRUD операций с активами."""
    
    BASE_URL = "http://localhost:8000"
    API_URL = f"{BASE_URL}/api"
    
    created_asset_ids = []
    created_group_ids = []
    
    @pytest.fixture(scope="class", autouse=True)
    def setup_and_cleanup(self):
        """Setup: создание тестовой группы. Cleanup: удаление данных."""
        logger.info("=" * 80)
        logger.info("SETUP Assets: Создание тестовой группы")
        
        # Создаем тестовую группу
        response = requests.post(f"{self.API_URL}/groups", json={"name": "test_assets_crud"})
        assert response.status_code in [200, 201]
        self.created_group_ids.append(response.json()["id"])
        
        yield
        
        # Cleanup
        logger.info("=" * 80)
        logger.info("CLEANUP Assets: Удаление тестовых данных")
        self._cleanup_all_data()
    
    def _cleanup_all_data(self):
        """Удаление всех созданных тестовых данных."""
        async def cleanup():
            async with async_session_maker() as db:
                try:
                    # Удаляем активы
                    for asset_id in self.created_asset_ids:
                        await db.execute(delete(Asset).where(Asset.id == asset_id))
                        logger.info(f"✓ Удален актив {asset_id}")
                    
                    # Удаляем группы
                    for group_id in self.created_group_ids:
                        await db.execute(delete(Group).where(Group.id == group_id))
                        logger.info(f"✓ Удалена группа {group_id}")
                    
                    await db.commit()
                except Exception as e:
                    logger.error(f"✗ Ошибка при очистке: {e}")
                    await db.rollback()
        
        asyncio.run(cleanup())
    
    def test_09_create_asset_manually(self):
        """Тест 9: Ручное создание актива через API."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 9: Ручное создание актива")
        
        payload = {
            "dns_name": "manual-test.example.com",
            "ip_address": "192.168.1.100",
            "group_id": self.created_group_ids[0] if self.created_group_ids else None,
            "description": "Тестовый актив созданный вручную"
        }
        
        response = requests.post(f"{self.API_URL}/assets", json=payload)
        assert response.status_code in [200, 201], f"Не удалось создать актив: {response.text}"
        
        asset_data = response.json()
        asset_id = asset_data["id"]
        self.created_asset_ids.append(asset_id)
        
        logger.info(f"✓ Актив создан (ID: {asset_id})")
        
        # Проверяем что актив есть в БД
        async def check_asset():
            async with async_session_maker() as db:
                query = select(Asset).where(Asset.id == asset_id)
                result = await db.execute(query)
                asset = result.scalar_one_or_none()
                return asset
        
        asset = asyncio.run(check_asset())
        assert asset is not None, "Актив не найден в БД после создания"
        assert asset.dns_name == "manual-test.example.com"
        assert asset.ip_address == "192.168.1.100"
        logger.info("✓ Актив найден в БД и данные совпадают")
    
    def test_10_get_asset_by_id(self):
        """Тест 10: Получение актива по ID."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 10: Получение актива по ID")
        
        # Сначала создаем актив
        payload = {
            "dns_name": "get-test.example.com",
            "ip_address": "192.168.1.101",
            "group_id": self.created_group_ids[0] if self.created_group_ids else None
        }
        
        response = requests.post(f"{self.API_URL}/assets", json=payload)
        assert response.status_code in [200, 201]
        asset_id = response.json()["id"]
        self.created_asset_ids.append(asset_id)
        
        # Получаем актив по ID
        response = requests.get(f"{self.API_URL}/assets/{asset_id}")
        assert response.status_code == 200, f"Не удалось получить актив: {response.text}"
        
        asset_data = response.json()
        assert asset_data["id"] == asset_id
        assert asset_data["dns_name"] == "get-test.example.com"
        logger.info(f"✓ Актив получен по ID: {asset_id}")
    
    def test_11_update_asset(self):
        """Тест 11: Обновление актива."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 11: Обновление актива")
        
        # Создаем актив
        payload = {
            "dns_name": "update-test.example.com",
            "ip_address": "192.168.1.102",
            "group_id": self.created_group_ids[0] if self.created_group_ids else None
        }
        
        response = requests.post(f"{self.API_URL}/assets", json=payload)
        assert response.status_code in [200, 201]
        asset_id = response.json()["id"]
        self.created_asset_ids.append(asset_id)
        
        # Обновляем актив
        update_payload = {
            "dns_name": "updated-test.example.com",
            "description": "Обновленное описание"
        }
        
        response = requests.put(f"{self.API_URL}/assets/{asset_id}", json=update_payload)
        assert response.status_code == 200, f"Не удалось обновить актив: {response.text}"
        
        # Проверяем обновление в БД
        async def check_update():
            async with async_session_maker() as db:
                query = select(Asset).where(Asset.id == asset_id)
                result = await db.execute(query)
                asset = result.scalar_one_or_none()
                return asset
        
        asset = asyncio.run(check_update())
        assert asset is not None
        assert asset.dns_name == "updated-test.example.com"
        assert asset.description == "Обновленное описание"
        logger.info("✓ Актив успешно обновлен")
    
    def test_12_delete_asset(self):
        """Тест 12: Удаление актива."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 12: Удаление актива")
        
        # Создаем актив для удаления
        payload = {
            "dns_name": "delete-test.example.com",
            "ip_address": "192.168.1.103",
            "group_id": self.created_group_ids[0] if self.created_group_ids else None
        }
        
        response = requests.post(f"{self.API_URL}/assets", json=payload)
        assert response.status_code in [200, 201]
        asset_id = response.json()["id"]
        
        # Проверяем что актив существует
        async def check_exists():
            async with async_session_maker() as db:
                query = select(Asset).where(Asset.id == asset_id)
                result = await db.execute(query)
                return result.scalar_one_or_none() is not None
        
        exists_before = asyncio.run(check_exists())
        assert exists_before, "Актив не создан"
        
        # Удаляем актив
        response = requests.delete(f"{self.API_URL}/assets/{asset_id}")
        assert response.status_code == 200, f"Не удалось удалить актив: {response.text}"
        
        # Проверяем что актив удален
        exists_after = asyncio.run(check_exists())
        assert not exists_after, "Актив не удален из БД"
        logger.info(f"✓ Актив {asset_id} успешно удален")
    
    def test_13_get_assets_list(self):
        """Тест 13: Получение списка активов."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 13: Получение списка активов")
        
        response = requests.get(f"{self.API_URL}/assets")
        assert response.status_code == 200, f"Не удалось получить список активов: {response.text}"
        
        assets_data = response.json()
        assert isinstance(assets_data, list)
        logger.info(f"✓ Получено активов: {len(assets_data)}")


class TestProjectsAndHistoryE2E:
    """E2E тесты для проектов и истории сканирований."""
    
    BASE_URL = "http://localhost:8000"
    API_URL = f"{BASE_URL}/api"
    
    def test_14_get_projects_list(self):
        """Тест 14: Получение списка проектов."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 14: Получение списка проектов")
        
        response = requests.get(f"{self.API_URL}/projects")
        assert response.status_code == 200, f"Не удалось получить список проектов: {response.text}"
        
        projects_data = response.json()
        assert isinstance(projects_data, list)
        logger.info(f"✓ Получено проектов: {len(projects_data)}")
    
    def test_15_get_scan_history(self):
        """Тест 15: Получение истории сканирований."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 15: Получение истории сканирований")
        
        response = requests.get(f"{self.API_URL}/scans/history")
        assert response.status_code == 200, f"Не удалось получить историю сканирований: {response.text}"
        
        history_data = response.json()
        assert isinstance(history_data, dict) or isinstance(history_data, list)
        
        # Если это пагинация
        if isinstance(history_data, dict):
            assert "items" in history_data or "scans" in history_data
            logger.info(f"✓ История сканирований получена (пагинация)")
        else:
            logger.info(f"✓ История сканирований получена (список: {len(history_data)})")
    
    def test_16_import_nmap_page(self):
        """Тест 16: Страница импорта Nmap доступна."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 16: Страница импорта Nmap")
        
        response = requests.get(f"{self.BASE_URL}/scans/import-nmap")
        assert response.status_code == 200, f"Страница импорта Nmap недоступна: {response.status_code}"
        logger.info("✓ Страница импорта Nmap доступна")


class TestSettingsAndTaxonomyE2E:
    """E2E тесты для настроек и таксономии."""
    
    BASE_URL = "http://localhost:8000"
    API_URL = f"{BASE_URL}/api"
    
    def test_17_get_settings(self):
        """Тест 17: Получение настроек."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 17: Получение настроек")
        
        response = requests.get(f"{self.API_URL}/settings")
        assert response.status_code == 200, f"Не удалось получить настройки: {response.text}"
        logger.info("✓ Настройки получены")
    
    def test_18_asset_taxonomy_page(self):
        """Тест 18: Страница таксономии активов доступна."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 18: Страница таксономии активов")
        
        # Проверяем страницу таксономии
        response = requests.get(f"{self.BASE_URL}/taxonomy")
        assert response.status_code == 200, f"Страница таксономии недоступна: {response.status_code}"
        logger.info("✓ Страница таксономии активов доступна")
    
    def test_19_groups_list_and_tree(self):
        """Тест 19: Получение списка групп и дерева групп."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 19: Список и дерево групп")
        
        # GET /api/groups/list
        response = requests.get(f"{self.API_URL}/groups/list")
        assert response.status_code == 200, f"Не удалось получить список групп: {response.text}"
        groups_list = response.json()
        assert isinstance(groups_list, list), "Список групп должен быть списком"
        logger.info(f"✓ Получен список групп: {len(groups_list)} групп")
        
        # GET /api/groups/tree
        response = requests.get(f"{self.API_URL}/groups/tree")
        assert response.status_code == 200, f"Не удалось получить дерево групп: {response.text}"
        groups_tree = response.json()
        assert isinstance(groups_tree, list), "Дерево групп должно быть списком"
        logger.info(f"✓ Получено дерево групп: {len(groups_tree)} корневых групп")
        
        # GET /api/groups/root
        response = requests.get(f"{self.API_URL}/groups/root")
        assert response.status_code == 200, f"Не удалось получить корневую группу: {response.text}"
        logger.info("✓ Получена корневая группа")
        
        # GET /api/groups/ungrouped/count
        response = requests.get(f"{self.API_URL}/groups/ungrouped/count")
        assert response.status_code == 200, f"Не удалось получить количество негруппированных: {response.text}"
        ungrouped_count = response.json()
        assert isinstance(ungrouped_count, dict), "Ответ должен быть словарём"
        logger.info(f"✓ Получено количество негруппированных активов: {ungrouped_count}")
    
    def test_20_group_crud_operations(self):
        """Тест 20: CRUD операции с группами (GET, PUT, DELETE по ID)."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 20: CRUD операции с группами")
        
        # Создаем временную группу для тестирования
        group_name = "test-crud-group"
        payload = {"name": group_name}
        response = requests.post(f"{self.API_URL}/groups", json=payload)
        assert response.status_code in [200, 201], f"Не удалось создать группу: {response.text}"
        group_data = response.json()
        group_id = group_data["id"]
        logger.info(f"✓ Создана тестовая группа (ID: {group_id})")
        
        try:
            # GET /api/groups/{id}
            response = requests.get(f"{self.API_URL}/groups/{group_id}")
            assert response.status_code == 200, f"Не удалось получить группу по ID: {response.text}"
            group = response.json()
            assert group["name"] == group_name, "Имя группы не совпадает"
            logger.info(f"✓ Получена группа по ID: {group_id}")
            
            # PUT /api/groups/{id} - обновление имени
            new_name = "test-crud-group-updated"
            payload = {"name": new_name}
            response = requests.put(f"{self.API_URL}/groups/{group_id}", json=payload)
            assert response.status_code == 200, f"Не удалось обновить группу: {response.text}"
            updated_group = response.json()
            assert updated_group["name"] == new_name, "Имя группы не обновилось"
            logger.info(f"✓ Группа обновлена: {new_name}")
            
        finally:
            # DELETE /api/groups/{id} - удаление
            response = requests.delete(f"{self.API_URL}/groups/{group_id}")
            assert response.status_code == 204, f"Не удалось удалить группу: {response.text}"
            logger.info(f"✓ Группа {group_id} удалена")
    
    def test_21_assets_schema_and_count(self):
        """Тест 21: Схема активов и подсчёт количества."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 21: Схема активов и подсчёт")
        
        # GET /api/assets/schema
        response = requests.get(f"{self.API_URL}/assets/schema")
        assert response.status_code == 200, f"Не удалось получить схему активов: {response.text}"
        schema = response.json()
        assert isinstance(schema, dict), "Схема должна быть словарём"
        logger.info("✓ Получена схема активов")
        
        # POST /api/assets/count
        payload = {}  # Пустой фильтр - считать все
        response = requests.post(f"{self.API_URL}/assets/count", json=payload)
        assert response.status_code == 200, f"Не удалось получить количество активов: {response.text}"
        count_data = response.json()
        assert isinstance(count_data, dict), "Ответ должен быть словарём"
        assert "total" in count_data or "count" in count_data, "Ответ должен содержать количество"
        logger.info(f"✓ Получено количество активов: {count_data}")
    
    def test_22_assets_bulk_operations(self):
        """Тест 22: Массовые операции с активами (bulk-delete, bulk-move)."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 22: Массовые операции с активами")
        
        # Создаем тестовые активы
        asset_ids = []
        for i in range(2):
            payload = {"dns_name": f"bulk-test-{i}.example.com", "ip_address": f"192.168.{i}.100"}
            response = requests.post(f"{self.API_URL}/assets", json=payload)
            if response.status_code in [200, 201]:
                asset_ids.append(response.json()["id"])
        
        logger.info(f"✓ Создано {len(asset_ids)} тестовых активов для массовых операций")
        
        try:
            # POST /api/assets/bulk-move - перемещение в группу
            if asset_ids and self.created_group_ids:
                payload = {
                    "asset_ids": asset_ids,
                    "group_id": self.created_group_ids[0]
                }
                response = requests.post(f"{self.API_URL}/assets/bulk-move", json=payload)
                assert response.status_code == 200, f"Массовое перемещение не удалось: {response.text}"
                logger.info(f"✓ Активы перемещены в группу {self.created_group_ids[0]}")
            
            # POST /api/assets/bulk-delete - массовое удаление
            if asset_ids:
                payload = {"asset_ids": asset_ids}
                response = requests.post(f"{self.API_URL}/assets/bulk-delete", json=payload)
                assert response.status_code == 204, f"Массовое удаление не удалось: {response.text}"
                logger.info(f"✓ Активы массово удалены: {len(asset_ids)} шт.")
                asset_ids = []  # Очищаем чтобы не удалять повторно в cleanup
                
        finally:
            # Если остались активы - удаляем их индивидуально
            for asset_id in asset_ids:
                async def cleanup():
                    async with async_session_maker() as db:
                        await db.execute(delete(Asset).where(Asset.id == asset_id))
                        await db.commit()
                asyncio.run(cleanup())
    
    def test_23_scans_utilities_check_and_status(self):
        """Тест 23: Проверка утилит сканирования и статуса."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 23: Проверка утилит и статуса сканирований")
        
        # GET /api/scans/utilities-check
        response = requests.get(f"{self.API_URL}/scans/utilities-check")
        assert response.status_code == 200, f"Не удалось проверить утилиты: {response.text}"
        utilities = response.json()
        assert isinstance(utilities, dict), "Ответ должен быть словарём"
        logger.info(f"✓ Проверка утилит: {list(utilities.keys())}")
        
        # GET /api/scans/status
        response = requests.get(f"{self.API_URL}/scans/status")
        assert response.status_code == 200, f"Не удалось получить статус: {response.text}"
        status = response.json()
        assert isinstance(status, dict), "Ответ должен быть словарём"
        logger.info(f"✓ Статус сканирований: {status}")
        
        # GET /api/scans/active
        response = requests.get(f"{self.API_URL}/scans/active")
        assert response.status_code == 200, f"Не удалось получить активные сканирования: {response.text}"
        active_scans = response.json()
        assert isinstance(active_scans, list), "Ответ должен быть списком"
        logger.info(f"✓ Активные сканирования: {len(active_scans)}")
    
    def test_24_scans_queue_and_jobs(self):
        """Тест 24: Очередь сканирований и управление задачами."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 24: Очередь сканирований и задачи")
        
        # GET /api/scans/scan-queue
        response = requests.get(f"{self.API_URL}/scans/scan-queue")
        assert response.status_code == 200, f"Не удалось получить очередь: {response.text}"
        queue = response.json()
        assert isinstance(queue, list), "Очередь должна быть списком"
        logger.info(f"✓ Очередь сканирований: {len(queue)} задач")
        
        # GET /api/scans/scan-job
        response = requests.get(f"{self.API_URL}/scans/scan-job")
        assert response.status_code == 200, f"Не удалось получить задачи: {response.text}"
        jobs = response.json()
        assert isinstance(jobs, list), "Задачи должны быть списком"
        logger.info(f"✓ Задачи сканирований: {len(jobs)}")
        
        # Если есть задачи в очереди - проверяем детали
        if queue:
            job_id = queue[0].get("id") or queue[0].get("job_id")
            if job_id:
                # GET /api/scans/scan-queue/{job_id}
                response = requests.get(f"{self.API_URL}/scans/scan-queue/{job_id}")
                if response.status_code == 200:
                    logger.info(f"✓ Получена информация о задаче {job_id}")
                
                # GET /api/scans/scan-job/{job_id}
                response = requests.get(f"{self.API_URL}/scans/scan-job/{job_id}")
                if response.status_code == 200:
                    logger.info(f"✓ Получена детальная информация о задаче {job_id}")
    
    def test_25_projects_crud_operations(self):
        """Тест 25: CRUD операции с проектами."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 25: CRUD операции с проектами")
        
        # Создаем тестовый проект
        project_name = "test-e2e-project"
        payload = {"name": project_name, "description": "E2E тестовый проект"}
        response = requests.post(f"{self.API_URL}/projects", json=payload)
        assert response.status_code in [200, 201], f"Не удалось создать проект: {response.text}"
        project_data = response.json()
        project_id = project_data["id"]
        logger.info(f"✓ Создан тестовый проект (ID: {project_id})")
        
        try:
            # GET /api/projects/{id}
            response = requests.get(f"{self.API_URL}/projects/{project_id}")
            assert response.status_code == 200, f"Не удалось получить проект: {response.text}"
            project = response.json()
            assert project["name"] == project_name, "Имя проекта не совпадает"
            logger.info(f"✓ Получен проект по ID: {project_id}")
            
            # PUT /api/projects/{id}
            new_description = "Обновленное описание"
            payload = {"description": new_description}
            response = requests.put(f"{self.API_URL}/projects/{project_id}", json=payload)
            assert response.status_code == 200, f"Не удалось обновить проект: {response.text}"
            logger.info(f"✓ Проект обновлен")
            
            # GET /api/projects/{id}/reports
            response = requests.get(f"{self.API_URL}/projects/{project_id}/reports")
            assert response.status_code == 200, f"Не удалось получить отчеты: {response.text}"
            reports = response.json()
            assert isinstance(reports, list), "Отчеты должны быть списком"
            logger.info(f"✓ Отчеты проекта: {len(reports)}")
            
            # GET /api/projects/{id}/artifacts
            response = requests.get(f"{self.API_URL}/projects/{project_id}/artifacts")
            assert response.status_code == 200, f"Не удалось получить артефакты: {response.text}"
            artifacts = response.json()
            assert isinstance(artifacts, list), "Артефакты должны быть списком"
            logger.info(f"✓ Артефакты проекта: {len(artifacts)}")
            
            # GET /api/projects/{id}/sessions
            response = requests.get(f"{self.API_URL}/projects/{project_id}/sessions")
            assert response.status_code == 200, f"Не удалось получить сессии: {response.text}"
            sessions = response.json()
            assert isinstance(sessions, list), "Сессии должны быть списком"
            logger.info(f"✓ Сессии проекта: {len(sessions)}")
            
        finally:
            # DELETE /api/projects/{id}
            response = requests.delete(f"{self.API_URL}/projects/{project_id}")
            assert response.status_code == 204, f"Не удалось удалить проект: {response.text}"
            logger.info(f"✓ Проект {project_id} удален")


class TestAssetsMergeLogic:
    """E2E тесты для проверки логики слияния результатов сканирования в активах."""

    BASE_URL = "http://localhost:8000"
    API_URL = f"{BASE_URL}/api"

    created_scan_ids = []
    created_asset_ids = []
    created_group_ids = []

    @pytest.fixture(scope="class", autouse=True)
    def setup_and_cleanup(self):
        """Setup: создание тестовой группы. Cleanup: удаление данных."""
        logger.info("=" * 80)
        logger.info("SETUP Merge: Создание тестовой группы")

        # Создаем тестовую группу
        response = requests.post(f"{self.API_URL}/groups", json={"name": "test_merge_logic"})
        assert response.status_code in [200, 201]
        self.created_group_ids.append(response.json()["id"])

        yield

        # Cleanup
        logger.info("=" * 80)
        logger.info("CLEANUP Merge: Удаление тестовых данных")
        self._cleanup_all_data()

    def _cleanup_all_data(self):
        """Удаление всех созданных тестовых данных."""
        async def cleanup():
            async with async_session_maker() as db:
                try:
                    # Удаляем результаты сканирований
                    for scan_id in self.created_scan_ids:
                        await db.execute(delete(ScanResult).where(ScanResult.scan_id == scan_id))
                        await db.execute(delete(Scan).where(Scan.id == scan_id))
                        logger.info(f"✓ Удалено сканирование {scan_id}")

                    # Удаляем активы
                    for asset_id in self.created_asset_ids:
                        await db.execute(delete(Asset).where(Asset.id == asset_id))
                        logger.info(f"✓ Удален актив {asset_id}")

                    # Удаляем группы
                    for group_id in self.created_group_ids:
                        await db.execute(delete(Group).where(Group.id == group_id))
                        logger.info(f"✓ Удалена группа {group_id}")

                    await db.commit()
                except Exception as e:
                    logger.error(f"✗ Ошибка при очистке: {e}")
                    await db.rollback()

        asyncio.run(cleanup())

    def _wait_for_scan_completion(self, scan_id: int, timeout: int = 120) -> bool:
        """Ожидание завершения сканирования через опрос БД."""
        start_time = time.time()
        
        async def check_status():
            async with async_session_maker() as db:
                query = select(Scan).where(Scan.id == scan_id)
                result = await db.execute(query)
                scan = result.scalar_one_or_none()
                
                if not scan:
                    return False, "not_found"
                
                if scan.status == ScanStatus.COMPLETED.value:
                    return True, "completed"
                elif scan.status == ScanStatus.FAILED.value:
                    return False, "failed"
                
                return False, "running"

        while time.time() - start_time < timeout:
            completed, status = asyncio.run(check_status())
            if completed or status == "failed":
                return completed
            time.sleep(2)
        
        return False

    def _get_assets_by_target(self, target: str) -> list:
        """Получение активов по целевому хосту из БД."""
        async def fetch_assets():
            async with async_session_maker() as db:
                query = select(Asset).where(
                    or_(
                        Asset.dns_name == target,
                        Asset.ip_address == target
                    )
                )
                result = await db.execute(query)
                return result.scalars().all()
        
        return asyncio.run(fetch_assets())

    def test_19_merge_nmap_rustscan_same_host(self):
        """Тест 19: Слияние результатов Nmap и Rustscan для одного хоста."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 19: Слияние Nmap + Rustscan для 1.1.1.1")

        target_ip = "1.1.1.1"
        group_id = self.created_group_ids[0]

        # Шаг 1: Запуск Nmap
        logger.info("Запуск Nmap...")
        nmap_payload = {
            "utility": "nmap",
            "target": target_ip,
            "group_id": group_id,
            "arguments": "-sV -T4"
        }
        response = requests.post(f"{self.API_URL}/scans/scan", json=nmap_payload)
        assert response.status_code == 200
        nmap_scan_id = response.json()["scan_id"]
        self.created_scan_ids.append(nmap_scan_id)

        # Ожидание завершения Nmap
        assert self._wait_for_scan_completion(nmap_scan_id), "Nmap сканирование не завершилось"
        logger.info("✓ Nmap завершен")

        # Получаем актив после Nmap
        assets_after_nmap = self._get_assets_by_target(target_ip)
        assert len(assets_after_nmap) > 0, "Актив не создан после Nmap"
        nmap_asset = assets_after_nmap[0]
        nmap_ports = set(nmap_asset.ports) if nmap_asset.ports else set()
        logger.info(f"Порты после Nmap: {nmap_ports}")

        # Шаг 2: Запуск Rustscan для того же хоста
        logger.info("Запуск Rustscan...")
        rustscan_payload = {
            "utility": "rustscan",
            "target": target_ip,
            "group_id": group_id,
            "arguments": "-a 1000-2000"
        }
        response = requests.post(f"{self.API_URL}/scans/scan", json=rustscan_payload)
        assert response.status_code == 200
        rustscan_scan_id = response.json()["scan_id"]
        self.created_scan_ids.append(rustscan_scan_id)

        # Ожидание завершения Rustscan
        assert self._wait_for_scan_completion(rustscan_scan_id), "Rustscan сканирование не завершилось"
        logger.info("✓ Rustscan завершен")

        # Проверка слияния
        assets_after_merge = self._get_assets_by_target(target_ip)
        assert len(assets_after_merge) > 0, "Актив не найден после слияния"
        
        merged_asset = assets_after_merge[0]
        merged_ports = set(merged_asset.ports) if merged_asset.ports else set()
        
        logger.info(f"Порты после слияния: {merged_ports}")
        logger.info(f"Порты Nmap: {nmap_ports}")
        
        # Проверяем что порты объединились (хотя бы часть портов от каждого)
        assert len(merged_ports) >= len(nmap_ports), "Порты не объединились корректно"
        assert merged_asset.last_scan_date is not None, "Дата последнего сканирования не обновлена"
        
        logger.info("✓ Слияние Nmap + Rustscan прошло успешно")

    def test_20_merge_dns_and_ip_fping(self):
        """Тест 20: Слияние результатов сканирования домена и IP через Fping."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 20: Слияние DNS + IP через Fping")

        target_dns = "ya.ru"
        target_ip = "8.8.8.8"
        group_id = self.created_group_ids[0]

        # Шаг 1: Fping для домена
        logger.info("Запуск Fping для домена...")
        fping_dns_payload = {
            "utility": "fping",
            "target": target_dns,
            "group_id": group_id
        }
        response = requests.post(f"{self.API_URL}/scans/scan", json=fping_dns_payload)
        assert response.status_code == 200
        fping_dns_scan_id = response.json()["scan_id"]
        self.created_scan_ids.append(fping_dns_scan_id)

        assert self._wait_for_scan_completion(fping_dns_scan_id), "Fping DNS сканирование не завершилось"
        logger.info("✓ Fping DNS завершен")

        # Шаг 2: Fping для IP
        logger.info("Запуск Fping для IP...")
        fping_ip_payload = {
            "utility": "fping",
            "target": target_ip,
            "group_id": group_id
        }
        response = requests.post(f"{self.API_URL}/scans/scan", json=fping_ip_payload)
        assert response.status_code == 200
        fping_ip_scan_id = response.json()["scan_id"]
        self.created_scan_ids.append(fping_ip_scan_id)

        assert self._wait_for_scan_completion(fping_ip_scan_id), "Fping IP сканирование не завершилось"
        logger.info("✓ Fping IP завершен")

        # Проверка что активы созданы и обновлены
        dns_assets = self._get_assets_by_target(target_dns)
        ip_assets = self._get_assets_by_target(target_ip)

        assert len(dns_assets) > 0, f"Актив для {target_dns} не найден"
        assert len(ip_assets) > 0, f"Актив для {target_ip} не найден"

        # Проверяем что статус 'up' у обоих
        dns_asset = dns_assets[0]
        ip_asset = ip_assets[0]

        assert dns_asset.status == "up", f"Статус DNS актива должен быть 'up', получен: {dns_asset.status}"
        assert ip_asset.status == "up", f"Статус IP актива должен быть 'up', получен: {ip_asset.status}"

        logger.info(f"✓ DNS актив: {dns_asset.dns_name}, статус: {dns_asset.status}")
        logger.info(f"✓ IP актив: {ip_asset.ip_address}, статус: {ip_asset.status}")
        logger.info("✓ Слияние DNS + IP через Fping прошло успешно")

    def test_21_merge_dig_expands_assets(self):
        """Тест 21: Dig расширяет активы через DNS записи."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 21: Dig расширяет активы через DNS записи")

        target_dns = "ya.ru"
        group_id = self.created_group_ids[0]

        # Получаем количество активов до Dig
        assets_before = self._get_assets_by_target(target_dns)
        count_before = len(assets_before)

        # Запуск Dig
        logger.info("Запуск Dig...")
        dig_payload = {
            "utility": "dig",
            "target": target_dns,
            "group_id": group_id,
            "arguments": "A"
        }
        response = requests.post(f"{self.API_URL}/scans/scan", json=dig_payload)
        assert response.status_code == 200
        dig_scan_id = response.json()["scan_id"]
        self.created_scan_ids.append(dig_scan_id)

        assert self._wait_for_scan_completion(dig_scan_id), "Dig сканирование не завершилось"
        logger.info("✓ Dig завершен")

        # Проверка результатов
        assets_after = self._get_assets_by_target(target_dns)
        assert len(assets_after) > 0, "Актив для домена не найден после Dig"

        dig_asset = assets_after[0]
        
        # Проверяем что есть DNS записи
        has_dns_records = False
        if dig_asset.dns_records:
            has_dns_records = len(dig_asset.dns_records) > 0
        
        logger.info(f"DNS записи: {dig_asset.dns_records}")
        
        # Актив должен иметь DNS записи или связанные IP
        assert has_dns_records or dig_asset.ip_address, "Dig не добавил DNS записи или IP"
        
        logger.info("✓ Dig расширил активы DNS записями")

    def test_22_sequential_scans_field_updates(self):
        """Тест 22: Последовательные сканирования обновляют поля актива."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 22: Последовательные сканирования обновляют поля")

        target_ip = "1.1.1.1"
        group_id = self.created_group_ids[0]

        # Первое сканирование (Nmap)
        logger.info("Первое сканирование (Nmap)...")
        scan1_payload = {
            "utility": "nmap",
            "target": target_ip,
            "group_id": group_id
        }
        response = requests.post(f"{self.API_URL}/scans/scan", json=scan1_payload)
        assert response.status_code == 200
        scan1_id = response.json()["scan_id"]
        self.created_scan_ids.append(scan1_id)

        assert self._wait_for_scan_completion(scan1_id), "Первое сканирование не завершилось"

        # Получаем актив после первого сканирования
        assets_1 = self._get_assets_by_target(target_ip)
        assert len(assets_1) > 0
        asset_1 = assets_1[0]
        first_scan_date = asset_1.last_scan_date
        first_updated_at = asset_1.updated_at
        logger.info(f"После 1-го сканирования: last_scan_date={first_scan_date}")

        # Ждем немного чтобы更新时间 отличалось
        time.sleep(2)

        # Второе сканирование (Rustscan)
        logger.info("Второе сканирование (Rustscan)...")
        scan2_payload = {
            "utility": "rustscan",
            "target": target_ip,
            "group_id": group_id
        }
        response = requests.post(f"{self.API_URL}/scans/scan", json=scan2_payload)
        assert response.status_code == 200
        scan2_id = response.json()["scan_id"]
        self.created_scan_ids.append(scan2_id)

        assert self._wait_for_scan_completion(scan2_id), "Второе сканирование не завершилось"

        # Получаем актив после второго сканирования
        assets_2 = self._get_assets_by_target(target_ip)
        assert len(assets_2) > 0
        asset_2 = assets_2[0]

        logger.info(f"После 2-го сканирования: last_scan_date={asset_2.last_scan_date}")
        logger.info(f"updated_at: {asset_2.updated_at}")

        # Проверяем что поля обновились
        assert asset_2.last_scan_date >= first_scan_date, "last_scan_date не обновилось"
        assert asset_2.updated_at >= first_updated_at, "updated_at не обновилось"

        # Проверяем что данные не потерялись (порты должны быть)
        assert asset_2.ports is not None, "Данные о портах потеряны"

        logger.info("✓ Последовательные сканирования корректно обновляют поля")


# Запуск тестов: pytest tests/e2e/test_headless_scan_e2e.py -v
