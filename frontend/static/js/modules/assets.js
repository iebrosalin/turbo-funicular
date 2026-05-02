// static/js/modules/assets.js
import { store } from './index.js';

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

  #handleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.asset-checkbox');
    const ids = Array.from(checkboxes).map(cb => cb.value);
    
    store.toggleAllAssets(ids, checkbox.checked);
    
    checkboxes.forEach(cb => {
      cb.checked = checkbox.checked;
      this.#toggleRowSelection(cb.closest('tr'), checkbox.checked);
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
      const countEl = toolbar.querySelector('#selected-count');
      if (countEl) countEl.textContent = count;
    }
  }

  /**
   * Отрисовать таблицу активов
   * @param {Array} assets - Массив активов
   * @param {Array} columns - Массив видимых колонок
   */
  render(assets, columns) {
    if (!this.tbody) return;
    
    const thead = this.tbody.parentElement?.querySelector('thead');
    if (thead) {
      const headerRow = thead.querySelector('#table-header-row');
      if (headerRow) {
        headerRow.innerHTML = '<th class="text-center"><input type="checkbox" id="select-all" class="form-check-input"></th>' +
          columns.map(col => `<th>${this.#getColumnLabel(col)}</th>`).join('') +
          '<th>Действия</th>';
        
        // Перепривязка чекбокса "Выбрать все"
        const selectAll = headerRow.querySelector('#select-all');
        if (selectAll) {
          selectAll.addEventListener('change', () => this.#handleSelectAll(selectAll));
        }
      }
    }

    this.tbody.innerHTML = '';
    assets.forEach(asset => {
      this.tbody.appendChild(this.createRow(asset, columns));
    });

    // Обновление счетчиков
    const totalCount = document.getElementById('total-count');
    const filteredCount = document.getElementById('filtered-count');
    if (totalCount) totalCount.textContent = assets.length;
    if (filteredCount) filteredCount.textContent = assets.length;
  }

  /**
   * Создать строку таблицы для актива
   * @param {Object} asset - Объект актива
   * @param {Array} columns - Массив видимых колонок
   * @returns {HTMLTableRowElement}
   */
  createRow(asset, columns) {
    const tr = document.createElement('tr');
    tr.className = 'asset-row';
    tr.dataset.assetId = asset.id;

    const selected = store.isSelected(asset.id);
    if (selected) tr.classList.add('selected');

    // Создаем ссылку на детальную страницу для IP или hostname (как в tree.js)
    const ipLink = asset.ip_address
      ? `<a href="/assets/${asset.id}" class="text-decoration-none"><strong>${asset.ip_address}</strong></a>`
      : '<strong>N/A</strong>';

    const hostnameDisplay = asset.hostname
      ? (asset.ip_address ? `<a href="/assets/${asset.id}" class="text-decoration-none">${asset.hostname}</a>` : `<strong>${asset.hostname}</strong>`)
      : '<span class="text-muted">-</span>';

    // Формируем ячейки с учётом специальных случаев для IP и hostname
    let cells = '';
    for (const col of columns) {
      let val = asset[col];

      // Специальная обработка для IP и hostname
      if (col === 'ip_address') {
        cells += `<td>${ipLink}</td>`;
        continue;
      }
      if (col === 'hostname') {
        cells += `<td>${hostnameDisplay}</td>`;
        continue;
      }

      // Обработка остальных колонок
      if (val === null || val === undefined) val = '-';
      else if (Array.isArray(val)) val = val.join(', ');
      else val = String(val);
      cells += `<td>${val}</td>`;
    }

    tr.innerHTML = `
      <td class="text-center">
        <input type="checkbox" class="form-check-input asset-checkbox" value="${asset.id}" ${selected ? 'checked' : ''}>
      </td>
      ${cells}
      <td>
        <button class="btn btn-sm btn-outline-primary me-1" title="Редактировать">
          <i class="bi bi-pencil"></i>
        </button>
        <button class="btn btn-sm btn-danger btn-delete-asset" data-asset-id="${asset.id}" title="Удалить">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    `;

    return tr;
  }

  #getColumnLabel(key) {
    const labels = {
      ip_address: 'IP Адрес',
      hostname: 'Hostname',
      os_family: 'ОС',
      os_name: 'ОС',
      device_type: 'Тип',
      status: 'Статус',
      open_ports: 'Порты',
      groups: 'Группы',
      last_nmap_scan: 'Last Nmap',
      last_rustscan_scan: 'Last Rustscan',
      source: 'Источник'
    };
    return labels[key] || key;
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
