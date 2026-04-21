// static/js/modules/tree.js
import { renderAssets } from './assets.js';

let currentFilter = { groupId: null, ungrouped: false };
let treeListenerAttached = false;

// Константа отступа на каждый уровень вложенности (в пикселях)
const INDENT_PER_LEVEL = 24;

// Безопасная нормализация ID для сравнения
const normId = (val) => (val === null || val === undefined) ? 'null' : String(val);

export async function refreshGroupTree() {
    try {
        const res = await fetch('/api/groups/tree');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        
        const treeContainer = document.getElementById('group-tree');
        if (!treeContainer) return;
        
        // Сохраняем состояние активного узла до перерисовки
        const activeNode = treeContainer.querySelector('.tree-node.active');
        const activeId = activeNode ? normId(activeNode.dataset.id) : null;
        const isUngrouped = !!document.querySelector('.tree-node[data-id="ungrouped"].active');
        
        // Рекурсивный рендер дерева с передачей глубины
        const buildTreeHtml = (nodes, parentId = null, depth = 0) => {
            const pIdStr = normId(parentId);
            const children = nodes.filter(n => normId(n.parent_id) === pIdStr);
            if (children.length === 0) return '';
            
            let html = '';
            children.forEach(node => {
                const nIdStr = normId(node.id);
                const hasChildren = nodes.some(n => normId(n.parent_id) === nIdStr);
                const isDynamic = node.is_dynamic;
                const typeIcon = isDynamic ? '<i class="bi bi-funnel ms-1 text-muted" title="Динамическая группа"></i>' : '';
                
                // Вычисляем отступ на основе глубины
                const indentPx = depth * INDENT_PER_LEVEL;

                html += `<li>`;
                html += `\n                <div class="tree-node" data-id="${node.id}" style="margin-left: ${indentPx}px;">`;
                html += `\n                    ${hasChildren ? '<span class="caret"></span>' : '<span class="caret-spacer"></span>'}`;
                html += `\n                    <i class="bi bi-folder folder-icon"></i>`;
                html += `\n                    <span class="group-name" data-id="${node.id}" data-type="${isDynamic ? 'dynamic' : 'manual'}">`;
                html += `\n                        ${node.name} ${typeIcon}`;
                html += `\n                    </span>`;
                html += `\n                    <span class="badge bg-secondary ms-auto">${node.asset_count ?? node.count ?? 0}</span>`;
                html += `\n                    <span class="group-actions ms-2">`;
                html += `\n                        <button type="button" class="btn-action" onclick="window.showRenameModal(${node.id})" title="Редактировать">`;
                html += `\n                            <i class="bi bi-pencil"></i>`;
                html += `\n                        </button>`;
                html += `\n                        <button type="button" class="btn-action text-danger" onclick="window.showDeleteModal(${node.id})" title="Удалить">`;
                html += `\n                            <i class="bi bi-trash"></i>`;
                html += `\n                        </button>`;
                html += `\n                    </span>`;
                html += `\n                </div>`;

                if (hasChildren) {
                    const childrenHtml = buildTreeHtml(nodes, node.id, depth + 1);
                    if (childrenHtml) {
                        html += `<ul class="nested">${childrenHtml}</ul>`;
                    }
                }
                html += `</li>`;
            });
            return html;
        };
        
        // Узел "Без группы"
        const ungroupedHtml = `
        <li>
            <div class="tree-node" data-id="ungrouped">
                <span class="caret-spacer"></span>
                <i class="bi bi-inbox folder-icon"></i>
                <span class="group-name" data-id="ungrouped">Без группы</span>
                <span class="badge bg-secondary ms-auto">${data.ungrouped_count || 0}</span>
            </div>
        </li>
        `;
        
        // Рендерим в контейнер
        // Примечание: API должно возвращать { flat: [...], ungrouped_count: N }
        // Если API возвращает просто дерево, логику нужно адаптировать
        const flatList = data.flat || []; 
        treeContainer.innerHTML = `<ul>${ungroupedHtml + buildTreeHtml(flatList)}</ul>`;
        
        // Восстановление состояния (выделение + раскрытие родителей)
        if (isUngrouped) {
            const n = treeContainer.querySelector('.tree-node[data-id="ungrouped"]');
            if (n) n.classList.add('active');
        } else if (activeId) {
            const node = treeContainer.querySelector(`.tree-node[data-id="${activeId}"]`);
            if (node) {
                node.classList.add('active');
                let el = node.closest('li');
                while (el) {
                    const parentUl = el.parentElement;
                    if (parentUl && parentUl.classList.contains('nested')) {
                        parentUl.classList.add('active');
                        const grandLi = parentUl.closest('li');
                        if (grandLi) {
                            const caret = grandLi.querySelector(':scope > .tree-node > .caret');
                            if (caret) caret.classList.add('down');
                        }
                        el = grandLi;
                    } else break;
                }
            }
        }
        
        // Инициализируем обработчики кликов
        initTreeTogglers();
        
    } catch (e) {
        console.error('Ошибка обновления дерева групп:', e);
        const treeContainer = document.getElementById('group-tree');
        if (treeContainer) {
            treeContainer.innerHTML = '<div class="text-danger small">Ошибка загрузки групп</div>';
        }
    }
}

export async function loadAssets(groupId = null, ungrouped = false) {
    let url;
    if (ungrouped) url = '/api/assets?ungrouped=true';
    else if (groupId) url = `/api/assets?group_id=${parseInt(groupId)}`;
    else url = '/api/assets';
    
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        
        // Проверка формата данных (как в dashboard-page.js)
        let assetsArray = [];
        if (Array.isArray(data)) {
            assetsArray = data;
        } else if (data.items && Array.isArray(data.items)) {
            assetsArray = data.items;
        } else {
            console.warn('Неожиданный формат ответа API активов:', data);
            assetsArray = [];
        }

        renderAssets(assetsArray);
        currentFilter = { groupId, ungrouped };
    } catch (e) { 
        console.error('Ошибка загрузки активов:', e); 
    }
}

export function filterByGroup(groupId) {
    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));
    const activeNode = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    if (activeNode) activeNode.classList.add('active');
    
    if (groupId === 'ungrouped') loadAssets(null, true);
    else loadAssets(parseInt(groupId), false);
}

export function initTreeTogglers() {
    if (treeListenerAttached) return; // Защита от дублирования
    
    const treeContainer = document.getElementById('group-tree');
    if (!treeContainer) return;
    
    treeContainer.addEventListener('click', function(e) {
        // Игнорируем клики по кнопкам действий
        if (e.target.closest('.group-actions') || e.target.closest('.btn-action')) return;
        
        // 1. Клик по стрелке (раскрытие/сворачивание)
        const caret = e.target.closest('.caret');
        if (caret) {
            e.preventDefault(); e.stopPropagation();
            const parentLi = caret.closest('li');
            if (parentLi) {
                const nestedUl = parentLi.querySelector(':scope > ul.nested');
                if (nestedUl) nestedUl.classList.toggle('active');
            }
            caret.classList.toggle('down');
            return;
        }
        
        // 2. Клик по названию группы
        const groupSpan = e.target.closest('.group-name');
        if (groupSpan) {
            filterByGroup(groupSpan.dataset.id);
        }
    });
    
    treeListenerAttached = true;
}

export function getCurrentFilter() { return currentFilter; }