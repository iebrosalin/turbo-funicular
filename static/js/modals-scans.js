// static/js/modals-scans.js
/**
 * Логика работы модальных окон сканирования (Импорт, Результаты, Ошибки)
 */

document.addEventListener('DOMContentLoaded', function() {
    initScanImportForm();
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
    try {
        const response = await fetch('/api/groups');
        if (!response.ok) return;
        const groups = await response.json();
        
        const select = document.getElementById('import-group-id');
        if (!select) return;

        // Сохраняем текущее значение
        const currentVal = select.value;
        
        // Очищаем кроме первого элемента
        select.innerHTML = '<option value="">Без группы</option>';
        
        groups.forEach(g => {
            const option = document.createElement('option');
            option.value = g.id;
            option.textContent = g.name;
            select.appendChild(option);
        });

        // Восстанавливаем значение если возможно
        if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) {
            select.value = currentVal;
        }
    } catch (e) {
        console.error('Не удалось обновить список групп для импорта', e);
    }
}

// Экспорт функций для глобального доступа
window.showScanError = showErrorModal;
window.showScanResults = showResultsModal;
window.updateImportGroupList = updateImportGroupList;