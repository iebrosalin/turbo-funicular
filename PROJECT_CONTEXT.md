# 📚 Project Context: Network Asset Manager

## 1. Общая информация
**Стек технологий:**
- **Backend:** Python 3.12, FastAPI (Async), SQLAlchemy 2.0 (Async), Pydantic v2.
- **Frontend:** Vanilla JavaScript (ES6 Modules), HTML5, CSS3, Bootstrap 5.3+.
- **Database:** SQLite (единственная поддерживаемая БД). Все сущности имеют поле `uuid`.
- **Infrastructure:** Docker, Docker Compose.
- **Testing:** Playwright (E2E в Docker).
- **Tools:** Nmap, Rustscan, Dig (dnsutils).

**Архитектурные принципы:**
- Разделение ответственности (Routes → Services → Models).
- Асинхронность на всех уровнях (I/O операции).
- Строгая валидация данных через Pydantic схемы.
- **Модульный Frontend:** Строгое использование ES6 Modules (`type="module"`).
- **Единый источник истины:** Логика фильтрации (`FilterBuilder`) унифицирована.
- **Темная тема по умолчанию:** Приложение стартует в темной теме. Переключение только через `/settings`.
- **Физическое создание файлов:** Все изменения кода выполняются реально в файловой системе `/workspace`.

---

## 2. Структура проекта
```text
/workspace/
├── app.py                     # Точка входа (uvicorn)
├── requirements.txt           # Зависимости Python
├── docker-compose.yml         # Docker конфигурация
├── Dockerfile                 # Docker образ
├── .env.example               # Шаблон переменных окружения
├── pytest.ini                 # Настройки pytest
├── instance/                  # SQLite БД
├── backend/
│   ├── main.py                # FastAPI приложение, роутинг, lifespan
│   ├── core/
│   │   ├── config.py          # Настройки через pydantic-settings
│   │   └── exceptions.py      # Кастомные исключения и обработчики
│   ├── db/
│   │   ├── base.py            # SQLAlchemy Base
│   │   ├── session.py         # AsyncSession, engine, таблица asset_change_logs
│   │   └── init_db.py         # Инициализация БД
│   ├── models/
│   │   ├── asset.py           # Asset модель + asset_groups association
│   │   ├── group.py           # Group модель (дерево)
│   │   ├── scan.py            # Scan, ScanResult модели
│   │   ├── service.py         # Service модель (порты/сервисы)
│   │   └── log.py             # AssetChangeLog модель
│   ├── schemas/
│   │   ├── asset.py           # Pydantic схемы для Asset
│   │   ├── group.py           # Pydantic схемы для Group
│   │   └── scan.py            # Pydantic схемы для Scan
│   ├── routes/
│   │   ├── assets.py          # API endpoints для активов
│   │   ├── groups.py          # API endpoints для групп
│   │   └── scans.py           # API endpoints для сканирований
│   ├── services/
│   │   ├── asset_service.py   # Бизнес-логика активов + change log
│   │   ├── asset_manager.py   # Управление активами
│   │   ├── group_service.py   # Логика дерева групп
│   │   ├── scan_service.py    # Логика сканирований
│   │   └── scan_queue_manager.py # Асинхронная очередь сканирований
│   ├── scanner/
│   │   ├── base.py            # Базовый класс сканера
│   │   ├── nmap/
│   │   │   └── nmap_async.py  # Асинхронный Nmap сканер
│   │   ├── rustscan/
│   │   │   └── rustscan_async.py # Асинхронный Rustscan сканер
│   │   └── dig/
│   │       └── dig_async.py   # Асинхронный DNS lookup
│   ├── utils/
│   │   ├── query_parser.py    # Парсер FilterBuilder запросов
│   │   ├── network_utils.py   # Сетевые утилиты
│   │   └── nmap_xml_importer.py # Импорт Nmap XML
│   ├── templates/
│   │   ├── base.html          # Базовый шаблон
│   │   ├── dashboard.html     # Главная страница
│   │   ├── scans.html         # Страница сканирований
│   │   ├── scan_history.html  # История сканирований
│   │   ├── asset_detail.html  # Детали актива
│   │   ├── asset_history.html # История изменений актива
│   │   ├── asset_taxonomy.html# Таксономия активов
│   │   ├── settings.html      # Настройки
│   │   ├── ui_kit.html        # UI компоненты
│   │   ├── utilities.html     # Утилиты
│   │   ├── utilities_check.html # Проверка утилит
│   │   ├── index.html         # Индекс страница
│   │   ├── 404.html           # Ошибка 404
│   │   ├── 500.html           # Ошибка 500
│   │   └── components/
│   │       ├── modals.html    # Общие модальные окна
│   │       ├── modals_assets.html
│   │       ├── modals_groups.html
│   │       ├── modals_scans.html
│   │       └── assets_rows.html # Шаблон строк активов
│   └── migrations/
│       └── versions/
│           └── add_asset_change_log.py # Миграция логов изменений
├── frontend/
│   └── static/
│       ├── js/
│       │   ├── main.js                # Инициализация приложения
│       │   ├── store.js               # Глобальное состояние
│       │   ├── filter-builder.js      # SQL-like конструктор фильтров
│       │   ├── filter-helpers.js      # Хелперы фильтров
│       │   ├── dashboard-page.js      # Логика Dashboard
│       │   ├── scans-page.js          # Логика страницы сканирований
│       │   ├── asset-detail.js        # Логика детали актива
│       │   ├── modals-scans.js        # Модальные окна сканирований
│       │   ├── scan-helpers.js        # Хелперы сканирований
│       │   └── modules/
│       │       ├── index.js           # Экспорт модулей
│       │       ├── utils.js           # Утилиты (getAssetSchema и др.)
│       │       ├── tree.js            # TreeManager для дерева групп
│       │       ├── assets.js          # API клиент для активов
│       │       ├── groups.js          # API клиент для групп
│       │       ├── scans.js           # API клиент для сканирований
│       │       ├── scan_history.js    # API клиент для истории
│       │       └── theme.js           # Управление темой
│       └── css/
│           ├── style.css              # Основные стили
│           ├── groups-tree.css        # Стили дерева групп
│           └── ui-kit-experiments.css # Экспериментальные UI стили
└── tests/
    └── integration/
        ├── conftest.py                # Playwright fixtures
        ├── test_dashboard.py          # E2E тесты Dashboard
        ├── test_scanners_e2e.py       # E2E тесты сканеров
        ├── test_groups.py             # E2E тесты групп
        ├── test_settings.py           # E2E тесты настроек
        └── test_dashboard.py          # E2E тесты дашборда
```

---

## 3. 🔧 Текущий статус проекта

✅ **Завершено:**
- **ES6 Модули:** Полный рефакторинг JS.
- **UUID:** Поле `uuid` во всех таблицах.
- **FilterBuilder:** Единый класс для сложных запросов (SQL-like синтаксис).
- **E2E Тесты:** Playwright тесты для UI и сканеров.
- **UI/UX:** Темная тема по умолчанию, страница настроек.
- **RedCheck Интеграция:**
  - Синхронизация активов через API RedCheck.
  - Сохранение только `redcheck_guid`, `ip` и `last_seen` в таблице `redcheck_hosts`.
  - Динамическое получение полных данных об активах при запросе.
  - Связь активов RedCheck с основными активами по IP-адресу.
  - Поддержка групп для активов RedCheck (назначение, фильтрация).
- **Управление активами:**
  - Единый интерфейс для работы с обычными активами и активами из RedCheck.
  - Несколько представлений: таблица, карточки, менеджер групп.
  - Фильтрация, поиск, массовые операции.
  - Назначение активов в группы прямо из списка.
- **Сканеры (Полная реализация):**
  - **Nmap:** Форма с поддержкой CSV (drag-and-drop + textarea), мульти-выбор групп, опции known_ports_only/save_assets.
  - **Rustscan:** Форма с мульти-выбором групп, опциями known_ports_only/save_assets/run_nmap_after/nmap_args/nmap_scripts.
  - **Dig:** Форма с загрузкой файлов (.txt/.csv), опцией save_assets, мульти-выбор групп.
  - **Fping:** Форма с настройками count/timeout/interval/broadcast/ping_all, мульти-выбор групп, опция save_assets.
  - **Общее:** Real-time обновление статуса очередей, история сканирований, модальные окна импорта.

---

## 4. 🔗 Карта связей: UI ↔ JS ↔ Backend

| Функционал | JS Модуль | API Endpoint | Страница |
| :--- | :--- | :--- | :--- |
| **Сканеры (E2E)** | `test_scanners_e2e.py`, `scans-page.js` | `POST /api/scans/start/{nmap,rustscan,dig,fping}` | `/scans` |
| **Фильтры** | `FilterBuilder` | `GET /api/assets?rules=...` | `/assets-table`, `/assets-cards` |
| **Схема полей** | `Utils.getAssetSchema()` | `GET /api/assets/schema` | Все страницы активов |
| **Дерево групп** | `TreeManager` | `GET /api/groups/tree` | `/groups-manager` |
| **RedCheck Sync** | `redcheck-page.js` | `POST /api/redcheck/sync` | `/redcheck` |
| **RedCheck Hosts** | `redcheck-hosts.js` | `GET /api/redcheck/hosts` | `/redcheck` |
| **Управление активами** | `assets-manager.js` | `GET /api/assets-manager` | `/assets-manager` |
| **Группы в сканерах** | `scans-page.js` (#loadGroupsForForms) | `GET /api/groups` | `/scans` |
| **Статус очередей** | `scans-page.js` (#updateQueueStatuses) | `GET /api/scans/queue/status` | `/scans` |
| **CSV обработка** | `scans-page.js` (#initCsvHandling, #validateCsv) | N/A (client-side) | `/scans` |

---

## 5. 🛠️ Практические команды

### Тестирование (E2E)
```bash
docker compose --profile e2e run --rm e2e-tests
```

### Сброс БД
```bash
rm instance/app.db && docker compose up -d
```

### Применение миграций RedCheck
```bash
# Переименование external_id → redcheck_guid
docker-compose exec app python backend/migrate_external_id.py

# Добавление поддержки групп для RedCheck
docker-compose exec app python backend/migrate_redcheck_groups.py

# Инициализация БД (если нужно)
docker-compose exec app python backend/init_db.py
```

### Перезапуск приложения
```bash
docker-compose restart app
```

---

## 6. 📁 Структура страниц управления активами

| Страница | URL | Описание |
| :--- | :--- | :--- |
| **Таблица активов** | `/assets-table` | Классическое табличное представление всех активов |
| **Карточки активов** | `/assets-cards` | Визуальное представление активов в виде карточек |
| **Менеджер групп** | `/groups-manager` | Управление группами и назначение активов |
| **RedCheck хосты** | `/redcheck` | Просмотр и синхронизация активов из RedCheck |
| **Универсальный менеджер** | `/assets-manager` | Единый интерфейс для всех типов активов |

---

## 7. 🗄️ Модель данных RedCheck

### Таблица `redcheck_hosts`
| Поле | Тип | Описание |
| :--- | :--- | :--- |
| `id` | Integer | Первичный ключ |
| `redcheck_guid` | String | Уникальный идентификатор из RedCheck (UUID) |
| `ip` | String | IP-адрес хоста (из `connectionAddress`) |
| `last_seen` | DateTime | Дата последнего сканирования (из `modificationDate`) |
| `group_id` | Integer | Внешний ключ на таблицу групп (опционально) |

**Принцип работы:**
- При синхронизации сохраняются только `redcheck_guid`, `ip` и `last_seen`.
- Полные данные (CPE, описание, UUID и т.д.) запрашиваются у API RedCheck динамически при отображении деталей.
- Связь с основными активами (`assets`) осуществляется по IP-адресу.

---

## 8. 📋 ПРОТОКОЛ РАБОТЫ (STRICT MODE)

### ⚡ ГЛАВНОЕ ПРАВИЛО: "BASH FIRST"
**Любое изменение файла ДОЛЖНО начинаться с выполнения команды записи через `bash`.**
1.  **Выполняй полную перезапись файлов через терминал, чтобы гарантированно обновить состояние в Code Tool Record** 
3.  **Запись:** Сначала выполняется команда `cat > file << 'EOF' ... EOF` или `echo ... > file`.
4.  **Проверка:** Убедиться, что Code Tool Record зафиксировал изменение.
5.  **Вывод:** Только после успешной записи разрешено выводить содержимое файла (`cat file`) или подтверждать успех текстом.
6.  **Запрет:** Запрещено утверждать "Файл изменен" до выполнения команды записи.

### 🛠 Стандарт команд записи
Для полной перезаписи файлов всегда использовать **heredoc** синтаксис для сохранения форматирования:
```bash
cat > /path/to/file << 'EOF'
<content>
