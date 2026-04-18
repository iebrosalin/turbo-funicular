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

        // Функция для построения дерева (рекурсивная)
        const buildTreeHtml = (nodes, parentId = null) => {
            // Фильтруем узлы, которые являются прямыми детьми текущего родителя
            // Используем == для нестрогого сравнения (важно для null/undefined и строк/чисел)
            const children = nodes.filter(n => n.parent_id == parentId);
            
            if (children.length === 0) return '';

            let html = '';
            
            children.forEach(node => {
                // Проверяем, есть ли у этого узла дети (для отображения стрелки)
                // Используем == для нестрогого сравнения (важно для null/undefined и строк/чисел)
                const hasChildren = nodes.some(n => n.parent_id == node.id);
                
                // Формируем HTML узла
                html += `<li>`;
                html += `
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

                // Если есть дети, рекурсивно строим вложенный список
                if (hasChildren) {
                    const childrenHtml = buildTreeHtml(nodes, node.id);
                    if (childrenHtml) {
                        html += `<ul class="nested" style="display: none;">${childrenHtml}</ul>`;
                    }
                }
                
                html += `</li>`;
            });

            return html;
        };

        // Секция "Без группы"
        const ungroupedHtml = `
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

        // Собираем всё дерево
        const treeHtml = ungroupedHtml + buildTreeHtml(data.flat);
        treeContainer.innerHTML = `<ul>${treeHtml}</ul>`;

        // Восстанавливаем выделение
        if (isUngrouped) {
            const ungroupedNode = treeContainer.querySelector('.tree-node[data-id="ungrouped"]');
            if (ungroupedNode) ungroupedNode.classList.add('active');
        } else if (activeId) {
            const node = treeContainer.querySelector(`.tree-node[data-id="${activeId}"]`);
            if (node) {
                node.classList.add('active');
                // Раскрываем родителей, если элемент глубоко вложен
                let parentUl = node.closest('ul.nested');
                while (parentUl) {
                    parentUl.style.display = 'block';
                    // Поворачиваем стрелку у родителя
                    const parentLi = parentUl.closest('li');
                    if (parentLi) {
                        const caret = parentLi.querySelector(':scope > .tree-node > .caret');
                        if (caret) caret.classList.add('down');
                    }
                    parentUl = parentUl.closest('ul.nested');
                }
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
    if (!treeContainer) return;
    
    treeContainer.addEventListener('click', function(e) {
        // Клик по названию группы
        const groupSpan = e.target.closest('.group-name');
        if (groupSpan) {
            const nodeId = groupSpan.dataset.id;
            
            treeContainer.querySelectorAll('.tree-node').forEach(node => {
                node.classList.remove('active');
            });
            
            const clickedNode = e.target.closest('.tree-node');
            if (clickedNode) clickedNode.classList.add('active');
            
            if (nodeId === 'ungrouped') {
                loadAssets(null, true);
            } else {
                loadAssets(parseInt(nodeId), false);
            }
            return;
        }
        
        // Клик по стрелке
        const caret = e.target.closest('.caret');
        if (caret) {
            e.stopPropagation(); // Предотвращаем всплытие события

            const parentLi = caret.closest('li');

            if (parentLi) {
                // Находим ul.nested как следующий соседний элемент после .tree-node
                const nestedUl = parentLi.querySelector('ul.nested');

                if (nestedUl) {
                    // Переключаем класс active для показа/скрытия вложенного списка
                    nestedUl.classList.toggle('active');
                }
            }

            caret.classList.toggle('down');
        }
    });
}

export function getCurrentFilter() {
    return currentFilter;
}