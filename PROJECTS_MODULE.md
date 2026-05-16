# 📁 Раздел "Проекты" - Документация

## Обзор

Раздел **Проекты** предназначен для управления информацией о работе утилит в рамках проектов пентеста, хранения отчётов в Markdown-формате (совместимом с Obsidian), артефактов и других файлов, связанных с результатами тестирования.

## Архитектура

### Модели данных

#### Project (Проект)
Основная сущность для управления проектами пентеста.

**Поля:**
- `id`, `uuid` - Идентификаторы
- `name` - Название проекта
- `description` - Описание
- `customer` - Заказчик
- `project_type` - Тип (pentest, audit, research)
- `status` - Статус (planning, active, paused, completed, archived)
- `priority` - Приоритет (low, medium, high, critical)
- `start_date`, `end_date` - Даты начала и окончания
- `groups` - Связь с группами активов (many-to-many)

#### ProjectReport (Отчёт)
Хранение отчётов в Markdown-формате.

**Поля:**
- `id`, `uuid` - Идентификаторы
- `project_id` - Связь с проектом
- `title` - Заголовок отчёта
- `report_type` - Тип (general, executive, technical, vulnerability)
- `content` - Markdown контент
- `content_html` - HTML версия (кэшированная)
- `version` - Версия отчёта
- `is_final` - Финальная версия
- `tags` - Теги
- `obsidian_tags` - Теги в формате Obsidian
- `obsidian_links` - Ссылки на другие заметки

**Obsidian совместимость:**
- Экспорт в формате Markdown с Front Matter
- Поддержка тегов Obsidian
- Поддержка внутренних ссылок

#### ProjectArtifact (Артефакт)
Хранение файлов, скриншотов, логов и других артефактов.

**Поля:**
- `id`, `uuid` - Идентификаторы
- `project_id` - Связь с проектом
- `name` - Название
- `description` - Описание
- `artifact_type` - Тип (file, screenshot, log, export, evidence)
- `file_path` - Путь к файлу
- `file_size` - Размер в байтах
- `mime_type` - MIME тип
- `checksum` - SHA256 хэш
- `category` - Категория (reconnaissance, exploitation, post_exploitation, reporting)
- `scan_id` - Связь со сканированием

#### ProjectScanSession (Сессия сканирования)
Информация о сессиях сканирования в рамках проекта.

**Поля:**
- `id`, `uuid` - Идентификаторы
- `project_id` - Связь с проектом
- `name` - Название сессии
- `description` - Описание
- `session_type` - Тип (manual, automated, scheduled)
- `utilities_used` - Использованные утилиты
- `parameters` - Параметры запуска
- `targets` - Цели сканирования
- `results_summary` - Краткое описание результатов
- `scan_ids` - ID связанных сканирований

## API Endpoints

### Проекты

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/projects` | Получить список проектов |
| GET | `/api/projects/{id}` | Получить проект по ID |
| POST | `/api/projects` | Создать проект |
| PUT | `/api/projects/{id}` | Обновить проект |
| DELETE | `/api/projects/{id}` | Удалить проект |

### Отчёты

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/projects/{id}/reports` | Получить все отчёты проекта |
| GET | `/api/projects/{id}/reports/{report_id}` | Получить отчёт по ID |
| POST | `/api/projects/{id}/reports` | Создать отчёт |
| PUT | `/api/projects/{id}/reports/{report_id}` | Обновить отчёт |
| DELETE | `/api/projects/{id}/reports/{report_id}` | Удалить отчёт |
| GET | `/api/projects/{id}/reports/{report_id}/export` | Экспорт в Markdown (Obsidian) |

### Артефакты

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/projects/{id}/artifacts` | Получить все артефакты |
| POST | `/api/projects/{id}/artifacts` | Загрузить артефакт |
| GET | `/api/projects/{id}/artifacts/{artifact_id}` | Скачать артефакт |
| DELETE | `/api/projects/{id}/artifacts/{artifact_id}` | Удалить артефакт |

### Сессии сканирования

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/projects/{id}/sessions` | Получить все сессии |
| POST | `/api/projects/{id}/sessions` | Создать сессию |
| PUT | `/api/projects/{id}/sessions/{session_id}` | Обновить сессию |
| DELETE | `/api/projects/{id}/sessions/{session_id}` | Удалить сессию |

## Frontend

### Страницы

- `/projects` - Список всех проектов (карточки)
- `/projects/{id}` - Детали проекта (отчёты, артефакты, сессии)

### JavaScript модуль

`/frontend/static/js/modules/projects.js`

**Функциональность:**
- Загрузка и отображение проектов
- Фильтрация по статусу, приоритету, поиску
- Создание/редактирование/удаление проектов
- Привязка групп активов к проектам

## Примеры использования

### Создание проекта через API

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Пентест веб-приложения",
    "description": "Тестирование безопасности веб-приложения",
    "customer": "ООО Рога и Копыта",
    "project_type": "pentest",
    "status": "active",
    "priority": "high",
    "group_ids": [1, 2]
  }'
```

### Создание отчёта

```bash
curl -X POST http://localhost:8000/api/projects/1/reports \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Отчёт о тестировании",
    "report_type": "technical",
    "content": "# Отчёт\n\n## Найденные уязвимости\n\n...",
    "tags": ["pentest", "web"],
    "obsidian_tags": "#pentest #web #security"
  }'
```

### Загрузка артефакта

```bash
curl -X POST http://localhost:8000/api/projects/1/artifacts \
  -F "file=@nmap_scan.xml" \
  -F "name=Nmap сканирование" \
  -F "artifact_type=log" \
  -F "category=reconnaissance"
```

### Экспорт отчёта для Obsidian

```bash
curl -O http://localhost:8000/api/projects/1/reports/1/export
```

## Хранение артефактов

Артефакты хранятся в директории `/workspace/backend/artifacts/`.

**Структура:**
- Файлы сохраняются с уникальными UUID-именами
- Вычисляется SHA256 хэш для каждого файла
- Информация о файле хранится в БД

## Obsidian интеграция

### Формат экспорта отчётов

Отчёты экспортируются в формате Markdown с Front Matter:

```markdown
---
title: Отчёт о тестировании
created: 2026-05-16 10:00
updated: 2026-05-16 12:00
tags: [pentest, web, security]
obsidian_tags: #pentest #web #security
---

# Отчёт о тестировании

## Содержание

...
```

### Совместимость

- ✅ Markdown формат
- ✅ Front Matter YAML
- ✅ Теги Obsidian
- ✅ Внутренние ссылки (через obsidian_links поле)

## Структура файлов

```
backend/
├── models/
│   └── project.py          # Модели данных
├── schemas/
│   └── project.py          # Pydantic схемы
├── routes/
│   └── projects.py         # API endpoints
├── templates/
│   ├── projects.html       # Страница списка проектов
│   └── project_detail.html # Страница деталей проекта
└── artifacts/              # Хранилище файлов артефактов

frontend/
└── static/
    └── js/
        └── modules/
            └── projects.js # Frontend логика
```

## Безопасность

- Все файлы артефактов хранятся с уникальными именами
- Вычисление контрольных сумм для проверки целостности
- Каскадное удаление связанных данных при удалении проекта

## Планы развития

- [ ] Редактор Markdown отчётов с предпросмотром
- [ ] Шаблоны отчётов
- [ ] Версионирование отчётов с сравнением версий
- [ ] Интеграция с Git для хранения отчётов
- [ ] Экспорт в различные форматы (PDF, DOCX, HTML)
- [ ] Управление доступом к проектам
- [ ] Комментарии и обсуждения в отчётах
