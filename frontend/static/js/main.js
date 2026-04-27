// static/js/main.js
import { store, treeManager, assetManager, groupManager, scanService, themeController } from './modules/index.js';

class App {
  constructor() {
    this.isResizing = false;
  }

  async init() {
    try {
      // Инициализация темы
      themeController.init();

      // Инициализация менеджеров
      await this.#initManagers();

      // Настройка UI компонентов
      this.#initUIComponents();

      // Загрузка начальных данных
      await this.#loadInitialData();

      // Обработка URL параметров
      this.#handleURLParams();

      // Горячие клавиши
      this.#initHotkeys();

      console.log('✅ Приложение инициализировано');
    } catch (error) {
      console.error('❌ Ошибка инициализации приложения:', error);
    }
  }

  async #initManagers() {
    // Менеджеры уже созданы как синглтоны в своих модулях
    // treeManager, assetManager, groupManager, scanService
  }

  #initUIComponents() {
    // --- Логика изменения размера сайдбара ---
    const sidebar = document.getElementById('sidebar');
    const resizer = document.getElementById('sidebarResizer');
    
    if (!resizer) return;

    // Восстановление ширины из localStorage
    const savedWidth = localStorage.getItem('sidebarWidth');
    if (savedWidth) {
      document.documentElement.style.setProperty('--sidebar-width', savedWidth);
    }

    resizer.addEventListener('mousedown', (e) => {
      this.isResizing = true;
      resizer.classList.add('resizing');
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!this.isResizing) return;

      let newWidth = e.clientX;
      const minWidth = 200;
      const maxWidth = 600;
      
      if (newWidth < minWidth) newWidth = minWidth;
      if (newWidth > maxWidth) newWidth = maxWidth;

      document.documentElement.style.setProperty('--sidebar-width', `${newWidth}px`);
    });

    document.addEventListener('mouseup', () => {
      if (this.isResizing) {
        this.isResizing = false;
        resizer.classList.remove('resizing');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        
        const currentWidth = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width').trim();
        localStorage.setItem('sidebarWidth', currentWidth);
      }
    });

    // Переключение сайдбара на мобильных
    document.getElementById('sidebarCollapse')?.addEventListener('click', () => {
      document.getElementById('sidebar')?.classList.toggle('active');
      document.getElementById('content')?.classList.toggle('active');
    });

    // Обработчик формы группы
    const groupEditForm = document.getElementById('groupEditForm');
    if (groupEditForm) {
      groupEditForm.addEventListener('submit', (e) => {
        e.preventDefault();
        groupManager.saveGroup();
      });
    }

    // Обработчик формы перемещения группы
    const groupMoveForm = document.getElementById('groupMoveForm');
    if (groupMoveForm) {
      groupMoveForm.addEventListener('submit', (e) => {
        e.preventDefault();
        groupManager.moveGroup();
      });
    }
    
    // Обработчик формы актива
    const assetForm = document.getElementById('assetForm');
    if (assetForm) {
      assetForm.addEventListener('submit', (e) => {
        e.preventDefault();
        assetManager.saveAsset(e);
      });
    }
  }

  async #loadInitialData() {
    try {
      await treeManager.refresh();
      
      // Поллинг активных сканирований
      scanService.pollActiveScans();
      setInterval(() => scanService.pollActiveScans(), 5000);
    } catch (err) {
      console.error('Ошибка загрузки начальных данных:', err);
    }
  }

  #handleURLParams() {
    const urlParams = new URLSearchParams(window.location.search);
    const groupIdParam = urlParams.get('group_id');
    const ungroupedParam = urlParams.get('ungrouped');

    if (ungroupedParam === 'true') {
      treeManager.filterByGroup('ungrouped');
    } else if (groupIdParam && groupIdParam !== 'all') {
      treeManager.filterByGroup(groupIdParam);
    } else {
      treeManager.filterByGroup('all');
    }
  }

  #initHotkeys() {
    document.addEventListener('keydown', e => {
      if (e.ctrlKey && e.key === 'a' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
        e.preventDefault();
        document.querySelectorAll('#assets-body .asset-checkbox').forEach(cb => {
          cb.checked = true;
          const row = cb.closest('tr');
          if (row) row.classList.add('selected');
          store.toggleAssetSelection(cb.value);
        });
        
        const tb = document.getElementById('bulk-toolbar');
        if (tb) {
          const count = store.getSelectedAssets().length;
          tb.style.display = count > 0 ? 'flex' : 'none';
          const countEl = document.getElementById('selected-count');
          if (countEl) countEl.textContent = count;
        }
      }
    });
  }
}

// Запуск приложения
document.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init();
});