from flask import Blueprint, request, jsonify, render_template, current_app
from models import db, Asset, Group, ScanJob, ScanResult
from utils import create_asset_if_not_exists, update_asset_dns_names
from utils.scan_queue import scan_queue_manager, utility_scan_queue_manager
import json
import os
import threading
import traceback
from datetime import datetime
from scanner import NmapScanner, RustscanScanner, DigScanner

scans_bp = Blueprint('scans', __name__)

# ────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ────────────────────────────────────────────────────────────────

def init_scan_queue(app):
    """Инициализация менеджеров очередей сканирований"""
    scan_queue_manager.start_worker(app)
    utility_scan_queue_manager.start_worker(app)

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
    
    # Добавляем информацию об очередях
    nmap_queue_status = scan_queue_manager.get_queue_status()
    utility_queue_status = utility_scan_queue_manager.get_queue_status()
    
    return jsonify({
        'active': jobs_data, 
        'nmap_queue': nmap_queue_status,
        'utility_queue': utility_queue_status
    })

@scans_bp.route('/api/scan-queue/status')
def get_queue_status():
    """Получение статуса очередей сканирований"""
    return jsonify({
        'nmap_queue': scan_queue_manager.get_queue_status(),
        'utility_queue': utility_scan_queue_manager.get_queue_status()
    })

@scans_bp.route('/api/scan-queue/<int:job_id>', methods=['DELETE'])
def remove_from_queue(job_id):
    """Удаление задачи из очереди nmap/rustscan"""
    if scan_queue_manager.remove_from_queue(job_id):
        job = ScanJob.query.get(job_id)
        if job and job.status == 'pending':
            job.status = 'cancelled'
            db.session.commit()
        return jsonify({'success': True, 'message': 'Задача удалена из очереди nmap/rustscan'})
    
    # Пробуем удалить из очереди утилит
    if utility_scan_queue_manager.remove_from_queue(job_id):
        job = ScanJob.query.get(job_id)
        if job and job.status == 'pending':
            job.status = 'cancelled'
            db.session.commit()
        return jsonify({'success': True, 'message': 'Задача удалена из очереди утилит'})
    
    return jsonify({'error': 'Задача не найдена в очередях'}), 404

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
    run_nmap_after = data.get('run_nmap_after', False)
    nmap_args = data.get('nmap_args', '')
    
    if not target:
        return jsonify({'error': 'Не указана цель'}), 400
        
    job = ScanJob(
        scan_type='rustscan',
        target=target,
        status='pending',
        progress=0,
        scan_parameters=json.dumps({'ports': ports, 'args': args, 'run_nmap_after': run_nmap_after, 'nmap_args': nmap_args})
    )
    db.session.add(job)
    db.session.commit()
    
    # Добавляем задачу в очередь вместо прямого запуска в потоке
    app = current_app._get_current_object()
    scan_queue_manager.add_to_queue(
        job.id, 
        'rustscan', 
        target, 
        ports=ports, 
        custom_args=args,
        run_nmap_after=run_nmap_after,
        nmap_args=nmap_args
    )
    
    return jsonify({'job_id': job.id, 'status': 'queued', 'message': 'Сканирование добавлено в очередь'})

@scans_bp.route('/api/scans/nmap', methods=['POST'])
def start_nmap():
    data = request.json
    target = data.get('target')
    ports = data.get('ports', '-')
    scripts = data.get('scripts', '')
    args = data.get('extra_args', '')
    known_ports_only = data.get('known_ports_only', False)
    group_ids = data.get('group_ids', [])
    
    # Если выбран режим "только известные порты", игнорируем ручной ввод портов
    if known_ports_only:
        ports = '-'  # Будут использованы порты из активов
    
    # Проверка: если known_ports_only=True, запрещаем передачу портов в custom_args
    if known_ports_only and args:
        import re
        if '-p' in args or '--port' in args:
            return jsonify({'error': '⚠️ В режиме "Только известные порты" нельзя указывать порты в дополнительных аргументах'}), 400
    
    if not target and not (known_ports_only and group_ids):
        return jsonify({'error': 'Не указана цель'}), 400
        
    job = ScanJob(
        scan_type='nmap',
        target=target if target else f"Группы: {', '.join(map(str, group_ids))}",
        status='pending',
        progress=0,
        scan_parameters=json.dumps({
            'ports': ports, 
            'scripts': scripts, 
            'args': args,
            'known_ports_only': known_ports_only,
            'group_ids': group_ids
        })
    )
    db.session.add(job)
    db.session.commit()
    
    # Добавляем задачу в очередь вместо прямого запуска в потоке
    app = current_app._get_current_object()
    scan_queue_manager.add_to_queue(
        job.id, 
        'nmap', 
        target if target else '',
        ports=ports, 
        scripts=scripts,
        custom_args=args,
        known_ports_only=known_ports_only,
        group_ids=group_ids if known_ports_only else None
    )
    
    return jsonify({'job_id': job.id, 'status': 'queued', 'message': 'Сканирование добавлено в очередь'})

@scans_bp.route('/api/scans/nslookup', methods=['POST'])
def start_nslookup():
    """Запуск сканирования dig (для обратной совместимости endpoint называется nslookup)"""
    data = request.json
    targets = data.get('targets', '') 
    dns_server = data.get('dns_server', '77.88.8.8')
    args = data.get('nslookup_args', '')
    record_types = data.get('record_types', ['A', 'AAAA', 'MX', 'TXT', 'NS', 'CNAME', 'SOA', 'PTR', 'SRV'])
    
    if not targets or not targets.strip():
        return jsonify({'error': 'Не указаны домены'}), 400
        
    params = {
        'targets': targets,
        'dns_server': dns_server,
        'args': args,
        'record_types': record_types
    }
    
    job = ScanJob(
        scan_type='dig',  # Теперь используем dig
        target=f"DIG ({len(targets.splitlines())} domains)",
        status='pending',
        progress=0,
        scan_parameters=json.dumps(params)
    )
    db.session.add(job)
    db.session.commit()
    
    # Добавляем задачу в очередь утилит
    app = current_app._get_current_object()
    utility_scan_queue_manager.add_to_queue(
        job.id, 
        'dig',  # Используем dig вместо nslookup
        f"DIG ({len(targets.splitlines())} domains)",
        targets_text=targets,
        dns_server=dns_server,
        cli_args=args,
        record_types=record_types
    )
    
    return jsonify({'job_id': job.id, 'status': 'queued', 'message': 'Сканирование DNS добавлено в очередь утилит'})

@scans_bp.route('/api/scans/<int:job_id>/results')
def get_scan_results(job_id):
    job = ScanJob.query.get_or_404(job_id)
    results = []
    
    # Поддержка как 'dig', так и 'nslookup' для обратной совместимости
    if job.scan_type in ['dig', 'nslookup'] and job.nslookup_output:
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
    
    # Собираем информацию о доступных файлах для скачивания
    download_files = []
    if job.scan_type == 'rustscan':
        if job.rustscan_text_path:
            download_files.append({'type': 'text', 'name': 'RustScan Results (TXT)', 'path': job.rustscan_text_path})
        if job.rustscan_output:
            download_files.append({'type': 'raw', 'name': 'RustScan Output (Raw)', 'format': 'text/plain'})
    elif job.scan_type == 'nmap':
        if job.nmap_xml_path:
            download_files.append({'type': 'file', 'name': 'Nmap XML', 'path': job.nmap_xml_path, 'format': 'application/xml'})
        if job.nmap_grep_path:
            download_files.append({'type': 'file', 'name': 'Nmap Grepable', 'path': job.nmap_grep_path, 'format': 'text/plain'})
        if job.nmap_normal_path:
            download_files.append({'type': 'file', 'name': 'Nmap Normal', 'path': job.nmap_normal_path, 'format': 'text/plain'})
        if job.nmap_xml_content:
            download_files.append({'type': 'raw', 'name': 'Nmap XML (Raw)', 'format': 'application/xml'})
    elif job.scan_type in ['dig', 'nslookup']:
        if job.nslookup_output:
            download_files.append({'type': 'raw', 'name': 'DIG Output (Raw)', 'format': 'text/plain'})
        if job.nslookup_file_path:
            download_files.append({'type': 'file', 'name': 'DIG Results (File)', 'path': job.nslookup_file_path, 'format': 'text/plain'})
    
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
            'nslookup_output': job.nslookup_output if job.scan_type in ['dig', 'nslookup'] else None
        },
        'results': results,
        'download_files': download_files
    })

@scans_bp.route('/api/scans/<int:job_id>/download/<file_type>')
def download_scan_file(job_id, file_type):
    """Скачивание результатов сканирования"""
    from flask import send_file, abort
    import os
    
    job = ScanJob.query.get_or_404(job_id)
    
    file_path = None
    mime_type = 'text/plain'
    
    if file_type == 'rustscan_txt':
        file_path = job.rustscan_text_path
    elif file_type == 'rustscan_raw':
        # Возвращаем raw вывод как файл
        from io import BytesIO
        if job.rustscan_output:
            buf = BytesIO(job.rustscan_output.encode('utf-8'))
            filename = f"rustscan_job_{job_id}.txt"
            return send_file(buf, mimetype='text/plain', as_attachment=True, download_name=filename)
    elif file_type == 'nmap_xml':
        file_path = job.nmap_xml_path
        mime_type = 'application/xml'
    elif file_type == 'nmap_grep':
        file_path = job.nmap_grep_path
    elif file_type == 'nmap_normal':
        file_path = job.nmap_normal_path
    elif file_type == 'nmap_xml_raw':
        # Возвращаем raw XML контент как файл
        from io import BytesIO
        if job.nmap_xml_content:
            buf = BytesIO(job.nmap_xml_content.encode('utf-8'))
            filename = f"nmap_job_{job_id}.xml"
            return send_file(buf, mimetype='application/xml', as_attachment=True, download_name=filename)
    elif file_type == 'nslookup_raw' or file_type == 'dig_raw':
        # Возвращаем raw вывод dig/nslookup как файл
        from io import BytesIO
        if job.nslookup_output:
            buf = BytesIO(job.nslookup_output.encode('utf-8'))
            filename = f"dig_job_{job_id}.txt"
            return send_file(buf, mimetype='text/plain', as_attachment=True, download_name=filename)
    elif file_type == 'nslookup_file' or file_type == 'dig_file':
        file_path = job.nslookup_file_path
    
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'Файл не найден'}), 404
    
    filename = os.path.basename(file_path)
    return send_file(file_path, mimetype=mime_type, as_attachment=True, download_name=filename)


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
        # Удаляем из очереди если там есть
        scan_queue_manager.remove_from_queue(job_id)
        db.session.delete(job)
        db.session.commit()
        return jsonify({'success': True})
        
    elif action == 'stop':
        if job.status in ['running', 'pending']:
            scan_queue_manager.remove_from_queue(job_id)
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
        
        # Добавляем в соответствующую очередь вместо прямого запуска
        if job.scan_type == 'rustscan':
            scan_queue_manager.add_to_queue(
                new_job.id, 
                'rustscan', 
                job.target, 
                ports=params.get('ports', '-'), 
                custom_args=params.get('args', ''),
                run_nmap_after=params.get('run_nmap_after', False),
                nmap_args=params.get('nmap_args', '')
            )
        elif job.scan_type == 'nmap':
            scan_queue_manager.add_to_queue(
                new_job.id, 
                'nmap', 
                job.target, 
                ports=params.get('ports', '-'), 
                scripts=params.get('scripts', ''),
                custom_args=params.get('args', '')
            )
        elif job.scan_type in ['dig', 'nslookup']:
            utility_scan_queue_manager.add_to_queue(
                new_job.id,
                'dig',
                job.target,
                targets_text=params.get('targets', ''),
                dns_server=params.get('dns_server', '77.88.8.8'),
                cli_args=params.get('args', ''),
                record_types=params.get('record_types', ['A', 'AAAA', 'MX', 'TXT', 'NS', 'CNAME', 'SOA', 'PTR', 'SRV'])
            )
        else:
            return jsonify({'error': 'Неизвестный тип'}), 400
            
        return jsonify({'success': True, 'new_id': new_job.id})
    
    return jsonify({'error': 'Недопустимое действие'}), 400