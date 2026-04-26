// static/js/scans-page.js
/**
 * Логика страницы управления сканированиями.
 * Обработка форм, обновление статуса очередей и управление историей заданий.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация автодополнения для всех полей ввода сканирования
    document.querySelectorAll('.scan-input').forEach(input => {
        const scanType = input.dataset.scanType;
        if (scanType) {
            if (typeof window.initScanAutocomplete === 'function') {
                window.initScanAutocomplete(input, scanType);
            }
        }
    });

    // Загрузка начальных данных
    loadGroups();
    updateQueueStatus();
    loadJobs();
    
    // Автообновление статуса каждые 5 секунд
    setInterval(updateQueueStatus, 5000);
    setInterval(loadJobs, 5000);

    // --- Логика чекбокса "Только известные порты" (Nmap) ---
    const knownPortsCheckbox = document.getElementById('nmap-known-ports-only');
    const portsInput = document.getElementById('nmap-ports');
    const groupsSelect = document.getElementById('nmap-groups');
    const portsWarning = document.getElementById('nmap-ports-warning');
    const argsWarning = document.getElementById('nmap-args-warning');

    if (knownPortsCheckbox) {
        knownPortsCheckbox.addEventListener('change', function() {
            if (this.checked) {
                portsInput.disabled = true;
                portsInput.value = '';
                portsInput.placeholder = 'Блокировано';
                groupsSelect.disabled = false;
                portsWarning.classList.remove('d-none');
                argsWarning.classList.remove('d-none');
            } else {
                portsInput.disabled = false;
                portsInput.placeholder = '22,80,443 или 1-1000';
                groupsSelect.disabled = true;
                groupsSelect.selectedIndex = -1; // Сброс выбора
                portsWarning.classList.add('d-none');
                argsWarning.classList.add('d-none');
            }
        });
    }

    // --- Обработчик формы Nmap ---
    const nmapForm = document.getElementById('nmap-form');
    if (nmapForm) {
        nmapForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const target = document.getElementById('nmap-target').value.trim();
            const knownOnly = knownPortsCheckbox.checked;
            const groupOptions = groupsSelect.selectedOptions;
            const groupIds = Array.from(groupOptions).map(opt => opt.value);

            if (!target && !knownOnly) {
                alert('Укажите цель или выберите опцию "Только известные порты"');
                return;
            }
            if (knownOnly && groupIds.length === 0) {
                alert('Выберите хотя бы одну группу для сканирования известных портов');
                return;
            }

            const payload = {
                target: target,
                ports: portsInput.value,
                scripts: document.getElementById('nmap-scripts').value,
                custom_args: document.getElementById('nmap-custom-args').value,
                known_ports_only: knownOnly,
                group_ids: groupIds
            };

            await submitScan('/api/scans/nmap', payload, 'Nmap');
        });
    }

    // --- Обработчик формы Rustscan ---
    const rustscanForm = document.getElementById('rustscan-form');
    if (rustscanForm) {
        rustscanForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const payload = {
                target: document.getElementById('rustscan-target').value,
                ports: document.getElementById('rustscan-ports').value,
                custom_args: document.getElementById('rustscan-custom-args').value,
                run_nmap_after: document.getElementById('rustscan-run-nmap').checked,
                nmap_args: document.getElementById('rustscan-nmap-args').value
            };

            if (!payload.target) {
                alert('Укажите цель сканирования');
                return;
            }

            await submitScan('/api/scans/rustscan', payload, 'Rustscan');
        });
    }

    // --- Обработчик формы Dig ---
    const digForm = document.getElementById('dig-form');
    if (digForm) {
        digForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            let targetsText = document.getElementById('dig-targets').value.trim();
            const fileInput = document.getElementById('dig-file');

            // Если загружен файл, читаем его содержимое
            if (fileInput && fileInput.files && fileInput.files.length > 0) {
                const file = fileInput.files[0];
                try {
                    const fileContent = await readFileAsText(file);
                    const fileTargets = fileContent.split('\n')
                        .map(line => line.trim())
                        .filter(line => line && !line.startsWith('#'));

                    // Объединяем с текстовым полем, если есть
                    if (targetsText) {
                        const textTargets = targetsText.split('\n')
                            .map(line => line.trim())
                            .filter(line => line);
                        fileTargets.push(...textTargets);
                    }

                    targetsText = fileTargets.join('\n');
                } catch (error) {
                    alert('Ошибка чтения файла: ' + error.message);
                    return;
                }
            }

            if (!targetsText) {
                alert('Введите список целей или загрузите файл');
            }

            let recordTypes = null;
            const typesInput = document.getElementById('dig-types').value.trim();
            if (typesInput) {
                recordTypes = typesInput.split(',').map(t => t.trim().toUpperCase());
            }

            const payload = {
                targets_text: targetsText,
                dns_server: document.getElementById('dig-server').value,
                cli_args: document.getElementById('dig-cli-args').value,
                record_types: recordTypes
            };

            await submitScan('/api/scans/dig', payload, 'Dig');
        });
    }

    // --- Обработчик импорта XML Nmap ---
    const importXmlBtn = document.getElementById('import-xml-btn');
    if (importXmlBtn) {
        importXmlBtn.addEventListener('click', handleXmlImport);
    }

    // Загрузка групп при открытии модального окна импорта
    const importXmlModal = document.getElementById('importXmlModal');
    if (importXmlModal) {
        importXmlModal.addEventListener('show.bs.modal', async function () {
            const groupSelect = document.getElementById('import-group');
            if (!groupSelect) return;

            // Сохраняем текущее состояние
            const currentValue = groupSelect.value;
            groupSelect.innerHTML = '<option value="">Не добавлять в группу</option>';
            groupSelect.disabled = true;

            try {
                // Используем endpoint дерева для получения информации о вложенности
                const response = await fetch('/api/groups/tree');
                if (response.ok) {
                    const data = await response.json();
                    const flatGroups = data.flat || [];
                    
                    flatGroups.forEach(g => {
                        const option = document.createElement('option');
                        option.value = g.id;

                        // Формируем отступы и значки в зависимости от глубины (бесконечный уровень)
                        const depth = g.depth || 0;
                        let prefix = '';
                        let icon = '📁 '; // Иконка для корневого уровня

                        if (depth > 0) {
                            // Создаем отступы для любого уровня вложенности
                            for (let i = 0; i < depth; i++) {
                                prefix += '    '; // 4 пробела на уровень
                            }
                            prefix += '└─ '; // Символ соединения
                            icon = '📂 '; // Иконка для всех вложенных уровней
                        }

                        option.textContent = `${prefix}${icon}${g.name}`;
                        groupSelect.appendChild(option);
                    });
                    
                    // Восстанавливаем выбор, если он был валидным
                    if (currentValue && flatGroups.some(g => g.id == currentValue)) {
                        groupSelect.value = currentValue;
                    }
                }
            } catch (error) {
                console.error('Ошибка загрузки групп:', error);
            } finally {
                groupSelect.disabled = false;
            }
        });
    }
});

/**
 * Универсальная функция отправки задачи сканирования
 */
async function submitScan(url, payload, scanName) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (response.ok) {
            alert(`Задача ${scanName} добавлена в очередь! ID: ${data.job_id}`);
            loadJobs();
            updateQueueStatus();
            // Очистка форм (опционально)
            // event.target.reset(); 
        } else {
            alert(`Ошибка: ${data.error}`);
        }
    } catch (err) {
        alert('Ошибка соединения: ' + err);
    }
}

/**
 * Загрузка списка групп для селекта Nmap
 */
async function loadGroups() {
    try {
        // Используем endpoint дерева для получения информации о вложенности
        const response = await fetch('/api/groups/tree');
        if (response.ok) {
            const data = await response.json();
            const flatGroups = data.flat || [];
            const select = document.getElementById('nmap-groups');
            if (select) {
                select.innerHTML = '';
                flatGroups.forEach(g => {
                    const option = document.createElement('option');
                    option.value = g.id;

                    // Формируем отступы и значки в зависимости от глубины (бесконечный уровень)
                    const depth = g.depth || 0;
                    let prefix = '';
                    let icon = '📁 '; // Иконка для корневого уровня

                    if (depth > 0) {
                        // Создаем отступы для любого уровня вложенности
                        for (let i = 0; i < depth; i++) {
                            prefix += '    '; // 4 пробела на уровень
                        }
                        prefix += '└─ '; // Символ соединения
                        icon = '📂 '; // Иконка для всех вложенных уровней
                    }

                    option.textContent = `${prefix}${icon}${g.name}`;
                    select.appendChild(option);
                });
            }
        }
    } catch (e) {
        console.error('Не удалось загрузить группы', e);
    }
}

/**
 * Обновление статуса очередей
 */
async function updateQueueStatus() {
    try {
        const response = await fetch('/api/scans/status');
        if (!response.ok) return;
        const data = await response.json();
        
        // Обновление очереди Nmap/Rustscan
        const nmapQ = data.queues.nmap_rustscan;
        if (nmapQ) {
            document.getElementById('nmap-queue-count').textContent = nmapQ.queue_length;
            document.getElementById('nmap-current-job').textContent = nmapQ.current_job_id ? `#${nmapQ.current_job_id}` : 'Нет';
            document.getElementById('nmap-queue-status').textContent = nmapQ.is_running ? 'Выполняется' : 'Ожидание';
            
            let nmapListHtml = '';
            nmapQ.queued_jobs.forEach(job => {
                nmapListHtml += `<div>#${job.job_id} (${job.scan_type}) - ${job.target}</div>`;
            });
            document.getElementById('nmap-queue-list').innerHTML = nmapListHtml;
        }

        // Обновление очереди утилит
        const utilQ = data.queues.utilities;
        if (utilQ) {
            document.getElementById('utility-queue-count').textContent = utilQ.queue_length;
            document.getElementById('utility-current-job').textContent = utilQ.current_job_id ? `#${utilQ.current_job_id}` : 'Нет';
            document.getElementById('utility-queue-status').textContent = utilQ.is_running ? 'Выполняется' : 'Ожидание';
            
            let utilListHtml = '';
            utilQ.queued_jobs.forEach(job => {
                utilListHtml += `<div>#${job.job_id} (${job.scan_type}) - ${job.target}</div>`;
            });
            document.getElementById('utility-queue-list').innerHTML = utilListHtml;
        }

    } catch (e) {
        console.error('Ошибка обновления статуса очередей', e);
    }
}

/**
 * Загрузка и отображение истории заданий
 */
async function loadJobs() {
    try {
        const response = await fetch('/api/scans/status');
        if (!response.ok) return;
        const data = await response.json();
        const tbody = document.querySelector('#jobs-table tbody');
        if (!tbody) return;
        
        tbody.innerHTML = '';

        data.recent_jobs.forEach(job => {
            const tr = document.createElement('tr');
            
            let statusClass = 'bg-secondary';
            if (job.status === 'completed') statusClass = 'bg-success';
            if (job.status === 'running') statusClass = 'bg-primary';
            if (job.status === 'failed') statusClass = 'bg-danger';
            if (job.status === 'pending' || job.status === 'queued') statusClass = 'bg-warning text-dark';

            let actions = '';
            if (job.status === 'pending' || job.status === 'queued') {
                actions += `<button class="btn btn-sm btn-outline-danger" onclick="removeJob(${job.id})" title="Удалить из очереди"><i class="bi bi-trash"></i></button> `;
            }
            if (job.status === 'running') {
                actions += `<button class="btn btn-sm btn-outline-warning" onclick="stopJob(${job.id})" title="Остановить"><i class="bi bi-stop-fill"></i></button> `;
            }
                        if (['completed', 'failed', 'stopped', 'cancelled'].includes(job.status)) {
                actions += `<button class="btn btn-sm btn-outline-primary" onclick="retryJob(${job.id})" title="Повторить"><i class="bi bi-arrow-clockwise"></i></button> `;
            }
            if (job.status === 'completed') {
                actions += `
                    <div class="btn-group btn-group-sm">
                        <button type="button" class="btn btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown" title="Скачать">⬇️</button>
                        <ul class="dropdown-menu">
                            ${getDownloadLinks(job)}
                        </ul>
                    </div>
                `;
            }
                        if (job.status !== 'pending' && job.status !== 'queued' && job.status !== 'running') {
                actions += `<button class="btn btn-sm btn-outline-danger" onclick="deleteJob(${job.id})" title="Удалить из истории"><i class="bi bi-trash"></i></button> `;
            }

            tr.innerHTML = `
                <td>${job.id}</td>
                <td><span class="badge bg-info text-dark">${job.scan_type}</span></td>
                <td>${job.target}</td>
                <td><span class="badge ${statusClass}">${job.status}</span></td>
                <td>
                    <div class="progress" style="height: 10px; width: 100px;">
                        <div class="progress-bar" role="progressbar" style="width: ${job.progress}%"></div>
                    </div>
                    <small>${job.progress}%</small>
                </td>
                <td>${new Date(job.created_at).toLocaleString('ru-RU')}</td>
                <td>${actions}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('Ошибка загрузки заданий', e);
    }
}

/**
 * Генерация ссылок для скачивания в зависимости от типа сканирования
 */
function getDownloadLinks(job) {
    let links = '';
    const base = `/api/scan-job/${job.id}/download`;
    
    if (job.scan_type === 'nmap') {
        links += `<li><a class="dropdown-item" href="${base}/xml">XML</a></li>`;
        links += `<li><a class="dropdown-item" href="${base}/gnmap">Grepable</a></li>`;
        links += `<li><a class="dropdown-item" href="${base}/normal">Normal (TXT)</a></li>`;
        links += `<li><hr class="dropdown-divider"></li>`;
        links += `<li><a class="dropdown-item" href="${base}/all"><strong>Все форматы (ZIP)</strong></a></li>`;
    } else if (job.scan_type === 'rustscan') {
        links += `<li><a class="dropdown-item" href="${base}/raw">Raw Output</a></li>`;
        links += `<li><a class="dropdown-item" href="${base}/txt">TXT Report</a></li>`;
        links += `<li><a class="dropdown-item" href="${base}/all"><strong>Все файлы (ZIP)</strong></a></li>`;
    } else if (job.scan_type === 'dig') {
        links += `<li><a class="dropdown-item" href="${base}/raw">Raw Output</a></li>`;
        links += `<li><a class="dropdown-item" href="${base}/txt">TXT Report</a></li>`;
        links += `<li><a class="dropdown-item" href="${base}/all"><strong>Все файлы (ZIP)</strong></a></li>`;
    }
    return links;
}

/**
 * Удаление задачи из очереди
 */
async function removeJob(id) {
    if (!confirm('Удалить задачу из очереди?')) return;
    try {
        const res = await fetch(`/api/scan-queue/${id}`, {method: 'DELETE'});
        const data = await res.json();
        alert(data.message);
        loadJobs();
        updateQueueStatus();
    } catch(e) { 
        alert('Ошибка при удалении: ' + e); 
    }
}

/**
 * Остановка выполняющейся задачи
 */
async function stopJob(id) {
    if (!confirm('Остановить выполнение задачи?')) return;
    try {
        const res = await fetch(`/api/scan-job/${id}/stop`, {method: 'POST'});
        const data = await res.json();
        alert(data.message);
        loadJobs();
    } catch(e) { 
        alert('Ошибка при остановке: ' + e); 
    }
}


/**
 * Повторное выполнение завершённой/неудачной задачи
 */
async function retryJob(id) {
    if (!confirm('Повторить задачу?')) return;
    try {
        const res = await fetch(`/api/scan-job/${id}/retry`, {method: 'POST'});
        const data = await res.json();
        alert(data.message);
        loadJobs();
        updateQueueStatus();
    } catch(e) {
        alert('Ошибка при повторе: ' + e);
    }
}

// Экспорт функций в глобальную область видимости для использования из onclick handlers
window.retryJob = retryJob;
window.removeJob = removeJob;
window.stopJob = stopJob;
window.deleteJob = deleteJob;

/**
 * Удаление задачи из истории
 */
async function deleteJob(id) {
    if (!confirm('Удалить задачу из истории?')) return;
    try {
        const res = await fetch(`/api/scan-job/${id}`, {method: 'DELETE'});
        const data = await res.json();
        alert(data.message);
        loadJobs();
    } catch(e) {
        alert('Ошибка при удалении: ' + e);
    }
}


/**
 * Обработка импорта XML Nmap
 */
async function handleXmlImport() {
    const fileInput = document.getElementById('xml-file');
    const groupSelect = document.getElementById('import-group');

    if (!fileInput.files.length) {
        alert('Выберите XML файл для импорта');
        return;
    }

    const formData = new FormData();
    formData.append('xml_file', fileInput.files[0]);

    if (groupSelect.value) {
        formData.append('group_id', groupSelect.value);
    }

    const btn = document.getElementById('import-xml-btn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Импорт...';

    try {
        const response = await fetch('/api/scans/import-xml', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            alert(`Импорт завершен!\n\n` +
                  `Добавлено хостов: ${data.hosts_added}\n` +
                  `Обновлено хостов: ${data.hosts_updated}\n` +
                  `Добавлено сервисов: ${data.services_added}\n` +
                  `Обновлено сервисов: ${data.services_updated}`);

            // Закрытие модального окна
            const modal = bootstrap.Modal.getInstance(document.getElementById('importXmlModal'));
            if (modal) {
                modal.hide();
            }

            // Очистка формы
            fileInput.value = '';
            groupSelect.selectedIndex = 0;

            // Обновление истории заданий
            loadJobs();
        } else {
            alert(`Ошибка импорта: ${data.error}`);
        }
    } catch (err) {
        alert('Ошибка соединения: ' + err);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}