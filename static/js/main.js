// ═══════════════════════════════════════════════════════════════
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
// ═══════════════════════════════════════════════════════════════
let currentGroupId = null; let contextMenu = null;
let editModal, moveModal, deleteModal, bulkDeleteModalInstance;
let lastSelectedIndex = -1; let selectedAssetIds = new Set();

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
// ТЕМА & ГРУППЫ
// ═══════════════════════════════════════════════════════════════
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
    updateThemeIcon(savedTheme);
}
function toggleTheme() {
    const html = document.documentElement; const newTheme = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    document.body.classList.add('theme-transition'); html.setAttribute('data-bs-theme', newTheme); localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme); setTimeout(() => document.body.classList.remove('theme-transition'), 300);
}
function updateThemeIcon(theme) {
    const toggle = document.querySelector('.theme-toggle'); if (!toggle) return;
    toggle.querySelector('.bi-moon').style.display = theme === 'dark' ? 'none' : 'block';
    toggle.querySelector('.bi-sun').style.display = theme === 'dark' ? 'block' : 'none';
}
function initTreeTogglers() {
    const groupTree = document.getElementById('group-tree'); if (!groupTree) return;
    const newGroupTree = groupTree.cloneNode(true); groupTree.parentNode.replaceChild(newGroupTree, groupTree);
    newGroupTree.addEventListener('click', function(e) {
        const treeNode = e.target.closest('.tree-node'); if (!treeNode) return;
        if (e.target.classList.contains('caret') || e.target.closest('.caret')) {
            e.preventDefault(); e.stopPropagation();
            const nested = treeNode.querySelector(".nested");
            if (nested) { nested.classList.toggle("active"); const caret = treeNode.querySelector('.caret'); if (caret) caret.classList.toggle("caret-down"); }
            return;
        }
        filterByGroup(treeNode.dataset.id);
    });
}
function filterByGroup(groupId) {
    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));
    const activeNode = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    if (activeNode) activeNode.classList.add('active');
    fetch(`/api/assets?group_id=${groupId === 'ungrouped' ? '' : groupId}&ungrouped=${groupId === 'ungrouped'}`)
        .then(r => r.json()).then(data => renderAssets(data)).catch(console.error);
}

// ═══════════════════════════════════════════════════════════════
// ВЫДЕЛЕНИЕ & ФИЛЬТРЫ
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

// ═══════════════════════════════════════════════════════════════
// КОНСТРУКТОР ФИЛЬТРОВ
// ═══════════════════════════════════════════════════════════════
function createConditionElement() {
    const div = document.createElement('div'); div.className = 'filter-condition'; div.dataset.type = 'condition';
    div.innerHTML = `<input type="text" class="form-control form-control-sm f-field" list="filter-fields-list" placeholder="Поле..." style="width:160px">
        <select class="form-select form-select-sm f-op" style="width:120px">${FILTER_OPS.map(o=>`<option value="${o.value}">${o.text}</option>`).join('')}</select>
        <input type="text" class="form-control form-control-sm f-val" placeholder="Значение" style="flex:1">
        <button class="btn btn-sm btn-outline-danger" onclick="this.parentElement.remove()">×</button>`;
    return div;
}
function createGroupElement() {
    const g = document.createElement('div'); g.className = 'filter-group'; g.dataset.type = 'group';
    g.innerHTML = `<div class="d-flex justify-content-between mb-2"><span class="badge bg-primary" onclick="this.textContent=this.textContent==='AND'?'OR':'AND'">AND</span><button class="btn btn-sm btn-close" onclick="this.closest('.filter-group').remove()"></button></div><div class="filter-group-content"></div><button class="btn btn-xs btn-outline-primary mt-1" onclick="this.closest('.filter-group').querySelector('.filter-group-content').appendChild(createConditionElement())">+ Условие</button>`;
    return g;
}
function initFilterRoot() {
    const r = document.getElementById('filter-root');
    if(r && !r.querySelector('.filter-group-content')) { r.innerHTML = '<div class="filter-group-content"></div>'; r.appendChild(createConditionElement()); }
}
function initFilterFieldDatalist() {
    if(!document.getElementById('filter-fields-list')) {
        const dl = document.createElement('datalist'); dl.id = 'filter-fields-list';
        dl.innerHTML = FILTER_FIELDS.map(f => `<option value="${f.value}">${f.text}</option>`).join('');
        document.body.appendChild(dl);
    }
}
function buildFilterJSON() {
    const root = document.getElementById('filter-root'); if(!root) return {logic:'AND', conditions:[]};
    const logic = root.querySelector('.badge')?.textContent || 'AND'; const conds = [];
    root.querySelectorAll('.filter-condition').forEach(c => {
        conds.push({field: c.querySelector('.f-field').value.trim(), op: c.querySelector('.f-op').value, value: c.querySelector('.f-val').value.trim()});
    });
    return {logic, conditions: conds};
}
function applyFilters() {
    const valid = new Set(FILTER_FIELDS.map(f=>f.value)); let err = false;
    document.querySelectorAll('.filter-condition').forEach(c => {
        const v = c.querySelector('.f-field').value.trim();
        if(!valid.has(v)) { c.classList.add('border-danger'); err = true; } else c.classList.remove('border-danger');
    });
    if(err) { alert('⚠️ Проверьте имена полей.'); return; }
    fetch(`/api/assets?filters=${encodeURIComponent(JSON.stringify(buildFilterJSON()))}`).then(r=>r.json()).then(renderAssets);
}
function resetFilters() { document.getElementById('filter-root').querySelector('.filter-group-content').innerHTML = ''; document.getElementById('filter-root').appendChild(createConditionElement()); loadAssets(); }
function loadAssets() { fetch('/api/assets').then(r=>r.json()).then(renderAssets); }

// ═══════════════════════════════════════════════════════════════
// РЕНДЕР & МОДАЛКИ
// ═══════════════════════════════════════════════════════════════
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
// WAZUH & ПРОФИЛИ
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
// ИНИЦИАЛИЗАЦИЯ
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    initTheme(); initFilterFieldDatalist(); initTreeTogglers(); initFilterRoot(); initAssetSelection();
    contextMenu = document.getElementById('group-context-menu');
    const e = document.getElementById('groupEditModal'); const m = document.getElementById('groupMoveModal');
    const d = document.getElementById('groupDeleteModal'); const b = document.getElementById('bulkDeleteModal');
    if(e) editModal = new bootstrap.Modal(e); if(m) moveModal = new bootstrap.Modal(m);
    if(d) deleteModal = new bootstrap.Modal(d); if(b) bulkDeleteModalInstance = new bootstrap.Modal(b);
    document.addEventListener('keydown', e => { if(e.ctrlKey && e.key==='a' && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) { e.preventDefault(); document.querySelectorAll('#assets-body .asset-checkbox').forEach(cb => { cb.checked=true; toggleRowSelection(cb.closest('tr'),true); selectedAssetIds.add(cb.value); }); updateBulkToolbar(); updateSelectAllCheckbox(); } });
});
