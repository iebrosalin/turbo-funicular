// static/js/modules/scans.js
import { store } from '../store.js';
import { Utils } from './utils.js';

/**
 * Класс управления сканированиями и отображением результатов
 */
export class ScanManager {
  constructor() {
    this.eventSource = null;
    this.#init();
  }

  #init() {
    // Запуск прослушивания событий от сервера (SSE)
    this.startEventListening();
    // Инициализация обработчиков модальных окон
    this.#initModalHandlers();
    // Инициализация обработчиков форм сканирования
    this.#initScanForms();
  }

  /**
   * Инициализация обработчиков форм сканирования (Nmap, Rustscan, Dig)
   */
  #initScanForms() {
    // Форма Nmap
    const nmapForm = document.getElementById('nmapScanForm');
    if (nmapForm) {
      nmapForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.#submitNmapScan(nmapForm);
      });
      
      // Обработчик изменения профиля Nmap
      const nmapProfile = document.getElementById('nmapProfile');
      const nmapCustomArgsContainer = document.getElementById('nmapCustomArgsContainer');
      if (nmapProfile && nmapCustomArgsContainer) {
        nmapProfile.addEventListener('change', (e) => {
          if (e.target.value === 'custom') {
            nmapCustomArgsContainer.classList.remove('d-none');
          } else {
            nmapCustomArgsContainer.classList.add('d-none');
          }
        });
      }
    }

    // Форма Rustscan
    const rustscanForm = document.getElementById('rustscanScanForm');
    if (rustscanForm) {
      rustscanForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.#submitRustscanScan(rustscanForm);
      });
      
      // Обработчик выбора топ портов
      const rustscanTopPorts = document.getElementById('rustscanTopPorts');
      const rustscanPortsContainer = document.getElementById('rustscanPortsContainer');
      if (rustscanTopPorts && rustscanPortsContainer) {
        rustscanTopPorts.addEventListener('change', (e) => {
          if (e.target.value === 'custom') {
            rustscanPortsContainer.classList.remove('d-none');
          } else {
            rustscanPortsContainer.classList.add('d-none');
          }
        });
      }
      
      // Обработчик чекбокса запуска Nmap
      const rustscanRunNmapAfter = document.getElementById('rustscanRunNmapAfter');
      const rustscanNmapArgsContainer = document.getElementById('rustscanNmapArgsContainer');
      if (rustscanRunNmapAfter && rustscanNmapArgsContainer) {
        rustscanRunNmapAfter.addEventListener('change', (e) => {
          if (e.target.checked) {
            rustscanNmapArgsContainer.classList.remove('d-none');
          } else {
            rustscanNmapArgsContainer.classList.add('d-none');
          }
        });
      }
    }

    // Форма Dig
    const digForm = document.getElementById('digScanForm');
    if (digForm) {
      digForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.#submitDigScan(digForm);
      });
    }
  }

  /**
   * Инициализация обработчиков модальных окон сканирования
   */
  #initModalHandlers() {
    // Обработчик формы запуска сканирования
    const scanForm = document.getElementById('scanForm');
    if (scanForm) {
      scanForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.#submitScan(scanForm);
      });
    }

    // Обработчик изменения типа сканирования
    const scanTypeSelect = document.getElementById('scan-type');
    if (scanTypeSelect) {
      scanTypeSelect.addEventListener('change', (e) => {
        const portsInput = document.getElementById('scan-ports');
        const type = e.target.value;
        
        if (type === 'quick') {
          portsInput.value = '';
          portsInput.placeholder = 'Топ-100 портов (автоматически)';
          portsInput.disabled = true;
        } else if (type === 'standard') {
          portsInput.value = '';
          portsInput.placeholder = 'Топ-1000 портов (автоматически)';
          portsInput.disabled = true;
        } else if (type === 'full') {
          portsInput.value = '';
          portsInput.placeholder = 'Все порты 1-65535 (автоматически)';
          portsInput.disabled = true;
        } else if (type === 'custom') {
          portsInput.value = '';
          portsInput.placeholder = '80,443,22 или 1-1000';
          portsInput.disabled = false;
        }
      });
    }
  }

  /**
   * Отправка формы сканирования Nmap
   */
  async #submitNmapScan(form) {
    const target = document.getElementById('nmapTarget').value.trim();
    const profile = document.getElementById('nmapProfile').value;
    const ports = document.getElementById('nmapPorts').value.trim();
    const scripts = document.getElementById('nmapScripts').value.trim();
    const customArgs = document.getElementById('nmapCustomArgs').value.trim();
    const saveAssets = document.getElementById('nmapSaveAssets').checked;

    if (!target) {
      Utils.showNotification('Укажите целевые хосты', 'warning');
      return;
    }

    try {
      const payload = {
        target,
        profile,
        ports: ports || undefined,
        scripts: scripts || undefined,
        custom_args: (profile === 'custom' ? customArgs : undefined),
        save_assets: saveAssets
      };

      const response = await fetch('/api/scans/nmap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка запуска сканирования');
      }

      const result = await response.json();
      Utils.showNotification(`Сканирование Nmap #${result.job_id} запущено`, 'success');
      form.reset();
      if (typeof window.scanResultsController !== 'undefined') {
        window.scanResultsController.loadHistory();
      }
    } catch (error) {
      console.error('Ошибка запуска Nmap:', error);
      Utils.showNotification(error.message, 'danger');
    }
  }

  /**
   * Отправка формы сканирования Rustscan
   */
  async #submitRustscanScan(form) {
    const target = document.getElementById('rustscanTarget').value.trim();
    const topPorts = document.getElementById('rustscanTopPorts').value;
    const portsRange = document.getElementById('rustscanPortsRange').value.trim();
    const customArgs = document.getElementById('rustscanCustomArgs').value.trim();
    const runNmapAfter = document.getElementById('rustscanRunNmapAfter').checked;
    const nmapArgs = document.getElementById('rustscanNmapArgs').value.trim();
    const saveAssets = document.getElementById('rustscanSaveAssets').checked;

    if (!target) {
      Utils.showNotification('Укажите целевые хосты', 'warning');
      return;
    }

    let ports = '';
    if (topPorts === 'custom') {
      ports = portsRange;
    } else if (topPorts === 'all') {
      ports = '1-65535';
    } else {
      ports = `--top-ports ${topPorts}`;
    }

    try {
      const payload = {
        target,
        ports: ports || undefined,
        custom_args: customArgs || undefined,
        run_nmap_after: runNmapAfter,
        nmap_args: runNmapAfter ? (nmapArgs || undefined) : undefined,
        save_assets: saveAssets
      };

      const response = await fetch('/api/scans/rustscan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка запуска сканирования');
      }

      const result = await response.json();
      let msg = `Сканирование Rustscan #${result.job_id} запущено`;
      if (runNmapAfter) {
        msg += '. После завершения будет запущен Nmap.';
      }
      Utils.showNotification(msg, 'success');
      form.reset();
      // Скрыть поле аргументов Nmap
      document.getElementById('rustscanNmapArgsContainer')?.classList.add('d-none');
      if (typeof window.scanResultsController !== 'undefined') {
        window.scanResultsController.loadHistory();
      }
    } catch (error) {
      console.error('Ошибка запуска Rustscan:', error);
      Utils.showNotification(error.message, 'danger');
    }
  }

  /**
   * Отправка формы сканирования Dig
   */
  async #submitDigScan(form) {
    const targetsText = document.getElementById('digTargetsText').value.trim();
    const recordTypes = document.getElementById('digRecordTypes').value;
    const dnsServer = document.getElementById('digDnsServer').value.trim();
    const cliArgs = document.getElementById('digCliArgs').value.trim();
    const saveAssets = document.getElementById('digSaveAssets').checked;

    if (!targetsText) {
      Utils.showNotification('Укажите домены для сканирования', 'warning');
      return;
    }

    try {
      const payload = {
        targets_text: targetsText,
        record_types: recordTypes,
        dns_server: dnsServer || undefined,
        cli_args: cliArgs || undefined,
        save_assets: saveAssets
      };

      const response = await fetch('/api/scans/dig', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка запуска сканирования');
      }

      const result = await response.json();
      Utils.showNotification(`Сканирование Dig #${result.job_id} запущено`, 'success');
      form.reset();
      if (typeof window.scanResultsController !== 'undefined') {
        window.scanResultsController.loadHistory();
      }
    } catch (error) {
      console.error('Ошибка запуска Dig:', error);
      Utils.showNotification(error.message, 'danger');
    }
  }

  /**
   * Отправка формы сканирования (устаревшая, для совместимости)
   */
  async #submitScan(form) {
    const target = document.getElementById('scan-target').value.trim();
    const scanType = document.getElementById('scan-type').value;
    const groupId = document.getElementById('scan-group-id').value;
    let ports = document.getElementById('scan-ports').value.trim();

    if (!target) {
      Utils.showNotification('Укажите целевые хосты', 'warning');
      return;
    }

    // Определение портов в зависимости от типа
    if (scanType === 'quick' && !ports) {
      ports = '-F'; // nmap флаг для быстрых портов
    } else if (scanType === 'standard' && !ports) {
      ports = ''; // стандартные топ-1000
    } else if (scanType === 'full' && !ports) {
      ports = '-p-'; // все порты
    }

    const progressDiv = document.getElementById('scan-progress');
    if (progressDiv) progressDiv.style.display = 'block';

    try {
      const formData = new FormData();
      formData.append('target', target);
      if (ports) formData.append('ports', ports);
      if (groupId) formData.append('group_id', groupId);
      formData.append('scan_type', scanType);

      const response = await fetch('/api/scans/start', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка запуска сканирования');
      }

      const result = await response.json();
      
      // Закрытие модального окна
      const modalEl = document.getElementById('scanModal');
      if (modalEl) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }

      Utils.showNotification(`Сканирование #${result.id} запущено`, 'success');
      
      // Очистка формы
      form.reset();
      
      // Обновление истории сканирований
      if (typeof window.scanResultsController !== 'undefined') {
        window.scanResultsController.loadHistory();
      }
    } catch (error) {
      console.error('Ошибка запуска сканирования:', error);
      Utils.showNotification(error.message, 'danger');
    } finally {
      const progressDiv = document.getElementById('scan-progress');
      if (progressDiv) progressDiv.style.display = 'none';
    }
  }

  /**
   * Просмотр результатов сканирования
   */
  async viewScanResults(id) {
    const modalId = 'scanResultsModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return;

    const m = new bootstrap.Modal(modalEl);
    const c = document.getElementById('scan-results-content');
    const errAlert = document.getElementById('scan-error-alert');
    const errText = document.getElementById('scan-error-text');
    
    if (c) c.innerHTML = '<div class="text-center"><div class="spinner-border"></div><p class="mt-2">Загрузка...</p></div>';
    if (errAlert) errAlert.style.display = 'none';
    
    m.show();
    
    try {
      const r = await fetch(`/api/scans/${id}/results`);
      const d = await r.json();
      
      if (d.job.status === 'failed' && d.job.error_message) {
        if (errAlert) errAlert.style.display = 'block';
        if (errText) errText.textContent = d.job.error_message;
      }
      
      let h = `<h6>#${d.job.id} - ${d.job.scan_type.toUpperCase()}</h6>`;
      h += `<p><strong>Цель:</strong> ${d.job.target}</p>`;
      h += `<p><strong>Статус:</strong> <span class="badge bg-${d.job.status === 'completed' ? 'success' : d.job.status === 'failed' ? 'danger' : 'warning'}">${d.job.status}</span></p>`;
      h += `<p><strong>Прогресс:</strong> ${d.job.progress}%</p>`;
      if (d.job.started_at) h += `<p><strong>Начало:</strong> ${d.job.started_at}</p>`;
      if (d.job.completed_at) h += `<p><strong>Завершение:</strong> ${d.job.completed_at}</p>`;
      h += `<hr>`;
      
      if (d.job.status === 'failed') {
        h += '<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Сканирование завершилось с ошибкой.</div>';
      } else if (!d.results || d.results.length === 0) {
        h += '<p class="text-muted">Нет результатов</p>';
      } else {
        h += `<p><strong>Найдено хостов:</strong> ${d.results.length}</p><div class="list-group">`;
        d.results.forEach(x => {
          const ports = x.ports?.join ? x.ports.join(', ') : 'Нет';
          const osInfo = x.os && x.os !== '-' ? `<p class="mb-0"><strong>ОС:</strong> ${x.os}</p>` : '';
          h += `<div class="list-group-item"><div class="d-flex justify-content-between"><h6 class="mb-1">${x.ip}</h6><small>${x.scanned_at}</small></div><p class="mb-1"><strong>Порты:</strong> ${ports}</p>${osInfo}</div>`;
        });
        h += '</div>';
      }
      if (c) c.innerHTML = h;
    } catch (err) { 
      if (errAlert) errAlert.style.display = 'block';
      if (errText) errText.textContent = `Ошибка загрузки результатов: ${err.message}`;
    }
  }

  /**
   * Показать ошибку сканирования
   */
  showScanError(jobId, errorMsg) {
    const modalId = 'scanErrorModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return Utils.showNotification(errorMsg, 'danger');

    const m = new bootstrap.Modal(modalEl);
    const c = document.getElementById('scan-error-content');
    const safeMsg = errorMsg ? errorMsg.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$') : 'Неизвестная ошибка';
    
    if (c) {
      c.innerHTML = `
        <div class="alert alert-danger">
          <h6><i class="bi bi-exclamation-triangle"></i> Ошибка сканирования #${jobId}:</h6>
          <pre class="mb-0" style="white-space:pre-wrap;max-height:400px;overflow-y:auto">${safeMsg}</pre>
        </div>
        <div class="mt-3">
          <button class="btn btn-sm btn-outline-secondary" id="btn-copy-error">
            <i class="bi bi-clipboard"></i> Копировать ошибку
          </button>
        </div>
      `;
      
      // Обработчик копирования
      setTimeout(() => {
        document.getElementById('btn-copy-error')?.addEventListener('click', () => {
          navigator.clipboard.writeText(safeMsg);
          Utils.showNotification('Ошибка скопирована в буфер', 'success');
        });
      }, 0);
    }
    m.show();
  }

  /**
   * Обновление истории сканирований
   */
  async updateScanHistory() {
    try {
      const res = await fetch('/api/scans/history');
      if (!res.ok) return;
      const jobs = await res.json();
      const tbody = document.querySelector('#history-table tbody');
      if (!tbody) return;

      jobs.forEach(j => {
        const row = document.getElementById(`scan-row-${j.id}`);
        if (!row) return;
        
        const badge = row.querySelector('.status-badge');
        if (badge) {
          badge.textContent = j.status;
          badge.className = `badge status-badge bg-${j.status === 'running' ? 'warning text-dark' : j.status === 'completed' ? 'success' : 'danger'}`;
          
          if (j.error_message) {
            badge.style.cursor = 'pointer';
            badge.setAttribute('title', 'Нажмите для просмотра детали ошибки');
            badge.onclick = () => this.showScanError(j.id, j.error_message);
          } else {
            badge.style.cursor = 'default';
            badge.removeAttribute('onclick');
          }
        }
        const bar = row.querySelector('.progress-bar');
        const txt = row.querySelector('.progress-text');
        if (bar) bar.style.width = `${j.progress}%`;
        if (txt) txt.textContent = `${j.progress}%`;
      });
    } catch (error) {
      console.error('Ошибка обновления истории сканирований:', error);
    }
  }

  /**
   * Обновление таблиц очередей (Эксклюзивная и Параллельная)
   */
  async updateQueueTables() {
    try {
      const res = await fetch('/api/scans/status');
      if (!res.ok) return;
      const jobs = await res.json();

      const exclusiveBody = document.querySelector('#exclusive-queue-table tbody');
      const parallelBody = document.querySelector('#parallel-queue-table tbody');
      const exclusiveEmpty = document.getElementById('exclusive-empty');
      const parallelEmpty = document.getElementById('parallel-empty');

      if (!exclusiveBody || !parallelBody) return;

      exclusiveBody.innerHTML = '';
      parallelBody.innerHTML = '';

      let hasExclusive = false;
      let hasParallel = false;

      jobs.forEach(job => {
        if (job.status === 'pending' || job.status === 'running') {
          const isExclusive = ['nmap', 'rustscan'].includes(job.scan_type);
          const targetBody = isExclusive ? exclusiveBody : parallelBody;
          
          if (isExclusive) hasExclusive = true;
          else hasParallel = true;

          const row = document.createElement('tr');
          row.id = `scan-row-${job.id}`;
          row.innerHTML = `
            <td><small>${job.id}</small></td>
            <td><span class="badge bg-${job.scan_type === 'nmap' ? 'primary' : job.scan_type === 'rustscan' ? 'info' : 'secondary'}">${job.scan_type.toUpperCase()}</span></td>
            <td><strong>${job.target}</strong></td>
            <td><span class="badge status-badge bg-${job.status === 'running' ? 'warning text-dark' : 'secondary'}">${job.status}</span></td>
            <td style="width: 150px;">
              <div class="progress" style="height: 6px;">
                <div class="progress-bar progress-bar-striped progress-bar-animated" style="width: ${job.progress}%"></div>
              </div>
              <small class="text-muted progress-text">${job.progress}%</small>
            </td>
            <td>
              <button class="btn btn-sm btn-outline-primary" onclick="scanManager.viewScanResults(${job.id})"><i class="bi bi-eye"></i></button>
              ${job.status === 'running' ? `<button class="btn btn-sm btn-outline-danger" onclick="scanManager.cancelScan(${job.id})"><i class="bi bi-x-circle"></i></button>` : ''}
            </td>
          `;
          targetBody.appendChild(row);
        }
      });

      if (exclusiveEmpty) exclusiveEmpty.style.display = hasExclusive ? 'none' : 'block';
      if (parallelEmpty) parallelEmpty.style.display = hasParallel ? 'none' : 'block';

    } catch (error) {
      console.error('Ошибка обновления очередей:', error);
    }
  } // <--- ДОБАВЛЕНО: закрытие метода updateQueueTables

  /**
   * Прослушивание событий от сервера через SSE (Server-Sent Events)
   */
  startEventListening() {
    if (this.eventSource) {
      this.eventSource.close();
    }

    this.eventSource = new EventSource('/api/scans/events');

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.updateScanStatusInUI(data);
        // Обновляем таблицы очередей при получении события
        this.updateQueueTables();
      } catch (e) {
        console.error('Ошибка парсинга SSE события:', e);
      }
    };

    this.eventSource.onerror = (err) => {
      console.warn('⚠️ Ошибка SSE соединения:', err);
      // Пытаемся переподключиться через 5 секунд
      setTimeout(() => {
        if (this.eventSource?.readyState === EventSource.CLOSED) {
          this.startEventListening();
        }
      }, 5000);
    };

    // Первичная загрузка очередей и истории
    this.updateQueueTables();
    this.updateScanHistory();
    
    // Периодическое обновление каждые 5 секунд
    setInterval(() => {
      this.updateQueueTables();
      this.updateScanHistory();
    }, 5000);
  }

  /**
   * Обновление статуса сканирования в UI
   */
  updateScanStatusInUI(jobData) {
    const row = document.getElementById(`scan-row-${jobData.id}`);
    if (!row) return;

    const badge = row.querySelector('.status-badge');
    if (badge) {
      badge.textContent = jobData.status;
      badge.className = `badge status-badge bg-${
        jobData.status === 'running' ? 'warning text-dark' :
        jobData.status === 'completed' ? 'success' : 'danger'
      }`;

      if (jobData.error_message) {
        badge.style.cursor = 'pointer';
        badge.setAttribute('title', 'Нажмите для просмотра детали ошибки');
        badge.onclick = () => this.showScanError(jobData.id, jobData.error_message);
      } else {
        badge.style.cursor = 'default';
        badge.removeAttribute('onclick');
      }
    }

    const bar = row.querySelector('.progress-bar');
    const txt = row.querySelector('.progress-text');
    if (bar) bar.style.width = `${jobData.progress}%`;
    if (txt) txt.textContent = `${jobData.progress}%`;

    // Логгируем только важные изменения статуса
    if (jobData.status === 'completed' || jobData.status === 'failed') {
      
    }
  }

  /**
   * Остановка прослушивания событий
   */
  stopEventListening() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      
    }
  }
} // <--- ДОБАВЛЕНО: закрытие класса ScanManager

// Экспорт синглтона
export const scanManager = new ScanManager();