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
        ├── conftest.py
        └── test_scanners_e2e.py
```

---

## 3. 🔧 Текущий статус проекта

✅ **Завершено:**
- **ES6 Модули:** Полный рефакторинг JS.
- **UUID:** Поле `uuid` во всех таблицах, автогенерация и миграция.
- **FilterBuilder:** Единый класс для сложных запросов (SQL-like синтаксис).
- **E2E Тесты:** Playwright тесты для UI и сканеров (Dig, Nmap, Rustscan).
- **UI/UX:** Темная тема по умолчанию, страница настроек, исправления контрастности.
- **Schema Caching:** Кеширование схемы полей активов на фронтенде и бэкенде.

---

## 4. 🔗 Карта связей: UI ↔ JS ↔ Backend

| Функционал | JS Модуль | API Endpoint |
| :--- | :--- | :--- |
| **Сканеры (E2E)** | `test_scanners_e2e.py` | `POST /api/scans/start/*` |
| **Фильтры (SQL-like)** | `FilterBuilder` | `GET /api/assets?rules=...` |
| **Схема полей** | `Utils.getAssetSchema()` | `GET /api/assets/schema` |
| **Дерево групп** | `TreeManager` | `GET /api/groups/tree` |

---

## 5. 🛠️ Практические команды

### Тестирование (E2E)
```bash
docker compose --profile e2e run --rm e2e-tests tests/integration/test_scanners_e2e.py
```

---

## 6. 📋 Протокол работы и ограничения

### 🚫 Критические запреты
1.  **Файл .gitignore:** ЗАПРЕЩЕНО изменять.
2.  **Системные пакеты:** ЗАПРЕЩЕНО менять набор инструментов сканирования в Dockerfile.
3.  **Безопасность:** ЗАПРЕЩЕНО внедрять аутентификацию/авторизацию.
4.  **PostgreSQL:** ЗАПРЕЩЕНО. Только SQLite.

### ✅ Правила исполнения (STRICT)
1.  **Запись через Bash:** Любое изменение файла должно начинаться с выполнения команды записи через `bash` (например, `cat > file << 'EOF'`).
2.  **Проверка Code Tool Record:** Если инструмент не показывает изменений, файл считается НЕ записанным. Требуется полное пересоздание через `bash`.
3.  **Вывод после записи:** Вывод содержимого (`cat` или `view`) разрешен ТОЛЬКО после успешной команды записи.
4.  **Двойное удаление:** При удалении файлов выполнять команду дважды.

---

## 7. ⚠️ Известные ограничения
- **Безопасность:** Полный доступ без пароля.
- **Масштабирование:** Одиночный инстанс с SQLite.

---

## 8. 📦 Зависимости проекта

### Python зависимости
- **FastAPI** 0.115.0
- **SQLAlchemy** 2.0.31 + **aiosqlite** 0.20.0
- **Playwright** (для тестов)

### Системные зависимости
- **nmap**, **rustscan**, **dnsutils**

---

*Последнее обновление: Май 2026*
