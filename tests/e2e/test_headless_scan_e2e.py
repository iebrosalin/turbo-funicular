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
