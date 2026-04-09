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
    // Подсветка активной группы в дереве
    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));
    const activeNode = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    if (activeNode) activeNode.classList.add('active');
    
    groupId = String(groupId);
    
    // 🔥 Проверка: если мы не на главной странице, перенаправляем на неё
    const currentPage = window.location.pathname;
    if (currentPage !== '/' && !currentPage.endsWith('/index.html')) {
        // Перенаправление на главную с параметром группы
        const url = groupId === 'ungrouped' 
            ? '/?ungrouped=true' 
            : `/?group_id=${parseInt(groupId)}`;
        window.location.href = url;
        return;
    }
    
    // Если мы на главной, просто фильтруем активы (существующее поведение)
    const url = groupId === 'ungrouped' 
        ? '/api/assets?ungrouped=true' 
        : `/api/assets?group_id=${parseInt(groupId)}`;
    
    fetch(url)
        .then(r => r.json())
        .then(data => renderAssets(data))
        .catch(e => console.error(e));
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

// ═══════════════════════════════════════════════════════════════
// ЭКСПОРТ ФУНКЦИЙ В ГЛОБАЛЬНУЮ ОБЛАСТЬ (для inline onclick)
// ═══════════════════════════════════════════════════════════════

function showRenameModal(id) {
    const modalEl = document.getElementById('groupEditModal');
    if (!modalEl) return console.warn('⚠️ #groupEditModal не найден');

    const idInput = document.getElementById('edit-group-id');
    if (idInput) idInput.value = id;

    const nameEl = document.querySelector(`.tree-node[data-id="${id}"] .group-name`);
    const nameInput = document.getElementById('edit-group-name');
    if (nameInput && nameEl) nameInput.value = nameEl.textContent.trim();

    const dynCheck = document.getElementById('edit-group-dynamic');
    if (dynCheck) dynCheck.checked = false;

    const filterSection = document.getElementById('dynamic-filter-section');
    if (filterSection) filterSection.style.display = 'none';

    new bootstrap.Modal(modalEl).show();
}

function showMoveModal(id) {
    const modalEl = document.getElementById('groupMoveModal');
    if (!modalEl) return console.warn('⚠️ #groupMoveModal не найден.');
    document.getElementById('move-group-id').value = id;
    new bootstrap.Modal(modalEl).show();
}

function showDeleteModal(id) {
    const modalEl = document.getElementById('groupDeleteModal');
    if (!modalEl) return console.warn('⚠️ #groupDeleteModal не найден.');
    document.getElementById('delete-group-id').value = id;
    new bootstrap.Modal(modalEl).show();
}

// 🔥 Просмотр результатов с отображением ошибок
async function viewScanResults(id){
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
        
        // 🔥 Показываем ошибку если статус failed
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
            h += '<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Сканирование завершилось с ошибкой. Смотрите детали выше.</div>';
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

// 🔥 Показ полной ошибки в отдельном модальном окне
function showScanError(jobId, errorMsg){
    const m = new bootstrap.Modal(document.getElementById('scanErrorModal'));
    const c = document.getElementById('scan-error-content');
    c.innerHTML = `
        <div class="alert alert-danger">
            <h6><i class="bi bi-exclamation-triangle"></i> Ошибка сканирования #${jobId}:</h6>
            <pre class="mb-0" style="white-space:pre-wrap;max-height:400px;overflow-y:auto">${errorMsg}</pre>
        </div>
        <div class="mt-3">
            <button class="btn btn-sm btn-outline-secondary" onclick="navigator.clipboard.writeText(\`${errorMsg.replace(/`/g, '\\`')}\`)">
                <i class="bi bi-clipboard"></i> Копировать ошибку
            </button>
        </div>
    `;
    m.show();
}

// 🔥 Обновление истории с кликабельной ошибкой
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
                
                // 🔥 Делаем ошибку кликабельной
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

// 🔥 Обновление дерева групп (вызывать после сканирования и при загрузке)
async function refreshGroupTree() {
    try {
        // Получаем актуальное дерево
        const res = await fetch('/api/groups/tree');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        
        // Обновляем счётчик "Без группы"
        const ungroupedRes = await fetch('/api/assets?ungrouped=true');
        const ungroupedAssets = await ungroupedRes.json();
        const ungroupedEl = document.getElementById('ungrouped-count');
        if (ungroupedEl) ungroupedEl.textContent = ungroupedAssets.length;
        
        // Обновляем счётчики у каждой группы в дереве
        data.flat.forEach(g => {
            const node = document.querySelector(`.tree-node[data-id="${g.id}"]`);
            if (node) {
                const badge = node.querySelector('.badge');
                if (badge) {
                    // Плавное обновление числа
                    const oldCount = parseInt(badge.textContent) || 0;
                    const newCount = g.count || 0;
                    if (oldCount !== newCount) {
                        badge.classList.add('bg-warning', 'text-dark');
                        setTimeout(() => {
                            badge.textContent = newCount;
                            badge.classList.remove('bg-warning', 'text-dark');
                        }, 300);
                    }
                }
            }
        });
        
        console.log('✅ Дерево групп обновлено');
    } catch (e) {
        console.warn('⚠️ Ошибка обновления дерева групп:', e);
    }
}

let lastCompletedScans = new Set();

function pollActiveScans(){
    fetch('/api/scans/status').then(r=>r.json()).then(d=>{
        const c=document.getElementById('active-scans');
        
        // 🔥 Проверяем завершённые сканирования
        fetch('/api/scans/history').then(hr=>hr.json()).then(history=>{
            history.forEach(j=>{
                if(j.status === 'completed' && !lastCompletedScans.has(j.id)){
                    lastCompletedScans.add(j.id);
                    // 🔥 Обновляем дерево групп при завершении сканирования
                    refreshGroupTree();
                }
            });
        });
        
        if(d.active?.length){
            let h='<div class="row">';
            d.active.forEach(j=>{
                const cls=j.status==='running'?'progress-bar-striped progress-bar-animated':'';
                const b=j.scan_type==='rustscan'?'bg-danger':'bg-info text-dark';
                const s=j.status==='running'?'bg-warning text-dark':j.status==='paused'?'bg-info text-dark':'bg-secondary';
                h+=`<div class="col-md-6 mb-3"><div class="card border-${j.status==='failed'?'danger':j.status==='running'?'warning':'info'}"><div class="card-body"><div class="d-flex justify-content-between align-items-center mb-2"><h6 class="mb-0"><span class="badge ${b} me-2">${j.scan_type.toUpperCase()}</span>${j.target}</h6><span class="badge ${s}">${j.status}</span></div><div class="progress mb-2" style="height:6px"><div class="progress-bar ${cls}" style="width:${j.progress}%"></div></div><small>${j.current_target&&j.status==='running'?`📡 ${j.current_target}<br>`:''}Прогресс: ${j.progress}%</small></div></div></div>`;
            });
            h+='</div>'; c.innerHTML=h;
        } else c.innerHTML='<p class="text-muted mb-0"><i class="bi bi-check-circle"></i> Нет активных сканирований</p>';
    }).catch(e=>console.warn('⚠️ Active poll error:',e));
}

// 🔥 Отслеживание завершённых сканирований для обновления групп
let lastKnownCompleted = new Set();

function checkCompletedScans() {
    fetch('/api/scans/history')
        .then(r => r.json())
        .then(history => {
            history.forEach(j => {
                // Если сканирование завершено и мы его ещё не обработали
                if (j.status === 'completed' && !lastKnownCompleted.has(j.id)) {
                    lastKnownCompleted.add(j.id);
                    console.log(`🔄 Сканирование #${j.id} завершено, обновляем группы...`);
                    refreshGroupTree();
                }
            });
        })
        .catch(e => console.warn('⚠️ Ошибка проверки сканирований:', e));
}

// В функции pollActiveScans добавьте вызов checkCompletedScans():
function pollActiveScans(){
    fetch('/api/scans/status').then(r=>r.json()).then(d=>{
        // ... существующий код для активных сканирований ...
        
        // 🔥 Проверяем завершённые сканирования
        checkCompletedScans();
        
    }).catch(e=>console.warn('⚠️ Active poll error:',e));
}

// 🔥 Экспорт в глобальную область
window.showRenameModal = showRenameModal;
window.showMoveModal = showMoveModal;
window.showDeleteModal = showDeleteModal;
window.refreshGroupTree = refreshGroupTree;
window.filterByGroup = filterByGroup;