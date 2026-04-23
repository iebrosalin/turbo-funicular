// static/js/modules/assets.js

export function initAssetSelection(targetTableId = 'assets-body') {
    // Инициализация глобального множества выбранных активов, если ещё не создано
    if (!window.selectedAssetIds) {
        window.selectedAssetIds = new Set();
    }
    
    const tbody = document.getElementById(targetTableId); 
    if (!tbody) return;
    
    const selAll = document.getElementById('select-all');
    if(selAll) selAll.addEventListener('change', function() {
        const checkboxes = document.querySelectorAll('.asset-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = this.checked; 
            toggleRowSelection(cb.closest('tr'), this.checked, targetTableId);
            if(this.checked) window.selectedAssetIds.add(cb.value); 
            else window.selectedAssetIds.delete(cb.value);
        });
        window.lastSelectedIndex = this.checked && checkboxes.length > 0 ? getRowIndex(checkboxes[checkboxes.length - 1].closest('tr'), targetTableId) : -1;
        updateBulkToolbar(); 
        updateSelectAllCheckbox(targetTableId);
    });
    
    tbody.addEventListener('change', e => { 
        if(e.target.classList.contains('asset-checkbox')) handleCheckboxChange(e.target, targetTableId); 
    });
    
    tbody.addEventListener('click', e => {
        const row = e.target.closest('.asset-row'); 
        if(!row || e.target.closest('a, button, .asset-checkbox')) return;
        const cb = row.querySelector('.asset-checkbox');
        if(cb) { 
            if(e.shiftKey && window.lastSelectedIndex >= 0) { 
                e.preventDefault(); 
                selectRange(window.lastSelectedIndex, getRowIndex(row, targetTableId), targetTableId); 
            } else { 
                cb.checked = !cb.checked; 
                handleCheckboxChange(cb, targetTableId); 
            } 
        }
    });
}

function handleCheckboxChange(cb, targetTableId = 'assets-body') {
    const row = cb.closest('tr'); 
    const id = cb.value; 
    const checked = cb.checked;
    toggleRowSelection(row, checked);
    if(checked) { 
        window.selectedAssetIds.add(id); 
        window.lastSelectedIndex = getRowIndex(row, targetTableId); 
    } else { 
        window.selectedAssetIds.delete(id); 
        if(window.lastSelectedIndex === getRowIndex(row, targetTableId)) window.lastSelectedIndex = -1; 
    }
    updateBulkToolbar(); 
    updateSelectAllCheckbox(targetTableId);
}

function toggleRowSelection(row, isSel) { 
    if(isSel) row.classList.add('selected'); 
    else row.classList.remove('selected'); 
}

function getRowIndex(row, targetTableId = 'assets-body') { 
    return Array.from(document.querySelectorAll(`#${targetTableId} .asset-row`)).indexOf(row); 
}

function selectRange(start, end, targetTableId = 'assets-body') {
    const [s, e] = start <= end ? [start, end] : [end, start];
    document.querySelectorAll(`#${targetTableId} .asset-row`).forEach((row, i) => {
        if(i >= s && i <= e) {
            const cb = row.querySelector('.asset-checkbox');
            if(cb && !cb.checked) { 
                cb.checked = true; 
                toggleRowSelection(row, true); 
                window.selectedAssetIds.add(cb.value); 
            }
        }
    }); 
    updateBulkToolbar(); 
    updateSelectAllCheckbox(targetTableId);
}

export function clearSelection(targetTableId = 'assets-body') {
    document.querySelectorAll(`#${targetTableId} .asset-checkbox:checked`).forEach(cb => { 
        cb.checked = false; 
        toggleRowSelection(cb.closest('tr'), false); 
        window.selectedAssetIds.delete(cb.value); 
    });
    window.lastSelectedIndex = -1; 
    updateBulkToolbar(); 
    updateSelectAllCheckbox(targetTableId);
}

function updateSelectAllCheckbox(targetTableId = 'assets-body') {
    const selAll = document.getElementById('select-all'); 
    const cbs = document.querySelectorAll(`#${targetTableId} .asset-checkbox`);
    const checked = document.querySelectorAll(`#${targetTableId} .asset-checkbox:checked`).length;
    if(selAll && cbs.length > 0) { 
        selAll.checked = checked === cbs.length; 
        selAll.indeterminate = checked > 0 && checked < cbs.length; 
    }
}

function updateBulkToolbar() {
    const tb = document.getElementById('bulk-toolbar'); 
    const c = window.selectedAssetIds ? window.selectedAssetIds.size : 0;
    if(tb) {
        tb.style.display = c > 0 ? 'flex' : 'none'; 
        const countEl = document.getElementById('selected-count');
        if(countEl) countEl.textContent = c;
    }
}

export function confirmBulkDelete() {
    if(window.selectedAssetIds.size === 0) return;
    const countEl = document.getElementById('bulk-delete-count');
    if(countEl) countEl.textContent = window.selectedAssetIds.size;

    const modalEl = document.getElementById('bulkDeleteModal');
    let modalInstance = bootstrap.Modal.getInstance(modalEl);
    if (!modalInstance) {
        modalInstance = new bootstrap.Modal(modalEl);
    }
    modalInstance.show();
}

export async function executeBulkDelete() {
    const ids = Array.from(window.selectedAssetIds);
    await fetch('/api/assets/bulk-delete', { 
        method: 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({ids}) 
    });
    clearSelection(); 
    
    const modalEl = document.getElementById('bulkDeleteModal');
    const modalInstance = bootstrap.Modal.getInstance(modalEl);
    if (modalInstance) {
        modalInstance.hide();
    }
    
    location.reload();
}


export function confirmBulkMove() {
    if(window.selectedAssetIds.size === 0) return;
        const modalEl = document.getElementById('bulkMoveModal');
        let modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (!modalInstance) {
            modalInstance = new bootstrap.Modal(modalEl);
        }
        modalInstance.show();

    // Загрузка списка групп для селекта
    loadGroupsForMoveModal().then(() => {
        const modalInstance = bootstrap.Modal.getInstance(document.getElementById('bulkMoveModal'));
        if(modalInstance) modalInstance.show();
    });
}

async function loadGroupsForMoveModal() {
    const select = document.getElementById('target-group-select');
    if(!select) return;

    // Сохраняем текущее значение
    const currentValue = select.value;

    try {
        const response = await fetch('/api/groups');
        if(!response.ok) throw new Error('Failed to load groups');

        const groups = await response.json();

        // Очищаем и заполняем селект
        select.innerHTML = '<option value="">-- Без группы --</option>';

        if(Array.isArray(groups)) {
            groups.forEach(g => {
                const option = document.createElement('option');
                option.value = g.id;
                option.textContent = g.name || g.group_name || `Группа ${g.id}`;
                select.appendChild(option);
            });
        }

        // Восстанавливаем значение если возможно
        if(currentValue && select.querySelector(`option[value="${currentValue}"]`)) {
            select.value = currentValue;
        }
    } catch(error) {
        console.error('Ошибка загрузки групп:', error);
        // Даже при ошибке показываем модальное окно с опцией "Без группы"
    }
}

export async function executeBulkMove() {
    const select = document.getElementById('target-group-select');
    if(!select) return;

    const groupId = select.value;
    const ids = Array.from(window.selectedAssetIds);

    await fetch('/api/assets/bulk-move', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ids, group_id: groupId})
    });

    clearSelection();

    const modalEl = document.getElementById('bulkMoveModal');
    const modalInstance = bootstrap.Modal.getInstance(modalEl);
    if (modalInstance) {
        modalInstance.hide();
    }

    location.reload();
}

const FILTER_FIELDS = [
    { value: 'ip_address', text: 'IP Адрес' }, { value: 'hostname', text: 'Hostname' },
    { value: 'os_info', text: 'ОС (Сканирование)' }, { value: 'device_role', text: 'Роль устройства' },
    { value: 'open_ports', text: 'Открытые порты' }, { value: 'status', text: 'Статус' },
    { value: 'notes', text: 'Заметки' }, { value: 'osquery_status', text: 'Статус OSquery' },
    { value: 'osquery_os', text: 'ОС (OSquery)' }, { value: 'scanners_used', text: 'Сканеры (JSON)' }
];

export function initFilterFieldDatalist() {
    if(!document.getElementById('filter-fields-list')) {
        const dl = document.createElement('datalist'); 
        dl.id = 'filter-fields-list';
        dl.innerHTML = FILTER_FIELDS.map(f => `<option value="${f.value}">${f.text}</option>`).join('');
        document.body.appendChild(dl);
    }
}

export function renderAssets(data, targetTableId = 'assets-body') {
    const tb = document.getElementById(targetTableId); 
    if(!tb) return;
    tb.innerHTML = ''; 
    clearSelection(targetTableId);
    if(data.length===0) { 
        tb.innerHTML='<tr><td colspan="7" class="text-center py-4 text-muted"><i class="bi bi-inbox fs-1 d-block mb-2"></i>Ничего не найдено</td></tr>'; 
        return; 
    }
    data.forEach(a => {
        const tr = document.createElement('tr'); 
        tr.className='asset-row'; 
        tr.dataset.assetId=a.id;
        tr.innerHTML=`<td><input type="checkbox" class="form-check-input asset-checkbox" value="${a.id}"></td>
            <td><a href="/asset/${a.id}"><strong>${a.ip}</strong></a></td><td>${a.hostname||'—'}</td>
            <td><span class="text-muted small">${a.os||'—'}</span></td><td><small class="text-muted">${a.ports||'—'}</small></td>
            <td><span class="badge bg-light text-dark border">${a.group}</span></td>
            <td><a href="/asset/${a.id}" class="btn btn-sm btn-outline-info"><i class="bi bi-eye"></i></a></td>`;
        tb.appendChild(tr);
    });
    
    // Инициализация выбора активов после рендеринга
    initAssetSelection(targetTableId);
}

// Экспорт для доступа из main.js
window.renderAssets = renderAssets;

/**
 * Показать модальное окно создания/редактирования актива
 * @param {number|null} assetId - ID актива для редактирования или null для создания
 */
export async function showAssetModal(assetId = null) {
    const modalEl = document.getElementById('assetModal');
    const modalTitle = document.getElementById('assetModalTitle');
    const form = document.getElementById('assetForm');
    const assetIdInput = document.getElementById('assetId');
    
    if (!modalEl || !form) {
        console.error('❌ Модальное окно assetModal не найдено');
        return;
    }

    // Сброс формы
    form.reset();
    assetIdInput.value = '';

    if (assetId) {
        // Режим редактирования
        modalTitle.innerHTML = '<i class="bi bi-pencil"></i> Редактировать актив';
        assetIdInput.value = assetId;

        // Загрузка данных актива
        try {
            const response = await fetch(`/api/assets/${assetId}`);
            if (!response.ok) throw new Error('Failed to load asset');
            const asset = await response.json();

            document.getElementById('assetIpAddress').value = asset.ip_address || '';
            document.getElementById('assetHostname').value = asset.hostname || '';
            document.getElementById('assetOsInfo').value = asset.os_info || '';
            document.getElementById('assetOpenPorts').value = asset.open_ports || '';
            document.getElementById('assetNotes').value = asset.notes || '';
            
            // Загрузка групп и установка выбранной
            await loadGroupsForAssetModal(asset.group_id);
        } catch (error) {
            console.error('Ошибка загрузки актива:', error);
            alert('Не удалось загрузить данные актива');
            return;
        }
    } else {
        // Режим создания
        modalTitle.innerHTML = '<i class="bi bi-plus-circle"></i> Новый актив';
        await loadGroupsForAssetModal(null);
    }

    // Показ модального окна
    let modalInstance = bootstrap.Modal.getInstance(modalEl);
    if (!modalInstance) {
        modalInstance = new bootstrap.Modal(modalEl);
    }
    modalInstance.show();
}

/**
 * Загрузка списка групп для модального окна актива
 */
async function loadGroupsForAssetModal(selectedGroupId = null) {
    const select = document.getElementById('assetGroupId');
    if (!select) return;

    try {
        const response = await fetch('/api/groups/tree');
        if (!response.ok) throw new Error('Failed to load groups');
        
        const groups = await response.json();
        
        // Очищаем селект
        select.innerHTML = '<option value="">-- Без группы --</option>';
        
        // Рекурсивная функция для добавления групп с отступами
        function addGroupOptions(groupList, depth = 0) {
            if (!Array.isArray(groupList)) return;
            
            groupList.forEach(g => {
                const option = document.createElement('option');
                option.value = g.id;
                const indent = depth > 0 ? '    '.repeat(depth) + '└─ ' : '';
                option.textContent = indent + (g.name || g.group_name || `Группа ${g.id}`);
                select.appendChild(option);
                
                // Рекурсивно добавляем дочерние группы
                if (g.children && g.children.length > 0) {
                    addGroupOptions(g.children, depth + 1);
                }
            });
        }
        
        addGroupOptions(groups);
        
        // Устанавливаем выбранную группу
        if (selectedGroupId && select.querySelector(`option[value="${selectedGroupId}"]`)) {
            select.value = selectedGroupId;
        }
    } catch (error) {
        console.error('Ошибка загрузки групп:', error);
    }
}

/**
 * Обработчик отправки формы создания/редактирования актива
 */
export async function saveAsset(event) {
    event.preventDefault();
    
    const assetId = document.getElementById('assetId').value;
    const formData = {
        ip_address: document.getElementById('assetIpAddress').value,
        hostname: document.getElementById('assetHostname').value,
        os_info: document.getElementById('assetOsInfo').value,
        open_ports: document.getElementById('assetOpenPorts').value,
        group_id: document.getElementById('assetGroupId').value || null,
        notes: document.getElementById('assetNotes').value
    };

    try {
        const url = assetId ? `/api/assets/${assetId}` : '/api/assets';
        const method = assetId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(formData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to save asset');
        }
        
        // Закрытие модального окна
        const modalEl = document.getElementById('assetModal');
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) {
            modalInstance.hide();
        }
        
        // Перезагрузка списка активов
        if (typeof window.loadAssets === 'function') {
            window.loadAssets();
        } else {
            location.reload();
        }
    } catch (error) {
        console.error('Ошибка сохранения актива:', error);
        alert('Не удалось сохранить актив: ' + error.message);
    }
}

// Экспорт функций для глобального доступа
window.showAssetModal = showAssetModal;
window.saveAsset = saveAsset;