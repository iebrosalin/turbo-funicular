// static/js/modules/utils.js

/**
 * Заполняет выпадающие списки родительских групп с визуальной иерархией.
 */
export async function populateParentSelect(excludeIds = [], selectedId = null) {
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

                const indent = '  '; // 2 пробела на уровень
                const label = indent.repeat(level) + node.name;
                
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

export function closeModalById(modalId) {
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