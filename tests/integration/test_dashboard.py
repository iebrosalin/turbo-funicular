from playwright.sync_api import expect

def test_dashboard_loads(page):
    """Проверка загрузки дашборда"""
    page.goto("/")
    expect(page).to_have_title("Asset Management")
    expect(page.locator("h1")).to_contain_text("Активы")

def test_dark_theme_default(page):
    """Проверка что тема по умолчанию тёмная"""
    page.goto("/")
    # Ждем применения темы
    page.wait_for_timeout(1000)
    body = page.locator("body")
    # Проверяем наличие класса dark или стилей темной темы
    assert body.evaluate("el => getComputedStyle(el).backgroundColor") != "rgb(255, 255, 255)"

def test_assets_table_exists(page):
    """Проверка наличия таблицы активов"""
    page.goto("/")
    table = page.locator("#assets-table")
    expect(table).to_be_visible()
    
    # Проверка заголовков
    headers = table.locator("thead th")
    expect(headers.first).to_be_visible()

def test_filter_panel_exists(page):
    """Проверка наличия панели фильтров"""
    page.goto("/")
    filter_panel = page.locator("#filterPanel")
    expect(filter_panel).to_be_visible()
    
    # Проверка кнопки применения фильтров
    apply_btn = page.locator("#btn-apply-filters")
    expect(apply_btn).to_be_visible()

def test_settings_page_exists(page):
    """Проверка страницы настроек"""
    page.goto("/settings")
    expect(page).to_have_title("Настройки - Asset Management")
    expect(page.locator("h2")).to_contain_text("Настройки")
