"""
E2E Tests for Scanners (Dig, Nmap, Rustscan) using Playwright.
Tests real scanning execution and UI updates.
"""
import pytest
from playwright.sync_api import Page, expect
import time
import uuid

# Base URL is passed via fixture conftest.py (BASE_URL)

def test_dig_scan_ya_ru(page: Page, base_url: str):
    """
    1. Запуск Dig сканирования для ya.ru
    2. Ожидание завершения задачи
    3. Проверка появления актива в таблице
    4. Переход на детальную страницу актива
    """
    page.goto(f"{base_url}/utilities")
    
    # Запуск Dig скана
    page.fill("#dig-domain-input", "ya.ru")
    page.click("#btn-run-dig")
    
    # Ожидание появления задачи в очереди
    expect(page.locator(".scan-queue-item")).to_be_visible(timeout=10000)
    
    # Ждем выполнения (для E2E теста может потребоваться время)
    # В реальном тесте лучше поллить статус, здесь упрощенно ждем
    page.wait_for_timeout(5000) 
    
    # Переход к активам
    page.goto(f"{base_url}/")
    
    # Ожидание появления IP адреса ya.ru в таблице
    # Dig обычно возвращает несколько IP, проверяем наличие любой записи с ya.ru или его IP
    # Для надежности ищем по hostname или IP, если он известен заранее
    # Здесь предполагаем, что актив появится с hostname ya.ru
    asset_row = page.locator(f"tr:has-text('ya.ru')").first
    expect(asset_row).to_be_visible(timeout=30000)
    
    # Клик по строке для перехода к деталям
    asset_row.click()
    
    # Проверка, что открылась детальная страница (URL изменился или виден заголовок)
    expect(page).to_have_url(f"{base_url}/assets/*")
    expect(page.locator("h5:has-text('ya.ru')")).to_be_visible()


def test_nmap_scan_google_dns(page: Page, base_url: str):
    """
    1. Запуск Nmap сканирования 8.8.8.8
    2. Ожидание результата
    3. Проверка актива 8.8.8.8 в дашборде
    4. Открытие детальной страницы
    """
    target_ip = "8.8.8.8"
    
    page.goto(f"{base_url}/scans")
    
    # Запуск Nmap
    page.fill("#nmap-target-input", target_ip)
    page.select_option("#nmap-scan-type", "quick") # или другой профиль
    page.click("#btn-start-nmap")
    
    # Ожидание в очереди
    expect(page.locator(".scan-queue-item")).to_be_visible(timeout=10000)
    
    # Ждем завершения сканирования (Nmap может быть долгим, ставим большой таймаут или поллинг)
    # Для теста можно использовать быстрый профиль
    page.wait_for_timeout(15000) 
    
    # Переход на дашборд
    page.goto(f"{base_url}/")
    
    # Поиск актива по IP
    asset_row = page.locator(f"tr:has-text('{target_ip}')").first
    expect(asset_row).to_be_visible(timeout=30000)
    
    # Проверка перехода на детальную страницу
    asset_row.click()
    expect(page).to_have_url(f"{base_url}/assets/*")
    expect(page.locator(f"h5:has-text('{target_ip}')")).to_be_visible()


def test_rustscan_port_80(page: Page, base_url: str):
    """
    1. Запуск Rustscan для 8.8.8.8:80
    2. Проверка обнаружения порта 80
    3. Верификация в UI
    """
    target_ip = "8.8.8.8"
    
    page.goto(f"{base_url}/scans")
    
    # Запуск Rustscan
    page.fill("#rustscan-target-input", f"{target_ip}:80")
    page.click("#btn-start-rustscan")
    
    # Ожидание очереди
    expect(page.locator(".scan-queue-item")).to_be_visible(timeout=10000)
    
    # Rustscan быстрый, ждем меньше
    page.wait_for_timeout(10000)
    
    page.goto(f"{base_url}/")
    
    # Находим актив
    asset_row = page.locator(f"tr:has-text('{target_ip}')").first
    expect(asset_row).to_be_visible(timeout=30000)
    
    # Кликаем для деталей
    asset_row.click()
    
    # Проверяем наличие порта 80 в списке
    # Селектор зависит от верстки карточки портов
    expect(page.locator("text=80")).to_be_visible(timeout=10000)
    
    # Дополнительно: проверка источника "Сканирование"
    expect(page.locator("text=🔍 Сканирование")).to_be_visible()
