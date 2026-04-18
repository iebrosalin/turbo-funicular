// static/js/modules/tree.js

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
                    <li class="tree-node ${indentClass}" data-id="${node.id}">
                        ${hasChildren ? '<span class="caret"></span>' : '<span class="caret-spacer"></span>'}
                        <span class="group-name" 
                              data-id="${node.id}" 
                              data-name="${node.name}"
                              data-parent="${node.parent_id || ''}"
                              data-type="${node.is_cidr ? 'cidr' : node.is_dynamic ? 'dynamic' : 'manual'}">
                            ${node.name}
                            ${node.is_cidr ? '<i class="bi bi-globe ms-1 text-muted" title="CIDR группа"></i>' : ''}
                            ${node.is_dynamic ? '<i class="bi bi-funnel ms-1 text-muted" title="Динамическая группа"></i>' : ''}
                        </span>
                        <span class="badge bg-secondary ms-auto">${node.asset_count || 0}</span>
                    </li>
                `;
                
                if (hasChildren) {
                    html += `<ul class="nested">${buildTreeHtml(nodes, node.id)}</ul>`;
                }
            });
            
            return html;
        };

        // Ungrouped секция
        let ungroupedHtml = `
            <li class="tree-node" data-id="ungrouped">
                <span class="group-name" data-id="ungrouped">
                    <i class="bi bi-inbox me-1"></i>Без группы
                </span>
                <span class="badge bg-secondary ms-auto">${data.ungrouped_count || 0}</span>
            </li>
        `;

        treeContainer.innerHTML = ungroupedHtml + buildTreeHtml(data.flat);

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

        // Пересоздаем обработчики событий
        if (typeof initTreeTogglers === 'function') {
            initTreeTogglers();
        }

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
        
        if (typeof renderAssets === 'function') {
            renderAssets(data);
        }
    } catch (e) {
        console.error('Ошибка загрузки активов:', e);
    }
}
