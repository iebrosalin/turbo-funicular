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
    
    this.#init();
  }

  async #init() {
    
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
    
    
    // Делегирование событий для кнопок управления заданиями
    const jobsTable = document.getElementById('jobs-table');
    
    jobsTable?.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-job-id]');
      if (!btn) return;
      
      const jobId = btn.dataset.jobId;
      
      
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
    
    nmapForm?.addEventListener('submit', async (e) => {
      
      e.preventDefault();
      
      await this.#submitNmapScan(e.target);
    });

    // Обработчик формы Rustscan
    const rustscanForm = document.getElementById('rustscan-form');
    
    rustscanForm?.addEventListener('submit', async (e) => {
      
      e.preventDefault();
      
      await this.#submitRustscanScan(e.target);
    });

    // Обработчик формы Dig
    const digForm = document.getElementById('dig-form');
    
    digForm?.addEventListener('submit', async (e) => {
      
      e.preventDefault();
      
      await this.#submitDigScan(e.target);
    });

    // Кнопки "Новое сканирование" и "Импорт Nmap XML"
    document.getElementById('newScanBtn')?.addEventListener('click', () => {
        // Можно добавить логику предзаполнения, если нужно
    });
    
    document.getElementById('importNmapBtn')?.addEventListener('click', () => this.#loadGroupsForImport());
    
    // Кнопка запуска простого сканирования из модального окна
    document.getElementById('startSimpleScanBtn')?.addEventListener('click', () => this.#handleSimpleScan());
    
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
      const res = await Utils.apiRequest(`/api/scans/scan-job/${id}/stop`, { method: 'POST' });
      Utils.showNotification(res.message || 'Задача остановлена', 'success');
      this.loadJobs();
    } catch(e) { 
      Utils.showNotification('Ошибка: ' + e.message, 'danger'); 
    }
  }

  async retryJob(id) {
    if (!confirm('Повторить задачу?')) return;
    try {
      const res = await Utils.apiRequest(`/api/scans/scan-job/${id}/retry`, { method: 'POST' });
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
      const res = await Utils.apiRequest(`/api/scans/scan-job/${id}`, { method: 'DELETE' });
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
    
    const target = document.getElementById('nmap-target').value.trim();
    const knownOnly = document.getElementById('nmap-known-ports-only').checked;
    const groupIds = Array.from(document.getElementById('nmap-groups').selectedOptions).map(opt => opt.value);

    

    if (!target && !knownOnly) { 
      Utils.showNotification('Укажите цель или выберите "Только известные порты"', 'warning'); 
      return; 
    }
    if (knownOnly && groupIds.length === 0) { 
      Utils.showNotification('Выберите хотя бы одну группу', 'warning'); 
      return; 
    }

    try {
      
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
      
      Utils.showNotification('Сканирование Nmap запущено', 'success');
      
      // Закрываем модальное окно без перезагрузки страницы
      const modal = bootstrap.Modal.getInstance(document.getElementById('nmapModal'));
      if (modal) modal.hide();
      
      this.loadJobs();
    } catch (error) {
      console.error('[ScanResultsController] Nmap scan error:', error);
      Utils.showNotification('Ошибка запуска сканирования: ' + error.message, 'danger');
    }
  }

  async #submitRustscanScan(form) {
    
    const target = document.getElementById('rustscan-target').value;
    
    
    if (!target) { 
      Utils.showNotification('Укажите цель', 'warning'); 
      return; 
    }

    try {
      
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
      
      Utils.showNotification('Сканирование Rustscan запущено', 'success');
      
      // Закрываем модальное окно без перезагрузки страницы
      const modal = bootstrap.Modal.getInstance(document.getElementById('rustscanModal'));
      if (modal) modal.hide();
      
      this.loadJobs();
    } catch (error) {
      console.error('[ScanResultsController] Rustscan scan error:', error);
      Utils.showNotification('Ошибка запуска сканирования: ' + error.message, 'danger');
    }
  }

  async #submitDigScan(form) {
    
    let targetsText = document.getElementById('dig-targets').value.trim();
    const fileInput = document.getElementById('dig-file');

    
    

    if (fileInput?.files?.length > 0) {
      try {
        const fileContent = await this.#readFileAsText(fileInput.files[0]);
        const fileTargets = fileContent.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
        if (targetsText) {
          fileTargets.push(...targetsText.split('\n').map(l => l.trim()).filter(l => l));
        }
        targetsText = fileTargets.join('\n');
        
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
      
      await Utils.apiRequest('/api/scans/dig', {
        method: 'POST',
        body: JSON.stringify({
          targets_text: targetsText, 
          dns_server: document.getElementById('dig-server').value,
          cli_args: document.getElementById('dig-cli-args').value, 
          record_types: recordTypes
        })
      });
      
      Utils.showNotification('Сканирование Dig запущено', 'success');
      
      // Закрываем модальное окно без перезагрузки страницы
      const modal = bootstrap.Modal.getInstance(document.getElementById('digModal'));
      if (modal) modal.hide();
      
      this.loadJobs();
    } catch (error) {
      console.error('[ScanResultsController] Dig scan error:', error);
      Utils.showNotification('Ошибка запуска сканирования: ' + error.message, 'danger');
    }
  }

  #getDownloadLinks(job) {
    const base = `/api/scan-job/${job.id}/download`;
    const scanBase = `/api/scan/${job.scan_id}/download`;
    let links = '';
    
    // Добавляем CSV и JSON для всех типов сканирований
    links += `<li><a class="dropdown-item" href="${scanBase}/csv">CSV</a></li>`;
    links += `<li><a class="dropdown-item" href="${scanBase}/json">JSON</a></li>`;
    links += `<li><a class="dropdown-item" href="${scanBase}/raw">Raw</a></li>`;
    
    if (job.scan_type === 'nmap') {
      links += `<li><hr class="dropdown-divider"></li>`;
      links += `<li><a class="dropdown-item" href="${base}/xml">XML</a></li>`;
      links += `<li><a class="dropdown-item" href="${base}/gnmap">Grepable</a></li>`;
      links += `<li><a class="dropdown-item" href="${base}/normal">Normal</a></li>`;
    }
    
    return links;
  }

  async #initScanAutocomplete(input, scanType) {
    // Автодополнение на основе известных активов
    let cachedAssets = [];
    
    try {
      const response = await fetch('/api/assets?limit=100');
      if (response.ok) {
        cachedAssets = await response.json();
      }
    } catch (e) {
      console.warn('Не удалось загрузить активы для автодополнения:', e);
    }
    
    input.addEventListener('input', async function() {
      const value = this.value.trim();
      if (value.length < 1) return;
      
      // Фильтруем активы по введённому значению
      const filtered = cachedAssets.filter(asset => 
        asset.ip_address?.toLowerCase().includes(value.toLowerCase()) ||
        asset.hostname?.toLowerCase().includes(value.toLowerCase())
      ).slice(0, 5);
      
      if (filtered.length === 0) return;
      
      // Показываем подсказки (можно добавить UI dropdown)
      console.log('Подсказки:', filtered.map(a => a.ip_address));
    });
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
    const fileInput = document.getElementById('xml-file');
    const groupId = document.getElementById('import-group')?.value;
    
    if (!fileInput || !fileInput.files[0]) {
      alert('Выберите XML файл для импорта');
      return;
    }

    const file = fileInput.files[0];
    const reader = new FileReader();
    
    reader.onload = (event) => {
      const base64Data = event.target.result.split(',')[1]; // Убираем префикс data:...;base64,
      
      const requestData = {
        filename: file.name,
        content: base64Data,
        group_id: groupId ? parseInt(groupId) : null
      };

      fetch('/api/scans/import-nmap-xml', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
      })
      .then(response => {
        if (!response.ok) throw new Error('Ошибка импорта');
        return response.json();
      })
      .then(data => {
        alert(`Импорт завершен! Создано активов: ${data.count || 0}`);
        const modal = bootstrap.Modal.getInstance(document.getElementById('importXmlModal'));
        if (modal) modal.hide();
        this.loadJobs();
      })
      .catch(error => {
        console.error('Ошибка импорта:', error);
        alert(`Ошибка: ${error.message}`);
      });
    };
    
    reader.onerror = () => {
      alert('Ошибка чтения файла');
    };
    
    reader.readAsDataURL(file);
  }

  async #handleSimpleScan() {
    // Получаем данные из активной вкладки модального окна
    const activeTab = document.querySelector('#newScanModal .tab-pane.active');
    if (!activeTab) return;

    const targetInput = activeTab.querySelector('input[id*="target"]');
    const csvInput = document.getElementById('simple-scan-csv');
    const groupSelect = document.getElementById('simple-scan-group-id');
    const scanTypeSelect = document.getElementById('simple-scan-type');
    
    let targets = [];
    
    // Проверяем, загружен ли CSV файл
    if (csvInput && csvInput.files.length > 0) {
      try {
        const file = csvInput.files[0];
        const text = await this.#readFileAsText(file);
        // Разбиваем по строкам и фильтруем пустые
        targets = text.split('\n')
          .map(line => line.trim())
          .filter(line => line.length > 0 && !line.startsWith('#'));
        
        if (targets.length === 0) {
          alert('CSV файл пуст или не содержит корректных целей');
          return;
        }
      } catch (error) {
        console.error('Ошибка чтения CSV:', error);
        alert(`Ошибка чтения файла: ${error.message}`);
        return;
      }
    } else if (targetInput && targetInput.value.trim()) {
      // Используем текстовый ввод
      const targetText = targetInput.value.trim();
      // Разбиваем по запятой если несколько целей
      targets = targetText.split(',').map(t => t.trim()).filter(t => t.length > 0);
    } else {
      alert('Введите цель сканирования или загрузите CSV файл');
      return;
    }

    const groupId = groupSelect?.value || '';
    const scanType = scanTypeSelect?.value || 'standard';

    try {
      const response = await fetch('/api/scans/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target: targets.join(','),
          group_id: groupId ? parseInt(groupId) : null,
          scan_type: scanType
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка запуска сканирования');
      }

      const result = await response.json();
      alert(`Сканирование запущено! ID: ${result.id}`);
      
      // Закрываем модальное окно
      const modal = bootstrap.Modal.getInstance(document.getElementById('newScanModal'));
      if (modal) modal.hide();
      
      // Обновляем список задач
      this.loadJobs();
      
    } catch (error) {
      console.error('Ошибка запуска сканирования:', error);
      alert(`Ошибка: ${error.message}`);
    }
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
  
  if (document.getElementById('nmap-form') || document.getElementById('rustscan-form') || document.getElementById('dig-form')) {
    
    window.scanResultsController = new ScanResultsController();
  } else {
    
  }
}, 100);
