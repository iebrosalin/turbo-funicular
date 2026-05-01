from playwright.sync_api import expect
import uuid

def test_create_group(page):
    """Проверка создания группы"""
    page.goto("/")
    
    # Находим кнопку добавления группы
    add_btn = page.locator("#btn-add-group")
    expect(add_btn).to_be_visible()
    add_btn.click()
    
    # Ждем открытия модального окна
    modal = page.locator("#groupModal")
    expect(modal).to_be_visible()
    
    # Вводим уникальное имя группы
    unique_name = f"TestGroup_{uuid.uuid4().hex[:8]}"
    name_input = page.locator("#groupName")
    name_input.fill(unique_name)
    
    # Сохраняем
    save_btn = page.locator("#btn-save-group")
    save_btn.click()
    
    # Ждем закрытия модального окна и появления группы в списке
    page.wait_for_timeout(1000)
    expect(page.locator(f"text={unique_name}")).to_be_visible(timeout=5000)

def test_group_unique_name(page):
    """Проверка что нельзя создать группу с дублирующимся именем"""
    page.goto("/")
    
    unique_name = f"UniqueGroup_{uuid.uuid4().hex[:8]}"
    
    # Создаем первую группу
    page.locator("#btn-add-group").click()
    page.locator("#groupName").fill(unique_name)
    page.locator("#btn-save-group").click()
    page.wait_for_timeout(1000)
    
    # Пытаемся создать вторую с таким же именем
    page.locator("#btn-add-group").click()
    page.locator("#groupName").fill(unique_name)
    page.locator("#btn-save-group").click()
    
    # Должна появиться ошибка или группа не создастся
    # Проверяем что группа с таким именем только одна
    groups = page.locator(f"text={unique_name}")
    assert groups.count() == 1
