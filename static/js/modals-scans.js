// static/js/modals-scans.js
/**
 * Логика работы модальных окон сканирования (Импорт, Результаты, Ошибки)
 */

document.addEventListener('DOMContentLoaded', function() {
    initScanImportForm();
    // Загружаем список групп при загрузке страницы
    if (typeof updateImportGroupList === 'function') {
        updateImportGroupList();
    }
});

/**
 * Инициализация формы импорта сканирования
 */
function initScanImportForm() {
    const form = document.getElementById('scanImportForm');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('import-file');
        const groupSelect = document.getElementById('import-group-id');
        const progressDiv = document.getElementById('import-progress');
        const submitBtn = form.querySelector('button[type="submit"]');

        if (!fileInput.files.length) {
            alert('Пожалуйста, выберите файл.');
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        if (groupSelect.value) {
            formData.append('group_id', groupSelect.value);
        }

        // UI обновления
        submitBtn.disabled = true;
        progressDiv.style.display = 'block';
        
        try {
            // Предполагаемый эндпоинт. Замените 'main.import_scan' на реальный URL если он отличается
            const response = await fetch('/api/scans/import', { 
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok) {
                // Успех
                bootstrap.Modal.getInstance(document.getElementById('scanImportModal')).hide();
                alert(`Импорт успешно завершен! Обработано активов: ${result.count || 0}`);
                location.reload(); // Перезагрузка для обновления данных
            } else {
                // Ошибка сервера
                showErrorModal(result.error || 'Неизвестная ошибка при импорте');
            }
        } catch (error) {
            console.error('Import error:', error);
            showErrorModal('Ошибка соединения: ' + error.message);
        } finally {
            submitBtn.disabled = false;
            progressDiv.style.display = 'none';
        }
    });
}

/**
 * Показать модальное окно с ошибкой сканирования
 * @param {string} message - Текст ошибки
 */
function showErrorModal(message) {
    const contentDiv = document.getElementById('scan-error-content');
    if (contentDiv) {
        contentDiv.innerHTML = `<div class="alert alert-danger">${message}</div>`;
    }
    
    const modalEl = document.getElementById('scanErrorModal');
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
}

/**
 * Показать модальное окно с результатами сканирования
 * @param {string} htmlContent - HTML контент результатов
 * @param {string|null} errorText - Текст ошибки (если есть)
 */
function showResultsModal(htmlContent, errorText = null) {
    const contentDiv = document.getElementById('scan-results-content');
    const errorAlert = document.getElementById('scan-error-alert');
    const errorTextPre = document.getElementById('scan-error-text');

    if (contentDiv) {
        contentDiv.innerHTML = htmlContent;
    }

    if (errorText && errorTextPre && errorAlert) {
        errorTextPre.textContent = errorText;
        errorAlert.style.display = 'block';
    } else if (errorAlert) {
        errorAlert.style.display = 'none';
    }

    const modalEl = document.getElementById('scanResultsModal');
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
}

/**
 * Динамическое обновление списка групп в модалке импорта (если нужно)
 */
async function updateImportGroupList() {
    const INDENT_PER_LEVEL = 24; // пикселей на каждый уровень
    
    try {
        const res = await fetch('/api/groups/tree');
        if (!res.ok) return;
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

        // Генерация div-элементов с отступами через margin-left
        const generateTreeItems = (nodes, level = 0) => {
            let items = [];
            nodes.forEach(node => {
                const indentPx = level * INDENT_PER_LEVEL;
                
                const itemDiv = document.createElement('div');
                itemDiv.className = 'group-tree-item';
                itemDiv.textContent = node.name;
                itemDiv.dataset.id = node.id;
                // Применяем отступ через стиль
                itemDiv.style.marginLeft = indentPx + 'px';
                itemDiv.style.cursor = 'pointer';
                itemDiv.style.padding = '4px 8px';
                itemDiv.style.borderRadius = '4px';
                itemDiv.onmouseover = () => itemDiv.style.backgroundColor = '#e9ecef';
                itemDiv.onmouseout = (e) => {
                    if (!e.currentTarget.classList.contains('selected')) {
                        itemDiv.style.backgroundColor = '';
                    }
                };
                itemDiv.onclick = () => {
                    // Снимаем выделение со всех
                    document.querySelectorAll('.group-tree-item').forEach(el => {
                        el.classList.remove('selected');
                        el.style.backgroundColor = '';
                    });
                    // Выделяем текущий
                    itemDiv.classList.add('selected');
                    itemDiv.style.backgroundColor = '#0d6efd';
                    itemDiv.style.color = 'white';
                    // Устанавливаем значение в скрытый input
                    document.getElementById('import-group-id').value = node.id;
                };
                
                items.push(itemDiv);

                if (node.children && node.children.length > 0) {
                    items = items.concat(generateTreeItems(node.children, level + 1));
                }
            });
            return items;
        };
        
        const treeContainer = document.getElementById('import-group-tree');
        if (!treeContainer) return;

        // Сохраняем текущее значение
        const currentVal = document.getElementById('import-group-id')?.value || '';
        
        // Очищаем контейнер, оставляем только "Без группы"
        treeContainer.innerHTML = '<div class="group-tree-item" data-id="">Без группы</div>';
        
        const items = generateTreeItems(tree);
        items.forEach(item => treeContainer.appendChild(item));

        // Добавляем обработчик для "Без группы"
        const noGroupItem = treeContainer.querySelector('.group-tree-item[data-id=""]');
        if (noGroupItem) {
            noGroupItem.style.cursor = 'pointer';
            noGroupItem.style.padding = '4px 8px';
            noGroupItem.style.borderRadius = '4px';
            noGroupItem.onclick = () => {
                document.querySelectorAll('.group-tree-item').forEach(el => {
                    el.classList.remove('selected');
                    el.style.backgroundColor = '';
                    el.style.color = '';
                });
                noGroupItem.classList.add('selected');
                noGroupItem.style.backgroundColor = '#0d6efd';
                noGroupItem.style.color = 'white';
                document.getElementById('import-group-id').value = '';
            };
        }

        // Восстанавливаем выделение если возможно
        if (currentVal) {
            const selectedItem = treeContainer.querySelector(`.group-tree-item[data-id="${currentVal}"]`);
            if (selectedItem) {
                selectedItem.click();
            } else {
                noGroupItem?.click();
            }
        }
    } catch (e) {
        console.error('Не удалось обновить список групп для импорта', e);
    }
}

// Экспорт функций для глобального доступа
window.showScanError = showErrorModal;
window.showScanResults = showResultsModal;
window.updateImportGroupList = updateImportGroupList;