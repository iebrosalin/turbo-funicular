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
    
    // Загрузка схемы активов для динамического заполнения опций группировки
    await this.#loadAssetSchema();
    
    // Подписка на обновления активов из Store
    store.subscribe('assets', (assets) => {
      this.allAssets = assets;
      this.applyFilters();
    });

    // Начальная загрузка данных (если еще не загружены в Store)
    if (!store.getState('assets')?.length) {
      try {
        // Загружаем активы с таксономией для экспорта
        const assets = await Utils.apiRequest('/api/assets?include_taxonomy=true');
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
  
  /**
   * Загрузка схемы активов для заполнения опций группировки
   */
  async #loadAssetSchema() {
    try {
      const schema = await Utils.apiRequest('/api/assets/schema');
      const groupSelect = document.getElementById('group-by-select');
      if (groupSelect && schema.schema) {
        // Очищаем все кроме базовых опций
        const baseOptions = Array.from(groupSelect.options).slice(0, 2);
        groupSelect.innerHTML = '';
        baseOptions.forEach(opt => groupSelect.appendChild(opt));
        
        // Добавляем опции для каждого поля
        schema.schema.forEach(field => {
          const option = document.createElement('option');
          option.value = field.field;
          option.textContent = `По ${field.label}`;
          groupSelect.appendChild(option);
        });
      }
    } catch (error) {
      console.error('Failed to load asset schema:', error);
    }
  }

  #setupEventListeners() {
    // Инициализация автодополнения для фильтра (теперь async)
    const filterInput = document.getElementById('asset-filter');
    if (filterInput) {
      this.filterAutocomplete.init(filterInput);  // init теперь async, но вызываем без await т.к. не блокирует
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
      const selectedOptions = Array.from(e.target.options).filter(opt => opt.selected);
      this.visibleColumns = selectedOptions.map(opt => opt.value);
      this.applyFilters();
    });

    // Кнопки фильтров
    document.getElementById('btn-apply-filters')?.addEventListener('click', () => this.applyFilters());
    document.getElementById('btn-reset-filters')?.addEventListener('click', () => this.resetFilters());

    // Toolbar кнопки
    document.getElementById('btn-clear-selection')?.addEventListener('click', () => store.clearSelectedAssets());
    document.getElementById('btn-bulk-move')?.addEventListener('click', () => this.#confirmBulkMove());
    document.getElementById('btn-bulk-delete')?.addEventListener('click', () => this.#confirmBulkDelete());
    
    // Кнопка выполнения массового перемещения в модальном окне
    document.getElementById('btn-execute-bulk-move')?.addEventListener('click', () => {
      const moveBtn = document.getElementById('btn-execute-bulk-move');
      const ids = JSON.parse(moveBtn.dataset.assetIds || '[]');
      const targetGroupId = document.getElementById('target-group-select').value;
      this.#executeBulkMove(ids, targetGroupId);
    });

    // Кнопка выполнения массового удаления в модальном окне
    document.getElementById('btn-execute-bulk-delete')?.addEventListener('click', () => {
      const deleteBtn = document.getElementById('btn-execute-bulk-delete');
      const ids = JSON.parse(deleteBtn.dataset.assetIds || '[]');
      this.#executeBulkDelete(ids);
    });

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
      
      // Обработка кнопки перемещения актива в другую группу
      const moveBtn = e.target.closest('.btn-move-asset');
      if (moveBtn) {
        const assetId = moveBtn.dataset.assetId;
        if (assetId) this.#confirmSingleMove(assetId);
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

    // Обновляем шапку таблицы при группировке
    this.assetManager.renderHeader(this.visibleColumns);

    const tableBody = document.querySelector('#assets-table tbody');
    if (!tableBody) return;

    const groups = {};
    this.filteredAssets.forEach(asset => {
      let key = 'Unknown';
      
      // Группировка по любому полю актива
      if (this.currentGrouping === 'group') {
        const assetGroups = asset.groups || [];
        key = assetGroups.length > 0 ? assetGroups[0] : 'Без группы';
      } else if (asset.hasOwnProperty(this.currentGrouping)) {
        // Динамическая группировка по любому полю актива
        const value = asset[this.currentGrouping];
        if (value === null || value === undefined) {
          key = 'Неизвестно';
        } else if (Array.isArray(value)) {
          key = value.length > 0 ? value.join(', ') : 'Неизвестно';
        } else {
          key = String(value);
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

  async #confirmBulkMove() {
    const ids = store.getSelectedAssets();
    if (!ids.length) {
      Utils.showNotification('Выберите активы для перемещения', 'warning');
      return;
    }
    
    try {
      // Загружаем список групп
      const groups = await Utils.apiRequest('/api/groups/tree');
      
      // Заполняем селект группами
      const select = document.getElementById('target-group-select');
      select.innerHTML = '<option value="">-- Без группы --</option>';
      
      function buildGroupOptions(groupList, level = 0) {
        groupList.forEach(group => {
          const indent = ' '.repeat(level * 2);
          const option = document.createElement('option');
          option.value = group.id;
          option.textContent = indent + (group.name || group.group_name);
          select.appendChild(option);
          
          if (group.children && group.children.length > 0) {
            buildGroupOptions(group.children, level + 1);
          }
        });
      }
      
      buildGroupOptions(groups);
      
      // Обновляем счетчик
      document.getElementById('bulk-move-count').textContent = ids.length;
      
      // Открываем модальное окно
      const modal = new bootstrap.Modal(document.getElementById('bulkMoveModal'));
      modal.show();
      
      // Сохраняем IDs в data-атрибут кнопки
      const moveBtn = document.getElementById('btn-execute-bulk-move');
      moveBtn.dataset.assetIds = JSON.stringify(ids);
      
    } catch (err) {
      Utils.showNotification('Ошибка загрузки групп: ' + err.message, 'danger');
    }
  }
  
  /**
   * Подтверждение перемещения одного актива в другую группу
   */
  async #confirmSingleMove(assetId) {
    try {
      // Загружаем список групп
      const groups = await Utils.apiRequest('/api/groups/tree');
      
      // Заполняем селект группами
      const select = document.getElementById('target-group-select');
      select.innerHTML = '<option value="">-- Без группы --</option>';
      
      function buildGroupOptions(groupList, level = 0) {
        groupList.forEach(group => {
          const indent = ' '.repeat(level * 2);
          const option = document.createElement('option');
          option.value = group.id;
          option.textContent = indent + (group.name || group.group_name);
          select.appendChild(option);
          
          if (group.children && group.children.length > 0) {
            buildGroupOptions(group.children, level + 1);
          }
        });
      }
      
      buildGroupOptions(groups);
      
      // Обновляем счетчик
      document.getElementById('bulk-move-count').textContent = '1';
      
      // Открываем модальное окно
      const modal = new bootstrap.Modal(document.getElementById('bulkMoveModal'));
      modal.show();
      
      // Сохраняем ID актива в data-атрибут кнопки
      const moveBtn = document.getElementById('btn-execute-bulk-move');
      moveBtn.dataset.assetIds = JSON.stringify([assetId]);
      
    } catch (err) {
      Utils.showNotification('Ошибка загрузки групп: ' + err.message, 'danger');
    }
  }
  
  async #executeBulkMove(ids, targetGroupId) {
    try {
      await Utils.apiRequest('/api/assets/bulk-move', {
        method: 'POST',
        body: JSON.stringify({ 
          ids,
          group_id: targetGroupId === '' ? null : parseInt(targetGroupId)
        })
      });
      Utils.showNotification('Активы перемещены', 'success');
      store.clearSelectedAssets();
      
      // Закрываем модальное окно
      const modalEl = document.getElementById('bulkMoveModal');
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
      
      // Полная перезагрузка данных с сервера для синхронизации
      await this.#reloadData();
      
      // Принудительно обновляем отображение
      this.applyFilters();
    } catch (err) {
      Utils.showNotification('Ошибка массового перемещения: ' + err.message, 'danger');
    }
  }

  #confirmBulkDelete() {
    const ids = store.getSelectedAssets();
    if (!ids.length) {
      Utils.showNotification('Выберите активы для удаления', 'warning');
      return;
    }
    
    // Обновляем счетчик в модальном окне
    document.getElementById('bulk-delete-count').textContent = ids.length;
    
    // Сохраняем IDs в data-атрибут кнопки
    const deleteBtn = document.getElementById('btn-execute-bulk-delete');
    deleteBtn.dataset.assetIds = JSON.stringify(ids);
    
    // Открываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('bulkDeleteModal'));
    modal.show();
  }

  async #executeBulkDelete(ids) {
    try {
      await Utils.apiRequest('/api/assets/bulk-delete', {
        method: 'POST',
        body: JSON.stringify({ ids })
      });
      Utils.showNotification('Активы удалены', 'success');
      store.clearSelectedAssets();
      
      // Закрываем модальное окно
      const modalEl = document.getElementById('bulkDeleteModal');
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
      
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

  async exportData(format, filteredOnly = true) {
    // Определяем данные для экспорта
    const dataToExport = filteredOnly ? this.filteredAssets : this.allAssets;
    
    if (!dataToExport || dataToExport.length === 0) {
      Utils.showNotification('Нет данных для экспорта', 'warning');
      return;
    }

    let content = '';
    let mimeType = '';
    let extension = '';
    const timestamp = new Date().toISOString().slice(0,19).replace(/[:T]/g, '-');

    if (format === 'csv') {
      // Для CSV экспортируем только видимые колонки + поля таксономии
      const headers = [...this.visibleColumns];
      
      // Добавляем поля таксономии если они есть в данных
      if (dataToExport.length > 0 && dataToExport[0].taxonomy) {
        const taxonomyFields = Object.keys(dataToExport[0].taxonomy);
        taxonomyFields.forEach(field => {
          if (!headers.includes(`taxonomy_${field}`)) {
            headers.push(`taxonomy_${field}`);
          }
        });
      }
      
      const headerLabels = headers.map(col => {
        const header = col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        return `"${header}"`;
      });
      content = headerLabels.join(',') + '\n';
      
      dataToExport.forEach(asset => {
        const row = [];
        headers.forEach(col => {
          let val;
          if (col.startsWith('taxonomy_')) {
            const taxonomyField = col.replace('taxonomy_', '');
            val = asset.taxonomy ? asset.taxonomy[taxonomyField] : null;
          } else {
            val = asset[col];
          }
          
          if (Array.isArray(val)) val = val.join('; ');
          if (val === null || val === undefined) val = '';
          val = String(val).replace(/"/g, '""');
          if (val.includes(',') || val.includes('\n') || val.includes('"')) {
            val = `"${val}"`;
          }
          row.push(val);
        });
        content += row.join(',') + '\n';
      });
      
      mimeType = 'text/csv;charset=utf-8;';
      extension = 'csv';
    } else if (format === 'json') {
      // Для JSON экспортируем полные данные активов включая таксономию
      content = JSON.stringify(dataToExport, null, 2);
      mimeType = 'application/json;charset=utf-8;';
      extension = 'json';
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
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