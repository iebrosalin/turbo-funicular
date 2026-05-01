// static/js/modules/assets.js
import { store } from './index.js';
import { Utils } from './utils.js';

export class AssetManager {
  constructor(targetTableId = 'assets-body') {
    this.targetTableId = targetTableId;
    this.tbody = document.getElementById(targetTableId);
    if (this.tbody) {
      this.#initListeners();
    }
  }

  #initListeners() {
    const selAll = document.getElementById('select-all');
    if (selAll) {
      selAll.addEventListener('change', () => this.#handleSelectAll(selAll));
    }

    this.tbody.addEventListener('change', e => {
      if (e.target.classList.contains('asset-checkbox')) {
        this.#handleCheckboxChange(e.target);
      }
    });

    this.tbody.addEventListener('click', e => {
      const row = e.target.closest('.asset-row');
      if (!row || e.target.closest('a, button, .asset-checkbox')) return;
      const cb = row.querySelector('.asset-checkbox');
      if (cb) {
        if (e.shiftKey && store.getLastSelectedIndex() >= 0) {
          e.preventDefault();
          this.#selectRange(store.getLastSelectedIndex(), this.#getRowIndex(row));
        } else {
          cb.checked = !cb.checked;
          this.#handleCheckboxChange(cb);
        }
      }
    });
  }

  /**
   * Отрисовка таблицы активов
   * @param {Array} assets - Массив активов
   * @param {Array} visibleColumns - Список видимых колонок
   */
  render(assets, visibleColumns) {
    console.log('[AssetManager] render called with', assets.length, 'assets');
    console.log('[AssetManager] visibleColumns:', visibleColumns);
    
    if (!this.tbody) {
      console.error('[AssetManager] tbody not found');
      return;
    }

    this.tbody.innerHTML = '';
    
    if (!assets || assets.length === 0) {
      this.tbody.innerHTML = '<tr><td colspan="100" class="text-center text-muted">Активы не найдены</td></tr>';
      return;
    }

    assets.forEach(asset => {
      const row = this.createRow(asset, visibleColumns);
      if (row) {
        this.tbody.appendChild(row);
      }
    });
    
    console.log('[AssetManager] rendered', this.tbody.querySelectorAll('tr').length, 'rows');
  }

  /**
   * Создание строки таблицы для актива
   * @param {Object} asset - Объект актива
   * @param {Array} visibleColumns - Список видимых колонок
   * @returns {HTMLTableRowElement}
   */
  createRow(asset, visibleColumns) {
    console.log('[AssetManager] createRow for asset:', asset);
    
    const tr = document.createElement('tr');
    tr.className = 'asset-row';
    tr.style.cursor = 'pointer';
    
    // Чекбокс выбора
    const tdCheckbox = document.createElement('td');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'form-check-input asset-checkbox';
    checkbox.value = asset.id;
    tdCheckbox.appendChild(checkbox);
    tr.appendChild(tdCheckbox);
    
    // Колонки данных
    const columns = visibleColumns || ['ip_address', 'hostname', 'os_name', 'status', 'device_type', 'open_ports', 'group_name', 'source'];
    
    columns.forEach(col => {
      const td = document.createElement('td');
      let value = asset[col];
      
      // Особая обработка для группы - выводим ВСЕ группы списком
      if (col === 'group_name' || col === 'group_id' || col === 'groups') {
        console.log('[AssetManager] Processing groups for asset', asset.id, ':', asset.groups);
        
        if (asset.groups && Array.isArray(asset.groups) && asset.groups.length > 0) {
          // groups - это массив ID (чисел). Нужно найти имена групп.
          // Предполагаем, что store.allGroups доступен или передаётся как контекст
          const allGroups = window.allGroups || (store && store.groups) || [];
          
          const groupNames = asset.groups.map(groupId => {
            const groupObj = allGroups.find(g => g.id === groupId);
            return groupObj ? groupObj.name : `ID: ${groupId}`;
          });
          
          // Формируем HTML с бейджами для каждой группы
          value = groupNames.map(name => 
            `<span class="badge bg-secondary me-1">${name}</span>`
          ).join('');
          
          console.log('[AssetManager] Rendered groups:', value);
        } else {
          value = '<span class="text-muted">Без группы</span>';
          console.log('[AssetManager] No group information');
        }
      }
      
      // Обработка ОС - приоритет os_name над os_family
      if (col === 'os_name') {
        if (asset.os_name) {
          value = asset.os_name;
        } else if (asset.os_family) {
          value = asset.os_version ? `${asset.os_family} (${asset.os_version})` : asset.os_family;
        } else {
          value = '-';
        }
      }
      
      // Обработка портов
      if (col === 'open_ports') {
        if (!value || (Array.isArray(value) && value.length === 0)) {
          value = '-';
        } else if (Array.isArray(value)) {
          value = value.join(', ');
        }
      }
      
      // Обработка null/undefined
      if (value === null || value === undefined) {
        value = '<span class="text-muted">-</span>';
      } else if (col === 'status') {
        // Бейдж для статуса
        const badgeClass = value === 'active' ? 'success' : 'secondary';
        value = `<span class="badge bg-${badgeClass}">${value}</span>`;
      } else if (col === 'ip_address') {
        // Жирный шрифт для IP
        value = `<strong>${value}</strong>`;
      }
      
      td.innerHTML = value;
      tr.appendChild(td);
    });
    
    // Колонка действий
    const tdActions = document.createElement('td');
    tdActions.className = 'text-end';
    tdActions.innerHTML = `
      <button class="btn btn-sm btn-outline-primary edit-asset-btn" data-id="${asset.id}" title="Редактировать">
        <i class="bi bi-pencil"></i>
      </button>
    `;
    tr.appendChild(tdActions);
    
    return tr;
  }

  #handleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.asset-checkbox');
    checkboxes.forEach(cb => {
      cb.checked = checkbox.checked;
      this.#toggleRowSelection(cb.closest('tr'), checkbox.checked);
      if (checkbox.checked) {
        store.addSelectedAsset(cb.value);
      } else {
        store.removeSelectedAsset(cb.value);
      }
    });

    const lastIndex = checkbox.checked && checkboxes.length > 0
      ? this.#getRowIndex(checkboxes[checkboxes.length - 1].closest('tr'))
      : -1;
    store.setLastSelectedIndex(lastIndex);

    this.#updateBulkToolbar();
    this.#updateSelectAllCheckbox();
  }

  #handleCheckboxChange(cb) {
    const row = cb.closest('tr');
    const id = cb.value;
    const checked = cb.checked;

    this.#toggleRowSelection(row, checked);

    if (checked) {
      store.addSelectedAsset(id);
      store.setLastSelectedIndex(this.#getRowIndex(row));
    } else {
      store.removeSelectedAsset(id);
      if (store.getLastSelectedIndex() === this.#getRowIndex(row)) {
        store.setLastSelectedIndex(-1);
      }
    }

    this.#updateBulkToolbar();
    this.#updateSelectAllCheckbox();
  }

  #toggleRowSelection(row, isSel) {
    if (!row) return;
    if (isSel) row.classList.add('selected');
    else row.classList.remove('selected');
  }

  #getRowIndex(row) {
    return Array.from(document.querySelectorAll(`#${this.targetTableId} .asset-row`)).indexOf(row);
  }

  #selectRange(start, end) {
    const [s, e] = start <= end ? [start, end] : [end, start];
    document.querySelectorAll(`#${this.targetTableId} .asset-row`).forEach((row, i) => {
      if (i >= s && i <= e) {
        const cb = row.querySelector('.asset-checkbox');
        if (cb && !cb.checked) {
          cb.checked = true;
          this.#toggleRowSelection(row, true);
          store.addSelectedAsset(cb.value);
        }
      }
    });
    this.#updateBulkToolbar();
    this.#updateSelectAllCheckbox();
  }

  clearSelection() {
    document.querySelectorAll(`#${this.targetTableId} .asset-checkbox:checked`).forEach(cb => {
      cb.checked = false;
      this.#toggleRowSelection(cb.closest('tr'), false);
      store.removeSelectedAsset(cb.value);
    });
    store.setLastSelectedIndex(-1);
    this.#updateBulkToolbar();
    this.#updateSelectAllCheckbox();
  }

  #updateSelectAllCheckbox() {
    const selAll = document.getElementById('select-all');
    const cbs = document.querySelectorAll(`#${this.targetTableId} .asset-checkbox`);
    const checked = document.querySelectorAll(`#${this.targetTableId} .asset-checkbox:checked`).length;

    if (selAll && cbs.length > 0) {
      selAll.checked = checked === cbs.length;
      selAll.indeterminate = checked > 0 && checked < cbs.length;
    }
  }

  #updateBulkToolbar() {
    const count = store.getSelectedCount();
    const toolbar = document.getElementById('bulk-toolbar');
    if (toolbar) {
      toolbar.style.display = count > 0 ? 'block' : 'none';
      const countEl = toolbar.querySelector('.selected-count');
      if (countEl) countEl.textContent = count;
    }
  }
}

// Создаем и экспортируем экземпляр по умолчанию
export const assetManager = new AssetManager();

// Обработчик кнопки сканирования на странице детали актива
document.addEventListener('DOMContentLoaded', function() {
    const scanBtn = document.getElementById('scanCurrentAssetBtn');
    if (scanBtn) {
        scanBtn.addEventListener('click', function() {
            // Получаем ID актива из data-атрибута или URL страницы
            const assetId = window.location.pathname.split('/').pop();
            if (assetId && !isNaN(assetId)) {
                startAssetScan(parseInt(assetId));
            } else {
                alert('Не удалось определить ID актива');
            }
        });
    }
});

// Функция запуска сканирования актива
function startAssetScan(assetId) {
    if (!confirm('Запустить сканирование для этого актива?')) {
        return;
    }
    
    fetch(`/api/scans/create`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            target_id: assetId,
            scan_type: 'nmap',
            name: `Сканирование актива ${assetId}`
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Ошибка запуска сканирования');
        return response.json();
    })
    .then(data => {
        alert('Сканирование запущено');
        // Опционально: перенаправить на страницу сканирований
        // window.location.href = '/scans';
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ошибка при запуске сканирования: ' + error.message);
    });
}
