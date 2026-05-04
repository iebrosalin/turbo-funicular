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
    
    // Пагинация истории сканирований
    this.historyPage = 0;
    this.historyPageSize = 20;
    this.historyLoading = false;
    this.historyEndReached = false;
    
    this.#init();
  }

  async #init() {
    // Загружаем группы для форм Nmap и Rustscan
    await this.#loadGroupsForForms();
    
    this.#setupEventListeners();
    this.#initUrlFiltering();
    await this.loadJobs();
    await this.updateQueueStatus();
    
    // Загружаем историю сканирований если есть контейнер
    if (document.getElementById('scansHistoryBody')) {
      await this.loadHistory();
    }
    
    // Автообновление каждые 5 секунд
    this.startPolling();
  }

  async #loadGroupsForForms() {
    try {
      const response = await fetch('/api/groups/list');
      if (!response.ok) return;
      const data = await response.json();
      
      // Обработка ответа: может быть массив или объект с полем flat/tree
      let groups = [];
      if (Array.isArray(data)) {
        groups = data;
      } else if (data && Array.isArray(data.flat)) {
        groups = data.flat;
      } else if (data && Array.isArray(data.tree)) {
        groups = data.tree;
      }
      
      if (!Array.isArray(groups)) {
        console.warn('Группы не являются массивом:', data);
        return;
      }

      const nmapSelect = document.getElementById('nmapGroups');
      const rustscanSelect = document.getElementById('rustscanGroups');
      
      const fillSelect = (select) => {
        if (!select) return;
        select.innerHTML = '';
        groups.forEach(group => {
          const option = document.createElement('option');
          option.value = group.id;
          option.textContent = group.name;
          select.appendChild(option);
        });
      };
      
      fillSelect(nmapSelect);
      fillSelect(rustscanSelect);
    } catch (error) {
      console.error('Ошибка загрузки групп:', error);
    }
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

  /**
   * Загрузка истории сканирований (с пагинацией)
   * @param {boolean} append - если true, добавлять к существующим записям, иначе очистить таблицу
   */
  async loadHistory(append = false) {
    if (this.historyLoading || this.historyEndReached) return;
    
    this.historyLoading = true;
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator && !append) {
      loadingIndicator.classList.remove('d-none');
    }
    
    try {
      const offset = this.historyPage * this.historyPageSize;
      const response = await fetch(`/api/scans/history?limit=${this.historyPageSize}&offset=${offset}`);
      if (!response.ok) {
        this.historyLoading = false;
        return;
      }
      const jobs = await response.json();
      
      const tbody = document.getElementById('scansHistoryBody');
      if (!tbody) {
        this.historyLoading = false;
        return;
      }
      
      // Очищаем таблицу только при первой загрузке
      if (!append) {
        tbody.innerHTML = '';
      }
      
      if (!jobs || jobs.length === 0) {
        if (!append) {
          tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">История пуста</td></tr>';
        }
        this.historyEndReached = true;
        const endMsg = document.getElementById('endOfListMessage');
        if (endMsg) endMsg.classList.remove('d-none');
        this.historyLoading = false;
        return;
      }
      
      jobs.forEach(job => {
        const tr = document.createElement('tr');
        let statusClass = 'bg-secondary';
        if (job.status === 'completed') statusClass = 'bg-success';
        if (job.status === 'running') statusClass = 'bg-warning';
        if (job.status === 'failed') statusClass = 'bg-danger';
        
        const duration = job.completed_at && job.started_at 
          ? Math.round((new Date(job.completed_at) - new Date(job.started_at)) / 1000) + ' сек'
          : '-';
        
        tr.innerHTML = `
          <td>${job.id}</td>
          <td><span class="badge bg-info">${job.scan_type}</span></td>
          <td>${job.target || '-'}</td>
          <td><span class="badge ${statusClass}">${job.status}</span></td>
          <td>${duration}</td>
          <td>${job.completed_at ? new Date(job.completed_at).toLocaleString('ru-RU') : '-'}</td>
          <td>
            <button class="btn btn-sm btn-outline-primary" onclick="window.scanResultsController.viewScanResults(${job.id})">
              <i class="bi bi-eye"></i>
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
      
      // Если загружено меньше чем pageSize, значит достигли конца
      if (jobs.length < this.historyPageSize) {
        this.historyEndReached = true;
        const endMsg = document.getElementById('endOfListMessage');
        if (endMsg) endMsg.classList.remove('d-none');
      }
      
      this.historyPage++;
      
    } catch (e) {
      console.error('Load history error:', e);
    } finally {
      this.historyLoading = false;
      const loadingIndicator = document.getElementById('loadingIndicator');
      if (loadingIndicator) {
        loadingIndicator.classList.add('d-none');
      }
    }
  }

  /**
   * Обновление статуса очередей сканирований
   */
  async updateQueueStatus() {
    try {
      const response = await fetch('/api/scans/status');
      if (!response.ok) return;
      const data = await response.json();
      
      // Очередь Nmap/Rustscan
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
        if (elList) elList.innerHTML = html || '<span class="text-muted">Пусто</span>';
      }

      // Очередь Utilities (Dig и другие)
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
        if (elList) elList.innerHTML = html || '<span class="text-muted">Пусто</span>';
      }
    } catch (e) {
      console.error('Update queue status error:', e);
    }
  }

  #setupEventListeners() {
    
    // Переключение видимости поля custom args для Nmap
    const nmapProfile = document.getElementById('nmapProfile');
    const nmapCustomArgsContainer = document.getElementById('nmapCustomArgsContainer');
    if (nmapProfile && nmapCustomArgsContainer) {
      nmapProfile.addEventListener('change', () => {
        if (nmapProfile.value === 'custom') {
          nmapCustomArgsContainer.classList.remove('d-none');
        } else {
          nmapCustomArgsContainer.classList.add('d-none');
        }
      });
    }

    // Переключение видимости поля портов для Rustscan
    const rustscanTopPorts = document.getElementById('rustscanTopPorts');
    const rustscanPortsContainer = document.getElementById('rustscanPortsContainer');
    if (rustscanTopPorts && rustscanPortsContainer) {
      rustscanTopPorts.addEventListener('change', () => {
        if (rustscanTopPorts.value === 'custom') {
          rustscanPortsContainer.classList.remove('d-none');
        } else {
          rustscanPortsContainer.classList.add('d-none');
        }
      });
    }

    // Делегирование событий для кнопок управления заданиями
    const jobsTable = document.getElementById('scansHistoryBody');
    
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
    const knownPortsCheckbox = document.getElementById('nmapKnownOnly');
    const groupsContainer = document.getElementById('nmapGroupsContainer');
    
    knownPortsCheckbox?.addEventListener('change', function() {
      if (this.checked) {
        groupsContainer?.classList.remove('d-none');
      } else {
        groupsContainer?.classList.add('d-none');
      }
    });
    
    // Логика чекбокса "Только известные порты" для Rustscan
    const rustscanKnownPortsCheckbox = document.getElementById('rustscanKnownOnly');
    const rustscanGroupsContainer = document.getElementById('rustscanGroupsContainer');
    
    rustscanKnownPortsCheckbox?.addEventListener('change', function() {
      if (this.checked) {
        rustscanGroupsContainer?.classList.remove('d-none');
      } else {
        rustscanGroupsContainer?.classList.add('d-none');
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

    // Бесконечный скролл для истории сканирований
    const historyContainer = document.querySelector('.table-responsive');
    if (historyContainer) {
      historyContainer.addEventListener('scroll', () => {
        const scrollTop = historyContainer.scrollTop;
        const scrollHeight = historyContainer.scrollHeight;
        const clientHeight = historyContainer.clientHeight;
        
        // Если прокрутили до конца (с запасом 50px)
        if (scrollTop + clientHeight >= scrollHeight - 50) {
          this.loadHistory(true); // append = true
        }
      });
    }

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
      const tbody = document.getElementById('scansHistoryBody');
      if (!tbody) return;
      
      tbody.innerHTML = '';
      const recentJobs = Array.isArray(data?.recent_jobs) ? data.recent_jobs : [];
      
      recentJobs.forEach(job => {
        const tr = document.createElement('tr');
        let statusClass = 'bg-secondary';
        if (job.status === 'completed') statusClass = 'bg-success';
        if (job.status === 'running') statusClass = 'bg-primary';
        if (job.status === 'failed') statusClass = 'bg-danger';
        if (['pending', 'queued'].includes(job.status)) statusClass = 'bg-warning';

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
      await Promise.all([this.loadJobs(), this.updateQueueStatus()]);
    } catch(e) { 
      Utils.showNotification('Ошибка: ' + e.message, 'danger'); 
    }
  }

  async stopJob(id) {
    if (!confirm('Остановить задачу?')) return;
    try {
      const res = await Utils.apiRequest(`/api/scans/scan-job/${id}/stop`, { method: 'POST' });
      Utils.showNotification(res.message || 'Задача остановлена', 'success');
      await Promise.all([this.loadJobs(), this.updateQueueStatus()]);
    } catch(e) { 
      Utils.showNotification('Ошибка: ' + e.message, 'danger'); 
    }
  }

  async retryJob(id) {
    if (!confirm('Повторить задачу?')) return;
    try {
      const res = await Utils.apiRequest(`/api/scans/scan-job/${id}/retry`, { method: 'POST' });
      Utils.showNotification(res.message || 'Задача перезапущена', 'success');
      await Promise.all([this.loadJobs(), this.updateQueueStatus()]);
    } catch(e) { 
      Utils.showNotification('Ошибка: ' + e.message, 'danger'); 
    }
  }

  async deleteJob(id) {
    if (!confirm('Удалить из истории?')) return;
    try {
      const res = await Utils.apiRequest(`/api/scans/scan-job/${id}`, { method: 'DELETE' });
      Utils.showNotification(res.message || 'Задача удалена из истории', 'success');
      await Promise.all([this.loadJobs(), this.updateQueueStatus()]);
    } catch(e) { 
      Utils.showNotification('Ошибка: ' + e.message, 'danger'); 
    }
  }

  startPolling() {
    if (this.pollingInterval) clearInterval(this.pollingInterval);
    this.pollingInterval = setInterval(async () => {
      await Promise.all([this.updateQueueStatus(), this.loadJobs()]);
    }, 5000);
  }

  stopPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }

  async #submitNmapScan(form) {
    const targetInput = document.getElementById('nmapTarget');
    const target = targetInput?.value.trim() || '';
    
    // Проверяем, выбран ли режим "Только известные порты"
    const knownOnlyCheckbox = document.getElementById('nmapKnownOnly');
    const knownOnly = knownOnlyCheckbox?.checked || false;
    
    const groupSelect = document.getElementById('nmapGroups');
    const groupIds = groupSelect ? Array.from(groupSelect.selectedOptions).map(opt => opt.value) : [];

    if (!target && !knownOnly) { 
      Utils.showNotification('Укажите цель или выберите "Только известные порты"', 'warning'); 
      return; 
    }
    if (knownOnly && groupIds.length === 0) { 
      Utils.showNotification('Выберите хотя бы одну группу', 'warning'); 
      return; 
    }

    // Собираем выбранные скрипты NSE
    let scripts = [];
    if (document.getElementById('nmapScriptDefault')?.checked) scripts.push('default');
    if (document.getElementById('nmapScriptSafe')?.checked) scripts.push('safe');
    if (document.getElementById('nmapScriptVuln')?.checked) scripts.push('vuln');
    const scriptsStr = scripts.join(',') || '';

    try {
      
      await Utils.apiRequest('/api/scans/nmap', {
        method: 'POST',
        body: JSON.stringify({
          target, 
          ports: document.getElementById('nmapPorts')?.value || '', 
          scripts: scriptsStr,
          custom_args: document.getElementById('nmapCustomArgs')?.value || '', 
          known_ports_only: knownOnly, 
          group_ids: groupIds,
          save_assets: document.getElementById('nmapSaveAssets')?.checked ?? true
        })
      });
      
      Utils.showNotification('Сканирование Nmap запущено', 'success');
      
      // Закрываем модальное окно без перезагрузки страницы
      const modal = bootstrap.Modal.getInstance(document.getElementById('nmapModal'));
      if (modal) modal.hide();
      
      await Promise.all([this.loadJobs(), this.updateQueueStatus()]);
    } catch (error) {
      console.error('[ScanResultsController] Nmap scan error:', error);
      Utils.showNotification('Ошибка запуска сканирования: ' + error.message, 'danger');
    }
  }

  async #submitRustscanScan(form) {
    const targetInput = document.getElementById('rustscanTarget');
    const target = targetInput?.value.trim() || '';
    
    // Проверяем, выбран ли режим "Только известные порты"
    const knownOnlyCheckbox = document.getElementById('rustscanKnownOnly');
    const knownOnly = knownOnlyCheckbox?.checked || false;
    
    const groupSelect = document.getElementById('rustscanGroups');
    const groupIds = groupSelect ? Array.from(groupSelect.selectedOptions).map(opt => opt.value) : [];

    if (!target && !knownOnly) { 
      Utils.showNotification('Укажите цель или выберите "Только известные порты"', 'warning'); 
      return; 
    }
    if (knownOnly && groupIds.length === 0) { 
      Utils.showNotification('Выберите хотя бы одну группу', 'warning'); 
      return; 
    }

    try {
      
      await Utils.apiRequest('/api/scans/rustscan', {
        method: 'POST',
        body: JSON.stringify({
          target: target || null, 
          ports: document.getElementById('rustscanPortsRange')?.value || '',
          custom_args: document.getElementById('rustscanCustomArgs')?.value || '',
          run_nmap_after: document.getElementById('rustscanRunNmap')?.checked || false,
          nmap_args: document.getElementById('rustscanNmapArgs')?.value || '',
          known_ports_only: knownOnly,
          group_ids: groupIds,
          save_assets: document.getElementById('rustscanSaveAssets')?.checked ?? true
        })
      });
      
      Utils.showNotification('Сканирование Rustscan запущено', 'success');
      
      // Закрываем модальное окно без перезагрузки страницы
      const modal = bootstrap.Modal.getInstance(document.getElementById('rustscanModal'));
      if (modal) modal.hide();
      
      await Promise.all([this.loadJobs(), this.updateQueueStatus()]);
    } catch (error) {
      console.error('[ScanResultsController] Rustscan scan error:', error);
      Utils.showNotification('Ошибка запуска сканирования: ' + error.message, 'danger');
    }
  }

  async #submitDigScan(form) {
    
    const targetsInput = document.getElementById('digDomain');
    let targetsText = targetsInput ? targetsInput.value.trim() : '';
    const fileInput = document.getElementById('digFile');

    
    

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
      Utils.showNotification('Введите домен или загрузите файл', 'warning'); 
      return; 
    }

    let recordTypes = null;
    const typesInput = document.getElementById('digType');
    if (typesInput) {
      const typesValue = typesInput.value.trim();
      if (typesValue && typesValue !== 'ANY') recordTypes = typesValue;
    }
    try {
      
      await Utils.apiRequest('/api/scans/dig', {
        method: 'POST',
        body: JSON.stringify({
          target: targetsText,
          dns_server: document.getElementById('digServer')?.value || '',
          cli_args: document.getElementById('digCustomArgs')?.value || '',
          record_types: recordTypes,
          save_assets: document.getElementById('digSaveAssets')?.checked ?? true
        })
      });
      
      Utils.showNotification('Сканирование Dig запущено', 'success');
      
      // Закрываем модальное окно без перезагрузки страницы
      const modal = bootstrap.Modal.getInstance(document.getElementById('digModal'));
      if (modal) modal.hide();
      
      await Promise.all([this.loadJobs(), this.updateQueueStatus()]);
    } catch (error) {
      console.error('[ScanResultsController] Dig scan error:', error);
      Utils.showNotification('Ошибка запуска сканирования: ' + error.message, 'danger');
    }
  }

  #getDownloadLinks(job) {
    const base = `/api/scan-job/${job.id}/download`;
    // Используем job_id как основной идентификатор, scan_id может быть undefined
    let links = '';
    
    // Добавляем JSON для всех типов сканирований
    links += `<li><a class="dropdown-item" href="${base}/json">JSON (из БД)</a></li>`;
    links += `<li><a class="dropdown-item" href="${base}/raw">Raw (stdout)</a></li>`;
    
    if (job.scan_type === 'nmap') {
      links += `<li><hr class="dropdown-divider"></li>`;
      links += `<li><a class="dropdown-item" href="${base}/xml">XML</a></li>`;
      links += `<li><a class="dropdown-item" href="${base}/gnmap">Grepable (nmap)</a></li>`;
      links += `<li><a class="dropdown-item" href="${base}/normal">Normal (nmap)</a></li>`;
    }
    
    if (job.scan_type === 'rustscan') {
      links += `<li><hr class="dropdown-divider"></li>`;
      links += `<li><a class="dropdown-item" href="${base}/json">JSON (rustscan)</a></li>`;
      links += `<li><a class="dropdown-item" href="${base}/grepable">Grepable (rustscan)</a></li>`;
    }
    
    if (job.scan_type === 'dig') {
      links += `<li><hr class="dropdown-divider"></li>`;
      links += `<li><a class="dropdown-item" href="${base}/json-dig">JSON (dig)</a></li>`;
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
      .then(async data => {
        alert(`Импорт завершен! Создано активов: ${data.count || 0}`);
        const modal = bootstrap.Modal.getInstance(document.getElementById('importXmlModal'));
        if (modal) modal.hide();
        await Promise.all([this.loadJobs(), this.updateQueueStatus()]);
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
    const groupSelect = document.getElementById('simple-scan-group-id');
    const scanTypeSelect = document.getElementById('simple-scan-type');
    
    let targets = [];
    
    // Используем текстовый ввод
    if (targetInput && targetInput.value.trim()) {
      const targetText = targetInput.value.trim();
      // Разбиваем по запятой если несколько целей
      targets = targetText.split(',').map(t => t.trim()).filter(t => t.length > 0);
    } else {
      alert('Введите цель сканирования');
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
      await Promise.all([this.loadJobs(), this.updateQueueStatus()]);
      
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

  /**
   * Просмотр результатов сканирования (для совместимости с templates/scans.html)
   */
  async viewScanResults(id) {
    const modalId = 'scanResultModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) {
      // Если модальное окно не найдено, просто загружаем историю
      await this.loadHistory();
      return;
    }

    const m = new bootstrap.Modal(modalEl);
    const c = document.getElementById('scanResultContent');
    const titleEl = document.getElementById('resultScanId');
    
    if (titleEl) titleEl.textContent = `#${id}`;
    if (c) c.innerHTML = '<div class="text-center"><div class="spinner-border"></div><p class="mt-2">Загрузка...</p></div>';
    
    m.show();
    
    try {
      const r = await fetch(`/api/scans/${id}/results`);
      const d = await r.json();
      
      let h = `<h6>#${d.job.id} - ${d.job.scan_type.toUpperCase()}</h6>`;
      h += `<p><strong>Цель:</strong> ${d.job.target}</p>`;
      h += `<p><strong>Статус:</strong> <span class="badge bg-${d.job.status === 'completed' ? 'success' : d.job.status === 'failed' ? 'danger' : 'warning'}">${d.job.status}</span></p>`;
      h += `<p><strong>Прогресс:</strong> ${d.job.progress}%</p>`;
      if (d.job.started_at) h += `<p><strong>Начало:</strong> ${d.job.started_at}</p>`;
      if (d.job.completed_at) h += `<p><strong>Завершение:</strong> ${d.job.completed_at}</p>`;
      
      // Добавляем вывод stdout утилиты
      if (d.raw_output) {
        h += `<hr><h6>Вывод утилиты (stdout):</h6>`;
        h += `<pre class="bg-dark text-light p-3 rounded" style="max-height: 400px; overflow-y: auto;"><code>${this.escapeHtml(d.raw_output)}</code></pre>`;
      }
      
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
      if (c) c.innerHTML = `<div class="alert alert-danger">Ошибка загрузки результатов: ${err.message}</div>`;
    }
  }
  
  /**
   * Экранирование HTML для безопасного вывода
   */
  escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Инициализация контроллера после загрузки DOM
// Используем setTimeout чтобы убедиться, что DOM полностью готов
setTimeout(() => {
  
  if (document.getElementById('nmap-form') || document.getElementById('rustscan-form') || document.getElementById('dig-form') || document.getElementById('scansHistoryBody')) {
    
    window.scanResultsController = new ScanResultsController();
  } else {
    
  }
}, 100);
