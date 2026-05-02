// static/js/dashboard-page.js
import { store } from './store.js';
import { Utils } from './modules/utils.js';
import { AssetManager } from './modules/assets.js';
import { FilterAutocompleteManager } from './filter-helpers.js';
import { treeManager, refreshGroupTree } from './modules/tree.js';
import { GroupManager } from './modules/groups.js';

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
    
    this.assetManager = new AssetManager('table-body');
    this.filterAutocomplete = new FilterAutocompleteManager();
    this.groupManager = new GroupManager();
    
    this.#init();
  }

  async #init() {
    this.#loadStateFromURL();
    this.#setupEventListeners();
    
    // Инициализация дерева групп и загрузка данных
    await refreshGroupTree();
    
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
        // Явно вызываем applyFilters после загрузки
        this.allAssets = assets;
        this.applyFilters();
      } catch (error) {
        console.error('Failed to load assets:', error);
        Utils.showNotification('Не удалось загрузить активы', 'danger');
      }
    } else {
      // Если активы уже есть в store, инициализируем их
      this.allAssets = store.getState('assets');
      this.applyFilters();
    }
  }

  #setupEventListeners() {
    // Инициализация автодополнения для фильтра
    const filterInput = document.getElementById('asset-filter');
    if (filterInput) {
      this.filterAutocomplete.init(filterInput);
    }

    // Кнопка проверки фильтра
    document.getElementById('btn-check-filter')?.addEventListener('click', () => this.#validateFilter());

    // Поиск
    filterInput?.addEventListener('input', (e) => {
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
      this.visibleColumns = Array.from(e.target.selectedOptions).map(opt => opt.value);
      this.applyFilters();
    });

    // Кнопки фильтров
    document.getElementById('btn-apply-filters')?.addEventListener('click', () => this.applyFilters());
    document.getElementById('btn-reset-filters')?.addEventListener('click', () => this.resetFilters());

    // Toolbar кнопки
    document.getElementById('btn-clear-selection')?.addEventListener('click', () => store.clearSelectedAssets());
    document.getElementById('btn-bulk-move')?.addEventListener('click', () => this.#confirmBulkMove());
    document.getElementById('btn-bulk-delete')?.addEventListener('click', () => this.#confirmBulkDelete());

    // Кнопки экспорта
    document.getElementById('btn-export-csv-current')?.addEventListener('click', () => this.exportData('csv', true));
    document.getElementById('btn-export-json-current')?.addEventListener('click', () => this.exportData('json', true));
    document.getElementById('btn-export-csv-full')?.addEventListener('click', () => this.exportData('csv', false));
    document.getElementById('btn-export-json-full')?.addEventListener('click', () => this.exportData('json', false));

    // Тема уже управляется через ThemeController в main.js

    // Делегирование событий для таблицы
    document.querySelector('#assets-table tbody')?.addEventListener('click', (e) => {
      const deleteBtn = e.target.closest('.btn-delete-asset');
      if (deleteBtn) {
        const assetId = deleteBtn.dataset.assetId;
        if (assetId) this.deleteAsset(assetId);
      }
      
      // Обработка чекбоксов
      const checkbox = e.target.closest('input[type="checkbox"].asset-checkbox');
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

    if (this.currentGrouping === 'none') {
      this.#renderTable();
    } else {
      this.#renderGrouping();
    }
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
    
    // Скрыть результат валидации
    const validationDiv = document.getElementById('filter-validation-result');
    if (validationDiv) validationDiv.style.display = 'none';
    
    this.#updateURL();
    this.applyFilters();
  }

  /**
   * Валидация синтаксиса фильтра с выводом результата
   */
  #validateFilter() {
    const filterInput = document.getElementById('asset-filter');
    const validationDiv = document.getElementById('filter-validation-result');
    const query = filterInput?.value.trim();

    if (!validationDiv) return;

    if (!query) {
      validationDiv.innerHTML = '<span class="text-muted">Введите запрос для проверки</span>';
      validationDiv.style.display = 'block';
      return;
    }

    // Простая валидация синтаксиса
    const errors = [];
    const parts = query.split(/,\s*/);

    for (const part of parts) {
      if (!part.trim()) continue;
      
      // Проверка наличия оператора
      const hasOperator = /[=:!<>]|like|contains|in|not_in/.test(part);
      if (!hasOperator) {
        errors.push(`"${part}" - отсутствует оператор (=, !=, like, contains, >, <, in)`);
        continue;
      }

      // Проверка формата "поле:оператор:значение" или "поле=значение"
      const match = part.match(/^([a-zA-Z_]+)\s*(=|!=|:|like|contains|>|<|in|not_in)?\s*(.*)$/i);
      if (!match) {
        errors.push(`"${part}" - неверный формат`);
      } else {
        const fieldName = match[1].toLowerCase();
        const knownFields = ['ip', 'hostname', 'fqdn', 'os', 'type', 'status', 'group', 'port', 'dns_name', 'dns_record_type', 'owner', 'location'];
        
        // Подсказка если поле не найдено
        if (!knownFields.includes(fieldName) && !knownFields.some(f => f.startsWith(fieldName))) {
          errors.push(`Поле "${fieldName}" не найдено. Доступные: ${knownFields.join(', ')}`);
        }
      }
    }

    if (errors.length === 0) {
      validationDiv.innerHTML = '<span class="text-success"><i class="bi bi-check-circle"></i> Синтаксис корректен</span>';
      validationDiv.style.display = 'block';
    } else {
      validationDiv.innerHTML = `<span class="text-danger"><i class="bi bi-exclamation-triangle"></i> Ошибки:<br>${errors.map(e => `• ${e}`).join('<br>')}</span>`;
      validationDiv.style.display = 'block';
    }
  }

  async deleteAsset(id) {
    if (!confirm('Вы уверены, что хотите удалить этот актив?')) return;
    
    try {
      await Utils.apiRequest(`/api/assets/${id}`, { method: 'DELETE' });
      Utils.showNotification('Актив удален', 'success');
      
      // Полная перезагрузка данных с сервера для синхронизации
      await this.#reloadData();
      
      // Принудительно обновляем отображение
      this.applyFilters();
    } catch (err) {
      console.error('Delete failed:', err);
      Utils.showNotification('Ошибка удаления: ' + (err.message), 'danger');
    }
  }

  async #reloadData() {
    try {
      const assets = await Utils.apiRequest('/api/assets');
      store.setState('assets', assets);
      // Обновление дерева групп
      await refreshGroupTree();
      // Явно вызываем applyFilters после обновления данных
      this.allAssets = assets;
    } catch (error) {
      console.error('Failed to reload data:', error);
      Utils.showNotification('Не удалось обновить данные', 'danger');
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
      
      // Полная перезагрузка данных с сервера для синхронизации
      await this.#reloadData();
      
      // Принудительно обновляем отображение
      this.applyFilters();
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

  exportData(format, filteredOnly = true) {
    const dataToExport = filteredOnly ? this.filteredAssets : this.allAssets;
    
    if (!dataToExport?.length) {
      Utils.showNotification('Нет данных для экспорта', 'warning');
      return;
    }

    let content = '';
    let mimeType = '';
    let extension = '';

    if (format === 'csv') {
      // Для CSV экспортируем только видимые колонки + ID
      const headers = ['ID', ...this.visibleColumns];
      content = headers.join(',') + '\n';
      
      dataToExport.forEach(asset => {
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
      
      mimeType = 'text/csv;charset=utf-8;';
      extension = 'csv';
    } else if (format === 'json') {
      // Для JSON экспортируем все данные актива целиком
      content = JSON.stringify(dataToExport, null, 2);
      mimeType = 'application/json;charset=utf-8;';
      extension = 'json';
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const timestamp = new Date().toISOString().slice(0,19).replace(/[:T]/g, '-');
    a.download = `assets_export_${timestamp}.${extension}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    Utils.showNotification(`Экспорт выполнен: ${dataToExport.length} записей`, 'success');
  }
}

// Инициализация контроллера при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
  window.dashboardController = new DashboardController();
});