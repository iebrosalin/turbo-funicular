// static/js/modules/assets.js

export function initAssetSelection() {
    // Инициализация глобального множества выбранных активов, если ещё не создано
    if (!window.selectedAssetIds) {
        window.selectedAssetIds = new Set();
    }
    
    const tbody = document.getElementById('assets-body'); 
    if (!tbody) return;
    
    const selAll = document.getElementById('select-all');
    if(selAll) selAll.addEventListener('change', function() {
        document.querySelectorAll('.asset-checkbox').forEach(cb => {
            cb.checked = this.checked; 
            toggleRowSelection(cb.closest('tr'), this.checked);
            if(this.checked) window.selectedAssetIds.add(cb.value); 
            else window.selectedAssetIds.delete(cb.value);
        });
        window.lastSelectedIndex = this.checked ? getRowIndex(document.querySelectorAll('.asset-checkbox').pop().closest('tr')) : -1;
        updateBulkToolbar(); 
        updateSelectAllCheckbox();
    });
    
    tbody.addEventListener('change', e => { 
        if(e.target.classList.contains('asset-checkbox')) handleCheckboxChange(e.target); 
    });
    
    tbody.addEventListener('click', e => {
        const row = e.target.closest('.asset-row'); 
        if(!row || e.target.closest('a, button, .asset-checkbox')) return;
        const cb = row.querySelector('.asset-checkbox');
        if(cb) { 
            if(e.shiftKey && window.lastSelectedIndex >= 0) { 
                e.preventDefault(); 
                selectRange(window.lastSelectedIndex, getRowIndex(row)); 
            } else { 
                cb.checked = !cb.checked; 
                handleCheckboxChange(cb); 
            } 
        }
    });
}

function handleCheckboxChange(cb) {
    const row = cb.closest('tr'); 
    const id = cb.value; 
    const checked = cb.checked;
    toggleRowSelection(row, checked);
    if(checked) { 
        window.selectedAssetIds.add(id); 
        window.lastSelectedIndex = getRowIndex(row); 
    } else { 
        window.selectedAssetIds.delete(id); 
        if(window.lastSelectedIndex === getRowIndex(row)) window.lastSelectedIndex = -1; 
    }
    updateBulkToolbar(); 
    updateSelectAllCheckbox();
}

function toggleRowSelection(row, isSel) { 
    if(isSel) row.classList.add('selected'); 
    else row.classList.remove('selected'); 
}

function getRowIndex(row) { 
    return Array.from(document.querySelectorAll('#assets-body .asset-row')).indexOf(row); 
}

function selectRange(start, end) {
    const [s, e] = start <= end ? [start, end] : [end, start];
    document.querySelectorAll('#assets-body .asset-row').forEach((row, i) => {
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
    updateSelectAllCheckbox();
}

function clearSelection() {
    document.querySelectorAll('#assets-body .asset-checkbox:checked').forEach(cb => { 
        cb.checked = false; 
        toggleRowSelection(cb.closest('tr'), false); 
        window.selectedAssetIds.delete(cb.value); 
    });
    window.lastSelectedIndex = -1; 
    updateBulkToolbar(); 
    updateSelectAllCheckbox();
}

function updateSelectAllCheckbox() {
    const selAll = document.getElementById('select-all'); 
    const cbs = document.querySelectorAll('#assets-body .asset-checkbox');
    const checked = document.querySelectorAll('#assets-body .asset-checkbox:checked').length;
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
    const modalInstance = bootstrap.Modal.getInstance(document.getElementById('bulkDeleteModal'));
    if(modalInstance) modalInstance.show();
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
    clearSelection();
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
    initAssetSelection();
}

// Экспорт для доступа из main.js
window.renderAssets = renderAssets;