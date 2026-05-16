# 🚫 DEVELOPMENT CONTEXT - ЗАПРЕЩЕНО ИСПОЛЬЗОВАТЬ ALEMBIC

## ⛔ КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО

**НА ЭТАПЕ РАЗРАБОТКИ ЗАПРЕЩЕНО ИСПОЛЬЗОВАТЬ ALEMBIC ДЛЯ МИГРАЦИЙ БД!**

### Почему?
- Alembic добавляет излишнюю сложность на этапе активной разработки
- Миграции выполняются вручную через Python скрипты
- SQLite не требует сложных миграций в разработке

### Как создавать миграции?
1. Создавать Python скрипты в `/workspace/backend/migrations/`
2. Выполнять их через `docker-compose exec app python backend/migrations/script_name.py`
3. Изменения моделей применяются напрямую через SQLAlchemy `Base.metadata.create_all()`

### Контекст применения Alembic
Alembic будет использоваться ТОЛЬКО:
- При переходе на production среду
- При работе с PostgreSQL/MySQL вместо SQLite
- По явному запросу разработчика

---

## 📋 ТЕКУЩИЙ СТАТУС ПРОЕКТА

### ✅ Исправленные проблемы:
1. **Добавлены Pydantic схемы для CTFMachine и ProjectGitSync** - модели теперь имеют полные схемы для API
2. **Исправлен requirements.txt** - заменён Flask на FastAPI и необходимые зависимости

### 🔧 Технологии проекта:
- **Backend:** FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2
- **Frontend:** Vanilla JavaScript (ES6 Modules), Bootstrap 5.3+
- **Database:** SQLite (единственная поддерживаемая БД)
- **Infrastructure:** Docker, Docker Compose

### 📁 Модули:
1. **Network Asset Manager** - управление активами, группами, сканированиями
2. **Projects Module** - проекты пентестинга, отчёты Markdown, артефакты, CTF-машины, Git-синхронизация

### 🚀 Команды для работы:
```bash
# Запуск приложения
docker-compose up -d

# Применение миграций БД (вручную)
docker-compose exec app python backend/init_db.py

# Перезапуск приложения
docker-compose restart app

# E2E тесты
docker compose --profile e2e run --rm e2e-tests
```

---

## ⚡ BASH FIRST ПРОТОКОЛ

Все изменения файлов должны выполняться через команды bash в терминале!

---

## 🔕 ИНТЕГРАЦИЯ С REDCHECK И ПРОЕКТАМИ - БЕЗ ТЕСТОВ

### ⛔ ЗАПРЕЩЕНО ПОКРЫВАТЬ ТЕСТАМИ:

1. **RedCheck Integration** - вся функциональность интеграции с RedCheck НЕ тестируется
   - API роуты `/api/redcheck/*`
   - Синхронизация хостов RedCheck
   - Сканирования через RedCheck

2. **Projects Module** - модуль проектов НЕ тестируется
   - CRUD проектов (`/api/projects/*`)
   - Отчёты проектов (`/api/projects/reports/*`)
   - Артефакты проектов (`/api/projects/artifacts/*`)
   - CTF-машины (`/api/projects/ctf-machines/*`)
   - Git-синхронизация проектов (`/api/projects/git-sync/*`)
   - Сессии сканирования проектов (`/api/projects/scan-sessions/*`)

### ✅ ЧТО ТЕСТИРОВАТЬ:

Только основной функционал Network Asset Manager:
- Управление активами (CRUD)
- Управление группами (иерархия, добавление/удаление активов)
- Сканирования (Nmap, Rustscan, Dig, Fping)
- Скачивание результатов сканирований
- История сканирований

---

## 📁 СТРУКТУРА ШАБЛОНОВ

Шаблоны организованы по разделам:
```
backend/templates/
├── assets/          # Шаблоны управления активами
├── scans/           # Шаблоны сканирований
├── groups/          # Шаблоны управления группами
├── projects/        # Шаблоны проектов
├── redcheck/        # Шаблоны RedCheck интеграции
├── components/      # Переиспользуемые компоненты
└── base.html        # Базовый шаблон
```

---

## 🧪 E2E ТЕСТЫ ДАННЫЕ

Для headless E2E тестов используются:
- **Цели:** ya.ru, 1.1.1.1, 8.8.8.8
- **Группы:** test1, test1-2, тест (разный уровень вложенности)

---

✅ DEVELOPMENT CONTEXT создан успешно!
