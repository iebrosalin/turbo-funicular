// Конфигурация API
const API_BASE = '/api'; // Замените на ваш базовый путь API

// Глобальное состояние
let currentAssetsPage = 1;
let selectedAssetIds = new Set();
let allGroups = [];

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    loadGroups();
    loadAssets();
    
    // Обработчик поиска
    document.getElementById('assetSearch').addEventListener('input', (e) => {
        currentAssetsPage = 1;
        loadAssets();
    });

    // Обработчик фильтра по группам
    document.getElementById('assetGroupFilter').addEventListener('change', () => {
        currentAssetsPage = 1;
        loadAssets();
    });
});

// --- Функции работы с Активы ---

async function loadAssets() {
    const tbody = document.getElementById('assetsTableBody');
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4"><div class="loader"></div> Загрузка...</td></tr>';

    const search = document.getElementById('assetSearch').value;
    const groupFilter = document.getElementById('assetGroupFilter').value;
    
    // Параметры запроса
    const params = new URLSearchParams({
        page: currentAssetsPage,
        size: 50, // Показываем много элементов, без жесткого лимита
        search: search,
        group_id: groupFilter
    });

    try {
        const response = await fetch(`${API_BASE}/assets?${params.toString()}`);
        if (!response.ok) throw new Error('Ошибка сети');
        
        const data = await response.json();
        renderAssets(data.items || data); // Поддержка разных форматов ответа
        renderPagination(data.total || data.count, data.page || currentAssetsPage, data.size || 50, 'assets');
        
    } catch (error) {
        console.error('Ошибка загрузки активов:', error);
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Ошибка: ${error.message}</td></tr>`;
    }
}

function renderAssets(assets) {
    const tbody = document.getElementById('assetsTableBody');
    if (!assets || assets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4">Активы не найдены</td></tr>';
        return;
    }

    tbody.innerHTML = assets.map(asset => `
        <tr>
            <td><input type="checkbox" class="asset-checkbox" value="${asset.id}" onchange="toggleAssetSelection(${asset.id})"></td>
            <td><strong>${asset.ip || 'N/A'}</strong></td>
            <td>${asset.hostname || asset.name || '-'}</td>
            <td>
                <small class="text-muted d-block">${asset.redcheck_guid ? 'RG: ' + asset.redcheck_guid.substring(0,8) + '...' : '-'}</small>
                <small class="text-muted">${asset.uuid ? 'UU: ' + asset.uuid.substring(0,8) + '...' : ''}</small>
            </td>
            <td>
                ${asset.groups && asset.groups.length > 0 
                    ? asset.groups.map(g => `<span class="group-tag">${g.name}</span>`).join('') 
                    : '<span class="text-muted small">Нет групп</span>'}
            </td>
            <td>
                <span class="badge ${getStatusBadgeClass(asset.status)} status-badge">
                    ${asset.status || 'unknown'}
                </span>
            </td>
            <td>${formatDate(asset.last_seen)}</td>
            <td>
                <button class="btn btn-sm btn-outline-info action-btn" title="Детали" onclick="showAssetDetails(${asset.id})">
                    <i class="fas fa-eye"></i>
                </button>
                <button class="btn btn-sm btn-outline-warning action-btn" title="Редактировать" onclick="editAsset(${asset.id})">
                    <i class="fas fa-edit"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

function getStatusBadgeClass(status) {
    if (!status) return 'bg-secondary';
    const s = status.toLowerCase();
    if (s === 'online' || s === 'alive') return 'bg-success';
    if (s === 'offline' || s === 'dead') return 'bg-danger';
    if (s === 'warning') return 'bg-warning text-dark';
    return 'bg-info';
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU') + ' ' + date.toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'});
}

// --- Пагинация ---

function renderPagination(total, currentPage, pageSize, type) {
    const container = document.getElementById(`${type}Pagination`);
    if (!total) {
        container.innerHTML = '';
        return;
    }

    const totalPages = Math.ceil(total / pageSize);
    let html = '';

    // Кнопка "Назад"
    html += `<li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="changePage('${type}', ${currentPage - 1}); return false;">&laquo;</a>
             </li>`;

    // Номера страниц (упрощенная логика)
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += `<li class="page-item ${i === currentPage ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="changePage('${type}', ${i}); return false;">${i}</a>
                     </li>`;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
    }

    // Кнопка "Вперед"
    html += `<li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="changePage('${type}', ${currentPage + 1}); return false;">&raquo;</a>
             </li>`;

    container.innerHTML = html;
}

function changePage(type, page) {
    if (type === 'assets') {
        currentAssetsPage = page;
        loadAssets();
    }
    window.scrollTo(0, 0);
}

// --- Выбор активов ---

function toggleSelectAll(type) {
    const checkbox = document.getElementById(`selectAll${type.charAt(0).toUpperCase() + type.slice(1)}`);
    const checkboxes = document.querySelectorAll(`.${type}-checkbox`);
    
    checkboxes.forEach(cb => {
        cb.checked = checkbox.checked;
        if (checkbox.checked) {
            selectedAssetIds.add(parseInt(cb.value));
        } else {
            selectedAssetIds.delete(parseInt(cb.value));
        }
    });
    updateSelectedCount();
}

function toggleAssetSelection(id) {
    if (selectedAssetIds.has(id)) {
        selectedAssetIds.delete(id);
    } else {
        selectedAssetIds.add(id);
    }
    updateSelectedCount();
}

function updateSelectedCount() {
    document.getElementById('selectedCount').innerText = selectedAssetIds.size;
}

// --- Группы ---

async function loadGroups() {
    try {
        const response = await fetch(`${API_BASE}/groups`);
        if (!response.ok) throw new Error('Ошибка загрузки групп');
        const data = await response.json();
        allGroups = data.items || data;
        
        // Заполнить фильтр в таблице активов
        const filterSelect = document.getElementById('assetGroupFilter');
        const targetSelect = document.getElementById('targetGroupSelect');
        
        // Сохраняем текущее значение фильтра
        const currentFilter = filterSelect.value;
        
        filterSelect.innerHTML = '<option value="">Все группы</option>';
        targetSelect.innerHTML = '';
        
        allGroups.forEach(group => {
            const option1 = document.createElement('option');
            option1.value = group.id;
            option1.textContent = group.name;
            filterSelect.appendChild(option1);
            
            const option2 = document.createElement('option');
            option2.value = group.id;
            option2.textContent = `${group.name} (${group.asset_count || 0} акт.)`;
            targetSelect.appendChild(option2);
        });
        
        // Восстанавливаем выбор фильтра
        filterSelect.value = currentFilter;

        // Рендер карточек групп
        renderGroups(allGroups);

    } catch (error) {
        console.error('Ошибка загрузки групп:', error);
    }
}

function renderGroups(groups) {
    const container = document.getElementById('groupsContainer');
    if (!groups || groups.length === 0) {
        container.innerHTML = '<div class="col-12 text-center text-muted">Группы не созданы</div>';
        return;
    }

    container.innerHTML = groups.map(group => `
        <div class="col-md-6 col-lg-4 mb-4">
            <div class="card h-100">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h5 class="card-title mb-0">${group.name}</h5>
                        <span class="badge bg-primary rounded-pill">${group.asset_count || 0}</span>
                    </div>
                    <p class="card-text text-muted small">${group.description || 'Описание отсутствует'}</p>
                    <div class="mt-3">
                        <button class="btn btn-sm btn-outline-primary" onclick="viewGroupAssets(${group.id})">
                            <i class="fas fa-list me-1"></i>Активы
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteGroup(${group.id})">
                            <i class="fas fa-trash me-1"></i>Удалить
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

// --- Модальные окна и действия ---

function openCreateGroupModal() {
    const modal = new bootstrap.Modal(document.getElementById('createGroupModal'));
    document.getElementById('newGroupName').value = '';
    modal.show();
}

async function createGroup() {
    const name = document.getElementById('newGroupName').value.trim();
    if (!name) return alert('Введите название группы');

    try {
        const response = await fetch(`${API_BASE}/groups`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name})
        });
        
        if (!response.ok) throw new Error('Ошибка создания');
        
        bootstrap.Modal.getInstance(document.getElementById('createGroupModal')).hide();
        loadGroups();
        loadAssets(); // Обновить фильтры
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

function openAddToGroupModal() {
    if (selectedAssetIds.size === 0) return alert('Выберите хотя бы один актив');
    const modal = new bootstrap.Modal(document.getElementById('addToGroupModal'));
    modal.show();
}

async function addAssetsToGroup() {
    const groupId = document.getElementById('targetGroupSelect').value;
    if (!groupId) return alert('Выберите группу назначения');

    try {
        // Используем bulk-move эндпоинт для перемещения активов в группу
        const response = await fetch(`${API_BASE}/assets/bulk-move`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ids: Array.from(selectedAssetIds), group_id: parseInt(groupId)})
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Ошибка перемещения');
        }
        
        const result = await response.json();
        bootstrap.Modal.getInstance(document.getElementById('addToGroupModal')).hide();
        selectedAssetIds.clear();
        updateSelectedCount();
        document.getElementById('selectAllAssets').checked = false;
        alert(`Успешно перемещено активов: ${result.count}`);
        loadAssets();
        loadGroups();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

async function deleteSelectedAssets() {
    if (selectedAssetIds.size === 0) return alert('Выберите активы для удаления');
    if (!confirm(`Вы уверены, что хотите удалить ${selectedAssetIds.size} активов?`)) return;

    try {
        // Используем bulk-delete эндпоинт для пакетного удаления
        const response = await fetch(`${API_BASE}/assets/bulk-delete`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ids: Array.from(selectedAssetIds)})
        });
        
        if (!response.ok && response.status !== 204) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Ошибка удаления');
        }
        
        selectedAssetIds.clear();
        updateSelectedCount();
        loadAssets();
        loadGroups();
        alert('Активы успешно удалены');
    } catch (error) {
        alert('Ошибка удаления: ' + error.message);
    }
}

async function deleteGroup(id) {
    if (!confirm('Вы уверены? Все связи с активами будут удалены.')) return;
    
    try {
        await fetch(`${API_BASE}/groups/${id}`, {method: 'DELETE'});
        loadGroups();
        loadAssets();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

function viewGroupAssets(groupId) {
    document.getElementById('assetGroupFilter').value = groupId;
    document.getElementById('pills-assets-tab').click();
    loadAssets();
}

// Заглушки для деталей и редактирования
function showAssetDetails(id) {
    alert(`Показать детали актива ${id} (требуется реализация модалки)`);
}

function editAsset(id) {
    alert(`Редактировать актив ${id} (требуется реализация)`);
}

// --- RedCheck ---

async function loadRedCheckHosts() {
    const tbody = document.getElementById('redcheckTableBody');
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4"><div class="loader"></div> Загрузка данных RedCheck...</td></tr>';

    try {
        // Эндпоинт для получения сырых данных из БД redcheck_hosts
        const response = await fetch(`${API_BASE}/redcheck/hosts`);
        if (!response.ok) throw new Error('Ошибка сети');
        
        const data = await response.json();
        const hosts = data.items || data;

        if (!hosts || hosts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Данные RedCheck отсутствуют. Выполните синхронизацию.</td></tr>';
            return;
        }

        tbody.innerHTML = hosts.map(host => `
            <tr>
                <td><strong>${host.ip || host.connection_address || '-'}</strong></td>
                <td><small>${host.redcheck_guid ? host.redcheck_guid.substring(0,8)+'...' : '-'}</small></td>
                <td><small>${host.uuid ? host.uuid.substring(0,8)+'...' : '-'}</small></td>
                <td><small class="text-truncate" style="max-width: 150px;" title="${host.cpe || ''}">${host.cpe || '-'}</small></td>
                <td>${host.is_dns ? '<i class="fas fa-check text-success"></i>' : '<i class="fas fa-times text-muted"></i>'}</td>
                <td><span class="badge ${host.status === 'alive' ? 'bg-success' : 'bg-secondary'}">${host.status || 'unknown'}</span></td>
                <td>${formatDate(host.last_seen || host.modified_date)}</td>
            </tr>
        `).join('');

    } catch (error) {
        console.error('Ошибка загрузки RedCheck:', error);
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Ошибка: ${error.message}</td></tr>`;
    }
}
