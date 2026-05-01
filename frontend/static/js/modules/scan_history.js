/**
 * Модуль управления историей сканирований
 */

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    
    // Обработчик кнопки обновления
    document.getElementById('refreshHistoryBtn')?.addEventListener('click', loadHistory);
    
    // Обработчики кнопок в модалке (будут назначены динамически или здесь)
    document.getElementById('retryScanFromDetail')?.addEventListener('click', () => {
        const scanId = document.getElementById('detailScanId').dataset.id;
        if (scanId) retryScan(scanId);
    });
    
    document.getElementById('deleteScanFromDetail')?.addEventListener('click', () => {
        const scanId = document.getElementById('detailScanId').dataset.id;
        if (scanId) deleteScan(scanId);
    });
});

/**
 * Загрузка истории сканирований
 */
async function loadHistory() {
    const tbody = document.getElementById('historyTableBody');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><br>Загрузка...</td></tr>';

    try {
        const response = await fetch('/api/scans');
        if (!response.ok) throw new Error('Ошибка сети');
        const scans = await response.json();

        if (scans.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">История пуста</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        scans.forEach(scan => {
            const row = createHistoryRow(scan);
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Ошибка загрузки истории:', error);
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Ошибка загрузки: ${error.message}</td></tr>`;
    }
}

/**
 * Создание строки таблицы
 */
function createHistoryRow(scan) {
    const tr = document.createElement('tr');
    
    const statusClass = getStatusClass(scan.status);
    const progressWidth = scan.progress ? `${scan.progress}%` : '0%';
    const dateStr = scan.created_at ? new Date(scan.created_at).toLocaleString() : 'N/A';

    tr.innerHTML = `
        <td>${scan.id}</td>
        <td><span class="badge bg-secondary">${scan.scan_type || 'Unknown'}</span></td>
        <td>${scan.target || '-'}</td>
        <td><span class="badge ${statusClass}">${scan.status}</span></td>
        <td style="width: 15%;">
            <div class="progress" style="height: 6px;">
                <div class="progress-bar" role="progressbar" style="width: ${progressWidth};"></div>
            </div>
            <small>${scan.progress || 0}%</small>
        </td>
        <td><small>${dateStr}</small></td>
        <td>
            <button class="btn btn-sm btn-outline-primary view-history-btn" data-id="${scan.id}" title="Просмотр">
                <i class="bi bi-eye"></i>
            </button>
            ${canRetry(scan.status) ? `
            <button class="btn btn-sm btn-outline-warning retry-history-btn" data-id="${scan.id}" title="Повторить">
                <i class="bi bi-arrow-repeat"></i>
            </button>` : ''}
            ${canCancel(scan.status) ? `
            <button class="btn btn-sm btn-outline-danger cancel-history-btn" data-id="${scan.id}" title="Отменить">
                <i class="bi bi-stop-fill"></i>
            </button>` : ''}
            <button class="btn btn-sm btn-outline-secondary delete-history-btn" data-id="${scan.id}" title="Удалить">
                <i class="bi bi-trash"></i>
            </button>
        </td>
    `;

    // Навешиваем обработчики
    tr.querySelector('.view-history-btn').addEventListener('click', () => viewScanDetails(scan.id));
    const retryBtn = tr.querySelector('.retry-history-btn');
    if (retryBtn) retryBtn.addEventListener('click', () => retryScan(scan.id));
    const cancelBtn = tr.querySelector('.cancel-history-btn');
    if (cancelBtn) cancelBtn.addEventListener('click', () => cancelScan(scan.id));
    tr.querySelector('.delete-history-btn').addEventListener('click', () => deleteScan(scan.id));

    return tr;
}

/**
 * Просмотр деталей сканирования
 */
async function viewScanDetails(scanId) {
    const modalEl = document.getElementById('scanDetailModal');
    const modal = new bootstrap.Modal(modalEl);
    
    document.getElementById('detailScanId').textContent = `#${scanId}`;
    document.getElementById('detailScanId').dataset.id = scanId;
    document.getElementById('detailStatus').textContent = 'Загрузка...';
    document.getElementById('detailProgress').textContent = '-';
    document.getElementById('detailOutput').textContent = 'Загрузка логов...';

    modal.show();

    try {
        const response = await fetch(`/api/scans/${scanId}`);
        if (!response.ok) throw new Error('Не найдено');
        const scan = await response.json();

        document.getElementById('detailStatus').innerHTML = `<span class="badge ${getStatusClass(scan.status)}">${scan.status}</span>`;
        document.getElementById('detailProgress').textContent = `${scan.progress || 0}%`;
        
        // Формируем вывод
        let output = `Цель: ${scan.target}\nТип: ${scan.scan_type}\nСтатус: ${scan.status}\n\n`;
        if (scan.results && scan.results.output) {
            output += scan.results.output;
        } else if (scan.error) {
            output += `Ошибка: ${scan.error}`;
        } else {
            output += 'Результатов пока нет.';
        }
        document.getElementById('detailOutput').textContent = output;

    } catch (error) {
        document.getElementById('detailOutput').textContent = `Ошибка загрузки деталей: ${error.message}`;
    }
}

/**
 * Повтор сканирования
 */
async function retryScan(scanId) {
    if (!confirm('Повторить это сканирование?')) return;

    try {
        const response = await fetch(`/api/scans/scan-job/${scanId}/retry`, { method: 'POST' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Ошибка повтора');
        }
        alert('Задача повтора создана');
        loadHistory();
        // Закрыть модалку если открыта
        const modalEl = document.getElementById('scanDetailModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
    } catch (error) {
        alert(`Ошибка: ${error.message}`);
    }
}

/**
 * Отмена сканирования
 */
async function cancelScan(scanId) {
    if (!confirm('Отменить это сканирование?')) return;

    try {
        const response = await fetch(`/api/scans/${scanId}/cancel`, { method: 'POST' });
        if (!response.ok) throw new Error('Ошибка отмены');
        alert('Отправка команды отмены...');
        loadHistory();
    } catch (error) {
        alert(`Ошибка: ${error.message}`);
    }
}

/**
 * Удаление сканирования
 */
async function deleteScan(scanId) {
    if (!confirm('Вы уверены, что хотите удалить эту запись?')) return;

    try {
        const response = await fetch(`/api/scans/${scanId}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Ошибка удаления');
        loadHistory();
        // Закрыть модалку если открыта
        const modalEl = document.getElementById('scanDetailModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
    } catch (error) {
        alert(`Ошибка: ${error.message}`);
    }
}

// Вспомогательные функции
function getStatusClass(status) {
    switch (status) {
        case 'completed': return 'bg-success';
        case 'running': return 'bg-primary';
        case 'failed': return 'bg-danger';
        case 'cancelled': return 'bg-secondary';
        default: return 'bg-info';
    }
}

function canRetry(status) {
    return ['failed', 'cancelled', 'completed'].includes(status);
}

function canCancel(status) {
    return ['running', 'pending'].includes(status);
}
