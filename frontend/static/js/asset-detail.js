/**
 * Страница детали актива - редактирование и отображение
 */

document.addEventListener('DOMContentLoaded', () => {
    const assetId = window.assetData?.id || null;
    if (!assetId) {
        console.error('[AssetDetail] Asset ID not found');
        return;
    }

    let isEditMode = false;

    // Кнопка переключения режима редактирования
    const toggleEditBtn = document.getElementById('toggleEditBtn');
    const saveBtn = document.getElementById('saveAssetBtn');
    const cancelBtn = document.getElementById('cancelEditBtn');

    if (toggleEditBtn) {
        toggleEditBtn.addEventListener('click', () => {
            isEditMode = !isEditMode;
            toggleEditMode(isEditMode);
        });
    }

    if (saveBtn) {
        saveBtn.addEventListener('click', saveAssetData);
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            isEditMode = false;
            toggleEditMode(false);
            location.reload(); // Перезагружаем для сброса изменений
        });
    }

    function toggleEditMode(enabled) {
        const inputs = document.querySelectorAll('.asset-edit-input');
        const viewElements = document.querySelectorAll('.asset-view-value');
        const editControls = document.getElementById('editControls');
        const taxonomyTab = document.getElementById('taxonomy-tab');
        const logsTab = document.getElementById('logs-tab');

        inputs.forEach(input => {
            input.disabled = !enabled;
        });

        viewElements.forEach(el => {
            el.style.display = enabled ? 'none' : '';
        });

        if (editControls) {
            editControls.style.display = enabled ? 'block' : 'none';
        }
        
        // Обновляем текст кнопки
        if (toggleEditBtn) {
            toggleEditBtn.innerHTML = enabled 
                ? '<i class="bi bi-x-lg"></i> Закрыть' 
                : '<i class="bi bi-pencil"></i> Редактировать';
        }

        // Блокируем вкладки Таксономия и История изменений в режиме редактирования
        if (taxonomyTab) {
            taxonomyTab.disabled = enabled;
            taxonomyTab.style.opacity = enabled ? '0.5' : '1';
            taxonomyTab.style.pointerEvents = enabled ? 'none' : 'auto';
        }
        if (logsTab) {
            logsTab.disabled = enabled;
            logsTab.style.opacity = enabled ? '0.5' : '1';
            logsTab.style.pointerEvents = enabled ? 'none' : 'auto';
        }

        if (enabled) {
            // Переключаем на первую вкладку при включении редактирования
            const overviewTab = document.querySelector('[data-bs-target="#overview"]');
            if (overviewTab) {
                const tab = new bootstrap.Tab(overviewTab);
                tab.show();
            }
        }
    }

    async function saveAssetData() {
        const formData = collectFormData();
        
        try {
            const response = await fetch(`/api/assets/${assetId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                const data = await response.json();
                showNotification('success', 'Данные успешно сохранены');
                isEditMode = false;
                toggleEditMode(false);
                
                // Обновляем данные на странице через небольшое обновление
                setTimeout(() => location.reload(), 1000);
            } else {
                const error = await response.json();
                showNotification('danger', `Ошибка: ${error.detail || 'Не удалось сохранить'}`);
            }
        } catch (err) {
            console.error('[AssetDetail] Save error:', err);
            showNotification('danger', 'Ошибка сети или сервера');
        }
    }

    function collectFormData() {
        const data = {};
        
        // Основная информация
        const fields = [
            'ip_address', 'hostname', 'fqdn', 'device_type',
            'os_family', 'os_version', 'owner', 'location', 'status',
            'mac_address', 'vendor', 'source'
        ];
        
        fields.forEach(field => {
            const input = document.querySelector(`[name="${field}"]`);
            if (input && !input.disabled) {
                data[field] = input.value || null;
            }
        });

        // Группы (если есть select)
        const groupSelect = document.querySelector('[name="group_id"]');
        if (groupSelect && !groupSelect.disabled) {
            data.group_id = groupSelect.value ? parseInt(groupSelect.value) : null;
        }

        // DNS имена (textarea)
        const dnsNamesInput = document.querySelector('[name="dns_names"]');
        if (dnsNamesInput && !dnsNamesInput.disabled) {
            const names = dnsNamesInput.value.split('\n').filter(n => n.trim());
            data.dns_names = names;
        }

        // Порты (textareas)
        ['rustscan_ports', 'nmap_ports'].forEach(portField => {
            const input = document.querySelector(`[name="${portField}"]`);
            if (input && !input.disabled) {
                const ports = input.value.split('\n')
                    .filter(p => p.trim())
                    .map(p => parseInt(p.trim()))
                    .filter(p => !isNaN(p));
                data[portField] = ports;
            }
        });

        return data;
    }

    function showNotification(type, message) {
        const container = document.getElementById('notificationContainer') || document.body;
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alert.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        container.appendChild(alert);
        
        setTimeout(() => alert.remove(), 5000);
    }

    // Инициализация - скрываем кнопки редактирования если они есть
    const editControls = document.getElementById('editControls');
    if (editControls) {
        editControls.style.display = 'none';
    }
});
