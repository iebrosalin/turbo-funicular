# SPA Frontend Implementation - Network Asset Manager

## Реализованные компоненты

### 1. Структура проекта

Создан новый SPA frontend в директории `/workspace/frontend-spa/` со следующей структурой:

```
frontend-spa/
├── src/
│   ├── api/
│   │   ├── client.js         # Axios клиент с интерцепторами
│   │   └── projects.js       # API методы для проектов, отчётов, артефактов
│   ├── layouts/
│   │   └── Layout.jsx        # Основной layout с навигацией
│   ├── pages/
│   │   ├── DashboardPage.jsx      # Главная страница
│   │   ├── ProjectsPage.jsx       # Список проектов с фильтрами
│   │   └── ProjectDetailPage.jsx  # Детали проекта с вкладками
│   ├── stores/
│   │   ├── projectStore.js    # Zustand store для проектов
│   │   ├── reportStore.js     # Zustand store для отчётов
│   │   └── artifactStore.js   # Zustand store для артефактов
│   ├── App.jsx               # Роутинг приложения
│   ├── main.jsx              # Точка входа React
│   └── index.css             # Глобальные стили Tailwind
├── public/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

### 2. Стек технологий

- **React 18** - UI библиотека
- **React Router DOM 6** - Клиентский роутинг
- **Vite** - Быстрый сборщик
- **TailwindCSS** - Утилитарные CSS классы
- **Zustand** - Легковесный менеджер состояния
- **@uiw/react-md-editor** - Markdown редактор на базе CodeMirror
- **Axios** - HTTP клиент
- **Lucide React** - Современные иконки

### 3. Функциональность

#### Страница проектов (`/projects`)
- Отображение списка проектов в виде карточек
- Поиск по названию и заказчику
- Фильтрация по статусу (planning, active, paused, completed, archived)
- Индикация приоритета и количества отчётов/артефактов
- Навигация к деталям проекта

#### Страница деталей проекта (`/projects/:id`)
- Вкладки: Обзор, Отчёты, Артефакты, Сессии, CTF, Git
- **Обзор**: Основная информация о проекте
- **Отчёты**: 
  - Список отчётов с мета-данными
  - Markdown редактор с предпросмотром (@uiw/react-md-editor)
  - Создание и редактирование отчётов
- **Артефакты**:
  - Таблица загруженных файлов
  - Загрузка новых файлов
  - Скачивание артефактов
- **Сессии, CTF, Git**: Заготовки для будущего функционала

### 4. API интеграция

#### Проекты API (`src/api/projects.js`)
```javascript
projectsApi.getAll()
projectsApi.getById(id)
projectsApi.create(data)
projectsApi.update(id, data)
projectsApi.delete(id)

// Отчёты
projectsApi.reports.getAll(projectId)
projectsApi.reports.create(projectId, data)
projectsApi.reports.update(projectId, reportId, data)
projectsApi.reports.export(projectId, reportId)

// Артефакты
projectsApi.artifacts.getAll(projectId)
projectsApi.artifacts.upload(projectId, formData)
projectsApi.artifacts.download(projectId, artifactId)

// Сессии
projectsApi.sessions.getAll(projectId)
projectsApi.sessions.create(projectId, data)

// CTF машины
projectsApi.ctfMachines.getAll(projectId)
projectsApi.ctfMachines.create(projectId, data)

// Git синхронизация
projectsApi.gitSync.get(projectId)
projectsApi.gitSync.sync(projectId)
```

### 5. Управление состоянием (Zustand)

#### Project Store
```javascript
useProjectStore({
  projects: [],
  currentProject: null,
  loading: false,
  error: null,
  
  // Actions
  fetchProjects,
  fetchProjectById,
  createProject,
  updateProject,
  deleteProject,
})
```

#### Report Store
```javascript
useReportStore({
  reports: [],
  currentReport: null,
  
  // Actions
  fetchReports,
  createReport,
  updateReport,
  exportReport,
})
```

#### Artifact Store
```javascript
useArtifactStore({
  artifacts: [],
  
  // Actions
  fetchArtifacts,
  uploadArtifact,
  downloadArtifact,
  deleteArtifact,
})
```

### 6. Markdown редактор

Используется `@uiw/react-md-editor` - полноценный редактор с:
- Подсветкой синтаксиса (CodeMirror)
- Предпросмотром в реальном времени
- Поддержкой таблиц, списков, кода
- Экспортом в формат Obsidian

```jsx
<MDEditor
  value={content}
  onChange={setContent}
  preview="edit"
  height={400}
/>
```

### 7. Obsidian совместимость

Отчёты хранятся в формате Markdown и экспортируются с Front Matter:

```markdown
---
title: Отчёт о тестировании
created: 2026-05-16 10:00
updated: 2026-05-16 12:00
tags: [pentest, web]
obsidian_tags: #pentest #web
---

# Заголовок
...
```

### 8. Настройка прокси

Vite настроен для проксирования API запросов на бэкенд:

```javascript
// vite.config.js
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:5000',
      changeOrigin: true,
    },
  },
}
```

## Установка и запуск

```bash
cd /workspace/frontend-spa
npm install
npm run dev
```

Приложение доступно по адресу http://localhost:3000

## Сборка для продакшена

```bash
npm run build
```

Файлы будут в `dist/`. Для интеграции с FastAPI нужно настроить раздачу статики.

## Ответы на требования пользователя

### 1. Хранение информации о CTF машинах
Реализована модель `CTFMachine` и API endpoints. В интерфейсе создана вкладка "CTF" с заготовкой для функционала.

### 2. Git синхронизация
Создана модель `ProjectGitSync` и API методы. В интерфейсе есть вкладка "Git".

### 3. Поддержка различных типов файлов
Артефакты разделены на типы (file, screenshot, log, export, evidence). Файлы хранятся на диске, метаданные - в БД.

### 4. Markdown редактор
Интегрирован `@uiw/react-md-editor` - полноценный редактор с предпросмотром на базе CodeMirror.

### 5. Экспорт активов
Отложен по запросу пользователя.

### 6. Переиспользование активов и групп
Код моделей и API для активов/групп сохраняется. В проекте есть связь Many-to-Many с группами.

### 7. SPA на React
Полностью реализовано SPA приложение с роутингом, управлением состоянием и компонентным подходом.

## Следующие шаги

1. Установить зависимости: `npm install`
2. Протестировать работу с бэкендом
3. Добавить недостающий функционал (сессии, CTF, Git sync)
4. Интегрировать собранное приложение с FastAPI
5. Мигрировать остальные страницы на React
