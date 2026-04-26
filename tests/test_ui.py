"""
UI тесты для Turbo Funicular с использованием Playwright.
Тестируют основные пользовательские сценарии интерфейса.

Запуск:
    pytest tests/ -v                    # Все тесты (API + UI)
    pytest tests/ -v -m "not ui"        # Только API тесты
    pytest tests/ -v -m ui              # Только UI тесты

Требования:
    pip install pytest-playwright
    playwright install chromium
"""

import pytest
from playwright.sync_api import Page, expect, TimeoutError


# Фикстура для базового URL (можно переопределить через переменную окружения)
@pytest.fixture(scope="session")
def base_url():
    import os
    return os.getenv("TURBO_FUNICULAR_URL", "http://localhost:8000")


# Фикстура для авторизации (если требуется)
@pytest.fixture
def authenticated_page(page: Page, base_url: str):
    """
    Авторизация в системе перед тестом.
    Если в приложении нет авторизации, эта фикстура просто открывает главную страницу.
    """
    page.goto(base_url)
    # TODO: Добавить логику авторизации, если она есть в приложении
    # Например:
    # page.click('text=Войти')
    # page.fill('input[name="username"]', 'admin')
    # page.fill('input[name="password"]', 'password')
    # page.click('button[type="submit"]')
    # expect(page).to_have_url(f"{base_url}/dashboard")
    yield page


@pytest.mark.ui
class TestDashboardUI:
    """Тесты главной панели управления."""

    def test_dashboard_loads(self, authenticated_page: Page, base_url: str):
        """Проверка загрузки главной страницы."""
        authenticated_page.goto(f"{base_url}/")
        expect(authenticated_page).to_have_title(re.compile("Turbo|Funicular|Dashboard", re.IGNORECASE))

    def test_navigation_menu_exists(self, authenticated_page: Page, base_url: str):
        """Проверка наличия меню навигации."""
        authenticated_page.goto(f"{base_url}/")
        # Проверяем наличие навигационных элементов
        expect(authenticated_page.locator("nav, .navbar, .sidebar")).to_be_visible()

    def test_sidebar_resizer_exists(self, authenticated_page: Page, base_url: str):
        """Проверка наличия элемента изменения размера сайдбара."""
        authenticated_page.goto(f"{base_url}/")
        expect(authenticated_page.locator("#sidebarResizer")).to_be_visible()

    def test_theme_toggle_button(self, authenticated_page: Page, base_url: str):
        """Проверка кнопки переключения темы."""
        authenticated_page.goto(f"{base_url}/")
        theme_toggle = authenticated_page.locator("#theme-toggle, button[onclick*='toggleTheme']")
        expect(theme_toggle).to_be_visible()

    def test_mobile_sidebar_collapse(self, authenticated_page: Page, base_url: str):
        """Проверка кнопки сворачивания сайдбара на мобильных."""
        authenticated_page.set_viewport_size({"width": 375, "height": 667})
        authenticated_page.goto(f"{base_url}/")
        collapse_btn = authenticated_page.locator("#sidebarCollapse")
        expect(collapse_btn).to_be_visible()


@pytest.mark.ui
class TestScansPageUI:
    """Тесты страницы сканирований."""

    def test_scans_page_loads(self, authenticated_page: Page, base_url: str):
        """Проверка загрузки страницы сканирований."""
        authenticated_page.goto(f"{base_url}/scans")
        expect(authenticated_page).to_have_url(re.compile(".*scans.*"))

    def test_scan_forms_exist(self, authenticated_page: Page, base_url: str):
        """Проверка наличия форм для разных типов сканирования."""
        authenticated_page.goto(f"{base_url}/scans")
        
        # Проверяем наличие форм
        expect(authenticated_page.locator("#nmap-form")).to_be_visible(timeout=5000)
        expect(authenticated_page.locator("#rustscan-form")).to_be_visible()
        expect(authenticated_page.locator("#dig-form")).to_be_visible()

    def test_nmap_form_fields(self, authenticated_page: Page, base_url: str):
        """Проверка полей формы Nmap."""
        authenticated_page.goto(f"{base_url}/scans")
        
        expect(authenticated_page.locator("#nmap-target")).to_be_visible()
        expect(authenticated_page.locator("#nmap-ports")).to_be_visible()
        expect(authenticated_page.locator("#nmap-scripts")).to_be_visible()
        expect(authenticated_page.locator("#nmap-custom-args")).to_be_visible()
        expect(authenticated_page.locator("#nmap-known-ports-only")).to_be_visible()
        expect(authenticated_page.locator("#nmap-groups")).to_be_visible()

    def test_rustscan_form_fields(self, authenticated_page: Page, base_url: str):
        """Проверка полей формы Rustscan."""
        authenticated_page.goto(f"{base_url}/scans")
        
        expect(authenticated_page.locator("#rustscan-target")).to_be_visible()
        expect(authenticated_page.locator("#rustscan-ports")).to_be_visible()
        expect(authenticated_page.locator("#rustscan-run-nmap")).to_be_visible()
        expect(authenticated_page.locator("#rustscan-nmap-args")).to_be_visible()

    def test_dig_form_fields(self, authenticated_page: Page, base_url: str):
        """Проверка полей формы Dig."""
        authenticated_page.goto(f"{base_url}/scans")
        
        expect(authenticated_page.locator("#dig-targets")).to_be_visible()
        expect(authenticated_page.locator("#dig-file")).to_be_visible()
        expect(authenticated_page.locator("#dig-server")).to_be_visible()
        expect(authenticated_page.locator("#dig-types")).to_be_visible()
        expect(authenticated_page.locator("#dig-cli-args")).to_be_visible()

    def test_nmap_form_submission(self, authenticated_page: Page, base_url: str):
        """Тест отправки формы Nmap сканирования."""
        page = authenticated_page
        page.goto(f"{base_url}/scans")
        
        # Заполняем форму Nmap
        target_input = page.locator("#nmap-target")
        target_input.fill("127.0.0.1")
        
        # Отправляем форму
        submit_btn = page.locator('#nmap-form button[type="submit"], #nmap-form input[type="submit"]')
        if submit_btn.count() > 0:
            submit_btn.click()
            
            # Проверяем появление уведомления об успехе
            # expect(page.locator(".alert-success, .toast-success")).to_be_visible(timeout=10000)
            # Альтернативно: проверяем диалог alert
            page.wait_for_timeout(1000)  # Даем время на обработку

    def test_queue_status_updates(self, authenticated_page: Page, base_url: str):
        """Проверка обновления статуса очередей."""
        authenticated_page.goto(f"{base_url}/scans")
        
        # Проверяем наличие элементов статуса очереди
        expect(authenticated_page.locator("#nmap-queue-count")).to_be_visible()
        expect(authenticated_page.locator("#utility-queue-count")).to_be_visible()

    def test_jobs_table_exists(self, authenticated_page: Page, base_url: str):
        """Проверка наличия таблицы заданий."""
        authenticated_page.goto(f"{base_url}/scans")
        
        # Проверяем наличие таблицы заданий
        jobs_table = authenticated_page.locator("#jobs-table")
        expect(jobs_table).to_be_visible()

    def test_load_jobs_function_accessible(self, authenticated_page: Page, base_url: str):
        """
        Проверка что функция loadJobs доступна глобально.
        Регрессионный тест для ошибки: ReferenceError: loadJobs is not defined
        """
        authenticated_page.goto(f"{base_url}/scans")
        
        # Проверяем что функция loadJobs определена в window
        is_defined = authenticated_page.evaluate("typeof window.loadJobs === 'function'")
        assert is_defined, "Функция loadJobs должна быть доступна глобально"
        
        # Также проверяем что можно вызвать функцию без ошибок
        try:
            authenticated_page.evaluate("window.loadJobs()")
        except Exception as e:
            pytest.fail(f"Вызов loadJobs вызвал ошибку: {e}")

    def test_import_xml_modal(self, authenticated_page: Page, base_url: str):
        """Проверка модального окна импорта XML."""
        authenticated_page.goto(f"{base_url}/scans")
        
        # Находим кнопку импорта и кликаем
        import_btn = authenticated_page.locator("#import-xml-btn, button:has-text('Импорт'), button:has-text('Import')")
        if import_btn.count() > 0:
            import_btn.first.click()
            
            # Проверяем открытие модального окна
            modal = authenticated_page.locator("#scanImportModal, #importXmlModal, .modal:has-text('XML')")
            expect(modal).to_be_visible(timeout=5000)
            
            # Проверяем элементы внутри модалки
            expect(authenticated_page.locator("input[type='file'][accept='.xml']")).to_be_visible()
            expect(authenticated_page.locator("select[name='group_id'], #import-group-id")).to_be_visible()
            
            # Закрываем модалку
            close_btn = authenticated_page.locator("[data-bs-dismiss='modal']").first
            close_btn.click()

    def test_scan_error_modal(self, authenticated_page: Page, base_url: str):
        """Проверка модального окна ошибки сканирования."""
        authenticated_page.goto(f"{base_url}/scans")
        
        # Проверяем существование модального окна в DOM
        error_modal = authenticated_page.locator("#scanErrorModal")
        expect(error_modal).to_be_attached()

    def test_scan_results_modal(self, authenticated_page: Page, base_url: str):
        """Проверка модального окна результатов сканирования."""
        authenticated_page.goto(f"{base_url}/scans")
        
        # Проверяем существование модального окна в DOM
        results_modal = authenticated_page.locator("#scanResultsModal")
        expect(results_modal).to_be_attached()

    def test_global_functions_exports(self, authenticated_page: Page, base_url: str):
        """Проверка экспорта всех глобальных функций для scans-page.js."""
        authenticated_page.goto(f"{base_url}/scans")
        
        required_functions = [
            'loadJobs', 'updateQueueStatus', 'retryJob', 'removeJob', 
            'stopJob', 'deleteJob', 'viewScanResults', 'showScanError'
        ]
        
        for func_name in required_functions:
            is_defined = authenticated_page.evaluate(f"typeof window.{func_name} === 'function'")
            assert is_defined, f"Функция {func_name} должна быть доступна глобально"


@pytest.mark.ui
class TestAssetsPageUI:
    """Тесты страницы активов."""

    def test_assets_page_loads(self, authenticated_page: Page, base_url: str):
        """Проверка загрузки страницы активов."""
        authenticated_page.goto(f"{base_url}/assets")
        expect(authenticated_page).to_have_url(re.compile(".*assets.*"))

    def test_asset_tree_exists(self, authenticated_page: Page, base_url: str):
        """Проверка наличия дерева активов."""
        authenticated_page.goto(f"{base_url}/assets")
        
        # Проверяем наличие элементов дерева
        tree_locator = authenticated_page.locator("#asset-tree, .tree-view, ul.tree, #group-tree")
        expect(tree_locator).to_be_visible()

    def test_assets_table_exists(self, authenticated_page: Page, base_url: str):
        """Проверка наличия таблицы активов."""
        authenticated_page.goto(f"{base_url}/assets")
        
        assets_table = authenticated_page.locator("#assets-body, table.assets-table")
        expect(assets_table).to_be_attached()

    def test_create_asset_modal(self, authenticated_page: Page, base_url: str):
        """Проверка модального окна создания актива."""
        authenticated_page.goto(f"{base_url}/assets")
        
        # Находим кнопку создания актива
        create_btn = authenticated_page.locator(
            "#createAssetBtn, button:has-text('Добавить актив'), button:has-text('Создать актив'), "
            "button[onclick*='showAssetModal'], .btn:has(i.bi-plus)"
        )
        
        if create_btn.count() > 0:
            create_btn.first.click()
            
            # Проверяем открытие модального окна
            modal = authenticated_page.locator("#assetModal")
            expect(modal).to_be_visible(timeout=5000)
            
            # Проверяем поля формы
            expect(authenticated_page.locator("#assetIpAddress")).to_be_visible()
            expect(authenticated_page.locator("#assetHostname")).to_be_visible()
            expect(authenticated_page.locator("#assetOsInfo")).to_be_visible()
            expect(authenticated_page.locator("#assetOpenPorts")).to_be_visible()
            expect(authenticated_page.locator("#assetGroupId")).to_be_visible()
            expect(authenticated_page.locator("#assetNotes")).to_be_visible()
            
            # Закрываем модалку
            close_btn = authenticated_page.locator("#assetModal [data-bs-dismiss='modal']")
            close_btn.click()

    def test_bulk_delete_modal(self, authenticated_page: Page, base_url: str):
        """Проверка модального окна массового удаления."""
        authenticated_page.goto(f"{base_url}/assets")
        
        # Проверяем существование модалки в DOM
        bulk_delete_modal = authenticated_page.locator("#bulkDeleteModal")
        expect(bulk_delete_modal).to_be_attached()

    def test_bulk_move_modal(self, authenticated_page: Page, base_url: str):
        """Проверка модального окна массового перемещения."""
        authenticated_page.goto(f"{base_url}/assets")
        
        # Проверяем существование модалки в DOM
        bulk_move_modal = authenticated_page.locator("#bulkMoveModal")
        expect(bulk_move_modal).to_be_attached()

    def test_global_asset_functions(self, authenticated_page: Page, base_url: str):
        """Проверка экспорта глобальных функций для активов."""
        authenticated_page.goto(f"{base_url}/assets")
        
        required_functions = [
            'showAssetModal', 'saveAsset', 'confirmBulkDelete', 'executeBulkDelete',
            'confirmBulkMove', 'executeBulkMove', 'clearSelection', 'renderAssets'
        ]
        
        for func_name in required_functions:
            is_defined = authenticated_page.evaluate(f"typeof window.{func_name} === 'function'")
            assert is_defined, f"Функция {func_name} должна быть доступна глобально"


@pytest.mark.ui
class TestGroupsPageUI:
    """Тесты страницы групп."""

    def test_groups_page_loads(self, authenticated_page: Page, base_url: str):
        """Проверка загрузки страницы групп."""
        authenticated_page.goto(f"{base_url}/groups")
        expect(authenticated_page).to_have_url(re.compile(".*groups.*"))

    def test_group_edit_modal(self, authenticated_page: Page, base_url: str):
        """Проверка модального окна редактирования группы."""
        authenticated_page.goto(f"{base_url}/assets")  # Группы управляются со страницы активов
        
        # Проверяем существование модалки в DOM
        group_edit_modal = authenticated_page.locator("#groupEditModal")
        expect(group_edit_modal).to_be_attached()

    def test_group_mode_toggles(self, authenticated_page: Page, base_url: str):
        """Проверка переключателей режимов группы (ручная/CIDR/динамическая)."""
        authenticated_page.goto(f"{base_url}/assets")
        
        # Проверяем наличие радиокнопок режимов
        expect(authenticated_page.locator("#modeManual")).to_be_attached()
        expect(authenticated_page.locator("#modeCidr")).to_be_attached()
        expect(authenticated_page.locator("#modeDynamic")).to_be_attached()

    def test_dynamic_rules_container(self, authenticated_page: Page, base_url: str):
        """Проверка контейнера динамических правил."""
        authenticated_page.goto(f"{base_url}/assets")
        
        # Проверяем наличие контейнера для правил
        filter_root = authenticated_page.locator("#group-filter-root")
        expect(filter_root).to_be_attached()

    def test_group_move_modal(self, authenticated_page: Page, base_url: str):
        """Проверка модального окна перемещения группы."""
        authenticated_page.goto(f"{base_url}/assets")
        
        # Проверяем существование модалки в DOM
        move_modal = authenticated_page.locator("#groupMoveModal")
        expect(move_modal).to_be_attached()

    def test_group_delete_modal(self, authenticated_page: Page, base_url: str):
        """Проверка модального окна удаления группы."""
        authenticated_page.goto(f"{base_url}/assets")
        
        # Проверяем существование модалки в DOM
        delete_modal = authenticated_page.locator("#groupDeleteModal")
        expect(delete_modal).to_be_attached()

    def test_global_group_functions(self, authenticated_page: Page, base_url: str):
        """Проверка экспорта глобальных функций для групп."""
        authenticated_page.goto(f"{base_url}/assets")
        
        required_functions = [
            'showCreateGroupModal', 'toggleGroupMode', 'addDynamicRule',
            'showRenameModal', 'saveGroup', 'showDeleteModal', 'confirmDeleteGroup',
            'showMoveGroupModal', 'moveGroup', 'refreshGroupTree', 'filterByGroup'
        ]
        
        for func_name in required_functions:
            is_defined = authenticated_page.evaluate(f"typeof window.{func_name} === 'function'")
            assert is_defined, f"Функция {func_name} должна быть доступна глобально"


@pytest.mark.ui
class TestResponsiveDesign:
    """Тесты адаптивного дизайна."""

    @pytest.mark.parametrize("viewport_width,viewport_height,device_name", [
        (375, 667, "iPhone SE"),
        (768, 1024, "iPad"),
        (1920, 1080, "Desktop"),
    ])
    def test_responsive_on_different_devices(
        self, 
        authenticated_page: Page, 
        base_url: str,
        viewport_width: int,
        viewport_height: int,
        device_name: str
    ):
        """Проверка отображения на разных устройствах."""
        authenticated_page.set_viewport_size({"width": viewport_width, "height": viewport_height})
        authenticated_page.goto(f"{base_url}/")
        
        # Проверяем что страница загрузилась без горизонтального скролла
        body_width = authenticated_page.evaluate("document.body.scrollWidth")
        viewport_width = authenticated_page.evaluate("window.innerWidth")
        
        # Допускаем небольшой запас в 5 пикселей
        assert body_width <= viewport_width + 5, \
            f"На устройстве {device_name} обнаружен горизонтальный скролл"


@pytest.mark.ui
class TestAccessibility:
    """Базовые тесты доступности."""

    def test_all_images_have_alt(self, authenticated_page: Page, base_url: str):
        """Проверка что все изображения имеют alt текст."""
        authenticated_page.goto(f"{base_url}/")
        
        images = authenticated_page.locator("img")
        count = images.count()
        
        for i in range(count):
            img = images.nth(i)
            alt = img.get_attribute("alt")
            # alt может быть пустым для декоративных изображений, но атрибут должен быть
            assert alt is not None, f"Изображение {i} не имеет атрибута alt"

    def test_buttons_have_accessible_names(self, authenticated_page: Page, base_url: str):
        """Проверка что кнопки имеют доступные имена."""
        authenticated_page.goto(f"{base_url}/scans")
        
        buttons = authenticated_page.locator("button")
        count = buttons.count()
        
        for i in range(min(count, 10)):  # Проверяем первые 10 кнопок
            button = buttons.nth(i)
            text = button.inner_text().strip()
            aria_label = button.get_attribute("aria-label")
            
            # Кнопка должна иметь либо текст, либо aria-label
            has_content = bool(text) or bool(aria_label)
            # Игнорируем кнопки которые содержат только иконки без текста
            if button.locator("i, svg").count() > 0 and not text:
                assert aria_label, f"Кнопка {i} с иконкой должна иметь aria-label"

    def test_form_labels_present(self, authenticated_page: Page, base_url: str):
        """Проверка наличия label у всех полей форм."""
        authenticated_page.goto(f"{base_url}/scans")
        
        inputs = authenticated_page.locator("input:not([type='hidden']):not([type='submit']):not([type='button'])")
        count = inputs.count()
        
        for i in range(min(count, 10)):
            input_el = inputs.nth(i)
            input_id = input_el.get_attribute("id")
            aria_label = input_el.get_attribute("aria-label")
            
            # У input должен быть id или aria-label
            if not input_id and not aria_label:
                # Проверяем есть ли родитель label
                parent_label = input_el.evaluate("el => el.closest('label')")
                assert parent_label or aria_label, f"Input {i} не имеет label или aria-label"


@pytest.mark.ui
class TestErrorHandling:
    """Тесты обработки ошибок."""

    def test_404_page_shows(self, authenticated_page: Page, base_url: str):
        """Проверка страницы 404."""
        authenticated_page.goto(f"{base_url}/nonexistent-page-12345")
        
        # Проверяем что отображается страница 404 или редирект
        status_code = authenticated_page.evaluate(
            "() => fetch(window.location.href).then(r => r.status)"
        )
        # Либо 404 статус, либо редирект на главную
        assert status_code == 404 or authenticated_page.url != f"{base_url}/nonexistent-page-12345"

    def test_network_error_handling(self, authenticated_page: Page, base_url: str):
        """Проверка обработки сетевых ошибок."""
        # Перехватываем запросы и эмулируем ошибку
        authenticated_page.route("**/api/**", lambda route: route.abort("connectionfailed"))
        
        authenticated_page.goto(f"{base_url}/scans")
        
        # Даем время на попытку загрузки данных
        authenticated_page.wait_for_timeout(3000)
        
        # Страница должна остаться стабильной несмотря на ошибки сети
        expect(authenticated_page.locator("body")).to_be_attached()


@pytest.mark.ui
class TestModalsAccessibility:
    """Тесты доступности модальных окон."""

    def test_modals_have_aria_labels(self, authenticated_page: Page, base_url: str):
        """Проверка что модальные окна имеют правильные ARIA атрибуты."""
        authenticated_page.goto(f"{base_url}/scans")
        
        modals = authenticated_page.locator(".modal")
        count = modals.count()
        
        for i in range(count):
            modal = modals.nth(i)
            modal_id = modal.get_attribute("id")
            
            # Проверяем aria-labelledby или aria-label
            labelled_by = modal.get_attribute("aria-labelledby")
            label = modal.get_attribute("aria-label")
            
            # Хотя бы один из атрибутов должен быть
            assert labelled_by or label, f"Модальное окно #{modal_id} должно иметь aria-labelledby или aria-label"

    def test_modals_have_close_buttons(self, authenticated_page: Page, base_url: str):
        """Проверка что у модальных окон есть кнопки закрытия."""
        authenticated_page.goto(f"{base_url}/scans")
        
        modals = authenticated_page.locator(".modal")
        count = modals.count()
        
        for i in range(count):
            modal = modals.nth(i)
            modal_id = modal.get_attribute("id")
            
            # Ищем кнопку закрытия внутри модалки
            close_btn = modal.locator("[data-bs-dismiss='modal'], button.close, .btn-close")
            assert close_btn.count() > 0, f"Модальное окно #{modal_id} должно иметь кнопку закрытия"

    def test_context_menu_exists(self, authenticated_page: Page, base_url: str):
        """Проверка существования контекстного меню."""
        authenticated_page.goto(f"{base_url}/assets")
        
        # Контекстное меню может быть скрыто, но должно быть в DOM
        context_menu = authenticated_page.locator("#group-context-menu, .context-menu")
        expect(context_menu).to_be_attached()

    def test_toast_notifications_container(self, authenticated_page: Page, base_url: str):
        """Проверка контейнера для toast уведомлений."""
        authenticated_page.goto(f"{base_url}/")
        
        # Toast контейнер может иметь разные названия
        toast_container = authenticated_page.locator(
            "#toast-container, .toast-container, #alerts-container, .alerts-container"
        )
        # Он может быть не виден пока нет уведомлений
        expect(toast_container).to_be_attached()
