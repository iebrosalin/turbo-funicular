cat << 'EOF' > /workspace/PROJECT_CONTEXT.md
# 📚 Project Context: Network Asset Manager

## 1. Общая информация
**Стек технологий:**
- **Backend:** Python 3.12, FastAPI (Async), SQLAlchemy 2.0 (Async), Alembic, Pydantic v2.
- **Frontend:** Vanilla JavaScript (ES6 Modules), HTML5, CSS3.
- **Database:** PostgreSQL 15+.
- **Infrastructure:** Docker, Docker Compose.
- **Testing:** Pytest, Pytest-Asyncio, Httpx.
- **Tools:** Nmap, Rustscan, Dig (dnsutils).

**Архитектурные принципы:**
- Разделение ответственности (Routes → Services → Models).
- Асинхронность на всех уровнях (I/O операции).
- Строгая валидация данных через Pydantic схемы.
- Отсутствие серверного рендеринга (SPA-подход на vanilla JS).
- **Физическое создание файлов:** Все изменения кода выполняются реально в файловой системе `/workspace`. Симуляции исключены.

---

## 2. Структура проекта

.
├── backend/
│   ├── app/
│   │   ├── core/          # Конфигурация, исключения, проверка целостности тестов
│   │   ├── db/            # Сессии БД, базовые модели
│   │   ├── models/        # SQLAlchemy модели (Asset, Group, Scan)
│   │   ├── schemas/       # Pydantic схемы (Request/Response)
│   │   ├── services/      # Бизнес-логика (AssetService, etc.)
│   │   ├── routes/        # API endpoints (FastAPI routers)
│   │   ├── test_hash.txt  # Эталонный хеш тестов (генерируется автоматически)
│   │   └── main.py        # Точка входа с проверкой безопасности
│   ├── alembic/           # Миграции БД
│   ├── scripts/           # Скрипты обслуживания (update_test_hash.py)
│   ├── tests/             # Тесты (Unit, Integration)
│   │   ├── unit/          # Тесты сервисов
│   │   └── integration/   # Тесты API и связей
│   ├── pytest.ini         # Конфиг тестов
│   ├── Dockerfile         # Образ с проверкой тестов при сборке
│   └── requirements.txt
├── frontend/
│   ├── static/
│   │   ├── js/
│   │   │   ├── modules/   # Переиспользуемая логика
│   │   │   ├── pages/     # Логика страниц
│   │   │   └── main.js    # Инициализация
│   │   └── css/
│   └── templates/         # HTML шаблоны
├── docker-compose.yml
├── .gitignore
└── PROJECT_CONTEXT.md

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
- Внедрение системы защиты целостности тестов (SHA256).

❌ **Удалено:**
- Авторизация и пользователи (режим анонимного админа).
- Синхронные блокирующие вызовы БД.
- Инлайн-скрипты в шаблонах.
- Сервис Adminer.

---

## 4. 🔗 Карта связей: UI ↔ JS ↔ Backend

| Функционал | HTML Элемент | JS Модуль / Функция | API Endpoint | Backend Service |
| :--- | :--- | :--- | :--- | :--- |
| **Дерево групп** | `.group-node` | `tree.js` → `handleGroupClick()` | `GET /api/groups/tree` | `GroupService.get_tree()` |
| **Фильтр активов** | `#asset-filter` | `dashboard-page.js` → `applyFilters()` | `GET /api/assets?search=...` | `AssetService.filter()` |
| **Создание актива** | `#asset-form` | `assets.js` → `handleAssetSubmit()` | `POST /api/assets` | `AssetService.create()` |
| **Удаление актива** | `.btn-delete-asset` | `assets.js` → `confirmAndDelete()` | `DELETE /api/assets/{id}` | `AssetService.delete()` |
| **Запуск скана** | `#scan-form` | `scans.js` → `submitScanForm()` | `POST /api/scans` | `ScanService.create()` |
| **Результаты скана** | `.btn-view-results` | `scans.js` → `viewScanResults()` | `GET /api/scans/{id}/results` | `ScanService.get_results()` |

---

## 5. 🛠️ Практические команды и инструкции

### Запуск проекта
# Сборка и запуск всех сервисов
docker-compose up --build

# Запуск в фоновом режиме
docker-compose up -d

# Остановка и удаление контейнеров + томов (сброс БД)
docker-compose down -v

### Работа с базой данных
# Применить миграции вручную
docker-compose exec backend alembic upgrade head

# Создать новую миграцию после изменения моделей
docker-compose exec backend alembic revision --autogenerate -m "Description"

# Подключиться к CLI базы данных
docker-compose exec db psql -U user -d assetdb

### Тестирование и Целостность
# Запуск всех тестов
docker-compose exec backend pytest --cov=app -v

# Обновление эталонного хеша тестов (обязательно после изменений в тестах)
docker-compose exec backend python scripts/update_test_hash.py

# Проверка целостности (выполняется автоматически при старте)
# Если хеш не совпадает, приложение откажется запускаться.

### Отладка
# Просмотр логов backend
docker-compose logs -f backend

# Войти в контейнер backend
docker-compose exec backend bash

# Проверка здоровья
curl http://localhost:8000/health

### Конфигурация портов
| Сервис | Порт | Описание |
| :--- | :--- | :--- |
| **Frontend/API** | 8000 | Приложение и Swagger UI (/docs) |
| **Database** | 5432 | PostgreSQL |

---

## 6. Протокол работы и ограничения

### 🛡️ Защита целостности тестов (CRITICAL)
**Механизм:** SHA256 хеширование всех файлов в директории tests/.
**Правило:** Запуск приложения (main.py) блокируется, если текущий хеш файлов тестов не совпадает с эталонным (app/test_hash.txt).
**Сборка Docker:** Образ не будет собран, если тесты не проходят успешно на этапе docker build.

**Как легально изменить тесты:**
1. Внесите необходимые изменения в код тестов.
2. Запустите команду обновления эталона (только если все тесты проходят локально):
   docker-compose exec backend python scripts/update_test_hash.py
3. После успешного выполнения скрипта хеш обновится, и приложение сможет запуститься.

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

### Обновление контекста
Файл PROJECT_CONTEXT.md должен обновляться после каждого значительного изменения архитектуры, добавления новых модулей или изменения правил безопасности.

---

## 7. Известные ограничения
- **Безопасность:** Отсутствует аутентификация и авторизация. Приложение доступно по сети без ограничений (режим разработки/доверенной сети).
- **Фоновые задачи:** Сканирования выполняются синхронно в рамках запроса (блокируют ответ до завершения). В будущем требуется вынос в Celery/BackgroundTasks.
- **Масштабирование:** Текущая конфигурация рассчитана на одиночный инстанс backend.
EOF