// static/js/scans-page.js
import { store } from './store.js';
import { Utils } from './modules/utils.js';

/**
 * Контроллер страницы управления сканированиями.
 * Обработка форм, обновление статуса очередей и управление историей заданий.
 */
export class ScanResultsController {
  constructor() {
    this.pollingInterval = null;
    this.assetsContainer = document.getElementById('assets-container');
    this.scanForms = document.querySelector('.tab-content');
    this.queueStatus = document.getElementById('queue-status-container');
    this.scanTabs = document.getElementById('scanTabs');
    console.log('[ScanResultsController] Constructor called, initializing...');
    this.#init();
  }

  async #init() {
    console.log('[ScanResultsController] #init called');
    this.#setupEventListeners();
    this.#initUrlFiltering();
    await this.loadJobs();
    await this.updateQueueStatus();
    
    // Автообновление каждые 5 секунд
    this.startPolling();
  }

  #initUrlFiltering() {
    const urlParams = new URLSearchParams(window.location.search);
    const groupIdParam = urlParams.get('group_id');
    const ungroupedParam = urlParams.get('ungrouped');

    if (ungroupedParam === 'true') {
      this.#filterByGroup('ungrouped');
    } else if (groupIdParam && groupIdParam !== 'all') {
      this.#filterByGroup(groupIdParam);
    }
  }

  #filterByGroup(groupId) {
    // Показываем контейнер с активами
    if (this.assetsContainer) {
      this.assetsContainer.style.display = 'block';
    }
    // Скрываем формы сканирований
    if (this.scanForms) this.scanForms.classList.add('d-none');
    if (this.queueStatus) this.queueStatus.classList.add('d-none');
    if (this.scanTabs) this.scanTabs.classList.add('d-none');

    // Загружаем активы для группы
    this.#loadAssetsForGroup(groupId);
  }

  async #loadAssetsForGroup(groupId) {
    const tbody = document.getElementById('assets-table-body');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4"><div class="spinner-border text-primary"></div><p class="mt-2 text-muted">Загрузка...</p></td></tr>';

    try {
      let url = '/api/assets?';
      if (groupId === 'ungrouped') {
        url += 'ungrouped=true';
      } else {
        url += `group_id=${groupId}`;
      }

      const response = await fetch(url);
      if (!response.ok) throw new Error('Ошибка загрузки');
      
      const assets = await response.json();
      tbody.innerHTML = '';
      
      if (assets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Активы не найдены</td></tr>';
        return;
      }

      assets.forEach(asset => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${asset.ip_address ?? 'N/A'}</strong></td>
          <td>${asset.hostname ?? '<span class="text-muted">-</span>'}</td>
          <td>${asset.mac_address ?? '<span class="text-muted">-</span>'}</td>
          <td>${asset.group_name ?? '<span class="text-muted">Без группы</span>'}</td>
          <td><small>${asset.open_ports ?? '<span class="text-muted">-</span>'}</small></td>
          <td><button class="btn btn-sm btn-outline-primary" onclick="window.location.href='/asset/${asset.id}'">Открыть</button></td>
        `;
        tbody.appendChild(tr);
      });
    } catch (error) {
      console.error('Ошибка загрузки активов:', error);
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger py-4">Ошибка: ${error.message}</td></tr>`;
    }
  }

  #setupEventListeners() {
    console.log('[ScanResultsController] Setting up event listeners...');
    
    // Делегирование событий для кнопок управления заданиями
    const jobsTable = document.getElementById('jobs-table');
    console.log('[ScanResultsController] Jobs table found:', !!jobsTable);
    jobsTable?.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-job-id]');
      if (!btn) return;
      
      const jobId = btn.dataset.jobId;
      console.log('[ScanResultsController] Job action clicked:', jobId, btn.className);
      
      if (btn.classList.contains('btn-remove-job')) this.removeJob(jobId);
      else if (btn.classList.contains('btn-stop-job')) this.stopJob(jobId);
      else if (btn.classList.contains('btn-retry-job')) this.retryJob(jobId);
      else if (btn.classList.contains('btn-delete-job')) this.deleteJob(jobId);
    });

    // Инициализация автодополнения для полей ввода целей
    document.querySelectorAll('.scan-input').forEach(input => {
      const scanType = input.dataset.scanType;
      if (scanType) this.#initScanAutocomplete(input, scanType);
    });

    // Логика чекбокса "Только известные порты" для Nmap
    const knownPortsCheckbox = document.getElementById('nmap-known-ports-only');
    const portsInput = document.getElementById('nmap-ports');
    const groupsSelect = document.getElementById('nmap-groups');
    const portsWarning = document.getElementById('nmap-ports-warning');
    const argsWarning = document.getElementById('nmap-args-warning');
    
    console.log('[ScanResultsController] Nmap form elements found:', {
      checkbox: !!knownPortsCheckbox,
      portsInput: !!portsInput,
      groupsSelect: !!groupsSelect
    });

    knownPortsCheckbox?.addEventListener('change', function() {
      if (this.checked) {
        portsInput.disabled = true; 
        portsInput.value = ''; 
        portsInput.placeholder = 'Блокировано';
        groupsSelect.disabled = false;
        portsWarning?.classList.remove('d-none'); 
        argsWarning?.classList.remove('d-none');
      } else {
        portsInput.disabled = false; 
        portsInput.placeholder = '22,80,443 или 1-1000';
        groupsSelect.disabled = true; 
        groupsSelect.selectedIndex = -1;
        portsWarning?.classList.add('d-none'); 
        argsWarning?.classList.add('d-none');
      }
    });

    // Обработчик формы Nmap
    const nmapForm = document.getElementById('nmap-form');
    console.log('[ScanResultsController] Nmap form found:', !!nmapForm);
    nmapForm?.addEventListener('submit', async (e) => {
      console.log('[ScanResultsController] Nmap form submit event fired!');
      e.preventDefault();
      console.log('[ScanResultsController] Nmap form default prevented, submitting...');
      await this.#submitNmapScan(e.target);
    });

    // Обработчик формы Rustscan
    const rustscanForm = document.getElementById('rustscan-form');
    console.log('[ScanResultsController] Rustscan form found:', !!rustscanForm);
    rustscanForm?.addEventListener('submit', async (e) => {
      console.log('[ScanResultsController] Rustscan form submit event fired!');
      e.preventDefault();
      console.log('[ScanResultsController] Rustscan form default prevented, submitting...');
      await this.#submitRustscanScan(e.target);
    });

    // Обработчик формы Dig
    const digForm = document.getElementById('dig-form');
    console.log('[ScanResultsController] Dig form found:', !!digForm);
    digForm?.addEventListener('submit', async (e) => {
      console.log('[ScanResultsController] Dig form submit event fired!');
      e.preventDefault();
      console.log('[ScanResultsController] Dig form default prevented, submitting...');
      await this.#submitDigScan(e.target);
    });

    // Импорт XML
    document.getElementById('import-xml-btn')?.addEventListener('click', () => this.#handleXmlImport());

    // Кнопка обновления списка задач
    document.getElementById('btn-refresh-jobs')?.addEventListener('click', () => this.loadJobs());

    // Загрузка групп при открытии модального окна импорта XML
    document.getElementById('importXmlModal')?.addEventListener('show.bs.modal', () => this.#loadGroupsForImport());

    // Кнопка "Вернуться к сканированиям"
    document.getElementById('back-to-scans-btn')?.addEventListener('click', () => this.#showScanForms());
  }

  #showScanForms() {
    // Скрываем контейнер с активами
    if (this.assetsContainer) this.assetsContainer.style.display = 'none';
    // Показываем формы сканирований и статус очередей
    if (this.scanForms) this.scanForms.classList.remove('d-none');
    if (this.queueStatus) this.queueStatus.classList.remove('d-none');
    if (this.scanTabs) this.scanTabs.classList.remove('d-none');
    
    // Показываем кнопку импорта
    const importBtn = document.querySelector('[data-bs-target="#importXmlModal"]');
    if (importBtn) importBtn.closest('.row')?.classList.remove('d-none');

    // Снимаем выделение с групп в дереве
    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));
  }

  async loadJobs() {
    try {
      const response = await fetch('/api/scans/status');
      if (!response.ok) return;
      const data = await response.json();
      const tbody = document.querySelector('#jobs-table tbody');
      if (!tbody) return;
      
      tbody.innerHTML = '';
      const recentJobs = Array.isArray(data?.recent_jobs) ? data.recent_jobs : [];
      
      recentJobs.forEach(job => {
        const tr = document.createElement('tr');
        let statusClass = 'bg-secondary';
        if (job.status === 'completed') statusClass = 'bg-success';
        if (job.status === 'running') statusClass = 'bg-primary';
        if (job.status === 'failed') statusClass = 'bg-danger';
        if (['pending', 'queued'].includes(job.status)) statusClass = 'bg-warning text-dark';

        let actions = '';
        if (['pending', 'queued'].includes(job.status)) {
          actions += `<button class="btn btn-sm btn-outline-danger btn-remove-job" data-job-id="${job.id}"><i class="bi bi-trash"></i></button> `;
        }
        if (job.status === 'running') {
          actions += `<button class="btn btn-sm btn-outline-warning btn-stop-job" data-job-id="${job.id}"><i class="bi bi-stop-fill"></i></button> `;
        }
        if (['completed', 'failed', 'stopped', 'cancelled'].includes(job.status)) {
          actions += `<button class="btn btn-sm btn-outline-primary btn-retry-job" data-job-id="${job.id}"><i class="bi bi-arrow-clockwise"></i></button> `;
        }
        if (job.status === 'completed') {
          actions += `<div class="btn-group btn-group-sm"><button type="button" class="btn btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown">⬇️</button><ul class="dropdown-menu">${this.#getDownloadLinks(job)}</ul></div>`;
        }
        if (!['pending', 'queued', 'running'].includes(job.status)) {
          actions += `<button class="btn btn-sm btn-outline-danger btn-delete-job" data-job-id="${job.id}"><i class="bi bi-trash"></i></button> `;
        }

        tr.innerHTML = `<td>${job.id}</td><td><span class="badge bg-info">${job.scan_type}</span></td><td>${job.target}</td><td><span class="badge ${statusClass}">${job.status}</span></td><td><div class="progress" style="height:10px;width:100px;"><div class="progress-bar" style="width:${job.progress}%"></div></div>${job.progress}%</td><td>${new Date(job.created_at).toLocaleString('ru-RU')}</td><td>${actions}</td>`;
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error('Load jobs error:', e);
    }
  }

  async updateQueueStatus() {
    try {
      const response = await fetch('/api/scans/status');
      if (!response.ok) return;
      const data = await response.json();
      
      const nmapQ = data?.queues?.nmap_rustscan;
      if (nmapQ) {
        const elCount = document.getElementById('nmap-queue-count');
        const elCurrent = document.getElementById('nmap-current-job');
        const elStatus = document.getElementById('nmap-queue-status');
        const elList = document.getElementById('nmap-queue-list');
        
        if (elCount) elCount.textContent = nmapQ.queue_length;
        if (elCurrent) elCurrent.textContent = nmapQ.current_job_id ? `#${nmapQ.current_job_id}` : 'Нет';
        if (elStatus) elStatus.textContent = nmapQ.is_running ? 'Выполняется' : 'Ожидание';
        
        let html = '';
        if (Array.isArray(nmapQ.queued_jobs)) {
          nmapQ.queued_jobs.forEach(job => { 
            html += `<div>#${job.job_id} (${job.scan_type}) - ${job.target}</div>`; 
          });
        }
        if (elList) elList.innerHTML = html;
      }

      const utilQ = data?.queues?.utilities;
      if (utilQ) {
        const elCount = document.getElementById('utility-queue-count');
        const elCurrent = document.getElementById('utility-current-job');
        const elStatus = document.getElementById('utility-queue-status');
        const elList = document.getElementById('utility-queue-list');

        if (elCount) elCount.textContent = utilQ.queue_length;
        if (elCurrent) elCurrent.textContent = utilQ.current_job_id ? `#${utilQ.current_job_id}` : 'Нет';
        if (elStatus) elStatus.textContent = utilQ.is_running ? 'Выполняется' : 'Ожидание';
        
        let html = '';
        if (Array.isArray(utilQ.queued_jobs)) {
          utilQ.queued_jobs.forEach(job => { 
            html += `<div>#${job.job_id} (${job.scan_type}) - ${job.target}</div>`; 
          });
        }
        if (elList) elList.innerHTML = html;
      }
    } catch (e) {
      console.error('Update queue status error:', e);
    }
  }

  async removeJob(id) {
    if (!confirm('Удалить задачу из очереди?')) return;
    try {
      const res = await Utils.apiRequest(`/api/scans/scan-queue/${id}`, { method: 'DELETE' });
      Utils.showNotification(res.message || 'Задача удалена', 'success');
      this.loadJobs();
      this.updateQueueStatus();
    } catch(e) { 
      Utils.showNotification('Ошибка: ' + e.message, 'danger'); 
    }
  }

  async stopJob(id) {
    if (!confirm('Остановить задачу?')) return;
    try {
      const res = await Utils.apiRequest(`/api/scan-job/${id}/stop`, { method: 'POST' });
      Utils.showNotification(res.message || 'Задача остановлена', 'success');
      this.loadJobs();
    } catch(e) { 
      Utils.showNotification('Ошибка: ' + e.message, 'danger'); 
    }
  }

  async retryJob(id) {
    if (!confirm('Повторить задачу?')) return;
    try {
      const res = await Utils.apiRequest(`/api/scan-job/${id}/retry`, { method: 'POST' });
      Utils.showNotification(res.message || 'Задача перезапущена', 'success');
      this.loadJobs();
      this.updateQueueStatus();
    } catch(e) { 
      Utils.showNotification('Ошибка: ' + e.message, 'danger'); 
    }
  }

  async deleteJob(id) {
    if (!confirm('Удалить из истории?')) return;
    try {
      const res = await Utils.apiRequest(`/api/scan-job/${id}`, { method: 'DELETE' });
      Utils.showNotification(res.message || 'Задача удалена из истории', 'success');
      this.loadJobs();
    } catch(e) { 
      Utils.showNotification('Ошибка: ' + e.message, 'danger'); 
    }
  }

  startPolling() {
    if (this.pollingInterval) clearInterval(this.pollingInterval);
    this.pollingInterval = setInterval(() => {
      this.updateQueueStatus();
      this.loadJobs();
    }, 5000);
  }

  stopPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }

  async #submitNmapScan(form) {
    console.log('[ScanResultsController] #submitNmapScan called');
    const target = document.getElementById('nmap-target').value.trim();
    const knownOnly = document.getElementById('nmap-known-ports-only').checked;
    const groupIds = Array.from(document.getElementById('nmap-groups').selectedOptions).map(opt => opt.value);

    console.log('[ScanResultsController] Nmap scan data:', { target, knownOnly, groupIds });

    if (!target && !knownOnly) { 
      Utils.showNotification('Укажите цель или выберите "Только известные порты"', 'warning'); 
      return; 
    }
    if (knownOnly && groupIds.length === 0) { 
      Utils.showNotification('Выберите хотя бы одну группу', 'warning'); 
      return; 
    }

    try {
      console.log('[ScanResultsController] Sending Nmap scan request to /api/scans/nmap');
      await Utils.apiRequest('/api/scans/nmap', {
        method: 'POST',
        body: JSON.stringify({
          target, 
          ports: document.getElementById('nmap-ports').value, 
          scripts: document.getElementById('nmap-scripts').value,
          custom_args: document.getElementById('nmap-custom-args').value, 
          known_ports_only: knownOnly, 
          group_ids: groupIds
        })
      });
      console.log('[ScanResultsController] Nmap scan request successful');
      Utils.showNotification('Сканирование Nmap запущено', 'success');
      this.loadJobs();
    } catch (error) {
      console.error('[ScanResultsController] Nmap scan error:', error);
      Utils.showNotification('Ошибка запуска сканирования: ' + error.message, 'danger');
    }
  }

  async #submitRustscanScan(form) {
    console.log('[ScanResultsController] #submitRustscanScan called');
    const target = document.getElementById('rustscan-target').value;
    console.log('[ScanResultsController] Rustscan target:', target);
    
    if (!target) { 
      Utils.showNotification('Укажите цель', 'warning'); 
      return; 
    }

    try {
      console.log('[ScanResultsController] Sending Rustscan scan request to /api/scans/rustscan');
      await Utils.apiRequest('/api/scans/rustscan', {
        method: 'POST',
        body: JSON.stringify({
          target, 
          ports: document.getElementById('rustscan-ports').value,
          custom_args: document.getElementById('rustscan-custom-args').value,
          run_nmap_after: document.getElementById('rustscan-run-nmap').checked,
          nmap_args: document.getElementById('rustscan-nmap-args').value
        })
      });
      console.log('[ScanResultsController] Rustscan scan request successful');
      Utils.showNotification('Сканирование Rustscan запущено', 'success');
      this.loadJobs();
    } catch (error) {
      console.error('[ScanResultsController] Rustscan scan error:', error);
      Utils.showNotification('Ошибка запуска сканирования: ' + error.message, 'danger');
    }
  }

  async #submitDigScan(form) {
    console.log('[ScanResultsController] #submitDigScan called');
    let targetsText = document.getElementById('dig-targets').value.trim();
    const fileInput = document.getElementById('dig-file');

    console.log('[ScanResultsController] Dig targets text:', targetsText);
    console.log('[ScanResultsController] Dig file input:', fileInput?.files?.length);

    if (fileInput?.files?.length > 0) {
      try {
        const fileContent = await this.#readFileAsText(fileInput.files[0]);
        const fileTargets = fileContent.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
        if (targetsText) {
          fileTargets.push(...targetsText.split('\n').map(l => l.trim()).filter(l => l));
        }
        targetsText = fileTargets.join('\n');
        console.log('[ScanResultsController] Combined dig targets:', targetsText);
      } catch (error) { 
        Utils.showNotification('Ошибка чтения файла: ' + error.message, 'danger'); 
        return; 
      }
    }

    if (!targetsText) { 
      Utils.showNotification('Введите цели или загрузите файл', 'warning'); 
      return; 
    }

    let recordTypes = null;
    const typesInput = document.getElementById('dig-types').value.trim();
    if (typesInput) recordTypes = typesInput.split(',').map(t => t.trim().toUpperCase());

    try {
      console.log('[ScanResultsController] Sending Dig scan request to /api/scans/dig');
      await Utils.apiRequest('/api/scans/dig', {
        method: 'POST',
        body: JSON.stringify({
          targets_text: targetsText, 
          dns_server: document.getElementById('dig-server').value,
          cli_args: document.getElementById('dig-cli-args').value, 
          record_types: recordTypes
        })
      });
      console.log('[ScanResultsController] Dig scan request successful');
      Utils.showNotification('Сканирование Dig запущено', 'success');
      this.loadJobs();
    } catch (error) {
      console.error('[ScanResultsController] Dig scan error:', error);
      Utils.showNotification('Ошибка запуска сканирования: ' + error.message, 'danger');
    }
  }

  #getDownloadLinks(job) {
    const base = `/api/scan-job/${job.id}/download`;
    let links = '';
    if (job.scan_type === 'nmap') {
      links += `<li><a class="dropdown-item" href="${base}/xml">XML</a></li><li><a class="dropdown-item" href="${base}/gnmap">Grepable</a></li><li><a class="dropdown-item" href="${base}/normal">Normal</a></li><li><hr class="dropdown-divider"></li><li><a class="dropdown-item" href="${base}/all"><strong>Все (ZIP)</strong></a></li>`;
    } else if (['rustscan', 'dig'].includes(job.scan_type)) {
      links += `<li><a class="dropdown-item" href="${base}/raw">Raw</a></li><li><a class="dropdown-item" href="${base}/txt">TXT</a></li><li><a class="dropdown-item" href="${base}/all"><strong>Все (ZIP)</strong></a></li>`;
    }
    return links;
  }

  #initScanAutocomplete(input, scanType) {
    // Заглушка для автодополнения
    // В реальной реализации здесь будет логика подгрузки известных хостов
    console.log(`Init autocomplete for ${scanType}`);
  }

  async #loadGroupsForImport() {
    const groupSelect = document.getElementById('import-group');
    if (!groupSelect) return;
    
    const currentValue = groupSelect.value;
    groupSelect.innerHTML = '<option value="">Не добавлять в группу</option>';
    groupSelect.disabled = true;
    
    try {
      const response = await fetch('/api/groups/tree');
      if (response.ok) {
        const data = await response.json();
        const flatGroups = Array.isArray(data?.flat) ? data.flat : [];
        flatGroups.forEach(g => {
          const option = document.createElement('option');
          option.value = g.id;
          const depth = g.depth || 0;
          let prefix = '', icon = '📁 ';
          if (depth > 0) {
            for (let i = 0; i < depth; i++) prefix += '    ';
            prefix += '└─ '; 
            icon = '📂 ';
          }
          option.textContent = `${prefix}${icon}${g.name}`;
          groupSelect.appendChild(option);
        });
        if (currentValue && flatGroups.some(g => g.id == currentValue)) {
          groupSelect.value = currentValue;
        }
      }
    } catch (error) { 
      console.error('Ошибка загрузки групп:', error); 
    } finally { 
      groupSelect.disabled = false; 
    }
  }

  #handleXmlImport() {
    // Логика импорта XML
    alert('Функционал импорта XML (в разработке)');
  }

  async #readFileAsText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsText(file);
    });
  }
}

// Инициализация контроллера после загрузки DOM
// Используем setTimeout чтобы убедиться, что DOM полностью готов
setTimeout(() => {
  console.log('[ScanResultsController] Initializing after timeout...');
  if (document.getElementById('nmap-form') || document.getElementById('rustscan-form') || document.getElementById('dig-form')) {
    console.log('[ScanResultsController] Scan forms found, creating instance...');
    window.scanResultsController = new ScanResultsController();
  } else {
    console.log('[ScanResultsController] Scan forms not found on this page');
  }
}, 100);
