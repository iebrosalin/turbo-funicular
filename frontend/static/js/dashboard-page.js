// static/js/dashboard-page.js
/**
 * Основная логика дашборда: фильтрация, группировка, экспорт.
 * Загрузка активов делегирована модулю tree.js (функция loadAssets).
 */

import { loadAssets } from './modules/tree.js';

let allAssets = [];
let filteredAssets = [];
let currentGrouping = 'none';
let visibleColumns = ['ip_address', 'hostname', 'os_family', 'status', 'device_type'];
let searchQuery = '';

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Загрузка параметров из URL (если есть)
    loadStateFromURL();
    
    // Инициализация автодополнения для фильтра
    const filterInput = document.getElementById('asset-filter');
    if (filterInput && window.initFilterAutocomplete) {
        window.initFilterAutocomplete(filterInput);
    }

    // Загрузка данных через центральный модуль tree.js
    loadAssets(null, false, 'assets-table', null);
    
    // Навешиваем обработчики событий
    setupEventListeners();
});

function setupEventListeners() {
    // Поиск
    const filterInput = document.getElementById('asset-filter');
    if (filterInput) {
        filterInput.addEventListener('input', (e) => {
            searchQuery = e.target.value.trim();
            updateURL();
            applyFilters();
        });
    }

    // Группировка
    const groupSelect = document.getElementById('group-by-select');
    if (groupSelect) {
        groupSelect.addEventListener('change', (e) => {
            currentGrouping = e.target.value;
            updateURL();
            applyFilters();
        });
    }

    // Кнопки фильтров
    const btnApplyFilters = document.getElementById('btn-apply-filters');
    const btnResetFilters = document.getElementById('btn-reset-filters');
    
    if (btnApplyFilters) btnApplyFilters.addEventListener('click', applyFilters);
    if (btnResetFilters) btnResetFilters.addEventListener('click', resetFilters);

    // Toolbar кнопки
    const btnClearSelection = document.getElementById('btn-clear-selection');
    const btnBulkMove = document.getElementById('btn-bulk-move');
    const btnBulkDelete = document.getElementById('btn-bulk-delete');
    
    if (btnClearSelection) btnClearSelection.addEventListener('click', clearSelection);
    if (btnBulkMove) btnBulkMove.addEventListener('click', confirmBulkMove);
    if (btnBulkDelete) btnBulkDelete.addEventListener('click', confirmBulkDelete);

    // Кнопки темы и добавления актива
    const btnToggleTheme = document.getElementById('btn-toggle-theme');
    const btnAddAsset = document.getElementById('btn-add-asset');
    
    if (btnToggleTheme) btnToggleTheme.addEventListener('click', toggleTheme);
    if (btnAddAsset) btnAddAsset.addEventListener('click', () => showAssetModal(null));
}

// Функция обновления данных после загрузки из tree.js
function handleAssetsLoaded(assetsArray) {
    try {
        allAssets = assetsArray;
        applyFilters();
    } catch (error) {
        console.error('Ошибка при обработке загруженных активов:', error);
    }
}

function applyFilters() {
    // Фильтрация по поиску
    if (!searchQuery) {
        filteredAssets = [...allAssets];
    } else {
        const queryLower = searchQuery.toLowerCase();
        filteredAssets = allAssets.filter(asset => {
            // Простой поиск по всем строковым полям
            return Object.values(asset).some(val => {
                if (val === null || val === undefined) return false;
                if (typeof val === 'string') return val.toLowerCase().includes(queryLower);
                if (Array.isArray(val)) return val.some(v => String(v).toLowerCase().includes(queryLower));
                return false;
            });
        });
    }

    // Дополнительная фильтрация по сложному синтаксису (если реализована в filter-helpers)
    // Здесь можно добавить парсинг "field:op:value" если нужно
    
    renderTable();
    renderGrouping();
}

function renderTable() {
    const tableBody = document.querySelector('#assets-table tbody');
    if (!tableBody) return;

    tableBody.innerHTML = '';

    if (!Array.isArray(filteredAssets) || filteredAssets.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="10" class="text-center text-muted">Активы не найдены</td></tr>';
        return;
    }

    // Ограничение на количество отображаемых элементов для производительности
    const displayLimit = 500;
    const assetsToRender = filteredAssets.slice(0, displayLimit);

    assetsToRender.forEach(asset => {
        const tr = document.createElement('tr');
        
        // Формирование ячеек в зависимости от видимых колонок
        let html = '';
        
        // Чекбокс выбора
        html += `<td><input type="checkbox" class="asset-select" value="${asset.id}"></td>`;
        
        visibleColumns.forEach(col => {
            let val = asset[col];
            
            // Форматирование значений
            if (col === 'ip_address') {
                const domainHint = asset.fqdn || (asset.dns_names && asset.dns_names[0]) || '';
                val = domainHint ? `${val} <small class="text-muted">(${domainHint})</small>` : val;
            } else if (col === 'groups') {
                val = Array.isArray(val) ? val.map(g => `<span class="badge bg-secondary">${g}</span>`).join(' ') : '';
            } else if (col === 'open_ports') {
                val = Array.isArray(val) ? `<span class="badge bg-info">${val.length}</span>` : '0';
            } else if (col === 'status') {
                const badgeClass = getStatusBadgeClass(val);
                val = `<span class="badge ${badgeClass}">${val}</span>`;
            } else if (!val) {
                val = '<span class="text-muted">-</span>';
            }
            
            html += `<td>${val}</td>`;
        });
        
        // Колонка действий
        html += `
            <td>
                <div class="btn-group btn-group-sm">
                    <a href="/assets/${asset.id}" class="btn btn-outline-primary" title="Детали"><i class="bi bi-eye"></i></a>
                    <button class="btn btn-outline-danger" title="Удалить" onclick="deleteAsset(${asset.id})"><i class="bi bi-trash"></i></button>
                </div>
            </td>
        `;
        
        tr.innerHTML = html;
        tableBody.appendChild(tr);
    });

    if (filteredAssets.length > displayLimit) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="100" class="text-center text-warning">Показано ${displayLimit} из ${filteredAssets.length}. Уточните поиск.</td>`;
        tableBody.appendChild(tr);
    }
}

function renderGrouping() {
    // Логика визуального разделения таблицы при группировке
    // В простой реализации мы просто перерисовываем таблицу, но можно добавлять заголовки групп
    if (currentGrouping === 'none') return;

    const tableBody = document.querySelector('#assets-table tbody');
    if (!tableBody) return;

    // Группировка данных
    const groups = {};
    filteredAssets.forEach(asset => {
        let key = 'Unknown';
        if (currentGrouping === 'group') {
            // Если групп много, берем первую или "Без группы"
            const assetGroups = asset.groups || [];
            key = assetGroups.length > 0 ? assetGroups[0] : 'Без группы';
        } else if (currentGrouping === 'os_family') {
            key = asset.os_family || 'Неизвестно';
        } else if (currentGrouping === 'status') {
            key = asset.status || 'Unknown';
        } else if (currentGrouping === 'device_type') {
            key = asset.device_type || 'Unknown';
        }

        if (!groups[key]) groups[key] = [];
        groups[key].push(asset);
    });

    // Перерисовка с заголовками групп
    tableBody.innerHTML = '';
    
    Object.keys(groups).sort().forEach(groupName => {
        // Заголовок группы
        const trGroup = document.createElement('tr');
        trGroup.className = 'table-active';
        trGroup.innerHTML = `<td colspan="100"><strong>${groupName}</strong> <span class="badge bg-secondary">${groups[groupName].length}</span></td>`;
        tableBody.appendChild(trGroup);

        // Элементы группы (упрощенно, копируем логику renderTable для одного элемента)
        groups[groupName].forEach(asset => {
            const tr = document.createElement('tr');
            // ... (логика создания строки такая же, как в renderTable)
            // Для краткости опустим дублирование кода, в реальности лучше вынести создание строки в функцию createAssetRow(asset)
            let html = `<td><input type="checkbox" class="asset-select" value="${asset.id}"></td>`;
            visibleColumns.forEach(col => {
                let val = asset[col];
                if (col === 'ip_address') {
                    const domainHint = asset.fqdn || (asset.dns_names && asset.dns_names[0]) || '';
                    val = domainHint ? `${val} <small class="text-muted">(${domainHint})</small>` : val;
                } else if (col === 'groups') {
                    val = Array.isArray(val) ? val.map(g => `<span class="badge bg-secondary">${g}</span>`).join(' ') : '';
                } else if (col === 'open_ports') {
                    val = Array.isArray(val) ? `<span class="badge bg-info">${val.length}</span>` : '0';
                } else if (col === 'status') {
                    val = `<span class="badge ${getStatusBadgeClass(val)}">${val}</span>`;
                } else if (!val) {
                    val = '<span class="text-muted">-</span>';
                }
                html += `<td>${val}</td>`;
            });
            html += `<td><div class="btn-group btn-group-sm"><a href="/assets/${asset.id}" class="btn btn-outline-primary"><i class="bi bi-eye"></i></a></div></td>`;
            tr.innerHTML = html;
            tableBody.appendChild(tr);
        });
    });
}

function getStatusBadgeClass(status) {
    switch(status) {
        case 'active': return 'bg-success';
        case 'inactive': return 'bg-secondary';
        case 'archived': return 'bg-dark';
        case 'maintenance': return 'bg-warning text-dark';
        default: return 'bg-info';
    }
}

function exportData(format) {
    if (!filteredAssets || filteredAssets.length === 0) {
        alert('Нет данных для экспорта');
        return;
    }

    let content = '';
    let mimeType = '';
    let extension = '';

    if (format === 'csv') {
        // Заголовки
        const headers = ['ID', ...visibleColumns];
        content = headers.join(',') + '\n';
        
        // Данные
        filteredAssets.forEach(asset => {
            const row = [asset.id];
            visibleColumns.forEach(col => {
                let val = asset[col];
                if (Array.isArray(val)) val = val.join('; ');
                if (val === null || val === undefined) val = '';
                // Экранирование запятых
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
        content = JSON.stringify(filteredAssets, null, 2);
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

function loadStateFromURL() {
    const params = new URLSearchParams(window.location.search);
    
    const search = params.get('search');
    if (search) {
        searchQuery = search;
        const input = document.getElementById('asset-filter');
        if (input) input.value = searchQuery;
    }
    
    const group = params.get('group');
    if (group) {
        currentGrouping = group;
        const select = document.getElementById('group-by-select');
        if (select) select.value = group;
    }
    
    const cols = params.get('cols');
    if (cols) {
        visibleColumns = cols.split(',');
        // Тут можно обновить UI чекбоксов колонок если они есть
    }
}

function updateURL() {
    const params = new URLSearchParams();
    
    if (searchQuery) params.set('search', searchQuery);
    if (currentGrouping !== 'none') params.set('group', currentGrouping);
    if (visibleColumns.length > 0) params.set('cols', visibleColumns.join(','));
    
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', newUrl);
}

// Глобальные функции для вызова из HTML
window.deleteAsset = function(id) {
    if (!confirm('Вы уверены, что хотите удалить этот актив?')) return;
    
    fetch(`/api/assets/${id}`, { method: 'DELETE' })
        .then(res => {
            if (res.ok) {
                alert('Актив удален');
                // Перезагружаем активы через центральный модуль tree.js
                if (window.loadAssets) {
                    window.loadAssets(null, false, 'assets-table', null);
                }
            } else {
                return res.json().then(err => Promise.reject(err));
            }
        })
        .catch(err => alert('Ошибка удаления: ' + (err.error || err.message)));
};

// Экспортируем функцию для использования из tree.js
window.handleAssetsLoaded = handleAssetsLoaded;

// Глобальные функции для вызова из HTML (теперь через event listeners)
function resetFilters() {
    searchQuery = '';
    currentGrouping = 'none';
    
    const filterInput = document.getElementById('asset-filter');
    const groupSelect = document.getElementById('group-by-select');
    
    if (filterInput) filterInput.value = '';
    if (groupSelect) groupSelect.value = '';
    
    updateURL();
    applyFilters();
}

// Экспорт функций в глобальную область видимости
window.applyFilters = applyFilters;
window.resetFilters = resetFilters;
window.exportData = exportData;