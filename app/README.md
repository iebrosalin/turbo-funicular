# SPA Frontend для Network Asset Manager

## Обзор

Это Single Page Application (SPA) на React для управления проектами пентеста, отчётами и артефактами.

## Стек технологий

- **React 18** - UI библиотека
- **React Router DOM 6** - Роутинг
- **Vite** - Сборщик
- **TailwindCSS** - Стилизация
- **Zustand** - Управление состоянием
- **@uiw/react-md-editor** - Markdown редактор (на базе CodeMirror)
- **Axios** - HTTP клиент
- **Lucide React** - Иконки

## Структура проекта

```
frontend-spa/
├── src/
│   ├── api/              # API клиенты
│   │   ├── client.js     # Базовый HTTP клиент
│   │   └── projects.js   # API для проектов
│   ├── components/       # Переиспользуемые компоненты
│   ├── layouts/          # Layouts (навигация, сайдбар)
│   ├── pages/            # Страницы приложения
│   │   ├── DashboardPage.jsx
│   │   ├── ProjectsPage.jsx
│   │   └── ProjectDetailPage.jsx
│   ├── stores/           # Zustand stores
│   │   ├── projectStore.js
│   │   ├── reportStore.js
│   │   └── artifactStore.js
│   ├── hooks/            # Custom hooks
│   ├── utils/            # Утилиты
│   ├── App.jsx           # Корневой компонент
│   ├── main.jsx          # Точка входа
│   └── index.css         # Глобальные стили
├── public/               # Статические файлы
├── index.html            # HTML шаблон
├── package.json          # Зависимости
├── vite.config.js        # Конфигурация Vite
├── tailwind.config.js    # Конфигурация Tailwind
└── postcss.config.js     # Конфигурация PostCSS
```

## Установка

```bash
cd frontend-spa
npm install
```

## Запуск в режиме разработки

```bash
npm run dev
```

Приложение будет доступно по адресу http://localhost:3000

Vite автоматически проксирует запросы к `/api` на бэкенд (http://localhost:5000).

## Сборка для продакшена

```bash
npm run build
```

Собранные файлы будут в директории `dist/`.

## Интеграция с бэкендом

### Настройка прокси

В `vite.config.js` настроен прокси для API запросов:

```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:5000',
      changeOrigin: true,
    },
  },
}
```

### Раздача статики через FastAPI

После сборки, настройте FastAPI для раздачи файлов из `dist/`:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Монтирование статики
app.mount("/static", StaticFiles(directory="frontend-spa/dist/static"), name="static")

# Fallback роутинг для SPA
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("static/"):
        raise HTTPException(status_code=404)
    return FileResponse("frontend-spa/dist/index.html")
```

## Компоненты

### Markdown редактор

Используется `@uiw/react-md-editor` - полноценный редактор с предпросмотром на базе CodeMirror.

```jsx
import MDEditor from '@uiw/react-md-editor';

<MDEditor
  value={markdown}
  onChange={setValue}
  preview="edit"  // Показывать предпросмотр рядом с редактором
  height={400}
/>
```

### Хранение состояния (Zustand)

Простой и эффективный менеджер состояния:

```javascript
import { create } from 'zustand';

export const useProjectStore = create((set) => ({
  projects: [],
  fetchProjects: async () => {
    const projects = await api.getProjects();
    set({ projects });
  },
}));
```

## API Endpoints

### Проекты

- `GET /api/projects` - Список проектов
- `GET /api/projects/:id` - Детали проекта
- `POST /api/projects` - Создать проект
- `PUT /api/projects/:id` - Обновить проект
- `DELETE /api/projects/:id` - Удалить проект

### Отчёты

- `GET /api/projects/:id/reports` - Список отчётов
- `POST /api/projects/:id/reports` - Создать отчёт
- `PUT /api/projects/:id/reports/:reportId` - Обновить отчёт
- `GET /api/projects/:id/reports/:reportId/export` - Экспорт в Markdown

### Артефакты

- `GET /api/projects/:id/artifacts` - Список артефактов
- `POST /api/projects/:id/artifacts` - Загрузить артефакт
- `GET /api/projects/:id/artifacts/:artifactId` - Скачать артефакт
- `DELETE /api/projects/:id/artifacts/:artifactId` - Удалить артефакт

## Obsidian совместимость

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

## Git синхронизация

Планируется интеграция с Git для автоматической синхронизации отчётов и артефактов с удалёнными репозиториями.

## Планы развития

- [ ] Полная реализация всех страниц (сканирования, активы, группы)
- [ ] WebSocket/SSE для real-time обновлений
- [ ] Drag-and-drop для дерева групп
- [ ] Расширенный поиск и фильтрация
- [ ] Темизация (светлая/тёмная тема)
- [ ] i18n поддержка
- [ ] Unit и E2E тесты
