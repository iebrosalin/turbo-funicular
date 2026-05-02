// static/js/main.js
import { store, treeManager, assetManager, groupManager, scanManager, themeController } from './modules/index.js';
import { FilterBuilder } from './filter-builder.js';
import { Utils } from './modules/utils.js';

class App {
  constructor() {
    this.isResizing = false;
  }

  async init() {
    try {
      // Тема инициализируется автоматически при создании экземпляра ThemeController

      // Инициализация менеджеров
      await this.#initManagers();

      // Настройка UI компонентов
      this.#initUIComponents();

      // Загрузка начальных данных
      await this.#loadInitialData();

      // Загрузка списка активов в сайдбар (для всех страниц)
      await this.#loadSidebarAssets();

      // Обработка URL параметров
      this.#handleURLParams();

      // Горячие клавиши
      this.#initHotkeys();

      
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
    
    if (resizer && sidebar) {
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
    }

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
    
    // Обработчик формы актива удалён - ручное добавление активов отключено

    // Инициализация конструктора фильтров
    this.#initFilterBuilder();
  }

  async #loadInitialData() {
    try {
      // Проверяем, находимся ли мы на странице сканирований (или другой странице с сайдбаром)
      const treeContainer = document.getElementById('sidebar-content');
      
      console.log('[DEBUG] #loadInitialData вызван');
      console.log('[DEBUG] Текущий путь:', window.location.pathname);
      console.log('[DEBUG] Элемент #sidebar-content найден:', !!treeContainer);
      
      if (treeContainer) {
        console.log('[DEBUG] Содержимое контейнера перед refresh:', treeContainer.innerHTML ? treeContainer.innerHTML.substring(0, 150) + '...' : '(пусто)');
        console.log('[DEBUG] Вызов treeManager.refresh()...');
        
        // Загружаем данные и рендерим дерево
        await treeManager.refresh();
        
        console.log('[DEBUG] treeManager.refresh() завершен');
        console.log('[DEBUG] Содержимое контейнера после refresh:', treeContainer.innerHTML ? treeContainer.innerHTML.substring(0, 150) + '...' : '(пусто)');
      } else {
        console.log('[INFO] Контейнер #sidebar-content не найден. Проверьте HTML шаблон.');
        console.log('[DEBUG] Доступные элементы в DOM:', Array.from(document.querySelectorAll('[id]')).map(el => el.id).join(', '));
      }
      
      // SSE подключение уже установлено в конструкторе ScanManager
    } catch (err) {
      console.error('[ERROR] Ошибка загрузки начальных данных:', err);
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

  async #loadSidebarAssets() {
    const sidebarContainer = document.getElementById('sidebar-assets-list');
    if (!sidebarContainer) return;

    try {
      const assets = await Utils.apiRequest('/api/assets?limit=100');
      
      if (!assets || assets.length === 0) {
        sidebarContainer.innerHTML = `
          <div class="list-group-item text-muted small">
            Активы не найдены
          </div>
        `;
        return;
      }

      let html = '';
      assets.forEach(asset => {
        const statusClass = asset.status === 'active' ? 'text-success' : 'text-secondary';
        const statusIcon = asset.status === 'active' ? 'bi-circle-fill' : 'bi-circle';
        html += `
          <a href="/assets/${asset.id}" class="list-group-item list-group-item-action small py-2">
            <i class="bi ${statusIcon} me-2 ${statusClass}" style="font-size: 0.6rem;"></i>
            <strong>${asset.ip_address}</strong>
            ${asset.hostname ? `<br><span class="text-muted" style="font-size: 0.85rem;">${asset.hostname}</span>` : ''}
          </a>
        `;
      });

      sidebarContainer.innerHTML = html;
    } catch (error) {
      console.error('[Sidebar] Ошибка загрузки активов:', error);
      sidebarContainer.innerHTML = `
        <div class="list-group-item text-danger small">
          <i class="bi bi-exclamation-triangle me-2"></i>
          Ошибка загрузки
        </div>
      `;
    }
  }

  #initFilterBuilder() {
    const filterRoot = document.getElementById('filter-root');
    const btnApply = document.getElementById('btn-apply-filters');
    const btnReset = document.getElementById('btn-reset-filters');
    
    if (!filterRoot) return;

    // Используем единый класс FilterBuilder
    this.dashboardFilterBuilder = new FilterBuilder('filter-root', {
      mode: 'dashboard',
      onApply: (rules) => {
        this.filterRules = rules;
        
        
        // Применяем фильтры через treeManager
        if (treeManager && typeof treeManager.applyCustomFilters === 'function') {
          treeManager.applyCustomFilters(rules);
        } else {
          // Резервная логика - фильтрация на клиенте
          if (assetManager && typeof assetManager.render === 'function') {
            const allAssets = store.getState('assets') || [];
            const filtered = allAssets.filter(asset => {
              return rules.every(rule => {
                const assetValue = asset[rule.field];
                if (assetValue === null || assetValue === undefined) return false;
                
                const strValue = Array.isArray(assetValue) ? assetValue.join(' ') : String(assetValue);
                
                switch (rule.operation) {
                  case 'eq': return strValue === rule.value;
                  case 'neq': return strValue !== rule.value;
                  case 'contains': return strValue.toLowerCase().includes(rule.value.toLowerCase());
                  case 'in': return rule.value.split(',').map(v => v.trim()).some(v => strValue.includes(v));
                  default: return true;
                }
              });
            });
            
            assetManager.render(filtered, ['ip_address', 'hostname', 'os_name', 'status', 'device_type']);
          }
        }
      },
      initialRules: []
    });
  }
}

// Запуск приложения
document.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init();
});