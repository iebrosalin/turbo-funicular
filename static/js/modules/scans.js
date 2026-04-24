// static/js/modules/scans.js

export async function viewScanResults(id) {
    const modalId = 'scanResultsModal';
    const modalEl = document.getElementById(modalId);
    if(!modalEl) return;

    const m = new bootstrap.Modal(modalEl);
    const c = document.getElementById('scan-results-content');
    const errAlert = document.getElementById('scan-error-alert');
    const errText = document.getElementById('scan-error-text');
    
    if(c) c.innerHTML = '<div class="text-center"><div class="spinner-border"></div><p class="mt-2">Загрузка...</p></div>';
    if(errAlert) errAlert.style.display = 'none';
    
    m.show();
    
    try{
        const r = await fetch(`/api/scans/${id}/results`);
        const d = await r.json();
        
        if(d.job.status === 'failed' && d.job.error_message){
            if(errAlert) errAlert.style.display = 'block';
            if(errText) errText.textContent = d.job.error_message;
        }
        
        let h = `<h6>#${d.job.id} - ${d.job.scan_type.toUpperCase()}</h6>`;
        h += `<p><strong>Цель:</strong> ${d.job.target}</p>`;
        h += `<p><strong>Статус:</strong> <span class="badge bg-${d.job.status==='completed'?'success':d.job.status==='failed'?'danger':'warning'}">${d.job.status}</span></p>`;
        h += `<p><strong>Прогресс:</strong> ${d.job.progress}%</p>`;
        if(d.job.started_at) h += `<p><strong>Начало:</strong> ${d.job.started_at}</p>`;
        if(d.job.completed_at) h += `<p><strong>Завершение:</strong> ${d.job.completed_at}</p>`;
        h += `<hr>`;
        
        if(d.job.status === 'failed'){
            h += '<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Сканирование завершилось с ошибкой.</div>';
        } else if(!d.results || d.results.length === 0){
            h += '<p class="text-muted">Нет результатов</p>';
        } else {
            h += `<p><strong>Найдено хостов:</strong> ${d.results.length}</p><div class="list-group">`;
            d.results.forEach(x=>{
                h += `<div class="list-group-item"><div class="d-flex justify-content-between"><h6 class="mb-1">${x.ip}</h6><small>${x.scanned_at}</small></div><p class="mb-1"><strong>Порты:</strong> ${x.ports && x.ports.join ? x.ports.join(', ') : 'Нет'}</p>${x.os && x.os !== '-' ? `<p class="mb-0"><strong>ОС:</strong> ${x.os}</p>`:''}</div>`;
            });
            h += '</div>';
        }
        if(c) c.innerHTML = h;
    }catch(err){ 
        if(errAlert) errAlert.style.display = 'block';
        if(errText) errText.textContent = `Ошибка загрузки результатов: ${err.message}`;
    }
}

export function showScanError(jobId, errorMsg){
    const modalId = 'scanErrorModal';
    const modalEl = document.getElementById(modalId);
    if(!modalEl) return alert(errorMsg);

    const m = new bootstrap.Modal(modalEl);
    const c = document.getElementById('scan-error-content');
    const safeMsg = errorMsg ? errorMsg.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$') : 'Неизвестная ошибка';
    
    if(c) {
        c.innerHTML = `
            <div class="alert alert-danger">
                <h6><i class="bi bi-exclamation-triangle"></i> Ошибка сканирования #${jobId}:</h6>
                <pre class="mb-0" style="white-space:pre-wrap;max-height:400px;overflow-y:auto">${safeMsg}</pre>
            </div>
            <div class="mt-3">
                <button class="btn btn-sm btn-outline-secondary" onclick="navigator.clipboard.writeText('${safeMsg}')">
                    <i class="bi bi-clipboard"></i> Копировать ошибку
                </button>
            </div>
        `;
    }
    m.show();
}

export async function updateScanHistory(){
    try{
        const res = await fetch('/api/scans/history');
        if(!res.ok) return;
        const jobs = await res.json();
        const tbody = document.querySelector('#history-table tbody');
        if(!tbody) return;

        jobs.forEach(j=>{
            const row = document.getElementById(`scan-row-${j.id}`);
            if(!row) return;
            
            const badge = row.querySelector('.status-badge');
            if(badge){
                badge.textContent = j.status;
                badge.className = `badge status-badge bg-${j.status==='running'?'warning text-dark':j.status==='completed'?'success':'danger'}`;
                
                if(j.error_message){
                    badge.style.cursor = 'pointer';
                    badge.setAttribute('title', 'Нажмите для просмотра детали ошибки');
                    badge.onclick = () => showScanError(j.id, j.error_message);
                } else {
                    badge.style.cursor = 'default';
                    badge.removeAttribute('onclick');
                }
            }
            const bar = row.querySelector('.progress-bar');
            const txt = row.querySelector('.progress-text');
            if(bar) bar.style.width = `${j.progress}%`;
            if(txt) txt.textContent = `${j.progress}%`;
        });
    }catch(e){console.warn('History poll error:',e);}
}

export async function pollActiveScans() {
    try {
        const res = await fetch('/scans/api/scans/status');
        if (!res.ok) return;
        const data = await res.json();
        
        if (data.active && data.active.length > 0) {
            if (typeof updateScanHistory === 'function') {
                updateScanHistory();
            }
        }
    } catch (e) {
        console.warn('⚠️ Ошибка проверки сканирований:', e);
    }
}

// Экспорт глобальных функций
window.viewScanResults = viewScanResults;
window.showScanError = showScanError;