import pytest
import time
import os
from playwright.sync_api import Playwright, expect

# Базовый URL приложения внутри Docker сети
BASE_URL = os.getenv("BASE_URL", "http://web:5000")

@pytest.fixture(scope="session")
def wait_for_app():
    """Ждем пока приложение будет готово принимать соединения"""
    import requests
    max_retries = 30
    for i in range(max_retries):
        try:
            resp = requests.get(BASE_URL, timeout=2)
            if resp.status_code == 200:
                print(f"✅ Приложение готово на {BASE_URL}")
                return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError("Приложение не запустилось в течение 30 секунд")

@pytest.fixture(scope="function")
def page(playwright: Playwright, wait_for_app):
    """Фикстура страницы браузера с базовыми настройками"""
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        base_url=BASE_URL
    )
    page = context.new_page()
    yield page
    context.close()
    browser.close()
