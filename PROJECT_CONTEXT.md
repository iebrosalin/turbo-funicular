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
├── app.py                 # Точка входа
├── requirements.txt       # Зависимости Python
├── docker-compose.yml     # Конфигурация Docker (профиль 'e2e')
├── instance/              # Локальная БД SQLite
├── backend/
│   ├── main.py            # FastAPI app
│   ├── models/            # SQLAlchemy модели с uuid
│   ├── services/          # Бизнес-логика
│   ├── routes/            # API endpoints
│   ├── scanner/           # Асинхронные сканеры
│   └── templates/         # HTML шаблоны
├── frontend/
│   └── static/
│       ├── js/
│       │   ├── modules/   # utils.js, tree.js
│       │   ├── filter-builder.js # SQL-like конструктор
│       │   └── main.js
│       └── css/
│           └── style.css
└── tests/
    └── integration/       # Playwright E2E тесты
```

---

## 3. 🔧 Текущий статус проекта

✅ **Завершено:**
- **ES6 Модули:** Полный рефакторинг JS.
- **UUID:** Поле `uuid` во всех таблицах.
- **FilterBuilder:** Единый класс для сложных запросов (SQL-like синтаксис).
- **E2E Тесты:** Playwright тесты для UI и сканеров.
- **UI/UX:** Темная тема по умолчанию, страница настроек.

---

## 4. 🔗 Карта связей: UI ↔ JS ↔ Backend

| Функционал | JS Модуль | API Endpoint |
| :--- | :--- | :--- |
| **Сканеры (E2E)** | `test_scanners_e2e.py` | `POST /api/scans/start/*` |
| **Фильтры** | `FilterBuilder` | `GET /api/assets?rules=...` |
| **Схема полей** | `Utils.getAssetSchema()` | `GET /api/assets/schema` |
| **Дерево групп** | `TreeManager` | `GET /api/groups/tree` |

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

---

## 6. 📋 ПРОТОКОЛ РАБОТЫ (STRICT MODE)

### ⚡ ГЛАВНОЕ ПРАВИЛО: "BASH FIRST"
**Любое изменение файла ДОЛЖНО начинаться с выполнения команды записи через `bash`.**
1.  **Запись:** Сначала выполняется команда `cat > file << 'EOF' ... EOF` или `echo ... > file`.
2.  **Проверка:** Убедиться, что Code Tool Record зафиксировал изменение.
3.  **Вывод:** Только после успешной записи разрешено выводить содержимое файла (`cat file`) или подтверждать успех текстом.
4.  **Запрет:** Запрещено утверждать "Файл изменен" до выполнения команды записи.

### 🛠 Стандарт команд записи
Для полной перезаписи файлов всегда использовать **heredoc** синтаксис для сохранения форматирования:
```bash
cat > /path/to/file << 'EOF'
<content>
