/**
 * Модуль управления историей сканирований
 * Реализует бесконечную прокрутку и функционал как на странице сканирования
 */

class ScanHistoryManager {
    constructor() {
        this.currentPage = 0;
        this.pageSize = 20;
        this.loading = false;
        this.endReached = false;
        this.init();
    }

    init() {
        this.loadHistory();
        
        // Обработчик кнопки обновления
        document.getElementById('refreshHistoryBtn')?.addEventListener('click', () => this.loadHistory());
        
        // Обработчик бесконечной прокрутки
        const tableContainer = document.querySelector('.table-responsive');
        if (tableContainer) {
            tableContainer.addEventListener('scroll', () => this.handleScroll());
        }
    }

    /**
     * Загрузка истории сканирований
     * @param {boolean} append - если true, добавлять к существующим записям
     */
    async loadHistory(append = false) {
        if (this.loading || this.endReached) return;
        
        this.loading = true;
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator && !append) {
            loadingIndicator.classList.remove('d-none');
        }
        
        try {
            const offset = this.currentPage * this.pageSize;
            const response = await fetch(`/api/scans/history?limit=${this.pageSize}&offset=${offset}`);
            if (!response.ok) throw new Error('Ошибка сети');
            const scans = await response.json();

            const tbody = document.getElementById('scansHistoryBody');
            if (!tbody) return;

            // Очищаем таблицу только при первой загрузке
            if (!append) {
                tbody.innerHTML = '';
            }

            if (scans.length === 0) {
                if (!append) {
                    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">История пуста</td></tr>';
                }
                this.endReached = true;
                const endMsg = document.getElementById('endOfListMessage');
                if (endMsg) endMsg.classList.remove('d-none');
                this.loading = false;
                return;
            }

            scans.forEach(scan => {
                const row = this.createHistoryRow(scan);
                tbody.appendChild(row);
            });

            // Если загружено меньше чем pageSize, значит достигли конца
            if (scans.length < this.pageSize) {
                this.endReached = true;
                const endMsg = document.getElementById('endOfListMessage');
                if (endMsg) endMsg.classList.remove('d-none');
            }

            this.currentPage++;
            
        } catch (error) {
            console.error('Ошибка загрузки истории:', error);
            const tbody = document.getElementById('scansHistoryBody');
            if (tbody && !append) {
                tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Ошибка загрузки: ${error.message}</td></tr>`;
            }
        } finally {
            this.loading = false;
            const loadingIndicator = document.getElementById('loadingIndicator');
            if (loadingIndicator) {
                loadingIndicator.classList.add('d-none');
            }
        }
    }

    /**
     * Обработка прокрутки для бесконечной загрузки
     */
    handleScroll() {
        const tableContainer = document.querySelector('.table-responsive');
        if (!tableContainer || this.loading || this.endReached) return;
        
        const scrollTop = tableContainer.scrollTop;
        const scrollHeight = tableContainer.scrollHeight;
        const clientHeight = tableContainer.clientHeight;
        
        // Если прокрутили до конца (с запасом 50px)
        if (scrollTop + clientHeight >= scrollHeight - 50) {
            this.loadHistory(true);
        }
    }

    /**
     * Создание строки таблицы
     */
    createHistoryRow(scan) {
        const tr = document.createElement('tr');
        
        const statusClass = this.getStatusClass(scan.status);
        const dateStr = scan.completed_at ? new Date(scan.completed_at).toLocaleString('ru-RU') : '-';
        
        // Расчет длительности
        let duration = '-';
        if (scan.started_at && scan.completed_at) {
            const start = new Date(scan.started_at);
            const end = new Date(scan.completed_at);
            const diffSec = Math.round((end - start) / 1000);
            if (diffSec < 60) {
                duration = `${diffSec} сек`;
            } else if (diffSec < 3600) {
                duration = `${Math.round(diffSec / 60)} мин`;
            } else {
                duration = `${Math.round(diffSec / 3600)} ч`;
            }
        }

        // Формируем действия как на странице сканирования
        let actions = '';
        if (['pending', 'queued'].includes(scan.status)) {
            actions += `<button class="btn btn-sm btn-outline-danger btn-remove-job" data-job-id="${scan.id}"><i class="bi bi-trash"></i></button> `;
        }
        if (scan.status === 'running') {
            actions += `<button class="btn btn-sm btn-outline-warning btn-stop-job" data-job-id="${scan.id}"><i class="bi bi-stop-fill"></i></button> `;
        }
        if (['completed', 'failed', 'stopped', 'cancelled'].includes(scan.status)) {
            actions += `<button class="btn btn-sm btn-outline-primary btn-retry-job" data-job-id="${scan.id}"><i class="bi bi-arrow-clockwise"></i></button> `;
        }
        if (scan.status === 'completed') {
            actions += `<div class="btn-group btn-group-sm"><button type="button" class="btn btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown">⬇️</button><ul class="dropdown-menu"><li><a class="dropdown-item" href="/api/scans/${scan.id}/download/xml">XML</a></li><li><a class="dropdown-item" href="/api/scans/${scan.id}/download/json">JSON</a></li></ul></div>`;
        }
        if (!['pending', 'queued', 'running'].includes(scan.status)) {
            actions += `<button class="btn btn-sm btn-outline-danger btn-delete-job" data-job-id="${scan.id}"><i class="bi bi-trash"></i></button> `;
        }

        tr.innerHTML = `
            <td>${scan.id}</td>
            <td><span class="badge bg-info">${scan.scan_type || 'Unknown'}</span></td>
            <td>${scan.target || '-'}</td>
            <td><span class="badge ${statusClass}">${scan.status}</span></td>
            <td>${duration}</td>
            <td><small>${dateStr}</small></td>
            <td>${actions}</td>
        `;

        // Навешиваем обработчики
        const retryBtn = tr.querySelector('.btn-retry-job');
        if (retryBtn) retryBtn.addEventListener('click', () => this.retryScan(scan.id));
        const cancelBtn = tr.querySelector('.btn-stop-job');
        if (cancelBtn) cancelBtn.addEventListener('click', () => this.cancelScan(scan.id));
        const deleteBtn = tr.querySelector('.btn-delete-job');
        if (deleteBtn) deleteBtn.addEventListener('click', () => this.deleteScan(scan.id));
        const removeBtn = tr.querySelector('.btn-remove-job');
        if (removeBtn) removeBtn.addEventListener('click', () => this.removeJob(scan.id));

        return tr;
    }

    /**
     * Просмотр результатов сканирования
     */
    async viewScanResults(scanId) {
        const modalEl = document.getElementById('scanResultModal');
        const modal = new bootstrap.Modal(modalEl);
        
        document.getElementById('resultScanId').textContent = `#${scanId}`;
        document.getElementById('scanResultContent').innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary"></div><br>Загрузка результатов...</div>';

        modal.show();

        try {
            const response = await fetch(`/api/scans/${scanId}`);
            if (!response.ok) throw new Error('Не найдено');
            const scan = await response.json();

            let html = `<div class="mb-3"><strong>Цель:</strong> ${scan.target || '-'} | <strong>Тип:</strong> ${scan.scan_type || '-'} | <strong>Статус:</strong> <span class="badge ${this.getStatusClass(scan.status)}">${scan.status}</span></div>`;
            
            if (scan.results && scan.results.length > 0) {
                html += '<div class="accordion" id="resultsAccordion">';
                scan.results.forEach((res, idx) => {
                    const ip = res.ip_address || `Хост ${idx + 1}`;
                    const ports = res.ports && res.ports.length > 0 
                        ? res.ports.map(p => `<span class="badge bg-secondary me-1">${p.port}/${p.protocol}</span>`).join('')
                        : '<span class="text-muted">Нет открытых портов</span>';
                    const os = res.os ? `<div class="mt-2"><strong>ОС:</strong> ${res.os}</div>` : '';
                    const rawOutput = res.raw_output ? `<pre class="bg-dark text-light p-3 rounded mt-2" style="max-height:300px;overflow-y:auto;">${this.escapeHtml(res.raw_output)}</pre>` : '';
                    
                    html += `
                        <div class="accordion-item">
                            <h2 class="accordion-header" id="heading${idx}">
                                <button class="accordion-button ${idx > 0 ? 'collapsed' : ''}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse${idx}">
                                    ${ip}
                                </button>
                            </h2>
                            <div id="collapse${idx}" class="accordion-collapse collapse ${idx === 0 ? 'show' : ''}" data-bs-parent="#resultsAccordion">
                                <div class="accordion-body">
                                    <div><strong>Порты:</strong></div>
                                    <div class="mt-1">${ports}</div>
                                    ${os}
                                    ${rawOutput}
                                </div>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            } else if (scan.error_message) {
                html += `<div class="alert alert-danger mt-3">Ошибка: ${scan.error_message}</div>`;
            } else {
                html += '<div class="alert alert-warning mt-3">Результатов пока нет</div>';
            }
            
            document.getElementById('scanResultContent').innerHTML = html;

        } catch (error) {
            document.getElementById('scanResultContent').innerHTML = `<div class="alert alert-danger">Ошибка загрузки результатов: ${error.message}</div>`;
        }
    }

    /**
     * Повтор сканирования
     */
    async retryScan(scanId) {
        if (!confirm('Повторить это сканирование?')) return;

        try {
            const response = await fetch(`/api/scans/scan-job/${scanId}/retry`, { method: 'POST' });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Ошибка повтора');
            }
            Utils.showNotification('Задача повтора создана', 'success');
            this.loadHistory();
        } catch (error) {
            Utils.showNotification(`Ошибка: ${error.message}`, 'danger');
        }
    }

    /**
     * Отмена сканирования
     */
    async cancelScan(scanId) {
        if (!confirm('Отменить это сканирование?')) return;

        try {
            const response = await fetch(`/api/scans/${scanId}/cancel`, { method: 'POST' });
            if (!response.ok) throw new Error('Ошибка отмены');
            Utils.showNotification('Отправка команды отмены...', 'info');
            this.loadHistory();
        } catch (error) {
            Utils.showNotification(`Ошибка: ${error.message}`, 'danger');
        }
    }

    /**
     * Удаление сканирования
     */
    async deleteScan(scanId) {
        if (!confirm('Вы уверены, что хотите удалить эту запись?')) return;

        try {
            const response = await fetch(`/api/scans/${scanId}`, { method: 'DELETE' });
            if (!response.ok) throw new Error('Ошибка удаления');
            Utils.showNotification('Запись удалена', 'success');
            this.loadHistory();
        } catch (error) {
            Utils.showNotification(`Ошибка: ${error.message}`, 'danger');
        }
    }

    /**
     * Удаление задачи из очереди
     */
    async removeJob(scanId) {
        if (!confirm('Удалить эту задачу из очереди?')) return;

        try {
            const response = await fetch(`/api/scans/${scanId}`, { method: 'DELETE' });
            if (!response.ok) throw new Error('Ошибка удаления');
            Utils.showNotification('Задача удалена', 'success');
            this.loadHistory();
        } catch (error) {
            Utils.showNotification(`Ошибка: ${error.message}`, 'danger');
        }
    }

    // Вспомогательные функции
    getStatusClass(status) {
        switch (status) {
            case 'completed': return 'bg-success';
            case 'running': return 'bg-primary';
            case 'failed': return 'bg-danger';
            case 'cancelled': return 'bg-secondary';
            default: return 'bg-info';
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.scanHistoryManager = new ScanHistoryManager();
});
