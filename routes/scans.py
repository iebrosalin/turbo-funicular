from flask import Blueprint, request, jsonify, render_template, current_app
from models import db, Asset, Group, ScanJob, ScanResult
from utils import create_asset_if_not_exists, update_asset_dns_names
import json
import os
import threading
import traceback
from datetime import datetime
from scanner import run_rustscan_scan, run_nmap_scan, run_nslookup_scan

scans_bp = Blueprint('scans', __name__)

# ────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ────────────────────────────────────────────────────────────────

def run_scan_wrapper(app, func, job_id, *args):
    """
    Обертка для безопасного запуска сканирования в потоке.
    app: объект приложения Flask
    func: функция сканирования (например, run_rustscan_scan)
    job_id: ID задачи
    *args: остальные аргументы для функции сканирования
    """
    try:
        with app.app_context():
            # ИСПРАВЛЕНИЕ: Передаем app первым аргументом, так как функции в scanner.py ожидают его там
            func(app, job_id, *args)
    except Exception as e:
        print(f"❌ Ошибка в потоке сканирования {job_id}: {e}")
        traceback.print_exc()
        
        try:
            with app.app_context():
                job = ScanJob.query.get(job_id)
                if job:
                    job.status = 'failed'
                    job.error_message = f"Exception in thread: {str(e)}\n{traceback.format_exc()}"
                    job.progress = 0
                    job.completed_at = datetime.utcnow()
                    db.session.commit()
        except Exception as db_err:
            print(f"❌ Ошибка обновления статуса задачи в БД: {db_err}")

# ────────────────────────────────────────────────────────────────
# СТРАНИЦЫ
# ────────────────────────────────────────────────────────────────

@scans_bp.route('/scans')
def scans_page():
    """Страница управления сканированиями"""
    jobs = ScanJob.query.order_by(ScanJob.created_at.desc()).limit(50).all()
    profiles = [] 
    all_groups = Group.query.all()
    return render_template('scans.html', scan_jobs=jobs, profiles=profiles, all_groups=all_groups)

# ────────────────────────────────────────────────────────────────
# API СКАНИРОВАНИЙ
# ────────────────────────────────────────────────────────────────

@scans_bp.route('/api/scans/status')
def get_active_scans_status():
    active_jobs = ScanJob.query.filter(
        ScanJob.status.in_(['pending', 'running', 'paused'])
    ).order_by(ScanJob.created_at.desc()).all()
    
    jobs_data = []
    for j in active_jobs:
        jobs_data.append({
            'id': j.id,
            'scan_type': j.scan_type,
            'target': j.target,
            'status': j.status,
            'progress': j.progress,
            'current_target': j.current_target,
            'created_at': j.created_at.strftime('%Y-%m-%d %H:%M:%S') if j.created_at else None
        })
    return jsonify({'active': jobs_data})

@scans_bp.route('/api/scans/history')
def get_scan_history():
    jobs = ScanJob.query.order_by(ScanJob.created_at.desc()).limit(50).all()
    history = []
    for j in jobs:
        history.append({
            'id': j.id,
            'scan_type': j.scan_type,
            'target': j.target,
            'status': j.status,
            'progress': j.progress,
            'error_message': j.error_message,
            'started_at': j.started_at.strftime('%Y-%m-%d %H:%M:%S') if j.started_at else None,
            'completed_at': j.completed_at.strftime('%Y-%m-%d %H:%M:%S') if j.completed_at else None
        })
    return jsonify(history)

@scans_bp.route('/api/scans/rustscan', methods=['POST'])
def start_rustscan():
    data = request.json
    target = data.get('target')
    ports = data.get('ports', '-')
    args = data.get('extra_args', '')
    use_known_ports = data.get('use_known_ports', False)
    
    if not target:
        return jsonify({'error': 'Не указана цель'}), 400
    
    # Если выбраны известные порты,目标 должен быть группой
    if use_known_ports and not target.startswith('group:'):
        return jsonify({'error': 'Опция "Известные порты" доступна только для групп активов'}), 400
        
    job = ScanJob(
        scan_type='rustscan',
        target=target,
        status='pending',
        progress=0,
        scan_parameters=json.dumps({'ports': ports, 'args': args, 'use_known_ports': use_known_ports})
    )
    db.session.add(job)
    db.session.commit()
    
    # Получаем текущее приложение и передаем в поток
    app = current_app._get_current_object()
    t = threading.Thread(
        target=run_scan_wrapper, 
        args=(app, run_rustscan_scan, job.id, target, ports, args, use_known_ports)
    )
    t.daemon = True
    t.start()
    
    return jsonify({'job_id': job.id, 'status': 'started', 'message': 'Сканирование запущено'})

@scans_bp.route('/api/scans/nmap', methods=['POST'])
def start_nmap():
    data = request.json
    target = data.get('target')
    ports = data.get('ports', '-')
    scripts = data.get('scripts', '')
    args = data.get('extra_args', '')
    use_known_ports = data.get('use_known_ports', False)
    
    if not target:
        return jsonify({'error': 'Не указана цель'}), 400
    
    # Если выбраны известные порты,目标 должен быть группой
    if use_known_ports and not target.startswith('group:'):
        return jsonify({'error': 'Опция "Известные порты" доступна только для групп активов'}), 400
        
    job = ScanJob(
        scan_type='nmap',
        target=target,
        status='pending',
        progress=0,
        scan_parameters=json.dumps({'ports': ports, 'scripts': scripts, 'args': args, 'use_known_ports': use_known_ports})
    )
    db.session.add(job)
    db.session.commit()
    
    app = current_app._get_current_object()
    t = threading.Thread(
        target=run_scan_wrapper, 
        args=(app, run_nmap_scan, job.id, target, ports, scripts, args, use_known_ports)
    )
    t.daemon = True
    t.start()
    
    return jsonify({'job_id': job.id, 'status': 'started', 'message': 'Сканирование запущено'})

@scans_bp.route('/api/scans/nslookup', methods=['POST'])
def start_nslookup():
    data = request.json
    targets = data.get('targets', '') 
    dns_server = data.get('dns_server', '77.88.8.8')
    args = data.get('nslookup_args', '')
    
    if not targets or not targets.strip():
        return jsonify({'error': 'Не указаны домены'}), 400
        
    params = {
        'targets': targets,
        'dns_server': dns_server,
        'args': args
    }
    
    job = ScanJob(
        scan_type='nslookup',
        target=f"NSLookup ({len(targets.splitlines())} domains)",
        status='pending',
        progress=0,
        scan_parameters=json.dumps(params)
    )
    db.session.add(job)
    db.session.commit()
    
    app = current_app._get_current_object()
    t = threading.Thread(
        target=run_scan_wrapper, 
        args=(app, run_nslookup_scan, job.id, targets, dns_server, args)
    )
    t.daemon = True
    t.start()
    
    return jsonify({'job_id': job.id, 'status': 'started', 'message': 'Сканирование запущено'})

@scans_bp.route('/api/scans/<int:job_id>/results')
def get_scan_results(job_id):
    job = ScanJob.query.get_or_404(job_id)
    results = []
    
    if job.scan_type == 'nslookup' and job.nslookup_output:
        lines = job.nslookup_output.split('\n')
        current_ip = None
        current_domain = None
        for line in lines:
            line = line.strip()
            if line.startswith('Name:'):
                current_domain = line.split(':', 1)[1].strip()
            elif line.startswith('Address:') and '#' not in line:
                 current_ip = line.split(':', 1)[1].strip()
                 if current_domain and current_ip:
                     results.append({'domain': current_domain, 'ip': current_ip})
                     try:
                         asset = create_asset_if_not_exists(current_ip, hostname=current_domain)
                         update_asset_dns_names(asset, current_domain)
                     except Exception as e:
                         print(f"Error creating asset: {e}")
                     current_domain = None
    
    return jsonify({
        'job': {
            'id': job.id,
            'scan_type': job.scan_type,
            'target': job.target,
            'status': job.status,
            'progress': job.progress,
            'error_message': job.error_message,
            'started_at': job.started_at.strftime('%Y-%m-%d %H:%M:%S') if job.started_at else None,
            'completed_at': job.completed_at.strftime('%Y-%m-%d %H:%M:%S') if job.completed_at else None,
            'nslookup_output': job.nslookup_output if job.scan_type == 'nslookup' else None
        },
        'results': results
    })

@scans_bp.route('/api/scans/<int:job_id>', methods=['DELETE'])
def delete_scan_job(job_id):
    job = ScanJob.query.get_or_404(job_id)
    if job.status == 'running':
        job.status = 'failed'
        job.error_message = 'Удалено пользователем во время выполнения'
        job.completed_at = datetime.utcnow()
        db.session.commit()
    
    db.session.delete(job)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Задача удалена'})

@scans_bp.route('/api/scans/<int:job_id>/control', methods=['POST'])
def control_scan(job_id):
    job = ScanJob.query.get_or_404(job_id)
    data = request.json
    action = data.get('action')
    
    if action == 'delete':
        db.session.delete(job)
        db.session.commit()
        return jsonify({'success': True})
        
    elif action == 'stop':
        if job.status == 'running':
            job.status = 'failed'
            job.error_message = 'Остановлено пользователем'
            job.completed_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True})
            
    elif action == 'pause':
        if job.status == 'running':
            job.status = 'paused'
            db.session.commit()
            return jsonify({'success': True})
            
    elif action == 'resume':
        if job.status == 'paused':
            job.status = 'running'
            db.session.commit()
            return jsonify({'success': True})
            
    elif action == 'rerun':
        if not job.scan_parameters:
            return jsonify({'error': 'Нет параметров для повтора'}), 400
            
        params = json.loads(job.scan_parameters)
        new_job = ScanJob(
            scan_type=job.scan_type,
            target=job.target,
            status='pending',
            progress=0,
            scan_parameters=job.scan_parameters
        )
        db.session.add(new_job)
        db.session.commit()
        
        app = current_app._get_current_object()
        
        use_known_ports = params.get('use_known_ports', False)
        
        if job.scan_type == 'rustscan':
            t = threading.Thread(target=run_scan_wrapper, args=(app, run_rustscan_scan, new_job.id, job.target, params.get('ports', '-'), params.get('args', ''), use_known_ports))
        elif job.scan_type == 'nmap':
            t = threading.Thread(target=run_scan_wrapper, args=(app, run_nmap_scan, new_job.id, job.target, params.get('ports', '-'), params.get('scripts', ''), params.get('args', ''), use_known_ports))
        elif job.scan_type == 'nslookup':
            t = threading.Thread(target=run_scan_wrapper, args=(app, run_nslookup_scan, new_job.id, params.get('targets', ''), params.get('dns_server', '77.88.8.8'), params.get('args', '')))
        else:
            return jsonify({'error': 'Неизвестный тип'}), 400
            
        t.daemon = True
        t.start()
        return jsonify({'success': True, 'new_id': new_job.id})
    
    return jsonify({'error': 'Недопустимое действие'}), 400