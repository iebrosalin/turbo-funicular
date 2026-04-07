// ═══════════════════════════════════════════════════════════════
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
// ═══════════════════════════════════════════════════════════════

let currentGroupId = null;
let contextMenu = null;
let editModal, moveModal, deleteModal, bulkDeleteModalInstance;
let lastSelectedIndex = -1;
let selectedAssetIds = new Set();

const FILTER_FIELDS = [
    { value: 'ip_address', text: 'IP Адрес' },
    { value: 'hostname', text: 'Hostname' },
    { value: 'os_info', text: 'ОС' },
    { value: 'open_ports', text: 'Порты' },
    { value: 'status', text: 'Статус' },
    { value: 'notes', text: 'Заметки' }
];

const FILTER_OPS = [
    { value: 'eq', text: '=' },
    { value: 'ne', text: '≠' },
    { value: 'like', text: 'содержит' },
    { value: 'in', text: 'в списке' }
];

// ═══════════════════════════════════════════════════════════════
// ТЕМА
// ═══════════════════════════════════════════════════════════════

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    const html = document.documentElement;
    html.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-bs-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.body.classList.add('theme-transition');
    html.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
    
    setTimeout(() => {
        document.body.classList.remove('theme-transition');
    }, 300);
}

function updateThemeIcon(theme) {
    const toggle = document.querySelector('.theme-toggle');
    if (!toggle) return;
    const moonIcon = toggle.querySelector('.bi-moon');
    const sunIcon = toggle.querySelector('.bi-sun');
    if (theme === 'dark') {
        moonIcon.style.display = 'none';
        sunIcon.style.display = 'block';
    } else {
        moonIcon.style.display = 'block';
        sunIcon.style.display = 'none';
    }
}

// ═══════════════════════════════════════════════════════════════
// ДЕРЕВО ГРУПП
// ═══════════════════════════════════════════════════════════════

function initTreeTogglers() {
    const groupTree = document.getElementById('group-tree');
    if (!groupTree) return;
    
    const newGroupTree = groupTree.cloneNode(true);
    groupTree.parentNode.replaceChild(newGroupTree, groupTree);
    
    newGroupTree.addEventListener('click', function(e) {
        const treeNode = e.target.closest('.tree-node');
        if (!treeNode) return;
        
        const groupId = treeNode.dataset.id;
        
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
        
        filterByGroup(groupId);
    });
}


// ═══════════════════════════════════════════════════════════════
// КОНТЕКСТНОЕ МЕНЮ
// ═══════════════════════════════════════════════════════════════

function attachContextMenuListeners() {
    if (!contextMenu) return;
    
    document.addEventListener('contextmenu', (e) => {
        const node = e.target.closest('.tree-node');
        if (node) {
            e.preventDefault();
            currentGroupId = node.dataset.id;
            contextMenu.style.display = 'block';
            contextMenu.style.left = `${e.pageX}px`;
            contextMenu.style.top = `${e.pageY}px`;
            
            const rect = contextMenu.getBoundingClientRect();
            if (rect.right > window.innerWidth) contextMenu.style.left = `${e.pageX - rect.width}px`;
            if (rect.bottom > window.innerHeight) contextMenu.style.top = `${e.pageY - rect.height}px`;
        } else {
            contextMenu.style.display = 'none';
        }
    });
}

document.addEventListener('click', () => {
    if (contextMenu) contextMenu.style.display = 'none';
});

// ═══════════════════════════════════════════════════════════════
// API ЗАПРОСЫ
// ═══════════════════════════════════════════════════════════════

async function apiCreateGroup(name, parentId, filterQuery) {
    const res = await fetch('/api/groups', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, parent_id: parentId, filter_query: filterQuery})
    });
    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed');
    }
    return await res.json();
}

async function apiUpdateGroup(id, data) {
    const res = await fetch(`/api/groups/${id}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed');
    }
    return await res.json();
}

async function apiDeleteGroup(id, moveToId) {
    const url = moveToId ? `/api/groups/${id}?move_to=${moveToId}` : `/api/groups/${id}`;
    const res = await fetch(url, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed');
    return await res.json();
}

async function loadGroupsTree() {
    try {
        const res = await fetch('/api/groups/tree');
        if (!res.ok) throw new Error('Failed');
        return await res.json();
    } catch (error) {
        alert('Ошибка загрузки дерева групп');
        return { tree: [], flat: [] };
    }
}

// ═══════════════════════════════════════════════════════════════
// МОДАЛЬНЫЕ ОКНА
// ═══════════════════════════════════════════════════════════════

function showCreateGroupModal(parentId) {
    document.getElementById('edit-group-id').value = '';
    document.getElementById('edit-group-name').value = '';
    document.getElementById('edit-group-parent').value = parentId || '';
    document.getElementById('groupEditTitle').textContent = parentId ? 'Новая подгруппа' : 'Новая группа';
    document.getElementById('edit-group-dynamic').checked = false;
    document.getElementById('dynamic-filter-section').style.display = 'none';
    initGroupFilterRoot();
    if (editModal) editModal.show();
}

function showRenameModal(id) {
    const node = document.querySelector(`.group-item[data-group-id="${id}"]`);
    if (!node) {
        console.error('Группа не найдена:', id);
        return;
    }

    // Получаем имя группы из текста элемента (убираем скобки с количеством, если есть)
    const nameElement = node.querySelector('.group-name');
    let currentName = nameElement ? nameElement.textContent.trim() : '';
    
    // Очищаем от бейджа количества (например "  (5)")
    const badge = node.querySelector('.badge');
    if (badge && currentName.includes(badge.textContent)) {
        currentName = currentName.replace(badge.textContent, '').trim();
    }

    // Заполняем форму
    document.getElementById('edit-group-id').value = id;
    document.getElementById('edit-group-name').value = currentName;
    
    // Сбрасываем родительскую группу для редактирования (оставляем текущую или корень, если нужно менять)
    // Для простого переименования можно оставить текущее значение родителя или сбросить
    const currentParentId = node.dataset.parentId || ''; 
    document.getElementById('edit-group-parent').value = currentParentId;

    document.getElementById('groupEditTitle').textContent = 'Редактировать группу';
    
    // Сбрасываем чекбокс динамической группы и скрываем секцию фильтров для простого режима
    // (Если нужно редактировать фильтры, логика должна быть сложнее, но для переименования так проще)
    document.getElementById('edit-group-dynamic').checked = false;
    document.getElementById('dynamic-filter-section').style.display = 'none';
    
    // Инициализируем пустой фильтр, чтобы форма была валидной при сохранении
    initGroupFilterRoot(); 

    if (editModal) {
        editModal.show();
    } else {
        console.error('Модальное окно editModal не инициализировано');
    }
}

const groupEditForm = document.getElementById('groupEditForm');
if (groupEditForm) {
    groupEditForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const id = document.getElementById('edit-group-id').value;
            const name = document.getElementById('edit-group-name').value;
            const parentId = document.getElementById('edit-group-parent').value;
            const isDynamic = document.getElementById('edit-group-dynamic').checked;
            
            let filterQuery = null;
            if (isDynamic) {
                const filterStruct = buildGroupFilterJSON();
                if (filterStruct.conditions && filterStruct.conditions.length > 0) {
                    filterQuery = JSON.stringify(filterStruct);
                }
            }
            
            if (id) {
                await apiUpdateGroup(id, { name, parent_id: parentId || null, filter_query: filterQuery });
            } else {
                await apiCreateGroup(name, parentId || null, filterQuery);
            }
            
            if (editModal) editModal.hide();
            location.reload();
        } catch (error) {
            alert(`Ошибка: ${error.message}`);
        }
    });
}

async function showMoveModal(id) {
    const data = await loadGroupsTree();
    const select = document.getElementById('move-group-parent');
    select.innerHTML = '<option value="">-- Корень --</option>';
    
    data.flat.forEach(g => {
        if (g.id != id) {
            const opt = document.createElement('option');
            opt.value = g.id;
            opt.textContent = g.name;
            select.appendChild(opt);
        }
    });
    
    document.getElementById('move-group-id').value = id;
    if (moveModal) moveModal.show();
}

const groupMoveForm = document.getElementById('groupMoveForm');
if (groupMoveForm) {
    groupMoveForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const id = document.getElementById('move-group-id').value;
            const parentId = document.getElementById('move-group-parent').value;
            await apiUpdateGroup(id, {parent_id: parentId});
            if (moveModal) moveModal.hide();
            location.reload();
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    });
}

async function showDeleteModal(id) {
    document.getElementById('delete-group-id').value = id;
    const data = await loadGroupsTree();
    const select = document.getElementById('delete-move-assets');
    select.innerHTML = '<option value="">-- Не переносить --</option>';
    
    data.flat.forEach(g => {
        if (g.id != id) {
            const opt = document.createElement('option');
            opt.value = g.id;
            opt.textContent = g.name;
            select.appendChild(opt);
        }
    });
    
    if (deleteModal) deleteModal.show();
}

async function confirmDeleteGroup() {
    try {
        const id = document.getElementById('delete-group-id').value;
        const moveTo = document.getElementById('delete-move-assets').value;
        await apiDeleteGroup(id, moveTo || null);
        if (deleteModal) deleteModal.hide();
        location.reload();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// ═══════════════════════════════════════════════════════════════
// ВЫДЕЛЕНИЕ АКТИВОВ
// ═══════════════════════════════════════════════════════════════

function initAssetSelection() {
    const tbody = document.getElementById('assets-body');
    if (!tbody) return;
    
    const selectAllCheckbox = document.getElementById('select-all');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const checkboxes = tbody.querySelectorAll('.asset-checkbox');
            const isChecked = this.checked;
            
            checkboxes.forEach(cb => {
                cb.checked = isChecked;
                toggleRowSelection(cb.closest('tr'), isChecked);
                if (isChecked) selectedAssetIds.add(cb.value);
                else selectedAssetIds.delete(cb.value);
            });
            
            if (isChecked && checkboxes.length > 0) {
                lastSelectedIndex = getRowIndex(checkboxes[checkboxes.length - 1].closest('tr'));
            } else {
                lastSelectedIndex = -1;
            }
            
            updateBulkToolbar();
            updateSelectAllCheckbox();
        });
    }
    
    tbody.addEventListener('change', (e) => {
        if (e.target.classList.contains('asset-checkbox')) {
            handleCheckboxChange(e.target);
        }
    });
    
    tbody.addEventListener('mousedown', (e) => {
        const row = e.target.closest('.asset-row');
        if (!row) return;
        if (e.shiftKey && !e.target.closest('a, button, .asset-checkbox, input, select, textarea')) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }
    });
    
    tbody.addEventListener('click', (e) => {
        const row = e.target.closest('.asset-row');
        if (!row) return;
        if (e.target.closest('a, button, .asset-checkbox')) return;
        const checkbox = row.querySelector('.asset-checkbox');
        if (checkbox) {
            if (e.shiftKey && lastSelectedIndex >= 0) {
                e.preventDefault();
                selectRange(lastSelectedIndex, getRowIndex(row));
            } else {
                checkbox.checked = !checkbox.checked;
                handleCheckboxChange(checkbox);
            }
        }
    });
}

function handleCheckboxChange(checkbox) {
    const row = checkbox.closest('tr');
    const assetId = checkbox.value;
    const isChecked = checkbox.checked;
    
    toggleRowSelection(row, isChecked);
    
    if (isChecked) {
        selectedAssetIds.add(assetId);
        lastSelectedIndex = getRowIndex(row);
    } else {
        selectedAssetIds.delete(assetId);
        if (lastSelectedIndex === getRowIndex(row)) lastSelectedIndex = -1;
    }
    
    updateBulkToolbar();
    updateSelectAllCheckbox();
}

function toggleRowSelection(row, isSelected) {
    if (isSelected) row.classList.add('selected');
    else row.classList.remove('selected');
}

function getRowIndex(row) {
    const rows = Array.from(document.querySelectorAll('#assets-body .asset-row'));
    return rows.indexOf(row);
}

function selectRange(startIndex, endIndex) {
    const [start, end] = startIndex <= endIndex ? [startIndex, endIndex] : [endIndex, startIndex];
    const rows = document.querySelectorAll('#assets-body .asset-row');
    for (let i = start; i <= end; i++) {
        if (rows[i]) {
            const checkbox = rows[i].querySelector('.asset-checkbox');
            if (checkbox && !checkbox.checked) {
                checkbox.checked = true;
                toggleRowSelection(rows[i], true);
                selectedAssetIds.add(checkbox.value);
            }
        }
    }
    updateBulkToolbar();
    updateSelectAllCheckbox();
}

function selectAllVisibleAssets() {
    const checkboxes = document.querySelectorAll('#assets-body .asset-checkbox');
    checkboxes.forEach(cb => {
        if (!cb.checked) {
            cb.checked = true;
            toggleRowSelection(cb.closest('tr'), true);
            selectedAssetIds.add(cb.value);
        }
    });
    updateBulkToolbar();
    updateSelectAllCheckbox();
}

function clearSelection() {
    const checkboxes = document.querySelectorAll('#assets-body .asset-checkbox:checked');
    checkboxes.forEach(cb => {
        cb.checked = false;
        toggleRowSelection(cb.closest('tr'), false);
        selectedAssetIds.delete(cb.value);
    });
    selectedAssetIds.clear();
    lastSelectedIndex = -1;
    updateBulkToolbar();
    updateSelectAllCheckbox();
}

function updateSelectAllCheckbox() {
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('#assets-body .asset-checkbox');
    const checkedCount = document.querySelectorAll('#assets-body .asset-checkbox:checked').length;
    if (selectAll && checkboxes.length > 0) {
        selectAll.checked = checkedCount === checkboxes.length;
        selectAll.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
    }
}

function updateBulkToolbar() {
    const toolbar = document.getElementById('bulk-toolbar');
    const countBadge = document.getElementById('selected-count');
    const count = selectedAssetIds.size;
    if (count > 0) {
        toolbar.style.display = 'flex';
        countBadge.textContent = count;
    } else {
        toolbar.style.display = 'none';
        countBadge.textContent = '0';
    }
}

// ═══════════════════════════════════════════════════════════════
// МАССОВОЕ УДАЛЕНИЕ
// ═══════════════════════════════════════════════════════════════

function confirmBulkDelete() {
    if (selectedAssetIds.size === 0) return;
    const preview = document.getElementById('bulk-delete-preview');
    const countEl = document.getElementById('bulk-delete-count');
    countEl.textContent = selectedAssetIds.size;
    
    const ids = Array.from(selectedAssetIds).slice(0, 5);
    let previewHtml = '<ul class="list-unstyled mb-0">';
    ids.forEach(id => {
        const row = document.querySelector(`.asset-row[data-asset-id="${id}"]`);
        if (row) {
            const ip = row.querySelector('td:nth-child(2)')?.textContent || `ID: ${id}`;
            previewHtml += `<li>• ${ip}</li>`;
        }
    });
    if (selectedAssetIds.size > 5) {
        previewHtml += `<li class="text-muted">... и ещё ${selectedAssetIds.size - 5}</li>`;
    }
    previewHtml += '</ul>';
    preview.innerHTML = previewHtml;
    
    if (bulkDeleteModalInstance) bulkDeleteModalInstance.show();
}

async function executeBulkDelete() {
    const ids = Array.from(selectedAssetIds);
    try {
        ids.forEach(id => {
            const row = document.querySelector(`.asset-row[data-asset-id="${id}"]`);
            if (row) row.classList.add('deleting');
        });
        
        const res = await fetch('/api/assets/bulk-delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ids})
        });
        
        if (!res.ok) throw new Error('Failed');
        const result = await res.json();
        
        ids.forEach(id => {
            const row = document.querySelector(`.asset-row[data-asset-id="${id}"]`);
            if (row) row.remove();
        });
        
        clearSelection();
        if (bulkDeleteModalInstance) bulkDeleteModalInstance.hide();
        showFlashMessage(`Удалено активов: ${result.deleted}`, 'success');
        checkEmptyState();
    } catch (error) {
        showFlashMessage('Ошибка при удалении', 'danger');
        document.querySelectorAll('.asset-row.deleting').forEach(row => row.classList.remove('deleting'));
    }
}

function showFlashMessage(text, category) {
    const alert = document.createElement('div');
    alert.className = `alert alert-${category} alert-dismissible fade show alert-fixed`;
    alert.innerHTML = `${text}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    document.body.appendChild(alert);
    setTimeout(() => { if (alert.parentNode) alert.remove(); }, 3000);
}

function checkEmptyState() {
    const tbody = document.getElementById('assets-body');
    const emptyState = document.getElementById('empty-state');
    const rows = tbody?.querySelectorAll('.asset-row');
    if (emptyState && rows && rows.length === 0) {
        emptyState.style.display = 'block';
    } else if (emptyState) {
        emptyState.style.display = 'none';
    }
}

// === ВЫДЕЛЕНИЕ ГРУППЫ ПО УМОЛЧАНИЮ ===
function setDefaultGroupSelection() {
    // Снимаем все выделения
    document.querySelectorAll('.group-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // 🔥 Выделяем "Без группы" по умолчанию 🔥
    const ungroupedItem = document.querySelector('[data-group-id="ungrouped"]');
    if (ungroupedItem) {
        ungroupedItem.classList.add('active');
        console.log('✅ Default selection: "Без группы"');
    }
}

// === ОТРИСОВКА АКТИВОВ (ГЛОБАЛЬНАЯ ФУНКЦИЯ) ===
window.renderAssets = function(data) {
    const tbody = document.getElementById('assets-body');
    if (!tbody) {
        console.error('❌ assets-body element not found!');
        return;
    }
    
    console.log('🎨 Rendering', data.length, 'assets');
    
    clearSelection();
    lastSelectedIndex = -1;
    
    tbody.innerHTML = '';
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted"><i class="bi bi-inbox fs-1 d-block mb-2"></i>Ничего не найдено</td></tr>';
        return;
    }
    
    data.forEach(a => {
        const tr = document.createElement('tr');
        tr.className = 'asset-row';
        tr.setAttribute('data-asset-id', a.id);
        tr.innerHTML = `
            <td><input type="checkbox" class="form-check-input asset-checkbox" value="${a.id}"></td>
            <td><a href="/asset/${a.id}" class="text-decoration-none"><strong>${a.ip}</strong></a></td>
            <td>${a.hostname}</td>
            <td><span class="badge bg-info text-dark">${a.os}</span></td>
            <td><small class="text-muted">${a.ports}</small></td>
            <td><span class="badge bg-secondary">${a.group}</span></td>
            <td>
                <a href="/asset/${a.id}" class="btn btn-sm btn-outline-info" title="Подробно"><i class="bi bi-eye"></i></a>
                <a href="/asset/${a.id}/delete" class="btn btn-sm btn-outline-danger" onclick="return confirm('Удалить?')"><i class="bi bi-trash"></i></a>
            </td>
        `;
        tbody.appendChild(tr);
    });
    
    checkEmptyState();
    console.log('✅ Assets rendered successfully');
};

// ═══════════════════════════════════════════════════════════════
// ОСНОВНЫЕ ФУНКЦИИ
// ═══════════════════════════════════════════════════════════════

function applyFilters() {
    const structure = buildFilterJSON();
    const jsonStr = JSON.stringify(structure);
    fetch(`/api/assets?filters=${encodeURIComponent(jsonStr)}`)
        .then(r => r.json())
        .then(data => renderAssets(data));
}

function resetFilters() {
    const root = document.getElementById('filter-root');
    if (root) {
        root.dataset.logic = 'AND';
        const content = root.querySelector('.filter-group-content');
        if (content) content.innerHTML = '';
    }
    loadAssets();
}

function loadAssets() {
    fetch('/api/assets').then(r => r.json()).then(data => renderAssets(data));
}

function loadAnalytics() {
    const groupBy = document.getElementById('analytics-group-by').value;
    const filterRoot = document.getElementById('filter-root');
    const filters = filterRoot && filterRoot.querySelector('.filter-group-content').children.length > 0 
                    ? JSON.stringify(buildFilterJSON()) : '';
    const url = `/api/analytics?group_by=${groupBy}${filters ? '&filters='+encodeURIComponent(filters) : ''}`;
    fetch(url).then(r => r.json()).then(data => {
        const container = document.getElementById('analytics-results');
        if (data.length === 0) {
            container.innerHTML = '<p class="text-muted">Нет данных</p>';
            return;
        }
        let html = '<div class="row">';
        data.forEach(item => {
            html += `<div class="col-md-4 mb-3"><div class="card h-100 border-0 shadow-sm"><div class="card-body text-center">
                <h6 class="card-title text-truncate text-muted">${item.label}</h6>
                <h2 class="display-4 text-primary fw-bold">${item.value}</h2>
                <span class="text-muted small">активов</span></div></div></div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    });
}

// ═══════════════════════════════════════════════════════════════
// КОНСТРУКТОР ФИЛЬТРОВ
// ═══════════════════════════════════════════════════════════════

function buildFilterJSON() {
    return buildNodeJSON(document.getElementById('filter-root'));
}

function buildNodeJSON(node) {
    if (!node) return { logic: 'AND', conditions: [] };
    const logic = node.dataset.logic || 'AND';
    const content = node.querySelector('.filter-group-content');
    const conditions = [];
    if (content) {
        content.children.forEach(child => {
            if (child.dataset.type === 'condition') {
                conditions.push({
                    type: 'condition',
                    field: child.querySelector('.f-field').value,
                    op: child.querySelector('.f-op').value,
                    value: child.querySelector('.f-val').value
                });
            } else if (child.dataset.type === 'group') {
                conditions.push(buildNodeJSON(child));
            }
        });
    }
    return { logic, conditions };
}

function toggleLogic(badge) {
    badge.textContent = badge.textContent === 'AND' ? 'OR' : 'AND';
    badge.className = badge.textContent === 'AND' ? 'badge bg-primary' : 'badge bg-warning text-dark';
    badge.parentElement.parentElement.dataset.logic = badge.textContent;
}

function createConditionElement() {
    const div = document.createElement('div');
    div.className = 'filter-condition';
    div.dataset.type = 'condition';
    const fieldOpts = FILTER_FIELDS.map(f => `<option value="${f.value}">${f.text}</option>`).join('');
    const opOpts = FILTER_OPS.map(o => `<option value="${o.value}">${o.text}</option>`).join('');
    div.innerHTML = `<select class="form-select form-select-sm f-field" style="width:160px">${fieldOpts}</select>
        <select class="form-select form-select-sm f-op" style="width:140px">${opOpts}</select>
        <input type="text" class="form-control form-control-sm f-val" placeholder="Значение" style="flex:1;min-width:120px">
        <button class="btn btn-sm btn-outline-danger" onclick="this.parentElement.remove()">×</button>`;
    return div;
}

function createGroupElement() {
    const group = document.createElement('div');
    group.className = 'filter-group';
    group.dataset.type = 'group';
    group.innerHTML = `<div class="filter-group-header">
        <span class="badge bg-primary" onclick="toggleLogic(this)">AND</span>
        <small class="text-muted ms-2">Вложенная группа</small>
        <button class="btn btn-sm btn-close" onclick="this.parentElement.parentElement.remove()"></button>
    </div><div class="filter-group-content"></div>
    <div class="mt-2">
        <button class="btn btn-xs btn-outline-primary" onclick="addCondition(this)">+ Условие</button>
        <button class="btn btn-xs btn-outline-success" onclick="addGroup(this)">+ Группа</button>
    </div>`;
    return group;
}

function addConditionToRoot() {
    const root = document.getElementById('filter-root');
    if (root?.querySelector('.filter-group-content')) {
        root.querySelector('.filter-group-content').appendChild(createConditionElement());
    }
}

function addGroupToRoot() {
    const root = document.getElementById('filter-root');
    if (root?.querySelector('.filter-group-content')) {
        root.querySelector('.filter-group-content').appendChild(createGroupElement());
    }
}

function addCondition(btn) {
    btn.closest('.filter-group').querySelector('.filter-group-content').appendChild(createConditionElement());
}

function addGroup(btn) {
    btn.closest('.filter-group').querySelector('.filter-group-content').appendChild(createGroupElement());
}

function clearGroup(btn) {
    btn.closest('.filter-group').querySelector('.filter-group-content').innerHTML = '';
}

function initFilterRoot() {
    const root = document.getElementById('filter-root');
    if (root && !root.querySelector('.filter-group-header')) {
        root.dataset.logic = 'AND';
        root.innerHTML = `<div class="filter-group-header">
            <span class="badge bg-primary" onclick="toggleLogic(this)">AND</span>
            <button class="btn btn-sm btn-close" onclick="clearGroup(this)"></button>
        </div><div class="filter-group-content"></div>`;
    }
}

function initGroupFilterRoot() {
    const root = document.getElementById('group-filter-root');
    if (root && !root.querySelector('.filter-group-header')) {
        root.dataset.logic = 'AND';
        root.innerHTML = `<div class="filter-group-header">
            <span class="badge bg-primary" onclick="toggleGroupFilterLogic(this)">AND</span>
            <button class="btn btn-sm btn-close" onclick="clearGroupFilter(this)"></button>
        </div><div class="filter-group-content"></div>`;
    }
}

function buildGroupFilterJSON() {
    return buildGroupFilterNodeJSON(document.getElementById('group-filter-root'));
}

function buildGroupFilterNodeJSON(node) {
    if (!node) return { logic: 'AND', conditions: [] };
    const logic = node.dataset.logic || 'AND';
    const content = node.querySelector('.filter-group-content');
    const conditions = [];
    if (content) {
        content.children.forEach(child => {
            if (child.dataset.type === 'condition') {
                conditions.push({
                    type: 'condition',
                    field: child.querySelector('.f-field').value,
                    op: child.querySelector('.f-op').value,
                    value: child.querySelector('.f-val').value
                });
            } else if (child.dataset.type === 'group') {
                conditions.push(buildGroupFilterNodeJSON(child));
            }
        });
    }
    return { logic, conditions };
}

function toggleGroupFilterLogic(badge) {
    toggleLogic(badge);
}

function addGroupFilterCondition() {
    const root = document.getElementById('group-filter-root');
    if (root?.querySelector('.filter-group-content')) {
        root.querySelector('.filter-group-content').appendChild(createConditionElement());
    }
}

function addGroupFilterGroup() {
    const root = document.getElementById('group-filter-root');
    if (root?.querySelector('.filter-group-content')) {
        root.querySelector('.filter-group-content').appendChild(createGroupElement());
    }
}

function clearGroupFilter(btn) {
    btn.closest('.filter-group').querySelector('.filter-group-content').innerHTML = '';
}

async function previewGroupFilter() {
    const filterStruct = buildGroupFilterJSON();
    if (!filterStruct.conditions || filterStruct.conditions.length === 0) {
        alert('Добавьте хотя бы одно условие');
        return;
    }
    const previewSection = document.getElementById('filter-preview-section');
    const previewContent = document.getElementById('filter-preview-content');
    previewSection.style.display = 'block';
    previewContent.innerHTML = '<p class="text-muted">Загрузка...</p>';
    try {
        const jsonStr = JSON.stringify(filterStruct);
        const res = await fetch(`/api/assets?filters=${encodeURIComponent(jsonStr)}`);
        const data = await res.json();
        if (data.length === 0) {
            previewContent.innerHTML = '<p class="text-warning">Нет активов</p>';
            return;
        }
        let html = `<p class="text-success">Найдено: <strong>${data.length}</strong></p>`;
        html += '<ul class="list-group list-group-flush small">';
        data.slice(0, 10).forEach(a => {
            html += `<li class="list-group-item">${a.ip} — ${a.hostname || 'No hostname'} <span class="badge bg-secondary">${a.os}</span></li>`;
        });
        if (data.length > 10) html += `<li class="list-group-item text-muted">... и ещё ${data.length - 10}</li>`;
        html += '</ul>';
        previewContent.innerHTML = html;
    } catch (error) {
        previewContent.innerHTML = `<p class="text-danger">Ошибка: ${error.message}</p>`;
    }
}

// ═══════════════════════════════════════════════════════════════
// ИНИЦИАЛИЗАЦИЯ
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    contextMenu = document.getElementById('group-context-menu');
    
    const editModalEl = document.getElementById('groupEditModal');
    const moveModalEl = document.getElementById('groupMoveModal');
    const deleteModalEl = document.getElementById('groupDeleteModal');
    const bulkDeleteModalEl = document.getElementById('bulkDeleteModal');
    
    if (editModalEl) editModal = new bootstrap.Modal(editModalEl);
    if (moveModalEl) moveModal = new bootstrap.Modal(moveModalEl);
    if (deleteModalEl) deleteModal = new bootstrap.Modal(deleteModalEl);
    if (bulkDeleteModalEl) bulkDeleteModalInstance = new bootstrap.Modal(bulkDeleteModalEl);
    
    initTreeTogglers();
    attachContextMenuListeners();
    initFilterRoot();
    initGroupFilterRoot();
    initAssetSelection();
    
    const dynamicCheckbox = document.getElementById('edit-group-dynamic');
    if (dynamicCheckbox) {
        dynamicCheckbox.addEventListener('change', function() {
            const section = document.getElementById('dynamic-filter-section');
            const preview = document.getElementById('filter-preview-section');
            section.style.display = this.checked ? 'block' : 'none';
            preview.style.display = 'none';
            if (!this.checked) {
                const root = document.getElementById('group-filter-root');
                if (root) root.querySelector('.filter-group-content').innerHTML = '';
            }
        });
    }
    
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key.toLowerCase() === 'a') {
            const target = e.target;
            if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
                e.preventDefault();
                selectAllVisibleAssets();
            }
        }
    });
});