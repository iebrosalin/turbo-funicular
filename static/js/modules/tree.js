// static/js/modules/tree.js
import { renderAssets } from './assets.js';

let currentFilter = { groupId: null, ungrouped: false };

export async function refreshGroupTree() {
    try {
        const res = await fetch('/api/groups/tree');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        
        const treeContainer = document.getElementById('group-tree');
        if (!treeContainer) return;

        // Сохраняем текущую выделенную группу
        const activeNode = treeContainer.querySelector('.tree-node.active');
        const activeId = activeNode ? activeNode.dataset.id : null;
        const isUngrouped = !!document.querySelector('.tree-node[data-id="ungrouped"].active');

        // Функция для построения дерева
        const buildTreeHtml = (nodes, parentId = null) => {
            let html = '';
            const children = nodes.filter(n => n.parent_id == parentId);
            
            children.forEach(node => {
                const hasChildren = nodes.some(n => n.parent_id == node.id);
                const indentClass = node.depth > 0 ? 'ms-' + Math.min(node.depth * 2, 5) : '';
                
                html += `
                    <li>
                        <div class="tree-node" data-id="${node.id}">
                            ${hasChildren ? '<span class="caret"></span>' : '<span class="caret-spacer"></span>'}
                            <i class="bi bi-folder folder-icon"></i>
                            <span class="group-name"
                                  data-id="${node.id}"
                                  data-name="${node.name}"
                                  data-parent="${node.parent_id || ''}"
                                  data-type="${node.is_cidr ? 'cidr' : node.is_dynamic ? 'dynamic' : 'manual'}">
                                ${node.name}
                                ${node.is_cidr ? '<i class="bi bi-globe ms-1 text-muted" title="CIDR группа"></i>' : ''}
                                ${node.is_dynamic ? '<i class="bi bi-funnel ms-1 text-muted" title="Динамическая группа"></i>' : ''}
                            </span>
                            <span class="badge bg-secondary ms-auto">${node.asset_count ?? node.count ?? 0}</span>
                        </div>
                `;

                if (hasChildren) {
                    html += `<ul class="nested">${buildTreeHtml(nodes, node.id)}</ul>`;
                }
                html += `</li>`;
            });

            return html;
        };

        // Ungrouped секция
        let ungroupedHtml = `
            <li>
                <div class="tree-node" data-id="ungrouped">
                    <span class="caret-spacer"></span>
                    <i class="bi bi-inbox folder-icon"></i>
                    <span class="group-name" data-id="ungrouped">
                        Без группы
                    </span>
                    <span class="badge bg-secondary ms-auto">${data.ungrouped_count || 0}</span>
                </div>
            </li>
        `;

        treeContainer.innerHTML = `<ul>${ungroupedHtml + buildTreeHtml(data.flat)}</ul>`;

        // Восстанавливаем выделение
        if (isUngrouped) {
            const ungroupedNode = treeContainer.querySelector('.tree-node[data-id="ungrouped"]');
            if (ungroupedNode) ungroupedNode.classList.add('active');
        } else if (activeId) {
            const node = treeContainer.querySelector(`.tree-node[data-id="${activeId}"]`);
            if (node) {
                node.classList.add('active');
                node.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        // Инициализируем обработчики событий
        initTreeTogglers();

    } catch (e) {
        console.error('Ошибка обновления дерева групп:', e);
    }
}

export async function loadAssets(groupId = null, ungrouped = false) {
    let url;
    
    if (ungrouped) {
        url = '/api/assets?ungrouped=true';
    } else if (groupId) {
        url = `/api/assets?group_id=${parseInt(groupId)}`;
    } else {
        url = '/api/assets';
    }
    
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        
        renderAssets(data);
        currentFilter = { groupId, ungrouped };
    } catch (e) {
        console.error('Ошибка загрузки активов:', e);
    }
}

function initTreeTogglers() {
    const treeContainer = document.getElementById('group-tree');
    
    // Обработчик кликов по узлам дерева
    treeContainer.addEventListener('click', function(e) {
        const groupSpan = e.target.closest('.group-name');
        if (groupSpan) {
            const nodeId = groupSpan.dataset.id;
            
            // Удаляем активный класс со всех узлов
            treeContainer.querySelectorAll('.tree-node').forEach(node => {
                node.classList.remove('active');
            });
            
            // Добавляем активный класс к выбранному узлу
            const clickedNode = e.target.closest('.tree-node');
            clickedNode.classList.add('active');
            
            // Загружаем активы в зависимости от типа узла
            if (nodeId === 'ungrouped') {
                loadAssets(null, true);
            } else {
                loadAssets(parseInt(nodeId), false);
            }
        }
        
        const caret = e.target.closest('.caret');
        if (caret) {
            const parentLi = caret.parentElement.parentElement;
            parentLi.classList.toggle("active");
            caret.classList.toggle("down");
        }
    });
}

export function getCurrentFilter() {
    return currentFilter;
}