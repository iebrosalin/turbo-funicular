# 📚 Project Context: Network Asset Manager

## 1. Общая информация
**Стек технологий:**
- **Backend:** Python 3.12, FastAPI (Async), SQLAlchemy 2.0 (Async), Alembic, Pydantic v2.
- **Frontend:** Vanilla JavaScript (ES6 Modules), HTML5, CSS3.
- **Database:** SQLite (по умолчанию и единственная поддерживаемая БД).
- **Infrastructure:** Docker, Docker Compose.
- **Testing:** Pytest, Pytest-Asyncio, Httpx.
- **Tools:** Nmap, Rustscan, Dig (dnsutils).

**Архитектурные принципы:**
- Разделение ответственности (Routes → Services → Models).
- Асинхронность на всех уровнях (I/O операции).
- Строгая валидация данных через Pydantic схемы.
- Отсутствие серверного рендеринга (SPA-подход на vanilla JS).
- **Физическое создание файлов:** Все изменения кода выполняются реально в файловой системе `/workspace`. Симуляции исключены.
- **Гибкость запуска:** Поддержка работы как в Docker, так и локально через `python app.py` без контейнеров.
- **Только SQLite:** Проект полностью переведён на SQLite для упрощения развёртывания. PostgreSQL удалён.

---

## 2. Структура проекта

```text
/workspace/
├── app.py                 # Точка входа для локального запуска (uvicorn wrapper)
├── .env                   # Конфигурация окружения (DATABASE_URL, настройки)
├── .env.example           # Шаблон конфигурации
├── requirements.txt       # Зависимости Python
├── docker-compose.yml     # Конфигурация Docker
├── Dockerfile             # Образ приложения
├── instance/              # Локальная БД SQLite (создается автоматически)
│   └── network_inventory.db
├── backend/
│   ├── app/
│   │   ├── core/          # Конфигурация, исключения
│   │   ├── db/            # Сессии БД, базовые модели
│   │   ├── models/        # SQLAlchemy модели (Asset, Group, Scan, Log)
│   │   ├── schemas/       # Pydantic схемы (Request/Response)
│   │   ├── services/      # Бизнес-логика + Менеджеры очередей сканирований
│   │   ├── routes/        # API endpoints (FastAPI routers)
│   │   ├── utils/         # Утилиты (время, сеть, импорт Nmap XML)
│   │   └── main.py        # Приложение FastAPI (lifespan, роутеры)
│   ├── alembic/           # Миграции БД
│   ├── tests/             # Тесты (Unit, Integration)
│   └── requirements.txt   # Дубль зависимостей (для совместимости)
├── frontend/
│   ├── static/
│   │   ├── js/
│   │   │   ├── modules/   # Переиспользуемая логика
│   │   │   ├── pages/     # Логика страниц
│   │   │   └── main.js    # Инициализация
│   │   └── css/
│   └── templates/         # HTML шаблоны
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
- Полное покрытие тестами (Unit + Integration).
- **Перенос всего функционала Flask:** модели, маршруты, утилиты, очереди сканирований.
- **Поддержка SQLite:** возможность запуска без Docker и PostgreSQL.
- **Создание точки входа `app.py`:** запуск одной командой `python app.py`.
- **Удаление PostgreSQL:** проект полностью переведён на SQLite.

❌ **Удалено:**
- Авторизация и пользователи (режим анонимного админа).
- Синхронные блокирующие вызовы БД.
- Инлайн-скрипты в шаблонах.
- Сервис Adminer.
- Дублирующиеся файлы (старые Dockerfile, папки api/v1).
- Поддержка PostgreSQL и зависимость asyncpg.

---

## 4. 🔗 Карта связей: UI ↔ JS ↔ Backend

| Функционал | HTML Элемент | JS Модуль / Функция | API Endpoint | Backend Service |
| :--- | :--- | :--- | :--- | :--- |
| **Дерево групп** | `.group-node` | `tree.js` → `handleGroupClick()` | `GET /api/groups/tree` | `GroupService.get_tree()` |
| **Фильтр активов** | `#asset-filter` | `dashboard-page.js` → `applyFilters()` | `GET /api/assets?search=...` | `AssetService.filter()` |
| **Создание актива** | `#asset-form` | `assets.js` → `handleAssetSubmit()` | `POST /api/assets` | `AssetService.create()` |
| **Удаление актива** | `.btn-delete-asset` | `assets.js` → `confirmAndDelete()` | `DELETE /api/assets/{id}` | `AssetService.delete()` |
| **Запуск скана** | `#scan-form` | `scans.js` → `submitScanForm()` | `POST /api/scans/start/nmap` | `ScanQueueManager.add_scan()` |
| **Результаты скана** | `.btn-view-results` | `scans.js` → `viewScanResults()` | `GET /api/scans/jobs/{job_id}` | `ScanService.get_job()` |
| **Очередь сканирований** | `.scan-queue` | `scans.js` → `refreshQueue()` | `GET /api/scans/jobs` | `ScanQueueManager.get_queue()` |
| **Импорт Nmap XML** | `#import-form` | `utilities.js` → `uploadXml()` | `POST /api/utilities/import-nmap-xml` | `NmapXmlImporter.parse_file()` |
| **Динамические группы** | `#group-rules` | `groups.js` → `saveDynamicGroup()` | `POST /api/groups` (с `filter_rules`) | `GroupService.create_dynamic()` |

---

## 5. 🛠️ Практические команды и инструкции

### Запуск проекта (Локально без Docker)
```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск приложения (SQLite создается автоматически)
python app.py

# Приложение доступно на http://localhost:8000
# Документация API: http://localhost:8000/docs
```

### Запуск проекта (Docker)
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
# Применить миграции вручную (Docker)
docker-compose exec web alembic upgrade head

# Создать новую миграцию после изменения моделей (Docker)
docker-compose exec web alembic revision --autogenerate -m "Description"

# Для SQLite локально:
# Файл БД: instance/network_inventory.db
# Просмотр через: sqlite3 instance/network_inventory.db
```

### Тестирование
```bash
# Запуск всех тестов (локально)
pytest backend/tests/ --cov=app -v

# Запуск всех тестов (Docker)
docker-compose exec web pytest --cov=app -v
```

### Отладка
```bash
# Просмотр логов backend (Docker)
docker-compose logs -f web

# Войти в контейнер web (Docker)
docker-compose exec web bash

# Проверка здоровья
curl http://localhost:8000/health
```

### Конфигурация портов
| Сервис | Порт | Описание |
| :--- | :--- | :--- |
| **Frontend/API** | 8000 | Приложение и Swagger UI (/docs) |

---

## 6. Протокол работы и ограничения

### 🚫 Критические запреты (Строго без согласования)
Следующие действия ЗАПРЕЩЕНЫ и будут отклонены:

1.  **Файл .gitignore:**
    *   ЗАПРЕЩЕНО добавлять, удалять или изменять правила игнорирования файлов.
    *   Этот файл контролирует чистоту репозитория.

2.  **Системные пакеты в Dockerfile:**
    *   ЗАПРЕЩЕНО изменять список пакетов apt-get install (особенно инструменты сканирования: nmap, rustscan, dnsutils).
    *   Любые изменения должны быть обоснованы критической необходимостью.

3.  **Веб-интерфейс (Frontend):**
    *   ЗАПРЕЩЕНО менять структуру HTML, CSS стили или логику JavaScript без предварительного утверждения макета и функционала.
    *   Интерфейс должен оставаться стабильным.

4.  **Безопасность и Пользователи (NO AUTH):**
    *   КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО внедрять системы аутентификации (JWT, сессии, OAuth), авторизации (RBAC), формы входа или регистрации.
    *   Приложение должно работать в режиме «Анонимный администратор» (полный доступ ко всем функциям без пароля).
    *   Любые попытки добавить меры безопасности считаются нарушением архитектуры текущего этапа.

5.  **PostgreSQL:**
    *   ЗАПРЕЩЕНО возвращать поддержку PostgreSQL или добавлять зависимости asyncpg/psycopg2.
    *   Проект использует только SQLite.

### Обновление контекста
Файл PROJECT_CONTEXT.md должен обновляться после каждого значительного изменения архитектуры, добавления новых модулей или изменения правил безопасности.

---

## 7. Известные ограничения
- **Безопасность:** Отсутствует аутентификация и авторизация. Приложение доступно по сети без ограничений (режим разработки/доверенной сети).
- **Фоновые задачи:** Сканирования выполняются асинхронно через `ScanQueueManager` в рамках процесса приложения.
- **Масштабирование:** Текущая конфигурация рассчитана на одиночный инстанс backend с SQLite. Для высокой нагрузки рекомендуется использовать Docker с настройками производительности SQLite или рассмотреть миграцию на PostgreSQL (но это требует отдельного согласования).
- **Режим запуска:** SQLite полностью функционален для всех операций проекта.