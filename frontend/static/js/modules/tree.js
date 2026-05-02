/**
 * Модуль управления деревом групп и фильтрацией активов
 */
import { store } from '../store.js';
import { Utils } from './utils.js';

export class TreeManager {
  constructor() {
    this.currentGroupId = null;
    this.#initStaticListeners();
    this.#initUrlFiltering();
  }

  #initUrlFiltering() {
    const urlParams = new URLSearchParams(window.location.search);
    const groupIdParam = urlParams.get('group_id');
    const ungroupedParam = urlParams.get('ungrouped');

    if (ungroupedParam === 'true') {
      this.handleGroupClick('ungrouped');
    } else if (groupIdParam && groupIdParam !== 'all') {
      this.handleGroupClick(groupIdParam);
    }
  }

  /**
   * Отрисовка дерева групп внутри контейнера #sidebar-content (SPA подход)
   * @param {Array} groups - Массив объектов групп
   * @param {Object} counts - Объект счетчиков
   */
  renderTree(groups, counts) {
    const container = document.getElementById('sidebar-content');
    if (!container) {
      // Тихо пропускаем, если контейнер не найден (страница без сайдбара)
      return;
    }

    // Формируем полный HTML для рендеринга
    let html = `
      <div class="sidebar-section">
        <div class="d-flex justify-content-between align-items-center sidebar-section-title">
          <span>Группы активов</span>
          <button class="btn btn-sm btn-link p-0" id="btn-create-group" title="Создать группу">
            <i class="bi bi-plus-circle"></i>
          </button>
        </div>
        
        <div id="group-tree" class="group-tree">
          <!-- Статический элемент: Все активы -->
          <div class="tree-node active" data-id="all">
            <i class="bi bi-globe folder-icon"></i>
            <span class="group-name" data-id="all">Все активы</span>
            <span class="badge bg-primary ms-auto" id="count-all">${counts['all'] || 0}</span>
          </div>
          <!-- Статический элемент: Без группы -->
          <div class="tree-node" data-id="ungrouped" style="margin-top: 5px; border-top: 1px solid var(--bs-border-color); padding-top: 5px;">
            <i class="bi bi-inbox folder-icon"></i>
            <span class="group-name" data-id="ungrouped">Без группы</span>
            <span class="badge bg-secondary ms-auto" id="count-ungrouped">${counts['ungrouped'] || 0}</span>
          </div>

          <!-- Динамический контейнер для вложенных групп -->
          <div id="group-tree-root" style="padding-left: 0;">
    `;

    if (Array.isArray(groups)) {
      groups.forEach(group => {
        const el = this.#createNodeElement(group, group.depth || 0, counts);
        html += el.outerHTML;
      });
    }

    html += `
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;

    // Переназначаем обработчики для статических элементов после рендеринга
    this.#initStaticListeners();
    
    this.#updateCounts(counts);
  }

  /**
   * Создать HTML элемент узла дерева
   * @private
   */
  #createNodeElement(group, depth, counts) {
    const node = document.createElement('div');
    node.className = 'tree-node';
    node.dataset.id = group.id;
    node.style.paddingLeft = `${depth * 20}px`;

    const icon = document.createElement('i');
    icon.className = 'bi bi-folder folder-icon';
    node.appendChild(icon);

    const nameSpan = document.createElement('span');
    nameSpan.className = 'group-name';
    nameSpan.textContent = group.name;
    nameSpan.dataset.id = group.id;
    node.appendChild(nameSpan);

    const badge = document.createElement('span');
    badge.className = 'badge bg-secondary ms-auto';
    badge.id = `count-${group.id}`;
    badge.textContent = counts[group.id] !== undefined ? counts[group.id] : 0;
    node.appendChild(badge);

    return node;
  }

  /**
   * Обновить счетчики
   * @private
   */
  #updateCounts(counts) {
    let totalDirectCount = 0;
    store.getState('groups')?.forEach(g => {
      totalDirectCount += g.direct_count ?? g.count ?? 0;
    });
    totalDirectCount += counts?.ungrouped ?? 0;

    const allBadge = document.getElementById('count-all');
    if (allBadge) allBadge.textContent = totalDirectCount;

    const ungroupedBadge = document.getElementById('count-ungrouped');
    if (ungroupedBadge) ungroupedBadge.textContent = counts?.ungrouped ?? 0;
  }

  /**
   * Обработчик клика по группе
   * @param {string|number} groupId
   */
  handleGroupClick(groupId) {
    
    
    // Если мы не на главной странице (дашборде), перенаправляем туда
    const isDashboard = window.location.pathname === '/' || window.location.pathname === '/index.html';
    if (!isDashboard) {
      const params = new URLSearchParams();
      if (groupId === 'ungrouped') {
        params.set('ungrouped', 'true');
      } else if (groupId !== 'all') {
        params.set('group_id', String(groupId));
      }
      
      const url = params.toString() ? `/?${params.toString()}` : '/';
      
      window.location.href = url;
      return;
    }

    // Если мы уже на дашборде, фильтруем активы без перезагрузки
    const assetsBody = document.getElementById('assets-body');
    if (!assetsBody) {
      
      this.#updateActiveNode(groupId);
      return;
    }

    this.#updateActiveNode(groupId);
    this.filterByGroup(groupId);
  }

  /**
   * Обновить визуальное выделение активного узла
   * @private
   */
  #updateActiveNode(groupId) {
    document.querySelectorAll('.tree-node').forEach(n => n.classList.remove('active'));
    
    const targetElement = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    if (targetElement) {
      targetElement.classList.add('active');
    }
    
    this.currentGroupId = groupId;
  }

  /**
   * Инициализация обработчиков для статических элементов
   * @private
   */
  #initStaticListeners() {
    const initListener = (selector, groupId) => {
      const node = document.querySelector(selector);
      if (!node) return;

      const newNode = node.cloneNode(true);
      node.parentNode.replaceChild(newNode, node);
      
      newNode.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleGroupClick(groupId);
      });
    };

    initListener('.tree-node[data-id="all"]', 'all');
    initListener('.tree-node[data-id="ungrouped"]', 'ungrouped');

    // Инициализация массовых операций
    this.#initBulkActions();
  }

  /**
   * Инициализация кнопок массовых операций
   * @private
   */
  #initBulkActions() {
    const selectAllCheckbox = document.getElementById('select-all');
    const bulkToolbar = document.getElementById('bulk-toolbar');
    const selectedCountBadge = document.getElementById('selected-count');
    const btnClearSelection = document.getElementById('btn-clear-selection');
    const btnBulkMove = document.getElementById('btn-bulk-move');
    const btnBulkDelete = document.getElementById('btn-bulk-delete');

    if (!selectAllCheckbox || !bulkToolbar) return;

    // Обработчик "Выбрать все"
    selectAllCheckbox.addEventListener('change', (e) => {
      const isChecked = e.target.checked;
      const checkboxes = document.querySelectorAll('.asset-checkbox');
      checkboxes.forEach(cb => {
        cb.checked = isChecked;
      });
      this.#updateBulkToolbar();
    });

    // Делегирование событий для чекбоксов активов
    const tbody = document.getElementById('assets-body');
    if (tbody) {
      tbody.addEventListener('change', (e) => {
        if (e.target.classList.contains('asset-checkbox')) {
          this.#updateBulkToolbar();
        }
      });
    }

    // Кнопка "Снять выделение"
    if (btnClearSelection) {
      btnClearSelection.addEventListener('click', () => {
        const checkboxes = document.querySelectorAll('.asset-checkbox');
        checkboxes.forEach(cb => {
          cb.checked = false;
        });
        if (selectAllCheckbox) selectAllCheckbox.checked = false;
        this.#updateBulkToolbar();
      });
    }

    // Кнопка "В группу"
    if (btnBulkMove) {
      btnBulkMove.addEventListener('click', async () => {
        const selectedIds = this.#getSelectedAssetIds();
        if (selectedIds.length === 0) return;
        
        // TODO: Открыть модалку выбора группы
        alert(`Переместить ${selectedIds.length} активов в группу (функционал в разработке)`);
      });
    }

    // Кнопка "Удалить"
    if (btnBulkDelete) {
      btnBulkDelete.addEventListener('click', async () => {
        const selectedIds = this.#getSelectedAssetIds();
        if (selectedIds.length === 0) return;

        if (!confirm(`Вы уверены, что хотите удалить ${selectedIds.length} активов? Это действие нельзя отменить.`)) {
          return;
        }

        try {
          const response = await fetch('/api/assets/bulk-delete', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ ids: selectedIds }),
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Ошибка при удалении активов');
          }

          // Успешное удаление - перезагрузить список
          await this.loadAssets(this.currentGroupId, this.currentGroupId === null);
          
          // Сбросить выделение
          const checkboxes = document.querySelectorAll('.asset-checkbox');
          checkboxes.forEach(cb => {
            cb.checked = false;
          });
          if (selectAllCheckbox) selectAllCheckbox.checked = false;
          this.#updateBulkToolbar();

          // Показать уведомление
          Utils.showFlashMessage(`Удалено ${selectedIds.length} активов`, 'success');
        } catch (error) {
          console.error('[Bulk Delete] Ошибка:', error);
          Utils.showFlashMessage(`Ошибка: ${error.message}`, 'danger');
        }
      });
    }
  }

  /**
   * Обновление видимости и счетчика панели массовых операций
   * @private
   */
  #updateBulkToolbar() {
    const bulkToolbar = document.getElementById('bulk-toolbar');
    const selectedCountBadge = document.getElementById('selected-count');
    const selectAllCheckbox = document.getElementById('select-all');
    
    if (!bulkToolbar || !selectedCountBadge) return;

    const checkboxes = document.querySelectorAll('.asset-checkbox:checked');
    const count = checkboxes.length;

    selectedCountBadge.textContent = count;

    if (count > 0) {
      bulkToolbar.style.display = 'flex';
    } else {
      bulkToolbar.style.display = 'none';
    }

    // Обновить состояние чекбокса "Выбрать все"
    if (selectAllCheckbox) {
      const allCheckboxes = document.querySelectorAll('.asset-checkbox');
      const allChecked = allCheckboxes.length > 0 && allCheckboxes.length === count;
      selectAllCheckbox.checked = allChecked;
      selectAllCheckbox.indeterminate = count > 0 && count < allCheckboxes.length;
    }
  }

  /**
   * Получить массив ID выбранных активов
   * @private
   * @returns {number[]}
   */
  #getSelectedAssetIds() {
    const checkboxes = document.querySelectorAll('.asset-checkbox:checked');
    return Array.from(checkboxes).map(cb => parseInt(cb.dataset.id, 10));
  }

  /**
   * Фильтрация активов по группе
   * @param {string|number|null} groupId
   * @param {string|null} sourceFilter - Фильтр по источнику (manual, scanning, all)
   */
  filterByGroup(groupId, sourceFilter = null) {
    const tbody = document.getElementById('assets-body');
    if (!tbody) {
      console.warn(`Таблица не найдена. Пропускаем фильтрацию.`);
      return;
    }

    
    this.#updateActiveNode(groupId);

    if (groupId === 'ungrouped') {
      
      this.loadAssets(null, true, sourceFilter);
    } else if (groupId === 'all') {
      
      this.loadAssets(null, false, sourceFilter);
    } else {
      
      this.loadAssets(parseInt(groupId), false, sourceFilter);
    }
  }

  /**
   * Загрузка активов с сервера
   * @param {number|null} groupId
   * @param {boolean} isUngrouped
   * @param {string|null} sourceFilter - Фильтр по источнику (manual, scanning, all)
   */
  async loadAssets(groupId = null, isUngrouped = false, sourceFilter = null) {
    const tbody = document.getElementById('assets-body');
    if (!tbody) {
      console.error('[TreeManager] loadAssets: tbody не найден');
      return;
    }

    
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><p class="mt-2 text-muted">Загрузка...</p></td></tr>';

    const params = new URLSearchParams();
    
    if (isUngrouped) {
      params.append('ungrouped', 'true');
    } else if (groupId !== null && groupId !== 'all') {
      params.append('group_id', String(groupId));
    }
    
    // Добавляем фильтр по источнику
    if (sourceFilter && sourceFilter !== 'all') {
      params.append('source', sourceFilter);
    }

    const queryString = params.toString();
    const url = `/api/assets${queryString ? '?' + queryString : ''}`;
    
    

    try {
      const response = await Utils.apiRequest(url);
      
      
      const data = response;
      const assets = Array.isArray(data) ? data : (data.assets || []);

      tbody.innerHTML = '';

      if (assets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">Активы не найдены</td></tr>';
        store.setCurrentAssets([]);
        return;
      }

      assets.forEach(asset => {
        const tr = this.#createAssetRow(asset);
        tbody.appendChild(tr);
      });

      store.setCurrentAssets(assets);
      

    } catch (error) {
      console.error('[TreeManager] Ошибка загрузки активов:', error);
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4">Ошибка: ${error.message}</td></tr>`;
    }
  }

  /**
   * Создать строку таблицы актива
   * @private
   */
  #createAssetRow(asset) {
    const tr = document.createElement('tr');
    
    tr.innerHTML = `
      <td><input type="checkbox" class="form-check-input asset-checkbox" data-id="${asset.id}"></td>
      <td><strong>${asset.ip_address ?? 'N/A'}</strong></td>
      <td>${asset.hostname ?? '<span class="text-muted">-</span>'}</td>
      <td>${asset.os_info ?? '<span class="text-muted">-</span>'}</td>
      <td><small>${asset.open_ports ?? '<span class="text-muted">-</span>'}</small></td>
      <td>${asset.group_name ? `<span class="badge bg-light text-dark border">${asset.group_name}</span>` : '<span class="badge bg-secondary">Без группы</span>'}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-primary edit-asset-btn" data-id="${asset.id}" title="Редактировать">
          <i class="bi bi-pencil"></i>
        </button>
      </td>
    `;
    
    tr.style.cursor = 'pointer';
    tr.addEventListener('click', (e) => {
      // Игнорируем клики по чекбоксам и кнопкам
      if (e.target.closest('button') || e.target.closest('input[type="checkbox"]')) return;
      window.location.href = `/asset/view/${asset.id}`;
    });

    // Обработчик для чекбокса - предотвращаем всплытие
    const checkbox = tr.querySelector('.asset-checkbox');
    if (checkbox) {
      checkbox.addEventListener('click', (e) => {
        e.stopPropagation();
      });
    }

    const editBtn = tr.querySelector('.edit-asset-btn');
    if (editBtn) {
      editBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const { showAssetModal } = await import('./index.js');
        showAssetModal(asset.id);
      });
    }

    return tr;
  }

  /**
   * Публичный метод обновления дерева
   */
  async refresh() {
    try {
      const data = await Utils.apiRequest('/api/groups/tree');
      
      let groups = [];
      let counts = {};

      if (data.flat && Array.isArray(data.flat)) {
        groups = data.flat;
        groups.forEach(g => {
          counts[g.id] = g.direct_count ?? g.count ?? g.asset_count ?? 0;
        });
        counts.ungrouped = data.ungrouped_count ?? 0;
      } else if (Array.isArray(data)) {
        groups = data;
      } else if (data.groups) {
        groups = data.groups;
        counts = data.counts ?? {};
      }

      store.setState('groups', groups);
      this.renderTree(groups, counts);
      
    } catch (err) {
      console.error('Ошибка обновления дерева:', err);
    }
  }
  /**
   * Применение пользовательских фильтров
   * @param {Array} rules - Массив правил фильтрации
   */
  applyCustomFilters(rules) {
    
    // Фильтрация происходит на стороне клиента в main.js
    // Этот метод может быть использован для дополнительной логики
  }

  /**
   * Очистка всех фильтров
   */
  clearFilters() {
    
    // Сброс фильтров и загрузка всех активов текущей группы
    this.filterByGroup(this.currentGroupId || 'all');
  }
}

// Экспорт экземпляра по умолчанию
export const treeManager = new TreeManager();

// Экспорт отдельных методов для использования в других модулях
export const filterByGroup = (groupId, sourceFilter = null) => treeManager.filterByGroup(groupId, sourceFilter);
export const loadAssets = (groupId = null, isUngrouped = false, sourceFilter = null) => treeManager.loadAssets(groupId, isUngrouped, sourceFilter);
export const refreshGroupTree = () => treeManager.refresh();

// Обработчик кнопки импорта сканирования
document.addEventListener('DOMContentLoaded', function() {
    const importBtn = document.getElementById('importScanBtn');
    if (importBtn) {
        importBtn.addEventListener('click', function() {
            // Модалка открывается автоматически через data-bs-toggle, 
            // здесь можно добавить дополнительную логику если нужно
            console.log('Import scan button clicked');
        });
    }
});
