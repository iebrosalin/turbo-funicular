# 📚 Project Context: Network Asset Manager

## 1. Общая информация
**Стек технологий:**
- **Backend:** Python 3.12, FastAPI (Async), SQLAlchemy 2.0 (Async), Alembic, Pydantic v2.
- **Frontend:** Vanilla JavaScript (ES6 Modules), HTML5, CSS3.
- **Database:** PostgreSQL 15+.
- **Infrastructure:** Docker, Docker Compose.
- **Testing:** Pytest, Pytest-Asyncio, Httpx.

**Архитектурные принципы:**
- Разделение ответственности (Routes → Services → Models).
- Асинхронность на всех уровнях (I/O операции).
- Строгая валидация данных через Pydantic схемы.
- Отсутствие серверного рендеринга (SPA-подход на vanilla JS).

---

## 2. Структура проекта

```text
.
├── backend/
│   ├── app/
│   │   ├── core/          # Конфигурация, исключения
│   │   ├── db/            # Сессии БД, базовые модели
│   │   ├── models/        # SQLAlchemy модели (Asset, Group, Scan)
│   │   ├── schemas/       # Pydantic схемы (Request/Response)
│   │   ├── services/      # Бизнес-логика (AssetService, etc.)
│   │   ├── routes/        # API endpoints (FastAPI routers)
│   │   └── main.py        # Точка входа
│   ├── alembic/           # Миграции БД
│   ├── tests/             # Тесты (Unit, Integration)
│   ├── pytest.ini         # Конфиг тестов
│   └── requirements.txt
├── frontend/
│   ├── static/
│   │   ├── js/
│   │   │   ├── modules/   # Переиспользуемая логика (tree, assets, groups)
│   │   │   ├── pages/     # Логика конкретных страниц
│   │   │   └── main.js    # Инициализация
│   │   └── css/
│   └── templates/         # HTML шаблоны
├── docker-compose.yml
├── .gitignore
└── PROJECT_CONTEXT.md
```

---

## 3. Статус рефакторинга (Flask → FastAPI)
✅ **Завершено:**
- Переход на асинхронный стек (FastAPI + AsyncSQLAlchemy).
- Выделение сервисного слоя для бизнес-логики.
- Настройка миграций Alembic.
- Удаление интеграций Wazuh/osquery.
- Вынос JS-логики из HTML в модули.
- Настройка инфраструктуры тестирования (Pytest).
- Удаление сервиса Adminer из Docker-конфигурации.

❌ **Удалено:**
- Авторизация и пользователи (режим анонимного админа).
- Синхронные блокирующие вызовы БД.
- Инлайн-скрипты в шаблонах.
- Сервис Adminer.

---

## 4. 🔗 Карта связей: UI ↔ JS ↔ Backend

Эта таблица описывает полный цикл обработки действия пользователя: от клика до ответа БД.

| Функционал | HTML Элемент (ID/Class) | JS Модуль / Функция | API Endpoint (Method) | Backend Service |
| :--- | :--- | :--- | :--- | :--- |
| **Дерево групп** | `.group-node` (click) | `tree.js` → `handleGroupClick()` | `GET /api/groups/tree` | `GroupService.get_tree()` |
| **Фильтр активов** | `#asset-filter` (input) | `dashboard-page.js` → `applyFilters()` | `GET /api/assets?search=...` | `AssetService.filter()` |
| **Создание актива** | `#asset-form` (submit) | `assets.js` → `handleAssetSubmit()` | `POST /api/assets` | `AssetService.create()` |
| **Удаление актива** | `.btn-delete-asset` (click) | `assets.js` → `confirmAndDelete()` | `DELETE /api/assets/{id}` | `AssetService.delete()` |
| **Запуск скана** | `#scan-form` (submit) | `scans.js` → `submitScanForm()` | `POST /api/scans` | `ScanService.create()` |
| **Результаты скана** | `.btn-view-results` | `scans.js` → `viewScanResults()` | `GET /api/scans/{id}/results` | `ScanService.get_results()` |
| **Переключение темы** | `#theme-toggle-btn` | `theme.js` → `toggleTheme()` | *(Local Storage)* | *N/A* |

### Жизненный цикл запроса (Пример: Создание актива)
1.  **UI:** Пользователь заполняет форму `#asset-form` и нажимает "Сохранить".
2.  **JS:** Срабатывает `submit` event → `assets.js` собирает данные → валидирует их → отправляет `fetch('/api/assets', { method: 'POST', ... })`.
3.  **Route:** FastAPI принимает запрос → валидирует тело через `AssetCreate` схему.
4.  **Service:** `AssetService.create()` выполняет логику (проверка дубликатов, связь с группой) → делает `await session.add()`.
5.  **DB:** PostgreSQL сохраняет запись → возвращает ID.
6.  **Response:** Сервер возвращает JSON `{ id: 1, status: "success" }`.
7.  **UI Update:** JS получает ответ → закрывает модалку → вызывает `loadAssets()` для обновления таблицы.

---

## 5. 🛠️ Практические команды и инструкции

### Запуск проекта
```bash
# Сборка и запуск всех сервисов
docker-compose up --build

# Запуск в фоновом режиме
docker-compose up -d

# Остановка и удаление контейнеров + томов (сброс БД)
docker-compose down -v
```

### Работа с базой данных
```bash
# Применить миграции вручную (если авто-применение не сработало)
docker-compose exec backend alembic upgrade head

# Создать новую миграцию после изменения моделей
docker-compose exec backend alembic revision --autogenerate -m "Description"

# Подключиться к CLI базы данных
docker-compose exec db psql -U user -d assetdb
```

### Тестирование
```bash
# Запуск всех тестов с отчетом о покрытии
docker-compose exec backend pytest --cov=app --cov-report=term-missing

# Запуск конкретного теста
docker-compose exec backend pytest tests/unit/test_asset_service.py -v

# Запуск тестов без coverage (быстрее)
docker-compose exec backend pytest
```

### Отладка
```bash
# Просмотр логов backend в реальном времени
docker-compose logs -f backend

# Просмотр логов только ошибок
docker-compose logs --tail=100 backend | grep ERROR

# Войти в контейнер backend для инспекции
docker-compose exec backend bash

# Проверка состояния здоровья сервисов
curl http://localhost:8000/health
```

### Конфигурация портов
| Сервис | Порт | Описание |
| :--- | :--- | :--- |
| **Frontend/API** | `8000` | Основной доступ к приложению и Swagger UI (`/docs`) |
| **Database** | `5432` | PostgreSQL (доступен внутри сети Docker) |

---

## 6. Протокол работы и ограничения

**🚫 Критическое правило: Файл `.gitignore`**
- **ЗАПРЕЩЕНО** вносить изменения в файл `.gitignore` без явного согласования.
- Этот файл контролирует целостность репозитория. Любые изменения могут привести к попаданию временных файлов, секретов или артефактов сборки в историю Git.
- Если необходимо игнорировать новый тип файлов, обсудите это перед правкой.

**Обновление контекста:**
После завершения значительных этапов разработки (например, добавление тестов, рефакторинг архитектуры, изменение API контрактов) **необходимо** актуализировать содержимое этого файла. Это гарантирует сохранение полной картины проекта для последующих итераций.

**Текущий приоритет:**
1.  Покрытие тестами бизнес-логики (Services).
2.  Покрытие тестами API (Routes).
3.  Оптимизация запросов к БД.

---

## 7. Известные ограничения
- **Безопасность:** Отсутствует аутентификация и авторизация. Приложение доступно по сети без ограничений.
- **Фоновые задачи:** Сканирования выполняются синхронно в рамках запроса (блокируют ответ до завершения). В будущем требуется вынос в Celery/BackgroundTasks.
- **Масштабирование:** Текущая конфигурация рассчитана на одиночный инстанс backend.
