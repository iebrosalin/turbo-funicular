/**
 * Модуль управления деревом групп и фильтрацией активов
 */
import { store } from '../store.js';
import { filterByGroup as filterAssets } from './assets.js';

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
   * Отрисовка дерева групп внутри контейнера #group-tree-root
   * @param {Array} groups - Массив объектов групп
   * @param {Object} counts - Объект счетчиков
   */
  renderTree(groups, counts) {
    const container = document.getElementById('group-tree-root');
    if (!container) {
      console.error('Контейнер #group-tree-root не найден');
      return;
    }

    container.innerHTML = '';

    if (Array.isArray(groups)) {
      groups.forEach(group => {
        const el = this.#createNodeElement(group, group.depth || 0, counts);
        container.appendChild(el);
        
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          this.handleGroupClick(group.id);
        });
      });
    }
    
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
    const assetsBody = document.getElementById('assets-body');
    if (!assetsBody) {
      console.log('Таблица активов не найдена. Пропускаем загрузку.');
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
  }

  /**
   * Фильтрация активов по группе
   * @param {string|number|null} groupId
   */
  filterByGroup(groupId) {
    const tbody = document.getElementById('assets-body');
    if (!tbody) {
      console.warn(`Таблица не найдена. Пропускаем фильтрацию.`);
      return;
    }

    this.#updateActiveNode(groupId);

    if (groupId === 'ungrouped') {
      this.loadAssets(null, true);
    } else if (groupId === 'all') {
      this.loadAssets(null, false);
    } else {
      this.loadAssets(parseInt(groupId), false);
    }
  }

  /**
   * Загрузка активов с сервера
   * @param {number|null} groupId
   * @param {boolean} isUngrouped
   */
  async loadAssets(groupId = null, isUngrouped = false) {
    const tbody = document.getElementById('assets-body');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><p class="mt-2 text-muted">Загрузка...</p></td></tr>';

    const params = new URLSearchParams();
    
    if (isUngrouped) {
      params.append('ungrouped', 'true');
      params.append('group_id', 'null'); 
    } else if (groupId !== null && groupId !== 'all') {
      params.append('group_id', String(groupId));
    }

    const queryString = params.toString();
    const url = `/api/assets${queryString ? '?' + queryString : ''}`;

    try {
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Ошибка сервера: ${response.status}`);
      }

      const data = await response.json();
      const assets = Array.isArray(data) ? data : (data.assets || []);

      tbody.innerHTML = '';

      if (assets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">Активы не найдены</td></tr>';
        store.updateAssets([]);
        return;
      }

      assets.forEach(asset => {
        const tr = this.#createAssetRow(asset);
        tbody.appendChild(tr);
      });

      store.updateAssets(assets);

    } catch (error) {
      console.error('Ошибка загрузки активов:', error);
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
      if (e.target.closest('button')) return;
      window.location.href = `/asset/${asset.id}`;
    });

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
      const response = await fetch('/api/groups/tree');
      if (!response.ok) throw new Error('Network response was not ok');
      
      const data = await response.json();
      
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
}

// Экспорт экземпляра по умолчанию
export const treeManager = new TreeManager();
