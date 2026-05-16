# Pentest Projects Manager

Система управления проектами для пентестинга с поддержкой CTF-машин, отчетов в Markdown и синхронизации с Git.

## Возможности

- **Гибридная архитектура БД**: Основная БД для реестра проектов + отдельная БД для каждого проекта
- **Отчеты в Markdown**: Полноценный веб-редактор с предпросмотром, совместимый с Obsidian
- **CTF-машины**: Специальная поддержка для написания writeup'ов с полями для флагов, сложности и названия машины
- **Артефакты**: Загрузка и хранение любых файлов (эксплойты, архивы, скриншоты)
- **Git-синхронизация**: Автоматический push изменений в удаленный репозиторий
- **Экспорт отчетов**: Выгрузка отчетов в .md файлы для использования в Obsidian
- **SPA на React**: Современный интерфейс с роутингом и состоянием

## Структура проекта

```
app/
├── backend/
│   ├── app.py              # Flask API сервер
│   └── requirements.txt    # Python зависимости
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # Основное React приложение
│   │   ├── main.jsx        # Точка входа
│   │   └── index.css       # Стили Tailwind
│   ├── package.json
│   ├── vite.config.js
│   └── ...
└── data/
    ├── main.db             # Основная БД с реестром проектов
    └── projects/
        └── {project_id}/
            ├── project.db  # БД проекта (отчеты, артефакты, сессии)
            ├── reports/    # Экспортированные .md файлы
            ├── artifacts/  # Загруженные файлы
            ├── media/      # Медиа для отчетов
            └── ctf/        # Файлы для CTF
```

## Запуск через Docker

### Основной режим

```bash
docker-compose up --build
```

Приложение будет доступно:
- Frontend: http://localhost:3000
- Backend API: http://localhost:5000

### Режим тестирования (headless)

```bash
docker-compose --profile test up --build
```

## API Endpoints

### Проекты
- `GET /api/projects` - Список всех проектов
- `POST /api/projects` - Создать проект
- `GET /api/projects/:id` - Информация о проекте

### Отчеты
- `GET /api/projects/:id/reports` - Список отчетов
- `POST /api/projects/:id/reports` - Создать отчет
- `PUT /api/projects/:id/reports/:reportId` - Обновить отчет
- `DELETE /api/projects/:id/reports/:reportId` - Удалить отчет
- `GET /api/projects/:id/export/:reportId` - Экспорт в Markdown

### Артефакты
- `GET /api/projects/:id/artifacts` - Список артефактов
- `POST /api/projects/:id/artifacts/upload` - Загрузить файл
- `GET /api/projects/:id/artifacts/:artifactId` - Скачать файл

### Git
- `POST /api/projects/:id/git/sync` - Синхронизация с Git

## Использование с Obsidian

1. Создайте проект с указанием Git-репозитория
2. Пишите отчеты во встроенном редакторе
3. Экспортируйте отчеты через кнопку 📥
4. Клонируйте репозиторий в папку Obsidian
5. Все файлы будут корректно отображаться в Obsidian

## Технологический стек

- **Backend**: Flask, SQLite
- **Frontend**: React 18, Vite, TailwindCSS, @uiw/react-md-editor
- **State Management**: Zustand
- **HTTP Client**: Axios
- **Routing**: React Router DOM
- **Containerization**: Docker, Docker Compose
