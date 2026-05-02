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
    // Инициализация обработчиков форм сканирования
    this.#initScanFormHandlers();
    // Инициализация обработчиков модальных окон
    this.#initModalHandlers();
  }

  /**
   * Инициализация обработчиков форм сканирования (Nmap, Rustscan, Dig)
   */
  #initScanFormHandlers() {
    // Nmap форма
    const nmapForm = document.getElementById('nmapScanForm');
    if (nmapForm) {
      nmapForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.#submitNmapScan(nmapForm);
      });
    }

    // Rustscan форма
    const rustscanForm = document.getElementById('rustscanScanForm');
    if (rustscanForm) {
      rustscanForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.#submitRustscanScan(rustscanForm);
      });
    }

    // Dig форма
    const digForm = document.getElementById('digScanForm');
    if (digForm) {
      digForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.#submitDigScan(digForm);
      });
    }
  }

  /**
   * Отправка формы Nmap сканирования
   */
  async #submitNmapScan(form) {
    const target = document.getElementById('nmapTarget').value.trim();
    const profile = document.getElementById('nmapProfile').value;
    const customArgs = document.getElementById('nmapCustomArgs')?.value.trim() || '';
    const ports = document.getElementById('nmapPorts')?.value.trim() || '';
    const scriptDefault = document.getElementById('nmapScriptDefault')?.checked;
    const scriptSafe = document.getElementById('nmapScriptSafe')?.checked;
    const scriptVuln = document.getElementById('nmapScriptVuln')?.checked;
    const saveAssets = document.getElementById('nmapSaveAssets')?.checked;

    if (!target) {
      Utils.showNotification('Укажите целевые хосты', 'warning');
      return;
    }

    // Построение аргументов на основе профиля
    let args = '';
    if (profile === 'quick') args = '-F';
    else if (profile === 'standard') args = '-sV -sC';
    else if (profile === 'full') args = '-p-';
    else if (profile === 'aggressive') args = '-A -T4';
    else if (profile === 'custom') args = customArgs;

    // Добавление портов
    if (ports && profile !== 'custom') {
      args += ` -p ${ports}`;
    }

    // Добавление скриптов NSE
    const scripts = [];
    if (scriptDefault) scripts.push('default');
    if (scriptSafe) scripts.push('safe');
    if (scriptVuln) scripts.push('vuln');
    if (scripts.length > 0) {
      args += ` --script=${scripts.join(',')}`;
    }

    await this.#sendScanRequest('nmap', target, args, saveAssets);
  }

  /**
   * Отправка формы Rustscan сканирования
   */
  async #submitRustscanScan(form) {
    const target = document.getElementById('rustscanTarget').value.trim();
    const topPorts = document.getElementById('rustscanTopPorts').value;
    const portsRange = document.getElementById('rustscanPortsRange')?.value.trim() || '';
    const customArgs = document.getElementById('rustscanCustomArgs')?.value.trim() || '';
    const saveAssets = document.getElementById('rustscanSaveAssets')?.checked;

    if (!target) {
      Utils.showNotification('Укажите целевые хосты', 'warning');
      return;
    }

    // Построение аргументов
    let args = '';
    if (topPorts === 'custom') {
      if (portsRange) args += `-p ${portsRange}`;
    } else if (topPorts === 'all') {
      args += '-p 1-65535';
    } else {
      args += `-c ${topPorts}`; // количество топ портов
    }

    if (customArgs) args += ` ${customArgs}`;

    await this.#sendScanRequest('rustscan', target, args, saveAssets);
  }

  /**
   * Отправка формы Dig сканирования
   */
  async #submitDigScan(form) {
    const domain = document.getElementById('digDomain').value.trim();
    const recordType = document.getElementById('digType').value;
    const server = document.getElementById('digServer')?.value.trim() || '';
    const customArgs = document.getElementById('digCustomArgs')?.value.trim() || '';
    const saveAssets = document.getElementById('digSaveAssets')?.checked;

    if (!domain) {
      Utils.showNotification('Укажите домен', 'warning');
      return;
    }

    // Построение аргументов
    let args = `${recordType}`;
    if (server) args += ` @${server}`;
    if (customArgs) args += ` ${customArgs}`;
    args += ` ${domain}`;

    await this.#sendScanRequest('dig', domain, args, saveAssets);
  }

  /**
   * Универсальная отправка запроса на сканирование
   */
  async #sendScanRequest(scanType, target, args, saveAssets) {
    const progressDiv = document.getElementById('scan-progress');
    if (progressDiv) progressDiv.style.display = 'block';

    try {
      // Формируем JSON объект
      const requestData = {
        target: target,
        args: args,
        scan_type: scanType,
        save_assets: saveAssets
      };

      // Определяем правильный эндпоинт для каждого типа сканирования
      let endpoint;
      switch (scanType) {
        case 'dig':
          endpoint = '/api/scans/dig';
          break;
        case 'nmap':
          endpoint = '/api/scans/nmap';
          // Для nmap добавляем дополнительные поля
          requestData.ports = null;
          requestData.custom_args = args;
          requestData.known_ports_only = false;
          break;
        case 'rustscan':
          endpoint = '/api/scans/rustscan';
          // Для rustscan добавляем дополнительные поля
          requestData.ports = null;
          requestData.custom_args = args;
          requestData.run_nmap_after = false;
          requestData.nmap_args = null;
          break;
        default:
          throw new Error(`Неизвестный тип сканирования: ${scanType}`);
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка запуска сканирования');
      }

      const result = await response.json();
      
      Utils.showNotification(`Сканирование #${result.id} запущено`, 'success');
      
      // Очистка формы
      const form = document.getElementById('dig-scan-form');
      if (form) form.reset();
      
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
   * Инициализация обработчиков модальных окон (для совместимости)
   */
  #initModalHandlers() {
    // Обработчики для модальных окон результатов и логов
    const logsModal = document.getElementById('scanLogsModal');
    if (logsModal) {
      logsModal.addEventListener('hidden.bs.modal', () => {
        // Очистка при закрытии
      });
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
  } // <--- ДОБАВЛЕНО: закрытие метода updateScanHistory

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