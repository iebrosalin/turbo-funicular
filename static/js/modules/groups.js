import { populateParentSelect, closeModalById } from './utils.js';

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

// Глобальный таймер для опроса сканирований
let scansPollingInterval = null;

/**
 * Инициализация обработчиков кликов для статических элементов дерева ("Все активы", "Без группы")
 */
export function initGroupTreeStaticListeners() {
    const handleStaticClick = (groupId) => {
        // Снимаем активный класс со всех узлов
        document.querySelectorAll('.tree-node').forEach(n => n.classList.remove('active'));
        
        // Находим элемент и добавляем активный класс
        const targetElement = document.querySelector(`.tree-node[data-id="${groupId}"]`);
        if (targetElement) {
            targetElement.classList.add('active');
        }

        // Вызываем фильтрацию
        if (typeof window.filterByGroup === 'function') {
            window.filterByGroup(groupId, false, 'assets-body', null);
        } else {
            console.warn('Функция window.filterByGroup еще не загружена.');
        }
    };

    // Обработчик для "Все активы"
    const allNode = document.querySelector('.tree-node[data-id="all"]');
    if (allNode) {
        // Клонируем чтобы сбросить старые слушатели и избежать дублей
        const newAllNode = allNode.cloneNode(true);
        allNode.parentNode.replaceChild(newAllNode, allNode);
        newAllNode.addEventListener('click', (e) => {
            e.stopPropagation();
            handleStaticClick('all');
        });
    }

    // Обработчик для "Без группы"
    const ungroupedNode = document.querySelector('.tree-node[data-id="ungrouped"]');
    if (ungroupedNode) {
        const newUngroupedNode = ungroupedNode.cloneNode(true);
        ungroupedNode.parentNode.replaceChild(newUngroupedNode, ungroupedNode);
        newUngroupedNode.addEventListener('click', (e) => {
            e.stopPropagation();
            handleStaticClick('ungrouped');
        });
    }
}

export async function showCreateGroupModal(parentId = null) {
    const modalId = 'groupEditModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return console.error('Modal #' + modalId + ' not found');

    document.getElementById('groupEditForm').reset();
    document.getElementById('edit-group-id').value = '';
    document.getElementById('groupEditTitle').textContent = 'Новая группа';
    document.getElementById('edit-group-name').value = '';
    document.getElementById('group-filter-root').innerHTML = '';
    
    await populateParentSelect([], parentId);
    
    document.getElementById('modeManual').checked = true;
    toggleGroupMode(); 

    const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
    modal.show();
}

export function toggleGroupMode() {
    const mode = document.querySelector('input[name="groupMode"]:checked')?.value;
    if(!mode) return;

    const secCommon = document.getElementById('sectionCommon');
    const secCidr = document.getElementById('sectionCidr');
    const secDynamic = document.getElementById('sectionDynamic');
    const nameInput = document.getElementById('edit-group-name');
    const parentSelect = document.getElementById('edit-group-parent');

    if(secCommon) secCommon.style.display = 'block';
    if(secCidr) secCidr.style.display = 'none';
    if(secDynamic) secDynamic.style.display = 'none';
    
    if (mode === 'manual') {
        if(nameInput) nameInput.required = true;
        if(parentSelect) parentSelect.disabled = false;
    } else if (mode === 'cidr') {
        if(secCidr) secCidr.style.display = 'block';
        if(nameInput) nameInput.required = false;
        if(parentSelect) parentSelect.disabled = false;
    } else if (mode === 'dynamic') {
        if(secDynamic) secDynamic.style.display = 'block';
        if(nameInput) nameInput.required = true;
        if(parentSelect) parentSelect.disabled = false;
        
        const root = document.getElementById('group-filter-root');
        if(root && root.children.length === 0) {
            addDynamicRule();
        }
    }
}

export function addDynamicRule(field = '', op = 'eq', value = '') {
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
}

export async function showRenameModal(id) {
    const modalId = 'groupEditModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return console.warn('⚠️ #' + modalId + ' не найден');

    const idInput = document.getElementById('edit-group-id');
    if (idInput) idInput.value = id;
    document.getElementById('groupEditTitle').textContent = 'Редактировать группу';

    let groupData;
    try {
        const r = await fetch(`/api/groups/${id}`);
        groupData = await r.json();
    } catch (err) {
        console.error('Ошибка загрузки данных группы:', err);
        return;
    }

    await populateParentSelect([String(id)], groupData.parent_id);

    const nameInput = document.getElementById('edit-group-name');
    const parentSelect = document.getElementById('edit-group-parent');
    
    if (nameInput) nameInput.value = groupData.name || '';
    if (parentSelect) parentSelect.value = groupData.parent_id || '';

    const dynCheck = document.getElementById('modeDynamic');
    const manualCheck = document.getElementById('modeManual');
    
    if (groupData.is_dynamic || (groupData.filter_rules && groupData.filter_rules.length > 0)) {
        if(dynCheck) dynCheck.checked = true;
        if(manualCheck) manualCheck.checked = false;
    } else {
        if(manualCheck) manualCheck.checked = true;
        if(dynCheck) dynCheck.checked = false;
    }
    
    toggleGroupMode();

    if (groupData.is_dynamic && groupData.filter_rules) {
        const root = document.getElementById('group-filter-root');
        if(root) root.innerHTML = '';
        groupData.filter_rules.forEach(rule => {
            addDynamicRule(rule.field, rule.op, rule.value);
        });
    }

    const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
    modal.show();
}

export async function saveGroup() {
    const id = document.getElementById('edit-group-id').value;
    const name = document.getElementById('edit-group-name').value.trim();
    const parentId = document.getElementById('edit-group-parent').value;
    const mode = document.querySelector('input[name="groupMode"]:checked')?.value;

    let payload = {
        name: name,
        parent_id: parentId === '' ? null : parseInt(parentId),
        mode: mode
    };

    if (mode === 'cidr') {
        const cidr = document.getElementById('cidr-network').value.trim();
        const mask = document.getElementById('cidr-mask').value;
        if (!cidr) {
            alert('Укажите CIDR');
            return;
        }
        payload.cidr_network = cidr;
        payload.cidr_mask = mask;
    } else if (mode === 'dynamic') {
        const rules = [];
        document.querySelectorAll('.filter-condition').forEach(el => {
            const field = el.querySelector('.rule-field').value;
            const op = el.querySelector('.rule-op').value;
            const value = el.querySelector('.rule-val').value.trim();
            if (field && value) rules.push({ field, op, value });
        });
        payload.filter_rules = rules;
    }

    const url = id ? `/api/groups/${id}` : '/api/groups';
    const method = id ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, {
            method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || 'Ошибка сохранения');
        }

        closeModalById('groupEditModal');
        
        // Обновляем дерево и список активов
        if (typeof window.refreshGroupTree === 'function') {
            await window.refreshGroupTree();
        }
        if (typeof window.loadAssets === 'function') {
            await window.loadAssets();
        }
    } catch (e) {
        console.error('Ошибка сохранения группы:', e);
        alert(e.message);
    }
}

export async function showDeleteModal(id) {
    const modalId = 'groupDeleteModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return console.warn('❌ Модальное окно удаления не найдено');

    document.getElementById('delete-group-id').value = id;
    
    // Заполняем селект всеми группами кроме удаляемой
    await populateParentSelect([String(id)], null);
    
    const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
    modal.show();
}

export function confirmDeleteGroup() {
    const groupId = document.getElementById('delete-group-id').value;
    const moveToId = document.getElementById('delete-move-assets').value;
    
    closeModalById('groupDeleteModal');

    fetch(`/api/groups/${groupId}`, {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ move_to_id: moveToId || null })
    })
    .then(response => {
        if (response.ok) {
            if (typeof window.refreshGroupTree === 'function') {
                window.refreshGroupTree();
            }
            if (typeof window.loadAssets === 'function' && window.currentGroupId == groupId) {
                window.currentGroupId = null;
                window.loadAssets(); 
            }
        } else {
            alert('Ошибка при удалении группы');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ошибка сети');
    });
}

export async function showMoveGroupModal(id) {
    const modalId = 'groupMoveModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return console.warn('❌ Модальное окно перемещения не найдено');

    document.getElementById('move-group-id').value = id;
    
    await populateParentSelect([String(id)]);
    
    const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
    modal.show();
}

export async function moveGroup() {
    const groupId = document.getElementById('move-group-id').value;
    const newParentId = document.getElementById('move-group-parent').value;

    try {
        const res = await fetch(`/api/groups/${groupId}/move`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ parent_id: newParentId === '' ? null : parseInt(newParentId) })
        });

        if (!res.ok) throw new Error('Не удалось переместить группу');

        closeModalById('groupMoveModal');
        
        if (typeof window.refreshGroupTree === 'function') {
            await window.refreshGroupTree();
        }
    } catch (e) {
        console.error('Ошибка перемещения группы:', e);
        alert(e.message);
    }
}

export function initContextMenu() {
    document.addEventListener('click', function(e) {
        const ctx = document.getElementById('group-context-menu');
        if (!ctx) return;
        ctx.style.display = 'none';
    });

    document.addEventListener('contextmenu', function(e) {
        const treeNode = e.target.closest('.tree-node');
        if (!treeNode) return;

        // Проверяем, что элемент находится внутри дерева групп активов (#group-tree)
        // Это предотвращает появление контекстного меню на других элементах сайдбара
        const groupTree = document.getElementById('group-tree');
        if (!groupTree || !groupTree.contains(treeNode)) return;

        const ctx = document.getElementById('group-context-menu');
        if (!ctx) return;

        e.preventDefault();
        e.stopPropagation();

        const groupId = treeNode.dataset.id;
        const isUngrouped = groupId === 'ungrouped';
        const isAll = groupId === 'all';

        ctx.style.display = 'block';
        ctx.style.left = e.pageX + 'px';
        ctx.style.top = e.pageY + 'px';

        const createItem = ctx.querySelector('[data-action="create-child"]');
        const renameItem = ctx.querySelector('[data-action="rename"]');
        const moveItem = ctx.querySelector('[data-action="move"]');
        const deleteItem = ctx.querySelector('[data-action="delete"]');

        // Скрываем действия для системных узлов "Все активы" и "Без группы"
        const isSystemNode = isUngrouped || isAll;

        if(createItem) createItem.style.display = isSystemNode ? 'none' : 'block';
        if(renameItem) renameItem.style.display = isSystemNode ? 'none' : 'block';
        if(moveItem) moveItem.style.display = isSystemNode ? 'none' : 'block';
        if(deleteItem) deleteItem.style.display = isSystemNode ? 'none' : 'block';

        ctx.dataset.groupId = groupId;
    });

    document.getElementById('group-context-menu')?.addEventListener('click', function(e) {
        const actionItem = e.target.closest('[data-action]');
        if (!actionItem) return;

        const groupId = this.dataset.groupId;
        const action = actionItem.dataset.action;

        if (action === 'create-child') {
            showCreateGroupModal(groupId);
        } else if (action === 'rename') {
            showRenameModal(groupId);
        } else if (action === 'move') {
            showMoveGroupModal(groupId);
        } else if (action === 'delete') {
            showDeleteModal(groupId);
        }

        this.style.display = 'none';
    });
}

/**
 * Инициализация монитора активных сканирований в сайдбаре
 */
export function initActiveScans() {
    const container = document.getElementById('active-scans-list');
    if (!container) return;

    // Функция обновления списка
    const updateScans = async () => {
        try {
            const res = await fetch('/scans/api/scans/status');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            const jobs = data.recent_jobs || [];
            // Фильтруем только активные (running, pending, queued)
            const activeJobs = jobs.filter(j => ['running', 'pending', 'queued'].includes(j.status));

            if (activeJobs.length === 0) {
                container.innerHTML = '<div class="text-center text-muted small py-3">Нет активных задач</div>';
                return;
            }

            let html = '';
            activeJobs.forEach(job => {
                let statusClass = 'status-pending';
                let statusText = 'Ожидание';
                
                if (job.status === 'running') {
                    statusClass = 'status-running';
                    statusText = 'Выполняется';
                } else if (job.status === 'failed') {
                    statusClass = 'status-failed';
                    statusText = 'Ошибка';
                }

                const progress = job.progress || 0;
                const typeBadge = job.scan_type === 'nmap' ? 'bg-primary' : (job.scan_type === 'rustscan' ? 'bg-warning text-dark' : 'bg-info text-dark');

                html += `
                <div class="scan-list-item">
                    <div class="d-flex justify-content-between align-items-start mb-1">
                        <span class="badge ${typeBadge} me-1">${job.scan_type.toUpperCase()}</span>
                        <small class="text-muted">#${job.id}</small>
                    </div>
                    <div class="mb-1 text-truncate" title="${job.target}">
                        <span class="scan-status-dot ${statusClass}"></span>
                        ${job.target}
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <small class="text-muted">${statusText}</small>
                        ${job.status === 'running' ? `<small class="text-primary fw-bold">${progress}%</small>` : ''}
                    </div>
                    ${job.status === 'running' ? `
                    <div class="progress" style="height: 4px; margin-top: 4px;">
                        <div class="progress-bar" role="progressbar" style="width: ${progress}%"></div>
                    </div>` : ''}
                </div>
                `;
            });

            container.innerHTML = html;

        } catch (e) {
            console.error('Ошибка обновления сканирований:', e);
            container.innerHTML = '<div class="text-danger small p-2">Ошибка загрузки</div>';
        }
    };

    // Первоначальная загрузка
    updateScans();

    // Очистка предыдущего интервала если есть
    if (scansPollingInterval) clearInterval(scansPollingInterval);

    // Опрос каждые 5 секунд
    scansPollingInterval = setInterval(updateScans, 5000);
}