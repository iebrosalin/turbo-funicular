/**
 * Модуль управления деревом групп и фильтрацией активов
 */

// Глобальное состояние для текущей выбранной группы (опционально)
let currentGroupId = null;

/**
 * Отрисовка дерева групп внутри контейнера #group-tree-root
 * ВАЖНО: Эта функция очищает ТОЛЬКО #group-tree-root, не затрагивая 
 * статические элементы "Все активы" и "Без группы", которые лежат выше/ниже в #group-tree.
 * 
 * @param {Array} groups - Массив объектов групп {id, name, depth, ...}
 * @param {Object} counts - Объект счетчиков {groupId: count, ungrouped: count}
 */
export function renderTree(groups, counts) {
    const container = document.getElementById('group-tree-root');
    if (!container) {
        console.error('Контейнер #group-tree-root не найден');
        return;
    }

    // Очищаем ТОЛЬКО контейнер для динамических групп
    container.innerHTML = '';

    // Вспомогательная функция для создания HTML элемента узла
    function createNodeElement(group, depth) {
        const node = document.createElement('div');
        node.className = 'tree-node';
        node.dataset.id = group.id;
        // Отступ зависит от глубины вложенности
        node.style.paddingLeft = `${depth * 20}px`;

        // Иконка папки
        const icon = document.createElement('i');
        icon.className = 'bi bi-folder folder-icon';
        node.appendChild(icon);

        // Название группы
        const nameSpan = document.createElement('span');
        nameSpan.className = 'group-name';
        nameSpan.textContent = group.name;
        nameSpan.dataset.id = group.id;
        node.appendChild(nameSpan);

        // Бейдж с количеством
        const badge = document.createElement('span');
        badge.className = 'badge bg-secondary ms-auto';
        badge.id = `count-${group.id}`;
        badge.textContent = counts[group.id] !== undefined ? counts[group.id] : 0;
        node.appendChild(badge);

        return node;
    }

    if (Array.isArray(groups)) {
        groups.forEach(group => {
            const el = createNodeElement(group, group.depth || 0);
            container.appendChild(el);
            
            // Навешиваем обработчик клика на каждую группу
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                handleGroupClick(group.id);
            });
        });
    }
    
    // Обновляем счетчик "Все активы" (сумма всех прямых активов групп + без группы)
    // counts уже содержит direct_count для каждой группы, поэтому просто суммируем
    const allCount = Object.values(counts).reduce((a, b) => a + b, 0);
    const allBadge = document.getElementById('count-all');
    if (allBadge) {
        allBadge.textContent = allCount;
    }

    // Обновляем счетчик "Без группы"
    const ungroupedBadge = document.getElementById('count-ungrouped');
    if (ungroupedBadge) {
        ungroupedBadge.textContent = counts['ungrouped'] || 0;
    }
}

/**
 * Обработчик клика по группе (динамической или статической)
 * @param {string|number} groupId - ID группы, 'all' или 'ungrouped'
 */
function handleGroupClick(groupId) {
    // Снимаем активный класс со всех узлов
    document.querySelectorAll('.tree-node').forEach(n => n.classList.remove('active'));
    
    let targetElement;
    // Находим элемент, по которому кликнули
    if (groupId === 'all') {
        targetElement = document.querySelector('.tree-node[data-id="all"]');
    } else if (groupId === 'ungrouped') {
        targetElement = document.querySelector('.tree-node[data-id="ungrouped"]');
    } else {
        targetElement = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    }

    // Добавляем активный класс
    if (targetElement) {
        targetElement.classList.add('active');
    }

    // Вызываем глобальную функцию фильтрации таблицы активов
    if (typeof window.filterByGroup === 'function') {
        window.filterByGroup(groupId);
    } else {
        // Если глобальная функция еще не определена, вызываем локальную логику
        filterByGroup(groupId);
    }
}

/**
 * Инициализация обработчиков для СТАТИЧЕСКИХ элементов ("Все активы", "Без группы").
 * Вызывается после загрузки DOM или обновления дерева.
 */
export function initGroupTreeStaticListeners() {
    const allNode = document.querySelector('.tree-node[data-id="all"]');
    if (allNode) {
        // Удаляем старые слушатели клонированием (простой способ сброса без утечек)
        const newAllNode = allNode.cloneNode(true);
        allNode.parentNode.replaceChild(newAllNode, allNode);
        
        newAllNode.addEventListener('click', (e) => {
            e.stopPropagation();
            handleGroupClick('all');
        });
    }

    const ungroupedNode = document.querySelector('.tree-node[data-id="ungrouped"]');
    if (ungroupedNode) {
        const newUngroupedNode = ungroupedNode.cloneNode(true);
        ungroupedNode.parentNode.replaceChild(newUngroupedNode, ungroupedNode);

        newUngroupedNode.addEventListener('click', (e) => {
            e.stopPropagation();
            handleGroupClick('ungrouped');
        });
    }
}

/**
 * Загрузка активов с сервера и рендеринг таблицы
 * Реализована внутри модуля, чтобы не зависеть от импорта assets.js
 * 
 * @param {number|null} groupId - ID группы или null (для всех или без группы)
 * @param {boolean} isUngrouped - true если запрашиваем активы БЕЗ группы
 * @param {string} targetTableId - ID элемента tbody, куда вставлять строки
 * @param {string|null} assetsContainerId - ID контейнера (резерв)
 */
export async function loadAssets(groupId = null, isUngrouped = false, targetTableId = 'assets-body', assetsContainerId = null) {
    const tbody = document.getElementById(targetTableId);
    if (!tbody) {
        console.warn(`Таблица с ID ${targetTableId} не найдена. Прерывание загрузки.`);
        return;
    }

    // Показываем индикатор загрузки
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><p class="mt-2 text-muted">Загрузка активов...</p></td></tr>';

    // Формируем параметры запроса
    const params = new URLSearchParams();
    
    if (isUngrouped) {
        // Вариант 1: Явный флаг (если бэкенд поддерживает ?ungrouped=true)
        params.append('ungrouped', 'true');
        // Вариант 2: Явный null (если бэкенд поддерживает ?group_id=null) - более надежно
        params.append('group_id', 'null'); 
    } else if (groupId !== null && groupId !== 'all') {
        params.append('group_id', String(groupId));
    }
    // Если groupId === null и isUngrouped === false -> загружаем все (параметры пустые)

    const queryString = params.toString();
    const url = `/api/assets${queryString ? '?' + queryString : ''}`;

    try {
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`Ошибка сервера: ${response.status}`);
        }

        const data = await response.json();
        const assets = Array.isArray(data) ? data : (data.assets || []);

        // Очищаем таблицу
        tbody.innerHTML = '';

        if (assets.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">Активы не найдены</td></tr>';
            return;
        }

        // Рендеринг строк
        assets.forEach(asset => {
            const tr = document.createElement('tr');
            
            // Определение статуса OSquery для иконки
            const osqueryIcon = asset.osquery_status === 'online' 
                ? '<i class="bi bi-pc-display text-success" title="OSquery Online"></i>' 
                : '<i class="bi bi-pc-display text-muted" title="OSquery Offline"></i>';

            // Формирование строки таблицы (адаптируйте колонки под вашу верстку)
            tr.innerHTML = `
                <td>${osqueryIcon}</td>
                <td><strong>${asset.ip_address || 'N/A'}</strong></td>
                <td>${asset.hostname || '<span class="text-muted">-</span>'}</td>
                <td>${asset.os_info || '<span class="text-muted">-</span>'}</td>
                <td><small>${asset.open_ports || '<span class="text-muted">-</span>'}</small></td>
                <td>${asset.group_name ? `<span class="badge bg-light text-dark border">${asset.group_name}</span>` : '<span class="badge bg-secondary">Без группы</span>'}</td>
                <td class="text-end">
                    <button class="btn btn-sm btn-outline-primary" onclick="window.editAsset(${asset.id})" title="Редактировать">
                        <i class="bi bi-pencil"></i>
                    </button>
                </td>
            `;
            
            // Добавляем обработчик клика на строку (опционально, для перехода к деталям)
            tr.style.cursor = 'pointer';
            tr.addEventListener('click', (e) => {
                // Игнорируем клик по кнопкам действий
                if (e.target.closest('button')) return;
                window.location.href = `/asset/${asset.id}`;
            });

            tbody.appendChild(tr);
        });

    } catch (error) {
        console.error('Ошибка загрузки активов:', error);
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4">Ошибка загрузки: ${error.message}</td></tr>`;
    }
}

/**
 * Глобальная функция обновления дерева групп
 * Доступна из window для вызова из HTML
 */
export async function refreshGroupTree() {
    return fetch('/api/groups/tree')
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            // Поддержка разных форматов ответа API
            let groups = [];
            let counts = {};

            // Формат от /api/groups/tree: {tree: [...], flat: [...], ungrouped_count: N}
            if (data.flat && Array.isArray(data.flat)) {
                groups = data.flat;
                // Строим counts из flat списка - используем direct_count для избежания дублирования
                groups.forEach(g => {
                    // Используем direct_count если есть (прямые активы без вложенных), иначе count или asset_count
                    counts[g.id] = g.direct_count !== undefined ? g.direct_count : (g.count || g.asset_count || 0);
                });
                // Добавляем счетчик "Без группы"
                counts['ungrouped'] = data.ungrouped_count || 0;
            } else if (Array.isArray(data)) {
                groups = data;
            } else if (data.groups) {
                groups = data.groups;
                counts = data.counts || {};
            }

            renderTree(groups, counts);
            
            // Перепривязываем слушатели к статическим элементам после перерисовки
            initGroupTreeStaticListeners();
            
            return Promise.resolve();
        })
        .catch(err => console.error('Ошибка загрузки дерева групп:', err));
};

/**
 * Функция фильтрации активов (SPA)
 * Вызывается при клике на элементы дерева
 * 
 * @param {string|number|null} groupId - ID группы, 'all', 'ungrouped'
 * @param {boolean} isUngrouped - Устаревший флаг, логика определяется через groupId
 * @param {string} targetTableId - ID tbody
 * @param {string|null} assetsContainerId - Резерв
 */
export function filterByGroup(groupId, isUngrouped = false, targetTableId = 'assets-body', assetsContainerId = null) {
    currentGroupId = groupId;

    // Визуальное выделение активной группы
    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));
    let activeNode;
    if (groupId === 'all') activeNode = document.querySelector('.tree-node[data-id="all"]');
    else if (groupId === 'ungrouped') activeNode = document.querySelector('.tree-node[data-id="ungrouped"]');
    else activeNode = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    
    if (activeNode) activeNode.classList.add('active');

    // Логика определения параметров для loadAssets
    if (groupId === 'ungrouped') {
        // Активы без группы
        loadAssets(null, true, targetTableId, assetsContainerId);
    } else if (groupId === 'all') {
        // Все активы
        loadAssets(null, false, targetTableId, assetsContainerId);
    } else {
        // Конкретная группа
        loadAssets(parseInt(groupId), false, targetTableId, assetsContainerId);
    }
}

// Экспорт функций в глобальную область видимости для доступа из HTML и других модулей
window.initGroupTreeStaticListeners = initGroupTreeStaticListeners;
window.filterByGroup = filterByGroup;
window.loadAssets = loadAssets;

/**
 * Инициализация обработчиков сворачивания/разворачивания (заглушка)
 */
export function initTreeTogglers() {
    // Здесь может быть логика для стрелочек сворачивания, если она потребуется в будущем
    // Сейчас функционал сворачивания не реализован в базовой версии
}
window.initTreeTogglers = initTreeTogglers;
