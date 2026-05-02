// static/js/dashboard-page.js
import { store } from './store.js';
import { Utils } from './modules/utils.js';
import { AssetManager } from './modules/assets.js';

/**
 * Контроллер страницы дашборда.
 * Управляет фильтрацией, группировкой, экспортом и отображением активов.
 */
export class DashboardController {
  constructor() {
    this.allAssets = [];
    this.filteredAssets = [];
    this.currentGrouping = 'none';
    this.visibleColumns = ['ip_address', 'hostname', 'os_name', 'status', 'device_type', 'open_ports', 'source'];
    this.searchQuery = '';
    
    this.assetManager = new AssetManager('assets-table');
    
    this.#init();
  }

  async #init() {
    this.#loadStateFromURL();
    this.#setupEventListeners();
    
    // Подписка на обновления активов из Store
    store.subscribe('assets', (assets) => {
      this.allAssets = assets;
      this.applyFilters();
    });

    // Начальная загрузка данных (если еще не загружены в Store)
    if (!store.getState('assets')?.length) {
      try {
        const assets = await Utils.apiRequest('/api/assets');
        store.setState('assets', assets);
      } catch (error) {
        console.error('Failed to load assets:', error);
        Utils.showNotification('Не удалось загрузить активы', 'danger');
      }
    }
  }

  #setupEventListeners() {
    // Поиск
    document.getElementById('asset-filter')?.addEventListener('input', (e) => {
      this.searchQuery = e.target.value.trim();
      this.#updateURL();
      this.applyFilters();
    });

    // Группировка
    document.getElementById('group-by-select')?.addEventListener('change', (e) => {
      this.currentGrouping = e.target.value;
      this.#updateURL();
      this.applyFilters();
    });

    // Выбор колонок
    document.getElementById('columns-select')?.addEventListener('change', (e) => {
      this.visibleColumns = Array.from(e.selectedOptions).map(opt => opt.value);
      this.applyFilters();
    });

    // Кнопки фильтров
    document.getElementById('btn-apply-filters')?.addEventListener('click', () => this.applyFilters());
    document.getElementById('btn-reset-filters')?.addEventListener('click', () => this.resetFilters());

    // Toolbar кнопки
    document.getElementById('btn-clear-selection')?.addEventListener('click', () => store.clearSelectedAssets());
    document.getElementById('btn-bulk-move')?.addEventListener('click', () => this.#confirmBulkMove());
    document.getElementById('btn-bulk-delete')?.addEventListener('click', () => this.#confirmBulkDelete());

    // Тема уже управляется через ThemeController в main.js
    document.getElementById('btn-add-asset')?.addEventListener('click', () => this.#showAssetModal(null));

    // Делегирование событий для таблицы
    document.querySelector('#assets-table tbody')?.addEventListener('click', (e) => {
      const deleteBtn = e.target.closest('.btn-delete-asset');
      if (deleteBtn) {
        const assetId = deleteBtn.dataset.assetId;
        if (assetId) this.deleteAsset(assetId);
      }
      
      // Обработка чекбоксов
      const checkbox = e.target.closest('input[type="checkbox"].asset-select');
      if (checkbox) {
        store.toggleAssetSelection(checkbox.value);
      }
    });
  }

  applyFilters() {
    // Фильтрация по поиску
    if (!this.searchQuery) {
      this.filteredAssets = [...this.allAssets];
    } else {
      const queryLower = this.searchQuery.toLowerCase();
      this.filteredAssets = this.allAssets.filter(asset => {
        return Object.values(asset).some(val => {
          if (val === null || val === undefined) return false;
          if (typeof val === 'string') return val.toLowerCase().includes(queryLower);
          if (Array.isArray(val)) return val.some(v => String(v).toLowerCase().includes(queryLower));
          return false;
        });
      });
    }

    this.#renderTable();
    this.#renderGrouping();
  }

  #renderTable() {
    this.assetManager.render(this.filteredAssets, this.visibleColumns);
  }

  #renderGrouping() {
    if (this.currentGrouping === 'none') return;

    const tableBody = document.querySelector('#assets-table tbody');
    if (!tableBody) return;

    const groups = {};
    this.filteredAssets.forEach(asset => {
      let key = 'Unknown';
      if (this.currentGrouping === 'group') {
        const assetGroups = asset.groups || [];
        key = assetGroups.length > 0 ? assetGroups[0] : 'Без группы';
      } else if (['os_name', 'os_family', 'status', 'device_type'].includes(this.currentGrouping)) {
        // Для os_name используем приоритет: os_name > os_family
        if (this.currentGrouping === 'os_name') {
          key = asset.os_name || (asset.os_family ? `${asset.os_family} ${asset.os_version || ''}`.trim() : 'Неизвестно');
        } else {
          key = asset[this.currentGrouping] || 'Неизвестно';
        }
      }

      if (!groups[key]) groups[key] = [];
      groups[key].push(asset);
    });

    tableBody.innerHTML = '';
    
    Object.keys(groups).sort().forEach(groupName => {
      const trGroup = document.createElement('tr');
      trGroup.className = 'table-active';
      trGroup.innerHTML = `<td colspan="100"><strong>${groupName}</strong> <span class="badge bg-secondary">${groups[groupName].length}</span></td>`;
      tableBody.appendChild(trGroup);

      groups[groupName].forEach(asset => {
        const tr = this.assetManager.createRow(asset, this.visibleColumns);
        tableBody.appendChild(tr);
      });
    });
  }

  resetFilters() {
    this.searchQuery = '';
    this.currentGrouping = 'none';
    
    const filterInput = document.getElementById('asset-filter');
    const groupSelect = document.getElementById('group-by-select');
    
    if (filterInput) filterInput.value = '';
    if (groupSelect) groupSelect.value = 'none';
    
    this.#updateURL();
    this.applyFilters();
  }

  async deleteAsset(id) {
    if (!confirm('Вы уверены, что хотите удалить этот актив?')) return;
    
    try {
      await Utils.apiRequest(`/api/assets/${id}`, { method: 'DELETE' });
      Utils.showNotification('Актив удален', 'success');
      
      // Обновляем список в Store
      const currentAssets = store.getState('assets');
      store.setState('assets', currentAssets.filter(a => a.id !== id));
    } catch (err) {
      console.error('Delete failed:', err);
      Utils.showNotification('Ошибка удаления: ' + (err.message), 'danger');
    }
  }

  #confirmBulkMove() {
    const ids = store.getSelectedAssets();
    if (!ids.length) {
      Utils.showNotification('Выберите активы для перемещения', 'warning');
      return;
    }
    // Открытие модального окна перемещения
    // Реализация зависит от структуры модальных окон
    alert(`Переместить ${ids.length} активов (функционал в разработке)`);
  }

  #confirmBulkDelete() {
    const ids = store.getSelectedAssets();
    if (!ids.length) {
      Utils.showNotification('Выберите активы для удаления', 'warning');
      return;
    }
    
    if (!confirm(`Удалить выбранные активы (${ids.length})?`)) return;
    
    this.#executeBulkDelete(ids);
  }

  async #executeBulkDelete(ids) {
    try {
      await Utils.apiRequest('/api/assets/bulk-delete', {
        method: 'POST',
        body: JSON.stringify({ ids })
      });
      Utils.showNotification('Активы удалены', 'success');
      store.clearSelectedAssets();
      
      // Обновление списка
      const currentAssets = store.getState('assets');
      store.setState('assets', currentAssets.filter(a => !ids.includes(a.id)));
    } catch (err) {
      Utils.showNotification('Ошибка массового удаления: ' + err.message, 'danger');
    }
  }

  #showAssetModal(asset) {
    // Логика открытия модального окна создания/редактирования актива
    alert('Модальное окно актива (функционал в разработке)');
  }

  #loadStateFromURL() {
    const params = new URLSearchParams(window.location.search);
    
    const search = params.get('search');
    if (search) {
      this.searchQuery = search;
      const input = document.getElementById('asset-filter');
      if (input) input.value = search;
    }
    
    const group = params.get('group');
    if (group) {
      this.currentGrouping = group;
      const select = document.getElementById('group-by-select');
      if (select) select.value = group;
    }
  }

  #updateURL() {
    const params = new URLSearchParams();
    
    if (this.searchQuery) params.set('search', this.searchQuery);
    if (this.currentGrouping !== 'none') params.set('group', this.currentGrouping);
    
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', newUrl);
  }

  exportData(format) {
    if (!this.filteredAssets?.length) {
      Utils.showNotification('Нет данных для экспорта', 'warning');
      return;
    }

    let content = '';
    let mimeType = '';
    let extension = '';

    if (format === 'csv') {
      const headers = ['ID', ...this.visibleColumns];
      content = headers.join(',') + '\n';
      
      this.filteredAssets.forEach(asset => {
        const row = [asset.id];
        this.visibleColumns.forEach(col => {
          let val = asset[col];
          if (Array.isArray(val)) val = val.join('; ');
          if (val === null || val === undefined) val = '';
          val = String(val).replace(/"/g, '""');
          if (val.includes(',') || val.includes('\n')) {
            val = `"${val}"`;
          }
          row.push(val);
        });
        content += row.join(',') + '\n';
      });
      
      mimeType = 'text/csv';
      extension = 'csv';
    } else if (format === 'json') {
      content = JSON.stringify(this.filteredAssets, null, 2);
      mimeType = 'application/json';
      extension = 'json';
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `assets_export_${new Date().toISOString().slice(0,10)}.${extension}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}

// Инициализация контроллера при загрузке модуля
const dashboardController = new DashboardController();

// Экспорт для кнопок экспорта
document.getElementById('btn-export-csv-current')?.addEventListener('click', () => {
  dashboardController.exportData('csv');
});
document.getElementById('btn-export-json-current')?.addEventListener('click', () => {
  dashboardController.exportData('json');
});
document.getElementById('btn-export-csv-full')?.addEventListener('click', () => {
  // Для полного экспорта используем все активы
  dashboardController.allAssets = dashboardController.filteredAssets;
  dashboardController.exportData('csv');
});
document.getElementById('btn-export-json-full')?.addEventListener('click', () => {
  // Для полного экспорта используем все активы
  dashboardController.allAssets = dashboardController.filteredAssets;
  dashboardController.exportData('json');
});