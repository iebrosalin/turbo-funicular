from playwright.sync_api import expect

def test_settings_page_loads(page):
    """Проверка загрузки страницы настроек"""
    page.goto("/settings")
    expect(page).to_have_title("Настройки - Asset Management")
    expect(page.locator("h2")).to_contain_text("Настройки")

def test_theme_toggle_exists(page):
    """Проверка наличия переключателя темы на странице настроек"""
    page.goto("/settings")
    
    theme_toggle = page.locator("#themeToggle")
    expect(theme_toggle).to_be_visible()

def test_theme_switching(page):
    """Проверка переключения темы"""
    page.goto("/settings")
    
    # Получаем текущий фон
    initial_bg = page.locator("body").evaluate("el => getComputedStyle(el).backgroundColor")
    
    # Кликаем по переключателю
    theme_toggle = page.locator("#themeToggle")
    theme_toggle.click()
    
    page.wait_for_timeout(500)
    
    # Проверяем что фон изменился
    new_bg = page.locator("body").evaluate("el => getComputedStyle(el).backgroundColor")
    assert initial_bg != new_bg, "Цвет фона не изменился после переключения темы"
