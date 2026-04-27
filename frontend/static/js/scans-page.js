// static/js/scans-page.js
/**
 * Логика страницы управления сканированиями.
 * Обработка форм, обновление статуса очередей и управление историей заданий.
 */

import { submitScan, handleXmlImport, loadGroups, readFileAsText, initScanAutocomplete } from './scan-helpers.js';

console.log('[DEBUG] scans-page.js loaded');

export async function loadJobs() {
    console.log('[DEBUG] loadJobs called');
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
            if (job.status === 'pending' || job.status === 'queued') statusClass = 'bg-warning text-dark';

            let actions = '';
            if (job.status === 'pending' || job.status === 'queued') {
                actions += `<button class="btn btn-sm btn-outline-danger btn-remove-job" data-job-id="${job.id}"><i class="bi bi-trash"></i></button> `;
            }
            if (job.status === 'running') {
                actions += `<button class="btn btn-sm btn-outline-warning btn-stop-job" data-job-id="${job.id}"><i class="bi bi-stop-fill"></i></button> `;
            }
            if (['completed', 'failed', 'stopped', 'cancelled'].includes(job.status)) {
                actions += `<button class="btn btn-sm btn-outline-primary btn-retry-job" data-job-id="${job.id}"><i class="bi bi-arrow-clockwise"></i></button> `;
            }
            if (job.status === 'completed') {
                actions += `<div class="btn-group btn-group-sm"><button type="button" class="btn btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown">⬇️</button><ul class="dropdown-menu">${getDownloadLinks(job)}</ul></div>`;
            }
            if (job.status !== 'pending' && job.status !== 'queued' && job.status !== 'running') {
                actions += `<button class="btn btn-sm btn-outline-danger btn-delete-job" data-job-id="${job.id}"><i class="bi bi-trash"></i></button> `;
            }

            tr.innerHTML = `<td>${job.id}</td><td><span class="badge bg-info">${job.scan_type}</span></td><td>${job.target}</td><td><span class="badge ${statusClass}">${job.status}</span></td><td><div class="progress" style="height:10px;width:100px;"><div class="progress-bar" style="width:${job.progress}%"></div></div>${job.progress}%</td><td>${new Date(job.created_at).toLocaleString('ru-RU')}</td><td>${actions}</td>`;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('[DEBUG] loadJobs error:', e);
    }
}

export async function updateQueueStatus() {
    try {
        const response = await fetch('/api/scans/status');
        if (!response.ok) return;
        const data = await response.json();
        
        const nmapQ = data?.queues?.nmap_rustscan;
        if (nmapQ) {
            document.getElementById('nmap-queue-count').textContent = nmapQ.queue_length;
            document.getElementById('nmap-current-job').textContent = nmapQ.current_job_id ? `#${nmapQ.current_job_id}` : 'Нет';
            document.getElementById('nmap-queue-status').textContent = nmapQ.is_running ? 'Выполняется' : 'Ожидание';
            let html = '';
            if (Array.isArray(nmapQ.queued_jobs)) {
                nmapQ.queued_jobs.forEach(job => { html += `<div>#${job.job_id} (${job.scan_type}) - ${job.target}</div>`; });
            }
            document.getElementById('nmap-queue-list').innerHTML = html;
        }

        const utilQ = data?.queues?.utilities;
        if (utilQ) {
            document.getElementById('utility-queue-count').textContent = utilQ.queue_length;
            document.getElementById('utility-current-job').textContent = utilQ.current_job_id ? `#${utilQ.current_job_id}` : 'Нет';
            document.getElementById('utility-queue-status').textContent = utilQ.is_running ? 'Выполняется' : 'Ожидание';
            let html = '';
            if (Array.isArray(utilQ.queued_jobs)) {
                utilQ.queued_jobs.forEach(job => { html += `<div>#${job.job_id} (${job.scan_type}) - ${job.target}</div>`; });
            }
            document.getElementById('utility-queue-list').innerHTML = html;
        }
    } catch (e) {
        console.error('[DEBUG] updateQueueStatus error:', e);
    }
}

export async function removeJob(id) {
    if (!confirm('Удалить задачу из очереди?')) return;
    try {
        const res = await fetch(`/api/scan-queue/${id}`, {method: 'DELETE'});
        const data = await res.json();
        alert(data.message);
        loadJobs();
        updateQueueStatus();
    } catch(e) { alert('Ошибка: ' + e); }
}

export async function stopJob(id) {
    if (!confirm('Остановить задачу?')) return;
    try {
        const res = await fetch(`/api/scan-job/${id}/stop`, {method: 'POST'});
        const data = await res.json();
        alert(data.message);
        loadJobs();
    } catch(e) { alert('Ошибка: ' + e); }
}

export async function retryJob(id) {
    if (!confirm('Повторить задачу?')) return;
    try {
        const res = await fetch(`/api/scan-job/${id}/retry`, {method: 'POST'});
        const data = await res.json();
        alert(data.message);
        loadJobs();
        updateQueueStatus();
    } catch(e) { alert('Ошибка: ' + e); }
}

export async function deleteJob(id) {
    if (!confirm('Удалить из истории?')) return;
    try {
        const res = await fetch(`/api/scan-job/${id}`, {method: 'DELETE'});
        const data = await res.json();
        alert(data.message);
        loadJobs();
    } catch(e) { alert('Ошибка: ' + e); }
}

// Функции теперь вызываются через event delegation, не экспортируем в window

function getDownloadLinks(job) {
    const base = `/api/scan-job/${job.id}/download`;
    let links = '';
    if (job.scan_type === 'nmap') {
        links += `<li><a class="dropdown-item" href="${base}/xml">XML</a></li><li><a class="dropdown-item" href="${base}/gnmap">Grepable</a></li><li><a class="dropdown-item" href="${base}/normal">Normal</a></li><li><hr class="dropdown-divider"></li><li><a class="dropdown-item" href="${base}/all"><strong>Все (ZIP)</strong></a></li>`;
    } else if (job.scan_type === 'rustscan' || job.scan_type === 'dig') {
        links += `<li><a class="dropdown-item" href="${base}/raw">Raw</a></li><li><a class="dropdown-item" href="${base}/txt">TXT</a></li><li><a class="dropdown-item" href="${base}/all"><strong>Все (ZIP)</strong></a></li>`;
    }
    return links;
}

document.addEventListener('DOMContentLoaded', function() {
    // Делегирование событий для кнопок управления заданиями
    const jobsTable = document.getElementById('jobs-table');
    if (jobsTable) {
        jobsTable.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-job-id]');
            if (!btn) return;
            
            const jobId = btn.dataset.jobId;
            
            if (btn.classList.contains('btn-remove-job')) {
                removeJob(jobId);
            } else if (btn.classList.contains('btn-stop-job')) {
                stopJob(jobId);
            } else if (btn.classList.contains('btn-retry-job')) {
                retryJob(jobId);
            } else if (btn.classList.contains('btn-delete-job')) {
                deleteJob(jobId);
            }
        });
    }

    document.querySelectorAll('.scan-input').forEach(input => {
        const scanType = input.dataset.scanType;
        if (scanType) {
            initScanAutocomplete(input, scanType);
        }
    });

    loadGroups();
    updateQueueStatus();
    loadJobs();
    
    setInterval(() => { updateQueueStatus(); loadJobs(); }, 5000);

    // Nmap known ports checkbox logic
    const knownPortsCheckbox = document.getElementById('nmap-known-ports-only');
    const portsInput = document.getElementById('nmap-ports');
    const groupsSelect = document.getElementById('nmap-groups');
    const portsWarning = document.getElementById('nmap-ports-warning');
    const argsWarning = document.getElementById('nmap-args-warning');

    if (knownPortsCheckbox) {
        knownPortsCheckbox.addEventListener('change', function() {
            if (this.checked) {
                portsInput.disabled = true; portsInput.value = ''; portsInput.placeholder = 'Блокировано';
                groupsSelect.disabled = false;
                portsWarning.classList.remove('d-none'); argsWarning.classList.remove('d-none');
            } else {
                portsInput.disabled = false; portsInput.placeholder = '22,80,443 или 1-1000';
                groupsSelect.disabled = true; groupsSelect.selectedIndex = -1;
                portsWarning.classList.add('d-none'); argsWarning.classList.add('d-none');
            }
        });
    }

    // Nmap form handler
    const nmapForm = document.getElementById('nmap-form');
    if (nmapForm) {
        nmapForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const target = document.getElementById('nmap-target').value.trim();
            const knownOnly = knownPortsCheckbox.checked;
            const groupIds = Array.from(groupsSelect.selectedOptions).map(opt => opt.value);

            if (!target && !knownOnly) { alert('Укажите цель или выберите "Только известные порты"'); return; }
            if (knownOnly && groupIds.length === 0) { alert('Выберите хотя бы одну группу'); return; }

            await submitScan('/api/scans/nmap', {
                target, ports: portsInput.value, scripts: document.getElementById('nmap-scripts').value,
                custom_args: document.getElementById('nmap-custom-args').value, known_ports_only: knownOnly, group_ids: groupIds
            }, 'Nmap');
        });
    }

    // Rustscan form handler
    const rustscanForm = document.getElementById('rustscan-form');
    if (rustscanForm) {
        rustscanForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const target = document.getElementById('rustscan-target').value;
            if (!target) { alert('Укажите цель'); return; }
            await submitScan('/api/scans/rustscan', {
                target, ports: document.getElementById('rustscan-ports').value,
                custom_args: document.getElementById('rustscan-custom-args').value,
                run_nmap_after: document.getElementById('rustscan-run-nmap').checked,
                nmap_args: document.getElementById('rustscan-nmap-args').value
            }, 'Rustscan');
        });
    }

    // Dig form handler
    const digForm = document.getElementById('dig-form');
    if (digForm) {
        digForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            let targetsText = document.getElementById('dig-targets').value.trim();
            const fileInput = document.getElementById('dig-file');

            if (fileInput && fileInput.files && fileInput.files.length > 0) {
                try {
                    const fileContent = await readFileAsText(fileInput.files[0]);
                    const fileTargets = fileContent.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
                    if (targetsText) {
                        fileTargets.push(...targetsText.split('\n').map(l => l.trim()).filter(l => l));
                    }
                    targetsText = fileTargets.join('\n');
                } catch (error) { alert('Ошибка чтения файла: ' + error.message); return; }
            }

            if (!targetsText) { alert('Введите цели или загрузите файл'); return; }

            let recordTypes = null;
            const typesInput = document.getElementById('dig-types').value.trim();
            if (typesInput) recordTypes = typesInput.split(',').map(t => t.trim().toUpperCase());

            await submitScan('/api/scans/dig', {
                targets_text: targetsText, dns_server: document.getElementById('dig-server').value,
                cli_args: document.getElementById('dig-cli-args').value, record_types: recordTypes
            }, 'Dig');
        });
    }

    // XML Import handler
    const importXmlBtn = document.getElementById('import-xml-btn');
    if (importXmlBtn) importXmlBtn.addEventListener('click', handleXmlImport);

    // Refresh jobs button handler
    const refreshJobsBtn = document.getElementById('btn-refresh-jobs');
    if (refreshJobsBtn) {
        refreshJobsBtn.addEventListener('click', loadJobs);
    }

    // Load groups on modal open
    const importXmlModal = document.getElementById('importXmlModal');
    if (importXmlModal) {
        importXmlModal.addEventListener('show.bs.modal', async function () {
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
                            prefix += '└─ '; icon = '📂 ';
                        }
                        option.textContent = `${prefix}${icon}${g.name}`;
                        groupSelect.appendChild(option);
                    });
                    if (currentValue && flatGroups.some(g => g.id == currentValue)) groupSelect.value = currentValue;
                }
            } catch (error) { console.error('Ошибка загрузки групп:', error); }
            finally { groupSelect.disabled = false; }
        });
    }
});
