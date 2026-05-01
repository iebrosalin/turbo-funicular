# 📚 Project Context: Network Asset Manager

## 1. Общая информация
**Стек технологий:**
- **Backend:** Python 3.12, FastAPI (Async), SQLAlchemy 2.0 (Async), Pydantic v2.
- **Frontend:** Vanilla JavaScript (ES6 Modules), HTML5, CSS3, Bootstrap 5.3+.
- **Database:** SQLite (единственная поддерживаемая БД). Все сущности имеют поле `uuid`.
- **Infrastructure:** Docker, Docker Compose.
- **Testing:** Playwright (E2E в Docker). Unit/Integration тесты на Pytest удалены.
- **Tools:** Nmap, Rustscan, Dig (dnsutils).

**Архитектурные принципы:**
- Разделение ответственности (Routes → Services → Models).
- Асинхронность на всех уровнях (I/O операции).
- Строгая валидация данных через Pydantic схемы.
- **Модульный Frontend:** Строгое использование ES6 Modules (`type="module"`). Глобальная область видимости запрещена.
- **Единый источник истины:** Логика фильтрации (`FilterBuilder`) унифицирована для дашборда и модальных окон групп.
- **Темная тема по умолчанию:** Приложение стартует в темной теме. Переключение только через `/settings`.
- **Физическое создание файлов:** Все изменения кода выполняются реально в файловой системе `/workspace`.
- **Гибкость запуска:** Поддержка работы как в Docker, так и локально.
- **Без миграций:** Alembic удален. Схема БД создается/обновляется при старте (`create_all`). Существующие записи получают UUID автоматически.

---

## 2. Структура проекта
```text
/workspace/
├── app.py                 # Точка входа (uvicorn wrapper)
├── .env                   # Конфигурация (DATABASE_URL, настройки)
├── requirements.txt       # Зависимости Python
├── docker-compose.yml     # Конфигурация Docker (профиль 'e2e' для тестов)
├── instance/              # Локальная БД SQLite (app.db)
├── backend/
│   ├── main.py            # FastAPI app (lifespan, роутеры)
│   ├── core/              # Конфигурация, исключения
│   ├── db/                # Сессии БД, базовые модели
│   ├── models/            # SQLAlchemy модели (Asset, Group, Scan...) с полем uuid
│   ├── schemas/           # Pydantic схемы
│   ├── services/          # Бизнес-логика + Менеджеры очередей
│   ├── routes/            # API endpoints (assets, groups, scans, settings)
│   ├── scanner/           # Асинхронные сканеры (nmap, rustscan, dig)
│   ├── utils/             # Утилиты
│   └── templates/         # HTML шаблоны (Jinja2)
│       ├── base.html      # Базовый шаблон (без переключателя темы в хедере)
│       ├── index.html     # Дашборд (с FilterBuilder)
│       ├── settings.html  # Страница настроек (переключение темы)
│       └── ...
├── frontend/
│   └── static/
│       ├── js/
│       │   ├── modules/   # Переиспользуемая логика (utils.js, tree.js, groups.js)
│       │   ├── filter-builder.js # Единый класс конструктора фильтров
│       │   └── main.js    # Инициализация приложения (App class)
│       └── css/
│           └── style.css  # Стили с CSS переменными (Dark/Light themes)
└── tests/
    └── integration/       # Playwright E2E тесты
        ├── conftest.py
        └── test_scanners_e2e.py # Тесты Dig, Nmap, Rustscan
```

---

## 3. 🔧 Текущий статус проекта

✅ **Завершено:**
- **ES6 Модули:** Полный рефакторинг JS. Удалены глобальные переменные, исправлены импорты/экспорты.
- **UUID:** Поле `uuid` добавлено во все основные таблицы. Реализована автогенерация и миграция старых записей.
- **FilterBuilder:** Создан единый класс для построения сложных запросов (Dashboard + Dynamic Groups).
- **E2E Тесты:** Интеграционные тесты на Playwright в Docker. Старые тесты удалены. Добавлены тесты реальных сканеров (Dig, Nmap, Rustscan).
- **UI/UX:**
  - Темная тема по умолчанию.
  - Страница настроек `/settings`.
  - Исправлена контрастность кнопок и таблиц в темной теме.
  - Исправлено поведение чекбоксов (без перехода по клику).
  - Исправлена ошибка 404 на странице деталей актива.
- **Backend API:**
  - Поддержка сложной фильтрации (`rules` JSON) в `/api/assets`.
  - Эндпоинт `/api/groups/preview` для предпросмотра динамических групп.

❌ **Удалено:**
- Старые unit/integration тесты на Pytest/Httpx.
- Лишние профили в `docker-compose.yml`.
- Переключатель темы из хедера (перенесен в настройки).
- Файлы `.cursorrules`, `CONTEXT.md`.

---

## 4. 🔗 Карта связей: UI ↔ JS ↔ Backend

| Функционал | HTML Элемент | JS Модуль / Класс | API Endpoint | Backend Service |
| :--- | :--- | :--- | :--- | :--- |
| **Дерево групп** | `.group-node` | `TreeManager` (`modules/tree.js`) | `GET /api/groups/tree` | `GroupService.get_tree()` |
| **Конструктор фильтров** | `#filter-root` | `FilterBuilder` (`filter-builder.js`) | `POST /api/assets` (rules) | `AssetService.filter_complex()` |
| **Предпросмотр группы** | `#group-preview-count` | `FilterBuilder` (method `checkRules`) | `POST /api/groups/preview` | `GroupService.preview_count()` |
| **Создание актива** | `#asset-form` | `App` (`main.js`) | `POST /api/assets` | `AssetService.create()` |
| **Детали актива** | `.asset-row` | `App` (`main.js`) | `GET /api/assets/{uuid}` | `AssetService.get_by_uuid()` |
| **Запуск скана** | `#scan-form` | `ScanManager` | `POST /api/scans/start/nmap` | `ScanQueueManager.add_scan()` |
| **Настройки темы** | `#theme-select` | `ThemeController` | `PUT /api/settings/theme` | `SettingsService.update()` |
| **E2E Сканеры** | N/A | `test_scanners_e2e.py` | `POST /api/scans/start/*` | `ScanQueueManager` |

---

## 5. 🛠️ Практические команды

### Запуск проекта
```bash
# Локально
python app.py

# Docker
docker compose up --build
```

### Тестирование (E2E)
```bash
# Запуск только E2E тестов в Docker
docker compose --profile e2e up --exit-code-from e2e-tests

# Запуск конкретных тестов сканеров
docker compose --profile e2e run --rm e2e-tests tests/integration/test_scanners_e2e.py
```

### Работа с БД
```bash
# Сброс БД (удаление файла и пересоздание)
rm instance/app.db
# При следующем старте БД создастся заново, UUID сгенерируются для новых записей.
```

---

## 6. 📋 Протокол работы и ограничения

### 🚫 Критические запреты
1.  **Файл .gitignore:** ЗАПРЕЩЕНО добавлять, удалять или изменять правила игнорирования файлов.
2.  **Системные пакеты:** ЗАПРЕЩЕНО менять набор инструментов сканирования в Dockerfile без критической необходимости.
3.  **Безопасность:** ЗАПРЕЩЕНО внедрять аутентификацию/авторизацию. Режим "Анонимный администратор".
4.  **PostgreSQL:** ЗАПРЕЩЕНО возвращать поддержку PostgreSQL. Только SQLite.
5.  **Вывод файлов:** ЗАПРЕЩЕНО утверждать о создании или изменении файла без его немедленного вывода через `cat` или `view`. Общение продолжается только после предоставления реального содержимого.

### ✅ Правила исполнения
- **Двойное удаление:** При удалении файлов выполнять команду дважды для гарантии синхронизации FS.
- **Прямое действие:** Минимум обсуждений, максимум кода. Сначала действие, потом отчет.
- **Проверка импортов:** Все JS файлы должны быть валидными ES6 модулями с явными импортами.
- **Реальный вывод:** Любой ответ о состоянии файла должен содержать его полное содержимое (через `cat` или `view`).

---

## 7. ⚠️ Известные ограничения
- **Безопасность:** Полный доступ без пароля.
- **Масштабирование:** Одиночный инстанс с SQLite.
- **Темы:** Переключение темы работает через `localStorage` и CSS переменные. Серверная часть хранит предпочтение опционально.

---

## 8. 📦 Зависимости проекта

### Python зависимости
- **FastAPI** 0.115.0
- **Uvicorn** 0.30.6
- **SQLAlchemy** 2.0.31 + **aiosqlite** 0.20.0
- **Pydantic** 2.8.2
- **Playwright** (для E2E тестов)

### Системные зависимости
- **nmap**
- **rustscan**
- **dnsutils** (dig)

---

*Последнее обновление: Май 2026*
