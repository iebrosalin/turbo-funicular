# 📘 Контекст проекта: Asset Management System

## 1. Общая информация
**Описание:** Система управления сетевыми активами, группами и сканированиями (nmap/rustscan).
**Архитектура:** Клиент-серверное приложение.
- **Frontend:** Vanilla JS (ES6 Modules), HTML5, CSS3. Без фреймворков.
- **Backend:** Python **FastAPI** (асинхронный), SQLAlchemy 2.0 (Async), Alembic.
- **Database:** PostgreSQL.
- **Infrastructure:** Docker, Docker Compose.

## 2. Структура проекта
```
/workspace
├── backend/
│   ├── app/
│   │   ├── core/          # Конфигурация, исключения
│   │   ├── db/            # Сессии БД, базовые модели
│   │   ├── models/        # SQLAlchemy модели (Asset, Group, Scan)
│   │   ├── routes/        # API роуты (assets, groups, scans)
│   │   ├── schemas/       # Pydantic схемы (валидация)
│   │   ├── services/      # Бизнес-логика (CRUD операции)
│   │   └── main.py        # Точка входа FastAPI
│   ├── alembic/           # Миграции БД
│   ├── requirements.txt   # Зависимости Python
│   └── Dockerfile
├── frontend/
│   ├── static/
│   │   ├── js/
│   │   │   ├── modules/   # Переиспользуемые модули (tree, assets, groups)
│   │   │   ├── pages/     # Специфичная логика страниц
│   │   │   └── main.js    # Глобальная инициализация
│   │   └── css/
│   └── templates/         # HTML шаблоны
├── docker-compose.yml
└── PROJECT_CONTEXT.md     # Этот файл
```

## 3. Статус рефакторинга (Flask → FastAPI)
**Дата завершения:** Текущая сессия.
**Ключевые изменения:**
- ✅ Переход на асинхронный стек (`async/await`).
- ✅ Внедрение сервисного слоя (`services/`) для отделения логики от роутов.
- ✅ Настройка миграций через **Alembic**.
- ✅ Валидация данных через **Pydantic v2**.
- ✅ Обновление Docker-конфигурации (Python 3.12, health-checks).
- ✅ Удаление интеграций с Wazuh и osquery.
- ✅ Удаление системы авторизации (режим анонимного администратора).

**Удаленные файлы (Flask):**
- `backend/app.py`
- `backend/models.py`
- `backend/migrations/` (старая папка)

**Созданные файлы (FastAPI):**
- `backend/app/main.py`, `backend/app/routes/*.py`, `backend/app/services/*.py`
- `backend/app/models/*.py`, `backend/app/schemas/*.py`
- `backend/alembic/` (новая структура)

## 4. API Контракты (Основные эндпоинты)
| Метод | Путь | Описание | Сервис |
|-------|------|----------|--------|
| GET | `/api/assets` | Список активов (с фильтрацией) | `AssetService` |
| POST | `/api/assets` | Создание актива | `AssetService` |
| DELETE | `/api/assets/{id}` | Удаление актива | `AssetService` |
| GET | `/api/groups` | Дерево групп | `GroupService` |
| POST | `/api/groups` | Создание группы | `GroupService` |
| PUT | `/api/groups/{id}` | Обновление группы | `GroupService` |
| POST | `/api/scans` | Запуск сканирования | `ScanService` |
| GET | `/api/scans/{id}/results` | Результаты сканирования | `ScanService` |

## 5. Инструкции по запуску
### Локальная разработка (Docker)
```bash
# Очистка старых томов (важно после смены ORM)
docker-compose down -v

# Сборка и запуск
docker-compose up --build

# Применение миграций (выполняется автоматически в контейнере)
# Проверка логов: docker-compose logs backend
```

### Доступ к сервисам
- **Приложение:** http://localhost:8000
- **Swagger UI (API Docs):** http://localhost:8000/docs
- **База данных:** localhost:5432 (user: postgres, pass: postgres)

## 6. План развития (Roadmap)
1.  **Тестирование:** Покрытие сервисов и API тестами (pytest).
2.  **Безопасность:** Возвращение JWT-аутентификации (опционально).
3.  **Оптимизация:** Кэширование частых запросов, индексы БД.
4.  **Функционал:** Поддержка массового импорта активов, расписание сканирований (Celery).

## 7. Известные ограничения
- ❌ Нет системы пользователей/ролей (все действия от имени админа).
- ❌ Нет интеграции с Wazuh/osquery (только nmap/rustscan).
- ⚠️ Фоновые задачи сканирования работают через `BackgroundTasks` FastAPI (не потоковый сервер задач). Для тяжелых нагрузок потребуется Celery.

---
*Файл автоматически обновляется при значительных изменениях архитектуры.*
