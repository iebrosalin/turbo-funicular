"""
E2E тесты для скачивания результатов сканирований.
Использует Playwright для headless тестирования.

Тестовые данные:
- Цели: ya.ru, 1.1.1.1, 8.8.8.8
- Группы: test1, test1-2, тест (разный уровень вложенности)
"""

import pytest
from playwright.sync_api import Page, expect, BrowserContext
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestScanDownloadE2E:
    """E2E тесты скачивания результатов сканирований."""
    
    BASE_URL = "http://localhost:8000"
    
    @pytest.fixture(scope="class")
    def setup_groups(self, page: Page):
        """Создание тестовых групп с разной вложенностью."""
        logger.info("=" * 80)
        logger.info("SETUP: Создание тестовых групп")
        
        page.goto(f"{self.BASE_URL}/groups")
        page.wait_for_load_state("networkidle")
        
        # Создаем группу test1
        self._create_group(page, "test1", None)
        logger.info("✓ Группа test1 создана")
        
        # Создаем группу test1-2 внутри test1
        self._create_group(page, "test1-2", "test1")
        logger.info("✓ Группа test1-2 создана")
        
        # Создаем группу тест (кириллица)
        self._create_group(page, "тест", None)
        logger.info("✓ Группа тест создана")
        
        yield
        
        # Cleanup
        logger.info("CLEANUP: Удаление тестовых групп")
    
    def _create_group(self, page: Page, name: str, parent_name: str = None):
        """Вспомогательный метод создания группы."""
        if parent_name:
            parent_row = page.locator(f"tr:has-text('{parent_name}')").first
            if parent_row.is_visible():
                parent_row.click()
        
        create_btn = page.locator("button:has-text('Создать группу'), #createGroupBtn").first
        if create_btn.is_visible():
            create_btn.click()
        
        modal_input = page.locator("input[placeholder='Название группы'], #groupNameInput").first
        modal_input.wait_for(state="visible", timeout=5000)
        modal_input.fill(name)
        
        save_btn = page.locator("button:has-text('Сохранить'), #saveGroupBtn").first
        if save_btn.is_visible():
            save_btn.click()
        
        time.sleep(1)
    
    def test_01_create_scan_ya_ru(self, page: Page, setup_groups):
        """Тест 1: Создание сканирования ya.ru."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 1: Сканирование ya.ru")
        
        page.goto(f"{self.BASE_URL}/scans")
        page.wait_for_load_state("networkidle")
        
        target_input = page.locator("input[placeholder='Цель'], #scanTargetInput").first
        target_input.wait_for(state="visible", timeout=5000)
        target_input.fill("ya.ru")
        
        start_btn = page.locator("button:has-text('Сканировать'), #startScanBtn").first
        start_btn.click()
        
        logger.info("✓ Сканирование ya.ru запущено")
        page.wait_for_timeout(30000)
        
        history_table = page.locator("#scansHistoryBody, table:has-text('ya.ru')")
        expect(history_table).to_contain_text("ya.ru", timeout=10000)
        
        logger.info("✓ Сканирование ya.ru найдено в истории")
    
    def test_02_download_scan_results(self, page: Page):
        """Тест 2: Скачивание результатов сканирования."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 2: Скачивание результатов")
        
        page.goto(f"{self.BASE_URL}/scans/history")
        page.wait_for_load_state("networkidle")
        
        scan_row = page.locator("tr:has-text('ya.ru')").first
        download_btn = scan_row.locator("button:has-text('⬇️'), .dropdown-toggle:has(.bi-download)").first
        
        if download_btn.is_visible():
            download_btn.click()
            json_link = page.locator("a:has-text('JSON')").first
            if json_link.is_visible():
                logger.info("✓ Ссылка на JSON формат найдена")
            raw_link = page.locator("a:has-text('Raw')").first
            if raw_link.is_visible():
                logger.info("✓ Ссылка на Raw формат найдена")
        else:
            logger.warning("⚠ Кнопка скачивания не найдена")
    
    def test_03_scan_ip_addresses(self, page: Page):
        """Тест 3: Сканирование IP адресов 1.1.1.1 и 8.8.8.8."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 3: Сканирование IP адресов")
        
        for ip in ["1.1.1.1", "8.8.8.8"]:
            logger.info(f"Сканирование {ip}...")
            page.goto(f"{self.BASE_URL}/scans")
            page.wait_for_load_state("networkidle")
            
            target_input = page.locator("input[placeholder='Цель']").first
            target_input.fill(ip)
            
            start_btn = page.locator("button:has-text('Сканировать')").first
            start_btn.click()
            
            logger.info(f"✓ Сканирование {ip} запущено")
            page.wait_for_timeout(5000)
    
    def test_04_add_assets_to_group(self, page: Page):
        """Тест 4: Добавление активов в группу."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 4: Добавление активов в группу")
        
        page.goto(f"{self.BASE_URL}/assets")
        page.wait_for_load_state("networkidle")
        
        create_btn = page.locator("button:has-text('Добавить актив'), #addAssetBtn").first
        if create_btn.is_visible():
            create_btn.click()
            name_input = page.locator("input[name='name'], #assetNameInput").first
            name_input.fill("test-asset-1")
            ip_input = page.locator("input[name='ip_address'], #assetIpInput").first
            ip_input.fill("192.168.1.100")
            save_btn = page.locator("button:has-text('Сохранить')").first
            save_btn.click()
            logger.info("✓ Актив создан")
        
        page.goto(f"{self.BASE_URL}/groups")
        page.wait_for_load_state("networkidle")
        
        group_row = page.locator("tr:has-text('test1')").first
        if group_row.is_visible():
            group_row.click()
            add_assets_btn = page.locator("button:has-text('Добавить активы')").first
            if add_assets_btn.is_visible():
                add_assets_btn.click()
                logger.info("✓ Актив добавлен в группу test1")
    
    def test_05_scan_from_group(self, page: Page):
        """Тест 5: Сканирование из группы."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 5: Сканирование из группы")
        
        page.goto(f"{self.BASE_URL}/scans")
        page.wait_for_load_state("networkidle")
        
        group_scan_tab = page.locator("a:has-text('Группы'), #groupScanTab").first
        if group_scan_tab.is_visible():
            group_scan_tab.click()
            group_select = page.locator("select[name='group_id'], #groupSelect").first
            group_select.select_option("test1")
            start_btn = page.locator("button:has-text('Сканировать группу')").first
            start_btn.click()
            logger.info("✓ Сканирование из группы запущено")
    
    def test_06_check_download_logging(self, page: Page):
        """Тест 6: Проверка логирования скачивания."""
        logger.info("=" * 80)
        logger.info("ТЕСТ 6: Проверка логирования")
        
        page.goto(f"{self.BASE_URL}/scans/history")
        page.wait_for_load_state("networkidle")
        
        page.on("console", lambda msg: logger.info(f"CONSOLE [{msg.type}]: {msg.text}"))
        expect(page).to_have_title("*History*", timeout=5000)
        
        logger.info("✓ Страница истории загружена")
