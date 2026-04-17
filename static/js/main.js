// ═══════════════════════════════════════════════════════════════
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
// ═══════════════════════════════════════════════════════════════
let currentGroupId = null; 
let contextMenu = null;
let editModal, createModal, moveModal, deleteModal, bulkDeleteModalInstance;
let lastSelectedIndex = -1; 
let selectedAssetIds = new Set();

const FILTER_FIELDS = [
    { value: 'ip_address', text: 'IP Адрес' }, { value: 'hostname', text: 'Hostname' },
    { value: 'os_info', text: 'ОС (Сканирование)' }, { value: 'device_role', text: 'Роль устройства' },
    { value: 'open_ports', text: 'Открытые порты' }, { value: 'status', text: 'Статус' },
    { value: 'notes', text: 'Заметки' }, { value: 'osquery_status', text: 'Статус OSquery' },
    { value: 'osquery_os', text: 'ОС (OSquery)' }, { value: 'scanners_used', text: 'Сканеры (JSON)' }
];
const FILTER_OPS = [
    { value: 'eq', text: '=' }, { value: 'ne', text: '≠' }, { value: 'like', text: 'содержит' }, { value: 'in', text: 'в списке' }
];

// ═══════════════════════════════════════════════════════════════
// ТЕМА & НАВИГАЦИЯ
// ═══════════════════════════════════════════════════════════════
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const html = document.documentElement; 
    const newTheme = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    document.body.classList.add('theme-transition'); 
    html.setAttribute('data-bs-theme', newTheme); 
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme); 
    setTimeout(() => document.body.classList.remove('theme-transition'), 300);
}

function updateThemeIcon(theme) {
    const toggle = document.querySelector('.theme-toggle'); 
    if (!toggle) return;
    toggle.querySelector('.bi-moon').style.display = theme === 'dark' ? 'none' : 'block';
    toggle.querySelector('.bi-sun').style.display = theme === 'dark' ? 'block' : 'none';
}

function initTreeTogglers() {
    const groupTree = document.getElementById('group-tree'); 
    if (!groupTree) return;
    
    const newGroupTree = groupTree.cloneNode(true); 
    groupTree.parentNode.replaceChild(newGroupTree, groupTree);
    
    newGroupTree.addEventListener('click', function(e) {
        const treeNode = e.target.closest('.tree-node'); 
        if (!treeNode) return;
        
        if (e.target.classList.contains('caret') || e.target.closest('.caret')) {
            e.preventDefault(); 
            e.stopPropagation();
            const nested = treeNode.querySelector(".nested");
            if (nested) { 
                nested.classList.toggle("active"); 
                const caret = treeNode.querySelector('.caret'); 
                if (caret) caret.classList.toggle("caret-down"); 
            }
            return;
        }
        
        filterByGroup(treeNode.dataset.id);
    });

    highlightActiveGroupFromUrl();
}

function highlightActiveGroupFromUrl() {
    const params = new URLSearchParams(window.location.search);
    let targetId = null;
    let isUngrouped = false;

    if (params.has('group_id')) {
        targetId = params.get('group_id');
    } else if (params.has('ungrouped')) {
        isUngrouped = true;
        targetId = 'ungrouped';
    }

    if (!targetId) return;

    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));

    if (isUngrouped) {
        const node = document.querySelector('.tree-node[data-id="ungrouped"]');
        if (node) {
            node.classList.add('active');
            node.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return;
    }

    const activeNode = document.querySelector(`.tree-node[data-id="${targetId}"]`);
    if (activeNode) {
        let parent = activeNode.parentElement;
        while (parent) {
            if (parent.classList.contains('nested')) {
                parent.classList.add('active');
                const parentLi = parent.previousElementSibling;
                if (parentLi && parentLi.querySelector('.caret')) {
                    parentLi.querySelector('.caret').classList.add('caret-down');
                }
            }
            if (parent.id === 'group-tree') break;
            parent = parent.parentElement;
        }

        activeNode.classList.add('active');
        activeNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function filterByGroup(groupId) {
    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));
    const activeNode = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    if (activeNode) activeNode.classList.add('active');
    
    groupId = String(groupId);
    
    const currentPage = window.location.pathname;
    if (currentPage !== '/' && !currentPage.endsWith('/index.html')) {
        const url = groupId === 'ungrouped' 
            ? '/?ungrouped=true' 
            : `/?group_id=${parseInt(groupId)}`;
        window.location.href = url;
        return;
    }
    
    const url = groupId === 'ungrouped' 
        ? '/api/assets?ungrouped=true' 
        : `/api/assets?group_id=${parseInt(groupId)}`;
    
    fetch(url)
        .then(r => r.json())
        .then(data => renderAssets(data))
        .catch(e => console.error(e));
}

// ═══════════════════════════════════════════════════════════════
// УПРАВЛЕНИЕ ГРУППАМИ (СОЗДАНИЕ / РЕДАКТИРОВАНИЕ / CIDR / DYNAMIC)
// ═══════════════════════════════════════════════════════════════

window.showCreateGroupModal = function(parentId = null) {
    // Закрываем заглушку если она вдруг открылась
    const dummyModalEl = document.getElementById('groupCreateModal');
    if(dummyModalEl) {
        const dummyModal = bootstrap.Modal.getInstance(dummyModalEl);
        if(dummyModal) dummyModal.hide();
    }

    const modalEl = document.getElementById('groupEditModal');
    if (!modalEl) return console.error('Modal #groupEditModal not found');

    document.getElementById('groupEditForm').reset();
    document.getElementById('edit-group-id').value = '';
    document.getElementById('groupEditTitle').textContent = 'Новая группа';
    document.getElementById('edit-group-parent').value = parentId || '';
    document.getElementById('edit-group-name').value = '';
    document.getElementById('group-filter-root').innerHTML = '';
    
    document.getElementById('modeManual').checked = true;
    toggleGroupMode(); 

    const modal = new bootstrap.Modal(modalEl);
    modal.show();
};

window.toggleGroupMode = function() {
    const mode = document.querySelector('input[name="groupMode"]:checked').value;
    const secCommon = document.getElementById('sectionCommon');
    const secCidr = document.getElementById('sectionCidr');
    const secDynamic = document.getElementById('sectionDynamic');
    const nameInput = document.getElementById('edit-group-name');
    const parentSelect = document.getElementById('edit-group-parent');

    secCidr.style.display = 'none';
    secDynamic.style.display = 'none';
    
    if (mode === 'manual') {
        secCommon.style.display = 'block';
        nameInput.required = true;
        parentSelect.disabled = false;
    } else if (mode === 'cidr') {
        secCommon.style.display = 'block';
        secCidr.style.display = 'block';
        nameInput.required = false;
        parentSelect.disabled = false;
    } else if (mode === 'dynamic') {
        secCommon.style.display = 'block';
        secDynamic.style.display = 'block';
        nameInput.required = true;
        parentSelect.disabled = false;
        
        if(document.getElementById('group-filter-root').children.length === 0) {
            addDynamicRule();
        }
    }
};

window.addDynamicRule = function(field = '', op = 'eq', value = '') {
    const container = document.getElementById('group-filter-root');
    if(!container) return;
    
    const div = document.createElement('div');
    div.className = 'filter-condition mb-2';
    div.innerHTML = `
        <div class="input-group input-group-sm">
            <select class="form-select rule-field">${FILTER_FIELDS.map(f => `<option value="${f.value}" ${f.value===field?'selected':''}>${f.text}</option>`).join('')}</select>
            <select class="form-select rule-op" style="max-width:100px">${FILTER_OPS.map(o => `<option value="${o.value}" ${o.value===op?'selected':''}>${o.text}</option>`).join('')}</select>
            <input type="text" class="form-control rule-val" value="${value}" placeholder="Значение">
            <button class="btn btn-outline-danger" type="button" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    container.appendChild(div);
};

window.showRenameModal = function(id) {
    const modalEl = document.getElementById('groupEditModal');
    if (!modalEl) return console.warn('⚠️ #groupEditModal не найден');

    const idInput = document.getElementById('edit-group-id');
    if (idInput) idInput.value = id;
    document.getElementById('groupEditTitle').textContent = 'Редактировать группу';

    fetch(`/api/groups/${id}`)
        .then(r => r.json())
        .then(data => {
            const nameInput = document.getElementById('edit-group-name');
            const parentSelect = document.getElementById('edit-group-parent');
            
            if (nameInput) nameInput.value = data.name || '';
            if (parentSelect) parentSelect.value = data.parent_id || '';

            const dynCheck = document.getElementById('modeDynamic');
            const manualCheck = document.getElementById('modeManual');
            
            if (data.is_dynamic || (data.filter_rules && data.filter_rules.length > 0)) {
                dynCheck.checked = true;
                renderGroupFilters(data.filter_rules);
            } else {
                manualCheck.checked = true;
                document.getElementById('group-filter-root').innerHTML = '';
            }
            
            toggleGroupMode();
            new bootstrap.Modal(modalEl).show();
        })
        .catch(err => console.error('Ошибка загрузки данных группы:', err));
};

function renderGroupFilters(rules) {
    const container = document.getElementById('group-filter-root');
    if(!container) return;
    container.innerHTML = '';
    
    if(!rules || rules.length === 0) {
        addDynamicRule();
        return;
    }

    rules.forEach(rule => {
        addDynamicRule(rule.field, rule.op, rule.value);
    });
}

window.showMoveModal = function(id) {
    const modalEl = document.getElementById('groupMoveModal');
    if (!modalEl) return console.warn('⚠️ #groupMoveModal не найден.');
    document.getElementById('move-group-id').value = id;
    
    const select = document.getElementById('move-group-parent');
    select.innerHTML = '<option value="">-- Корень --</option>';
    
    fetch('/api/groups/tree').then(r=>r.json()).then(data => {
        data.flat.forEach(g => {
            if(g.id != id) {
                const opt = document.createElement('option');
                opt.value = g.id;
                opt.textContent = g.name;
                select.appendChild(opt);
            }
        });
        new bootstrap.Modal(modalEl).show();
    });
};

window.showDeleteModal = function(id) {
    const modalEl = document.getElementById('groupDeleteModal');
    if (!modalEl) return console.warn('⚠️ #groupDeleteModal не найден.');
    document.getElementById('delete-group-id').value = id;
    
    const select = document.getElementById('delete-move-assets');
    select.innerHTML = '<option value="">-- Удалить активы вместе с группой --</option>';
    
    fetch('/api/groups/tree').then(r=>r.json()).then(data => {
        data.flat.forEach(g => {
            if(g.id != id) {
                const opt = document.createElement('option');
                opt.value = g.id;
                opt.textContent = g.name;
                select.appendChild(opt);
            }
        });
        new bootstrap.Modal(modalEl).show();
    });
};

// Обработка форм
document.addEventListener('DOMContentLoaded', () => {
    const e = document.getElementById('groupEditModal'); 
    const m = document.getElementById('groupMoveModal');
    const d = document.getElementById('groupDeleteModal'); 
    const b = document.getElementById('bulkDeleteModal');
    
    if(e) editModal = new bootstrap.Modal(e); 
    if(m) moveModal = new bootstrap.Modal(m);
    if(d) deleteModal = new bootstrap.Modal(d); 
    if(b) bulkDeleteModalInstance = new bootstrap.Modal(b);

    // Форма редактирования/создания
    const editForm = document.getElementById('groupEditForm');
    if(editForm) {
        editForm.addEventListener('submit', async (ev) => {
            ev.preventDefault();
            const id = document.getElementById('edit-group-id').value;
            const mode = document.querySelector('input[name="groupMode"]:checked').value;
            const name = document.getElementById('edit-group-name').value;
            const parentId = document.getElementById('edit-group-parent').value;
            
            let payload = {
                name: name,
                parent_id: parentId || null,
                is_dynamic: mode === 'dynamic'
            };

            if (mode === 'cidr') {
                payload.cidr_network = document.getElementById('cidr-network').value;
                payload.cidr_mask = document.getElementById('cidr-mask').value;
                if(!payload.cidr_network) return alert('Введите сеть CIDR');
            }

            if(mode === 'dynamic') {
                const rules = [];
                document.querySelectorAll('#group-filter-root .filter-condition').forEach(cond => {
                    const f = cond.querySelector('.rule-field').value;
                    const o = cond.querySelector('.rule-op').value;
                    const v = cond.querySelector('.rule-val').value;
                    if(f && v) rules.push({field: f, op: o, value: v});
                });
                payload.filter_rules = rules;
                if(rules.length === 0) return alert('Добавьте хотя бы одно правило');
            }

            const url = id ? `/api/groups/${id}` : '/api/groups';
            const method = id ? 'PUT' : 'POST';

            try {
                const res = await fetch(url, {
                    method: method,
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });

                if(res.ok) {
                    editModal.hide();
                    refreshGroupTree();
                } else {
                    const err = await res.json();
                    alert('Ошибка: ' + (err.error || 'Неизвестная ошибка'));
                }
            } catch (e) {
                console.error(e);
                alert('Ошибка сети');
            }
        });
    }

    // Форма перемещения
    const moveForm = document.getElementById('groupMoveForm');
    if(moveForm) {
        moveForm.addEventListener('submit', async (ev) => {
            ev.preventDefault();
            const id = document.getElementById('move-group-id').value;
            const newParent = document.getElementById('move-group-parent').value;

            const res = await fetch(`/api/groups/${id}/move`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ parent_id: newParent || null })
            });

            if(res.ok) {
                moveModal.hide();
                refreshGroupTree();
            } else {
                alert('Ошибка перемещения');
            }
        });
    }
});

// ═══════════════════════════════════════════════════════════════
// ВЫДЕЛЕНИЕ АКТИВОВ
// ═══════════════════════════════════════════════════════════════
function initAssetSelection() {
    const tbody = document.getElementById('assets-body'); if (!tbody) return;
    const selAll = document.getElementById('select-all');
    if(selAll) selAll.addEventListener('change', function() {
        document.querySelectorAll('.asset-checkbox').forEach(cb => {
            cb.checked = this.checked; toggleRowSelection(cb.closest('tr'), this.checked);
            if(this.checked) selectedAssetIds.add(cb.value); else selectedAssetIds.delete(cb.value);
        });
        lastSelectedIndex = this.checked ? getRowIndex(document.querySelectorAll('.asset-checkbox').pop().closest('tr')) : -1;
        updateBulkToolbar(); updateSelectAllCheckbox();
    });
    tbody.addEventListener('change', e => { if(e.target.classList.contains('asset-checkbox')) handleCheckboxChange(e.target); });
    tbody.addEventListener('click', e => {
        const row = e.target.closest('.asset-row'); if(!row || e.target.closest('a, button, .asset-checkbox')) return;
        const cb = row.querySelector('.asset-checkbox');
        if(cb) { if(e.shiftKey && lastSelectedIndex >= 0) { e.preventDefault(); selectRange(lastSelectedIndex, getRowIndex(row)); } else { cb.checked = !cb.checked; handleCheckboxChange(cb); } }
    });
}

function handleCheckboxChange(cb) {
    const row = cb.closest('tr'); const id = cb.value; const checked = cb.checked;
    toggleRowSelection(row, checked);
    if(checked) { selectedAssetIds.add(id); lastSelectedIndex = getRowIndex(row); }
    else { selectedAssetIds.delete(id); if(lastSelectedIndex === getRowIndex(row)) lastSelectedIndex = -1; }
    updateBulkToolbar(); updateSelectAllCheckbox();
}

function toggleRowSelection(row, isSel) { if(isSel) row.classList.add('selected'); else row.classList.remove('selected'); }
function getRowIndex(row) { return Array.from(document.querySelectorAll('#assets-body .asset-row')).indexOf(row); }
function selectRange(start, end) {
    const [s, e] = start <= end ? [start, end] : [end, start];
    document.querySelectorAll('#assets-body .asset-row').forEach((row, i) => {
        if(i >= s && i <= e) {
            const cb = row.querySelector('.asset-checkbox');
            if(cb && !cb.checked) { cb.checked = true; toggleRowSelection(row, true); selectedAssetIds.add(cb.value); }
        }
    }); updateBulkToolbar(); updateSelectAllCheckbox();
}
function clearSelection() {
    document.querySelectorAll('#assets-body .asset-checkbox:checked').forEach(cb => { cb.checked = false; toggleRowSelection(cb.closest('tr'), false); selectedAssetIds.delete(cb.value); });
    lastSelectedIndex = -1; updateBulkToolbar(); updateSelectAllCheckbox();
}
function updateSelectAllCheckbox() {
    const selAll = document.getElementById('select-all'); const cbs = document.querySelectorAll('#assets-body .asset-checkbox');
    const checked = document.querySelectorAll('#assets-body .asset-checkbox:checked').length;
    if(selAll && cbs.length > 0) { selAll.checked = checked === cbs.length; selAll.indeterminate = checked > 0 && checked < cbs.length; }
}
function updateBulkToolbar() {
    const tb = document.getElementById('bulk-toolbar'); const c = selectedAssetIds.size;
    tb.style.display = c > 0 ? 'flex' : 'none'; document.getElementById('selected-count').textContent = c;
}
function confirmBulkDelete() {
    if(selectedAssetIds.size === 0) return;
    document.getElementById('bulk-delete-count').textContent = selectedAssetIds.size;
    if(bulkDeleteModalInstance) bulkDeleteModalInstance.show();
}
async function executeBulkDelete() {
    const ids = Array.from(selectedAssetIds);
    await fetch('/api/assets/bulk-delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids}) });
    clearSelection(); if(bulkDeleteModalInstance) bulkDeleteModalInstance.hide(); location.reload();
}

function createConditionElement() {
    const div = document.createElement('div'); div.className = 'filter-condition'; div.dataset.type = 'condition';
    div.innerHTML = `<input type="text" class="form-control form-control-sm f-field" list="filter-fields-list" placeholder="Поле..." style="width:160px">
        <select class="form-select form-select-sm f-op" style="width:120px">${FILTER_OPS.map(o=>`<option value="${o.value}">${o.text}</option>`).join('')}</select>
        <input type="text" class="form-control form-control-sm f-val" placeholder="Значение" style="flex:1">
        <button class="btn btn-sm btn-outline-danger" onclick="this.parentElement.remove()">×</button>`;
    return div;
}

function initFilterFieldDatalist() {
    if(!document.getElementById('filter-fields-list')) {
        const dl = document.createElement('datalist'); dl.id = 'filter-fields-list';
        dl.innerHTML = FILTER_FIELDS.map(f => `<option value="${f.value}">${f.text}</option>`).join('');
        document.body.appendChild(dl);
    }
}

window.renderAssets = function(data) {
    const tb = document.getElementById('assets-body'); if(!tb) return;
    tb.innerHTML = ''; clearSelection();
    if(data.length===0) { tb.innerHTML='<tr><td colspan="7" class="text-center py-4 text-muted"><i class="bi bi-inbox fs-1 d-block mb-2"></i>Ничего не найдено</td></tr>'; return; }
    data.forEach(a => {
        const tr = document.createElement('tr'); tr.className='asset-row'; tr.dataset.assetId=a.id;
        tr.innerHTML=`<td><input type="checkbox" class="form-check-input asset-checkbox" value="${a.id}"></td>
            <td><a href="/asset/${a.id}"><strong>${a.ip}</strong></a></td><td>${a.hostname||'—'}</td>
            <td><span class="text-muted small">${a.os||'—'}</span></td><td><small class="text-muted">${a.ports||'—'}</small></td>
            <td><span class="badge bg-light text-dark border">${a.group}</span></td>
            <td><a href="/asset/${a.id}" class="btn btn-sm btn-outline-info"><i class="bi bi-eye"></i></a></td>`;
        tb.appendChild(tr);
    });
};

// ═══════════════════════════════════════════════════════════════
// WAZUH
// ═══════════════════════════════════════════════════════════════
document.getElementById('data-source-filter')?.addEventListener('change', function() {
    const p = new URLSearchParams(window.location.search); p.set('data_source', this.value); window.location.search = p.toString();
});
async function saveWazuhConfig() {
    const btn = event.target; btn.disabled = true; btn.textContent = '⏳ Синхронизация...';
    const st = document.getElementById('waz-status');
    const body = { url: document.getElementById('waz-url').value, username: document.getElementById('waz-user').value, password: document.getElementById('waz-pass').value, verify_ssl: document.getElementById('waz-ssl').checked, is_active: document.getElementById('waz-active').checked };
    await fetch('/api/wazuh/config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
    const res = await fetch('/api/wazuh/sync', { method: 'POST' }); const d = await res.json();
    if(res.ok) { st.innerHTML=`<span class="text-success">✅ +${d.new} | обн. ${d.updated}</span>`; setTimeout(()=>location.reload(), 1500); }
    else { st.innerHTML=`<span class="text-danger">❌ ${d.error}</span>`; }
    btn.disabled = false; btn.textContent = '💾 Сохранить и синхронизировать';
}
document.getElementById('wazuhModal')?.addEventListener('show.bs.modal', async () => {
    const c = await (await fetch('/api/wazuh/config')).json();
    document.getElementById('waz-url').value = c.url; document.getElementById('waz-user').value = c.username;
    document.getElementById('waz-pass').value = c.password; document.getElementById('waz-ssl').checked = c.verify_ssl; document.getElementById('waz-active').checked = c.is_active;
});

// ═══════════════════════════════════════════════════════════════
// СКАНИРОВАНИЯ
// ═══════════════════════════════════════════════════════════════
window.viewScanResults = async function(id){
    const m = new bootstrap.Modal(document.getElementById('scanResultsModal'));
    const c = document.getElementById('scan-results-content');
    const errAlert = document.getElementById('scan-error-alert');
    const errText = document.getElementById('scan-error-text');
    
    c.innerHTML = '<div class="text-center"><div class="spinner-border"></div><p class="mt-2">Загрузка...</p></div>';
    errAlert.style.display = 'none';
    m.show();
    
    try{
        const r = await fetch(`/api/scans/${id}/results`);
        const d = await r.json();
        
        if(d.job.status === 'failed' && d.job.error_message){
            errAlert.style.display = 'block';
            errText.textContent = d.job.error_message;
        }
        
        let h = `<h6>#${d.job.id} - ${d.job.scan_type.toUpperCase()}</h6>`;
        h += `<p><strong>Цель:</strong> ${d.job.target}</p>`;
        h += `<p><strong>Статус:</strong> <span class="badge bg-${d.job.status==='completed'?'success':d.job.status==='failed'?'danger':'warning'}">${d.job.status}</span></p>`;
        h += `<p><strong>Прогресс:</strong> ${d.job.progress}%</p>`;
        if(d.job.started_at) h += `<p><strong>Начало:</strong> ${d.job.started_at}</p>`;
        if(d.job.completed_at) h += `<p><strong>Завершение:</strong> ${d.job.completed_at}</p>`;
        h += `<hr>`;
        
        if(d.job.status === 'failed'){
            h += '<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Сканирование завершилось с ошибкой.</div>';
        } else if(d.results.length === 0){
            h += '<p class="text-muted">Нет результатов</p>';
        } else {
            h += `<p><strong>Найдено хостов:</strong> ${d.results.length}</p><div class="list-group">`;
            d.results.forEach(x=>{
                h += `<div class="list-group-item"><div class="d-flex justify-content-between"><h6 class="mb-1">${x.ip}</h6><small>${x.scanned_at}</small></div><p class="mb-1"><strong>Порты:</strong> ${x.ports.join(', ')||'Нет'}</p>${x.os && x.os !== '-' ? `<p class="mb-0"><strong>ОС:</strong> ${x.os}</p>`:''}</div>`;
            });
            h += '</div>';
        }
        c.innerHTML = h;
    }catch(err){ 
        errAlert.style.display = 'block';
        errText.textContent = `Ошибка загрузки результатов: ${err.message}`;
    }
}

window.showScanError = function(jobId, errorMsg){
    const m = new bootstrap.Modal(document.getElementById('scanErrorModal'));
    const c = document.getElementById('scan-error-content');
    const safeMsg = errorMsg.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
    
    c.innerHTML = `
        <div class="alert alert-danger">
            <h6><i class="bi bi-exclamation-triangle"></i> Ошибка сканирования #${jobId}:</h6>
            <pre class="mb-0" style="white-space:pre-wrap;max-height:400px;overflow-y:auto">${safeMsg}</pre>
        </div>
        <div class="mt-3">
            <button class="btn btn-sm btn-outline-secondary" onclick="navigator.clipboard.writeText('${safeMsg}')">
                <i class="bi bi-clipboard"></i> Копировать ошибку
            </button>
        </div>
    `;
    m.show();
}

async function updateScanHistory(){
    try{
        const res = await fetch('/api/scans/history');
        if(!res.ok) return;
        const jobs = await res.json();
        const tbody = document.querySelector('#history-table tbody');
        if(!tbody) return;

        jobs.forEach(j=>{
            const row = document.getElementById(`scan-row-${j.id}`);
            if(!row) return;
            
            const badge = row.querySelector('.status-badge');
            if(badge){
                badge.textContent = j.status;
                badge.className = `badge status-badge bg-${j.status==='running'?'warning text-dark':j.status==='completed'?'success':'danger'}`;
                
                if(j.error_message){
                    badge.style.cursor = 'pointer';
                    badge.setAttribute('title', 'Нажмите для просмотра детали ошибки');
                    badge.onclick = () => showScanError(j.id, j.error_message);
                } else {
                    badge.style.cursor = 'default';
                    badge.removeAttribute('onclick');
                }
            }
            const bar = row.querySelector('.progress-bar');
            const txt = row.querySelector('.progress-text');
            if(bar) bar.style.width = `${j.progress}%`;
            if(txt) txt.textContent = `${j.progress}%`;
        });
    }catch(e){console.warn('History poll error:',e);}
}

// ═══════════════════════════════════════════════════════════════
// ОБНОВЛЕНИЕ ДЕРЕВА ГРУПП
// ═══════════════════════════════════════════════════════════════
async function refreshGroupTree() {
    try {
        const res = await fetch('/api/groups/tree');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        
        // Обновляем счётчик "Без группы"
        const ungroupedRes = await fetch('/api/assets?ungrouped=true');
        const ungroupedAssets = await ungroupedRes.json();
        const ungroupedEl = document.getElementById('ungrouped-count');
        if (ungroupedEl) ungroupedEl.textContent = ungroupedAssets.length;
        
        const treeContainer = document.getElementById('group-tree');
        if(treeContainer && data.flat) {
             let html = '';
             const roots = data.flat.filter(g => !g.parent_id);
             
             function buildNode(g, level) {
                 const children = data.flat.filter(c => c.parent_id == g.id);
                 const hasChildren = children.length > 0;
                 const caret = hasChildren ? '<i class="bi bi-caret-right caret"></i>' : '<i class="bi bi-dot"></i>';
                 
                 // 🔥 Добавляем кнопки действий
                 const actionsHtml = `
                    <div class="group-actions">
                        <button class="btn-action btn-sm text-muted" onclick="event.stopPropagation(); showRenameModal(${g.id})" title="Редактировать">
                            <i class="bi bi-pencil-square"></i>
                        </button>
                        <button class="btn-action btn-sm text-muted" onclick="event.stopPropagation(); showMoveModal(${g.id})" title="Переместить">
                            <i class="bi bi-arrow-move"></i>
                        </button>
                        <button class="btn-action btn-sm text-danger" onclick="event.stopPropagation(); showDeleteModal(${g.id})" title="Удалить">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                 `;

                 let nodeHtml = `
                    <div class="tree-node" data-id="${g.id}" style="padding-left:${10 + level*15}px; display:flex; justify-content:space-between; align-items:center;">
                        <div style="display:flex; align-items:center; flex:1;">
                            ${caret} 
                            <span class="group-name ms-2">${g.name}</span> 
                        </div>
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span class="badge bg-secondary">${g.count||0}</span>
                            ${actionsHtml}
                        </div>
                    </div>
                 `;
                 
                 if(hasChildren) {
                     nodeHtml += `<ul class="nested">`;
                     children.forEach(c => nodeHtml += buildNode(c, level+1));
                     nodeHtml += `</ul>`;
                 }
                 return nodeHtml;
             }

             html = '<ul style="list-style:none; padding:0; margin:0;">';
             roots.forEach(r => html += buildNode(r, 0));
             html += '</ul>';
             
             // Добавляем "Без группы" (без кнопок удаления/перемещения)
             html += `<div class="tree-node" data-id="ungrouped" style="padding-left:10px; margin-top:10px; border-top:1px solid var(--border-color); display:flex; justify-content:space-between;">
                <div><i class="bi bi-folder-minus"></i> <span class="group-name ms-2">Без группы</span></div>
                <span id="ungrouped-count" class="badge bg-secondary">${ungroupedAssets.length}</span>
             </div>`;

             treeContainer.innerHTML = html;
             initTreeTogglers(); // Перевешиваем слушатели кликов
        }
        
    } catch (e) {
        console.warn('⚠️ Ошибка обновления дерева групп:', e);
    }
}

// Поллинг активных сканирований
function pollActiveScans(){
    fetch('/api/scans/status').then(r=>r.json()).then(d=>{
        const c = document.getElementById('active-scans');
        
        if (!c) return; // Защита от ошибки если элемента нет на странице

        if(d.active?.length){
            let h='<div class="row">';
            d.active.forEach(j=>{
                const cls=j.status==='running'?'progress-bar-striped progress-bar-animated':'';
                const b=j.scan_type==='rustscan'?'bg-danger':'bg-info text-dark';
                const s=j.status==='running'?'bg-warning text-dark':j.status==='paused'?'bg-info text-dark':'bg-secondary';
                h+=`<div class="col-md-12 mb-2"><div class="card border-${j.status==='failed'?'danger':j.status==='running'?'warning':'info'}"><div class="card-body p-2"><div class="d-flex justify-content-between align-items-center mb-1"><h6 class="mb-0 small"><span class="badge ${b} me-1">${j.scan_type.toUpperCase()}</span>${j.target}</h6><span class="badge ${s} small">${j.status}</span></div><div class="progress mb-1" style="height:4px"><div class="progress-bar ${cls}" style="width:${j.progress}%"></div></div><small class="text-muted" style="font-size:0.7rem">Прогресс: ${j.progress}%</small></div></div></div>`;
            });
            h+='</div>';
            c.innerHTML = h;
        } else {
            c.innerHTML='<p class="text-muted mb-0 small"><i class="bi bi-check-circle"></i> Нет активных сканирований</p>';
        }
        
        checkCompletedScans();
    }).catch(e=>console.warn('⚠️ Active poll error:',e));
}

let lastKnownCompleted = new Set();
function checkCompletedScans() {
    fetch('/api/scans/history')
        .then(r => r.json())
        .then(history => {
            history.forEach(j => {
                if (j.status === 'completed' && !lastKnownCompleted.has(j.id)) {
                    lastKnownCompleted.add(j.id);
                    refreshGroupTree();
                }
            });
        })
        .catch(e => console.warn('⚠️ Ошибка проверки сканирований:', e));
}

// ═══════════════════════════════════════════════════════════════
// ИНИЦИАЛИЗАЦИЯ
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    initTheme(); 
    initFilterFieldDatalist(); 
    initTreeTogglers(); 
    initAssetSelection();
    
    contextMenu = document.getElementById('group-context-menu');
    
    setInterval(pollActiveScans, 5000);
    pollActiveScans();

    document.addEventListener('keydown', e => { 
        if(e.ctrlKey && e.key==='a' && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) { 
            e.preventDefault(); 
            document.querySelectorAll('#assets-body .asset-checkbox').forEach(cb => { 
                cb.checked=true; 
                toggleRowSelection(cb.closest('tr'),true); 
                selectedAssetIds.add(cb.value); 
            }); 
            updateBulkToolbar(); 
            updateSelectAllCheckbox(); 
        } 
    });
});

// Функция подтверждения удаления группы (вызывается из HTML onclick)
window.confirmDeleteGroup = function() {
    const groupId = document.getElementById('delete-group-id').value;
    const moveToId = document.getElementById('delete-move-assets').value;
    
    // Закрываем модальное окно вручную, так как кнопка не внутри формы submit
    const modalEl = document.getElementById('groupDeleteModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();

    fetch(`/api/groups/${groupId}`, {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ move_to_id: moveToId || null })
    })
    .then(response => {
        if (response.ok) {
            refreshGroupTree();
            // Если удалили текущую группу, сбросить фильтр
            if (currentGroupId == groupId) {
                currentGroupId = null;
                loadAssets(); 
            }
        } else {
            alert('Ошибка при удалении группы');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ошибка сети');
    });
};