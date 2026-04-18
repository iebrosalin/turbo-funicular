// static/js/main.js

// ═══════════════════════════════════════════════════════════════
// ЗАЩИТА ОТ ПОВТОРНОГО ВЫПОЛНЕНИЯ
// ═══════════════════════════════════════════════════════════════
(function() {
    if (window.__MAIN_JS_LOADED) {
        console.warn('main.js уже был загружен, пропускаем повторную инициализацию.');
        return;
    }
    window.__MAIN_JS_LOADED = true;

    // ═══════════════════════════════════════════════════════════════
    // ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
    // ═══════════════════════════════════════════════════════════════
    var currentGroupId = null; 
    var contextMenu = null;
    var editModal, createModal, moveModal, deleteModal, bulkDeleteModalInstance;
    var lastSelectedIndex = -1; 
    var selectedAssetIds = new Set();

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
    // УТИЛИТЫ МОДАЛЬНЫХ ОКОН
    // ═══════════════════════════════════════════════════════════════

    // 🔥 ДОБАВЛЯЕМ СТИЛЬ ДЛЯ СОХРАНЕНИЯ ПРОБЕЛОВ В SELECT
    if (!document.getElementById('hierarchy-select-style')) {
        const style = document.createElement('style');
        style.id = 'hierarchy-select-style';
        style.textContent = `
            select.hierarchy-select, 
            select.hierarchy-select option {
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                white-space: pre;
            }
        `;
        document.head.appendChild(style);
    }

    function closeModalById(modalId) {
        const modalEl = document.getElementById(modalId);
        if (!modalEl) return;

        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        
        if (modalInstance) {
            modalInstance.hide();
        } else {
            modalEl.classList.remove('show');
            modalEl.removeAttribute('aria-modal');
            modalEl.removeAttribute('role');
            modalEl.style.display = '';
            
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) backdrop.remove();
            
            document.body.classList.remove('modal-open');
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
        }

        const form = modalEl.querySelector('form');
        if (form) form.reset();
    }

    /**
     * Заполняет выпадающие списки родительских групп с визуальной иерархией.
     */
    async function populateParentSelect(excludeIds = [], selectedId = null) {
    try {
        const res = await fetch('/api/groups/tree');
        if (!res.ok) throw new Error('Failed to fetch tree');
        const data = await res.json();
        
        if (!data.flat) return;

        // Построение дерева
        const buildTree = (parentId) => {
            return data.flat
                .filter(g => g.parent_id == parentId)
                .map(g => ({
                    ...g,
                    children: buildTree(g.id)
                }));
        };
        const tree = buildTree(null);

        // Генерация опций
        const generateOptions = (nodes, level = 0) => {
            let options = '';
            nodes.forEach(node => {
                if (excludeIds.includes(String(node.id))) return;

                const indent = '    '; // 4 пробела
                const prefix = level > 0 ? '└─ ' : '';
                const label = (indent.repeat(level)) + prefix + node.name;
                
                const option = document.createElement('option');
                option.value = node.id;
                option.text = label; 
                if (selectedId !== null && String(node.id) === String(selectedId)) {
                    option.selected = true;
                }
                
                options += option.outerHTML;
                
                if (node.children && node.children.length > 0) {
                    options += generateOptions(node.children, level + 1);
                }
            });
            return options;
        };

        const baseOption = '<option value="">-- Корень --</option>';
        const optionsContent = baseOption + generateOptions(tree);

        const selectors = [
            '#edit-group-parent',   
            '#move-group-parent',   
            '#delete-move-assets'   
        ];

        selectors.forEach(sel => {
            const el = document.querySelector(sel);
            if (el) {
                // 1. Сначала очищаем и заполняем контент
                el.innerHTML = optionsContent;
                
                // 2. Явно добавляем класс для стилей (важно для всех страниц)
                el.classList.add('hierarchy-select');
                
                // 3. Принудительно задаем стиль через JS, если CSS по какой-то причине не применился
                el.style.fontFamily = "'Consolas', 'Monaco', 'Courier New', monospace";
                
                // 4. Восстанавливаем выбор
                const currentVal = selectedId !== null ? selectedId : el.getAttribute('data-last-value') || el.value;
                if (currentVal) {
                    el.value = currentVal;
                } else {
                    el.value = ""; // Сброс на "-- Корень --" если ничего не выбрано
                }
                
                // Сохраняем текущее значение для возможного следующего открытия
                el.setAttribute('data-last-value', el.value);
            }
        });

    } catch (e) {
        console.error('Ошибка загрузки дерева групп:', e);
    }
}

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
        const moon = toggle.querySelector('.bi-moon');
        const sun = toggle.querySelector('.bi-sun');
        if(moon) moon.style.display = theme === 'dark' ? 'none' : 'block';
        if(sun) sun.style.display = theme === 'dark' ? 'block' : 'none';
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
    // УПРАВЛЕНИЕ ГРУППАМИ
    // ═══════════════════════════════════════════════════════════════

    window.showCreateGroupModal = async function(parentId = null) {
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
    };

    window.toggleGroupMode = function() {
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

    window.showRenameModal = async function(id) {
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
            renderGroupFilters(groupData.filter_rules);
        } else {
            if(manualCheck) manualCheck.checked = true;
            const root = document.getElementById('group-filter-root');
            if(root) root.innerHTML = '';
        }
        
        toggleGroupMode();
        
        const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
        modal.show();
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

    window.showMoveModal = async function(id) {
        const modalId = 'groupMoveModal';
        const modalEl = document.getElementById(modalId);
        if (!modalEl) return console.warn('⚠️ #' + modalId + ' не найден.');
        
        const idInput = document.getElementById('move-group-id');
        if(idInput) idInput.value = id;
        
        await populateParentSelect([String(id)], "");
        
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    };

    window.showDeleteModal = async function(id) {
        const modalId = 'groupDeleteModal';
        const modalEl = document.getElementById(modalId);
        if (!modalEl) return console.warn('⚠️ #' + modalId + ' не найден.');
        
        const idInput = document.getElementById('delete-group-id');
        if(idInput) idInput.value = id;
        
        await populateParentSelect([String(id)], "");
        
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    };

    // Обработка форм
    document.addEventListener('DOMContentLoaded', () => {
        const e = document.getElementById('groupEditModal'); 
        const m = document.getElementById('groupMoveModal');
        const d = document.getElementById('groupDeleteModal'); 
        const b = document.getElementById('bulkDeleteModal');
        
        if(e) editModal = new bootstrap.Modal(e, { backdrop: 'static' }); 
        if(m) moveModal = new bootstrap.Modal(m);
        if(d) deleteModal = new bootstrap.Modal(d); 
        if(b) bulkDeleteModalInstance = new bootstrap.Modal(b);

        const editForm = document.getElementById('groupEditForm');
        if(editForm) {
            editForm.addEventListener('submit', async (ev) => {
                ev.preventDefault();
                const id = document.getElementById('edit-group-id').value;
                const mode = document.querySelector('input[name="groupMode"]:checked')?.value;
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
                        closeModalById('groupEditModal');
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
                    closeModalById('groupMoveModal');
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
        if(tb) {
            tb.style.display = c > 0 ? 'flex' : 'none'; 
            const countEl = document.getElementById('selected-count');
            if(countEl) countEl.textContent = c;
        }
    }
    function confirmBulkDelete() {
        if(selectedAssetIds.size === 0) return;
        const countEl = document.getElementById('bulk-delete-count');
        if(countEl) countEl.textContent = selectedAssetIds.size;
        if(bulkDeleteModalInstance) bulkDeleteModalInstance.show();
    }
    async function executeBulkDelete() {
        const ids = Array.from(selectedAssetIds);
        await fetch('/api/assets/bulk-delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids}) });
        clearSelection(); 
        closeModalById('bulkDeleteModal');
        location.reload();
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
    const dsFilter = document.getElementById('data-source-filter');
    if(dsFilter) {
        dsFilter.addEventListener('change', function() {
            const p = new URLSearchParams(window.location.search); p.set('data_source', this.value); window.location.search = p.toString();
        });
    }

    async function saveWazuhConfig() {
        const btn = event.target; 
        if(!btn) return;
        btn.disabled = true; 
        const originalText = btn.textContent;
        btn.textContent = '⏳ Синхронизация...';
        
        const st = document.getElementById('waz-status');
        const body = { 
            url: document.getElementById('waz-url').value, 
            username: document.getElementById('waz-user').value, 
            password: document.getElementById('waz-pass').value, 
            verify_ssl: document.getElementById('waz-ssl').checked, 
            is_active: document.getElementById('waz-active').checked 
        };
        
        await fetch('/api/wazuh/config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
        const res = await fetch('/api/wazuh/sync', { method: 'POST' }); 
        const d = await res.json();
        
        if(res.ok) { 
            if(st) st.innerHTML=`<span class="text-success">✅ +${d.new} | обн. ${d.updated}</span>`; 
            setTimeout(()=>location.reload(), 1500); 
        } else { 
            if(st) st.innerHTML=`<span class="text-danger">❌ ${d.error}</span>`; 
            btn.disabled = false; 
            btn.textContent = originalText;
        }
    }

    const wazuhModalEl = document.getElementById('wazuhModal');
    if(wazuhModalEl) {
        wazuhModalEl.addEventListener('show.bs.modal', async () => {
            const c = await (await fetch('/api/wazuh/config')).json();
            document.getElementById('waz-url').value = c.url || ''; 
            document.getElementById('waz-user').value = c.username || '';
            document.getElementById('waz-pass').value = c.password || ''; 
            document.getElementById('waz-ssl').checked = !!c.verify_ssl; 
            document.getElementById('waz-active').checked = !!c.is_active;
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // СКАНИРОВАНИЯ
    // ═══════════════════════════════════════════════════════════════
    window.viewScanResults = async function(id){
        const modalId = 'scanResultsModal';
        const modalEl = document.getElementById(modalId);
        if(!modalEl) return;

        const m = new bootstrap.Modal(modalEl);
        const c = document.getElementById('scan-results-content');
        const errAlert = document.getElementById('scan-error-alert');
        const errText = document.getElementById('scan-error-text');
        
        if(c) c.innerHTML = '<div class="text-center"><div class="spinner-border"></div><p class="mt-2">Загрузка...</p></div>';
        if(errAlert) errAlert.style.display = 'none';
        
        m.show();
        
        try{
            const r = await fetch(`/api/scans/${id}/results`);
            const d = await r.json();
            
            if(d.job.status === 'failed' && d.job.error_message){
                if(errAlert) errAlert.style.display = 'block';
                if(errText) errText.textContent = d.job.error_message;
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
            } else if(!d.results || d.results.length === 0){
                h += '<p class="text-muted">Нет результатов</p>';
            } else {
                h += `<p><strong>Найдено хостов:</strong> ${d.results.length}</p><div class="list-group">`;
                d.results.forEach(x=>{
                    h += `<div class="list-group-item"><div class="d-flex justify-content-between"><h6 class="mb-1">${x.ip}</h6><small>${x.scanned_at}</small></div><p class="mb-1"><strong>Порты:</strong> ${x.ports && x.ports.join ? x.ports.join(', ') : 'Нет'}</p>${x.os && x.os !== '-' ? `<p class="mb-0"><strong>ОС:</strong> ${x.os}</p>`:''}</div>`;
                });
                h += '</div>';
            }
            if(c) c.innerHTML = h;
        }catch(err){ 
            if(errAlert) errAlert.style.display = 'block';
            if(errText) errText.textContent = `Ошибка загрузки результатов: ${err.message}`;
        }
    }

    window.showScanError = function(jobId, errorMsg){
        const modalId = 'scanErrorModal';
        const modalEl = document.getElementById(modalId);
        if(!modalEl) return alert(errorMsg);

        const m = new bootstrap.Modal(modalEl);
        const c = document.getElementById('scan-error-content');
        const safeMsg = errorMsg ? errorMsg.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$') : 'Неизвестная ошибка';
        
        if(c) {
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
        }
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
                         nodeHtml += `<ul class="nested active">`; 
                         children.forEach(c => nodeHtml += buildNode(c, level+1));
                         nodeHtml += `</ul>`;
                     }
                     return nodeHtml;
                 }

                 html = '<ul style="list-style:none; padding:0; margin:0;">';
                 roots.forEach(r => html += buildNode(r, 0));
                 html += '</ul>';
                 
                 html += `<div class="tree-node" data-id="ungrouped" style="padding-left:10px; margin-top:10px; border-top:1px solid var(--border-color); display:flex; justify-content:space-between;">
                    <div><i class="bi bi-folder-minus"></i> <span class="group-name ms-2">Без группы</span></div>
                    <span id="ungrouped-count" class="badge bg-secondary">${ungroupedAssets.length}</span>
                 </div>`;

                 treeContainer.innerHTML = html;
                 initTreeTogglers(); 
            }
            
        } catch (e) {
            console.warn('⚠️ Ошибка обновления дерева групп:', e);
        }
    }

    // Поллинг активных сканирований
    function pollActiveScans(){
        fetch('/api/scans/status').then(r=>r.json()).then(d=>{
            const c = document.getElementById('active-scans');
            
            if (!c) return;

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

    window.confirmDeleteGroup = function() {
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
                refreshGroupTree();
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

})();