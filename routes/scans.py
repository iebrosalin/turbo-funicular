# routes/scans.py
"""
Маршруты для управления сканированиями (Nmap, Rustscan, Dig/Nslookup)
Поддержка очередей, статусов, остановки и скачивания результатов
"""
from flask import Blueprint, request, jsonify, send_file, render_template, abort
from datetime import datetime
import os
import io
import zipfile
from extensions import db
from models import ScanJob, Asset, ServiceInventory, ScanResult, ActivityLog
from utils.scan_queue import scan_queue_manager, utility_scan_queue_manager
from utils import MOSCOW_TZ, parse_nmap_xml, create_asset_if_not_exists, log_asset_change
import re

# Префикс_blueprint'а: /scans
# Итоговые пути будут начинаться с /scans/...
scans_bp = Blueprint('scans', __name__, url_prefix='/scans')
# --- Страницы интерфейса ---

@scans_bp.route('/')
def scans_page():
    """Страница управления сканированиями"""
    return render_template('scans.html')

# --- API: Запуск сканирований ---

@scans_bp.route('/api/scans/nmap', methods=['POST'])
def start_nmap_scan():
    """Запуск сканирования Nmap (добавление в очередь)"""
    data = request.get_json()
    
    target = data.get('target', '').strip()
    ports = data.get('ports', '').strip()
    scripts = data.get('scripts', '').strip()
    custom_args = data.get('custom_args', '').strip()
    known_ports_only = data.get('known_ports_only', False)
    group_ids = data.get('group_ids', [])
    
    if not target and not (known_ports_only and group_ids):
        return jsonify({'error': 'Необходимо указать цель или выбрать группы для сканирования известных портов'}), 400
    
    # Валидация: если known_ports_only=True, порты в явном виде запрещены
    if known_ports_only and ports:
        return jsonify({'error': 'При выборе опции "Только известные порты" явное указание портов запрещено'}), 400
        
    # Валидация кастомных аргументов на наличие портов
    if known_ports_only and custom_args:
        port_args = ['-p', '--port', '--ports']
        for arg in port_args:
            if arg in custom_args.split():
                return jsonify({'error': f'Передача аргумента портов ({arg}) запрещена при сканировании известных портов'}), 400

    # Создание записи задания
    new_job = ScanJob(
        scan_type='nmap',
        target=target or 'Группы: ' + ', '.join(map(str, group_ids)),
        status='pending',
        created_at=datetime.now(MOSCOW_TZ),
        parameters={
            'ports': ports,
            'scripts': scripts,
            'custom_args': custom_args,
            'known_ports_only': known_ports_only,
            'group_ids': group_ids
        }
    )
    
    db.session.add(new_job)
    db.session.commit()
    
    # Добавление в очередь nmap/rustscan
    job_id = scan_queue_manager.add_to_queue(
        job_id=new_job.id,
        scan_type='nmap',
        target=target,
        ports=ports,
        scripts=scripts,
        custom_args=custom_args,
        known_ports_only=known_ports_only,
        group_ids=group_ids if group_ids else None
    )
    
    return jsonify({
        'message': 'Задача Nmap добавлена в очередь',
        'job_id': job_id,
        'status': 'pending'
    }), 202

@scans_bp.route('/api/scans/rustscan', methods=['POST'])
def start_rustscan_scan():
    """Запуск сканирования Rustscan (добавление в очередь)"""
    data = request.get_json()
    
    target = data.get('target', '').strip()
    ports = data.get('ports', '').strip()
    custom_args = data.get('custom_args', '').strip()
    run_nmap_after = data.get('run_nmap_after', False)
    nmap_args = data.get('nmap_args', '').strip()
    
    if not target:
        return jsonify({'error': 'Цель сканирования обязательна'}), 400
    
    # Создание записи задания
    new_job = ScanJob(
        scan_type='rustscan',
        target=target,
        status='pending',
        created_at=datetime.now(MOSCOW_TZ),
        parameters={
            'ports': ports,
            'custom_args': custom_args,
            'run_nmap_after': run_nmap_after,
            'nmap_args': nmap_args
        }
    )
    
    db.session.add(new_job)
    db.session.commit()
    
    # Добавление в очередь nmap/rustscan
    job_id = scan_queue_manager.add_to_queue(
        job_id=new_job.id,
        scan_type='rustscan',
        target=target,
        ports=ports,
        custom_args=custom_args,
        run_nmap_after=run_nmap_after,
        nmap_args=nmap_args
    )
    
    return jsonify({
        'message': 'Задача Rustscan добавлена в очередь',
        'job_id': job_id,
        'status': 'pending'
    }), 202

@scans_bp.route('/api/scans/nslookup', methods=['POST'])
@scans_bp.route('/api/scans/dig', methods=['POST'])
def start_dig_scan():
    """Запуск сканирования Dig (бывший Nslookup) (добавление в очередь утилит)"""
    data = request.get_json()
    
    targets_text = data.get('targets_text', '').strip()
    dns_server = data.get('dns_server', '77.88.8.8').strip()
    cli_args = data.get('cli_args', '').strip()
    record_types = data.get('record_types') # Может быть списком или None
    
    if not targets_text:
        return jsonify({'error': 'Список целей обязателен'}), 400
    
    # Создание записи задания
    scan_type = 'dig' 
    
    new_job = ScanJob(
        scan_type=scan_type,
        target=targets_text.split()[0] if targets_text else 'Bulk DNS',
        status='pending',
        created_at=datetime.now(MOSCOW_TZ),
        parameters={
            'targets_text': targets_text,
            'dns_server': dns_server,
            'cli_args': cli_args,
            'record_types': record_types
        }
    )
    
    db.session.add(new_job)
    db.session.commit()
    
    # Добавление в очередь утилит
    job_id = utility_scan_queue_manager.add_to_queue(
        job_id=new_job.id,
        scan_type='dig',
        target=targets_text,
        targets_text=targets_text,
        dns_server=dns_server,
        cli_args=cli_args,
        record_types=record_types
    )
    
    return jsonify({
        'message': 'Задача DNS (Dig) добавлена в очередь',
        'job_id': job_id,
        'status': 'pending'
    }), 202

# --- API: Статус и управление ---

@scans_bp.route('/api/scans/status')
def get_scan_status():
    """Получение статуса всех очередей и последних заданий"""
    try:
        # Статус очередей
        nmap_queue_status = scan_queue_manager.get_queue_status()
        utility_queue_status = utility_scan_queue_manager.get_queue_status()

        # Последние 50 заданий
        recent_jobs = ScanJob.query.order_by(ScanJob.created_at.desc()).limit(50).all()
        jobs_data = []
        for job in recent_jobs:
            jobs_data.append({
                'id': job.id,
                'scan_type': job.scan_type,
                'target': job.target,
                'status': job.status,
                'progress': job.progress,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'error_message': job.error_message
            })

        return jsonify({
            'queues': {
                'nmap_rustscan': nmap_queue_status,
                'utilities': utility_queue_status
            },
            'recent_jobs': jobs_data
        })
    except Exception as e:
        return jsonify({'error': str(e), 'detail': 'Failed to retrieve scan status'}), 500

@scans_bp.route('/api/scan-job/<int:job_id>')
def get_job_details(job_id):
    """Детальная информация о задании"""
    job = ScanJob.query.get_or_404(job_id)
    
    # Попытка найти связанные результаты сканирования
    results = ScanResult.query.filter_by(job_id=job_id).all()
    results_data = []
    for res in results:
        results_data.append({
            'id': res.id,
            'asset_ip': res.asset_ip,
            'hostname': res.hostname,
            'os_match': res.os_match,
            'ports_count': len(res.ports) if res.ports else 0,
            'has_xml': bool(res.raw_output)
        })

    return jsonify({
        'id': job.id,
        'scan_type': job.scan_type,
        'target': job.target,
        'status': job.status,
        'progress': job.progress,
        'parameters': job.parameters,
        'output_file': job.output_file,
        'error_message': job.error_message,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'scan_results_summary': results_data
    })

@scans_bp.route('/api/scan-queue/<int:job_id>', methods=['DELETE'])
def remove_from_queue(job_id):
    """Удаление задачи из очереди (если она еще не запущена)"""
    job = ScanJob.query.get_or_404(job_id)
    
    if job.status not in ['pending', 'queued']:
        return jsonify({'error': 'Можно удалить только задачи со статусом pending/queued'}), 400
    
    removed = False
    # Пробуем удалить из очереди nmap/rustscan
    if scan_queue_manager.remove_from_queue(job_id):
        removed = True
    # Пробуем удалить из очереди утилит
    elif utility_scan_queue_manager.remove_from_queue(job_id):
        removed = True
        
    if removed:
        job.status = 'cancelled'
        job.completed_at = datetime.now(MOSCOW_TZ)
        db.session.commit()
        return jsonify({'message': f'Задача #{job_id} удалена из очереди'}), 200
    else:
        job.status = 'cancelled'
        job.completed_at = datetime.now(MOSCOW_TZ)
        db.session.commit()
        return jsonify({'message': f'Задача #{job_id} помечена как отмененная (не найдена в активных очередях)'}), 200

@scans_bp.route('/api/scan-job/<int:job_id>/stop', methods=['POST'])
def stop_job(job_id):
    """Остановка выполняющегося задания (флажок в БД)"""
    job = ScanJob.query.get_or_404(job_id)
    
    if job.status != 'running':
        return jsonify({'error': 'Задание не выполняется'}), 400
    
    job.status = 'stopping'
    db.session.commit()
    
    return jsonify({'message': f'Отправлен сигнал остановки для задачи #{job_id}'}), 200
@scans_bp.route('/api/scan-job/<int:job_id>/retry', methods=['POST'])
def retry_job(job_id):
    """Повторное выполнение завершенного или неудачного задания с теми же параметрами"""
    job = ScanJob.query.get_or_404(job_id)

    # Разрешаем повтор только для завершенных или неудачных задач
    if job.status not in ['completed', 'failed', 'stopped', 'cancelled']:
        return jsonify({'error': 'Можно повторить только завершенные, неудачные или остановленные задачи'}), 400

    # Создаем новую запись задания с теми же параметрами
    new_job = ScanJob(
        scan_type=job.scan_type,
        target=job.target,
        status='pending',
        created_at=datetime.now(MOSCOW_TZ),
        parameters=job.parameters,
        progress=0
    )

    db.session.add(new_job)
    db.session.commit()

    # Добавляем в соответствующую очередь
    params = job.parameters or {}

    if job.scan_type in ['nmap', 'rustscan']:
        new_job_id = scan_queue_manager.add_to_queue(
            job_id=new_job.id,
            scan_type=job.scan_type,
            target=job.target,
            ports=params.get('ports', ''),
            scripts=params.get('scripts', ''),
            custom_args=params.get('custom_args', ''),
            run_nmap_after=params.get('run_nmap_after', False),
            nmap_args=params.get('nmap_args', ''),
            known_ports_only=params.get('known_ports_only', False),
            group_ids=params.get('group_ids')
        )
    elif job.scan_type in ['dig', 'nslookup']:
        new_job_id = utility_scan_queue_manager.add_to_queue(
            job_id=new_job.id,
            scan_type=job.scan_type,
            target=job.target,
            targets_text=params.get('targets_text', ''),
            dns_server=params.get('dns_server', '77.88.8.8'),
            cli_args=params.get('cli_args', ''),
            record_types=params.get('record_types')
        )
    else:
        db.session.delete(new_job)
        db.session.commit()
        return jsonify({'error': f'Неподдерживаемый тип сканирования: {job.scan_type}'}), 400

    return jsonify({
        'message': f'Задача #{job_id} добавлена на повторение как задача #{new_job_id}',
        'new_job_id': new_job_id,
        'status': 'pending'
    }), 202

# --- API: Скачивание результатов ---

@scans_bp.route('/api/scan-job/<int:job_id>/download/<format_type>')
def download_scan_result(job_id, format_type):
    """Скачивание результатов сканирования в различных форматах"""
    job = ScanJob.query.get_or_404(job_id)
    
    if job.status != 'completed':
        return jsonify({'error': 'Результаты доступны только для завершенных задач'}), 400
    
    base_dir = os.path.join(os.getcwd(), 'scanner_output', str(job_id))
    
    if not os.path.exists(base_dir):
        return jsonify({'error': 'Файлы результатов не найдены на диске'}), 404
    
    filename = None
    content_type = 'application/octet-stream'
    
    if job.scan_type == 'nmap':
        if format_type == 'xml':
            filename = 'nmap.xml'
            content_type = 'application/xml'
        elif format_type == 'gnmap':
            filename = 'nmap.gnmap'
            content_type = 'text/plain'
        elif format_type == 'normal':
            filename = 'nmap.nmap'
            content_type = 'text/plain'
        elif format_type == 'all':
            return _download_zip(job_id, base_dir, ['nmap.xml', 'nmap.gnmap', 'nmap.nmap'])
            
    elif job.scan_type == 'rustscan':
        if format_type in ['raw', 'txt']:
            if job.output_file and os.path.exists(job.output_file):
                 return send_file(job.output_file, as_attachment=True, download_name=f'rustscan_{job_id}.txt')
            for f in os.listdir(base_dir):
                if f.endswith('.txt') or 'rustscan' in f.lower():
                    filename = f
                    break
            if not filename:
                 return jsonify({'error': 'Файл вывода Rustscan не найден'}), 404
            content_type = 'text/plain'
        elif format_type == 'all':
            files = [f for f in os.listdir(base_dir) if f.endswith('.txt') or 'rustscan' in f.lower()]
            if not files:
                return jsonify({'error': 'Файлы не найдены'}), 404
            return _download_zip(job_id, base_dir, files)

    elif job.scan_type in ['dig', 'nslookup']:
        if format_type in ['raw', 'txt']:
            if job.output_file and os.path.exists(job.output_file):
                return send_file(job.output_file, as_attachment=True, download_name=f'dig_{job_id}.txt')
            
            for f in os.listdir(base_dir):
                if f.endswith('.txt') or 'dig' in f.lower() or 'dns' in f.lower():
                    filename = f
                    break
            if not filename:
                return jsonify({'error': 'Вывод Dig не найден'}), 404
            content_type = 'text/plain'
        elif format_type == 'all':
            files = [f for f in os.listdir(base_dir) if f.endswith('.txt')]
            if not files:
                return jsonify({'error': 'Файлы не найдены'}), 404
            return _download_zip(job_id, base_dir, files)
    
    else:
        return jsonify({'error': f'Неподдерживаемый тип сканирования: {job.scan_type}'}), 400

    if not filename:
        return jsonify({'error': f'Формат {format_type} не найден для типа {job.scan_type}'}), 404
    
    file_path = os.path.join(base_dir, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'Файл не найден на диске'}), 404
    
    return send_file(file_path, as_attachment=True, download_name=filename, mimetype=content_type)

def _download_zip(job_id, base_dir, filenames):
    """Создание ZIP архива с файлами"""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in filenames:
            fpath = os.path.join(base_dir, fname)
            if os.path.exists(fpath):
                zf.write(fpath, fname)
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'scan_{job_id}_results.zip'
    )

# --- API: Удаление истории ---

@scans_bp.route('/api/scan-job/<int:job_id>', methods=['DELETE'])
def delete_job(job_id):
    """Удаление записи о задании и связанных файлов"""
    job = ScanJob.query.get_or_404(job_id)
    
    # Удаление файлов
    if job.output_file and os.path.exists(job.output_file):
        try:
            os.remove(job.output_file)
        except Exception:
            pass
            
    # Удаление папки результатов
    base_dir = os.path.join(os.getcwd(), 'scanner_output', str(job_id))
    if os.path.exists(base_dir):
        try:
            import shutil
            shutil.rmtree(base_dir)
        except Exception:
            pass
            
    db.session.delete(job)
    db.session.commit()
    
    return jsonify({'message': f'Задание #{job_id} и файлы удалены'}), 200


# --- API: Импорт XML Nmap ---

@scans_bp.route('/api/scans/import-xml', methods=['POST'])
def import_nmap_xml():
    """Импорт результатов сканирования Nmap из XML файла"""
    from utils.nmap_xml_importer import NmapXmlImporter

    if 'xml_file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    file = request.files['xml_file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    if not file.filename.endswith('.xml'):
        return jsonify({'error': 'Файл должен быть в формате XML'}), 400

    group_id = request.form.get('group_id')
    if group_id:
        try:
            group_id = int(group_id)
        except ValueError:
            group_id = None

    # Сохранение временного файла
    import tempfile
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f'nmap_import_{datetime.now(MOSCOW_TZ).strftime("%Y%m%d_%H%M%S")}.xml')

    try:
        file.save(temp_path)

        # Создание записи задания для импорта
        new_job = ScanJob(
            scan_type='nmap_import',
            target=f'Import: {file.filename}',
            status='running',
            progress=0,
            created_at=datetime.now(MOSCOW_TZ),
            parameters={
                'original_filename': file.filename,
                'group_id': group_id
            }
        )
        db.session.add(new_job)
        db.session.flush()
        job_id = new_job.id

        # Импорт
        importer = NmapXmlImporter(scans_bp.app)
        result = importer.import_file(temp_path, job_id=job_id, group_id=group_id)

        # Удаление временного файла
        os.remove(temp_path)

        return jsonify({
            'message': 'Импорт завершен успешно',
            'hosts_added': result['hosts_added'],
            'hosts_updated': result['hosts_updated'],
            'services_added': result['services_added'],
            'services_updated': result['services_updated'],
            'errors': result['errors']
        }), 200

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # Удаление временного файла при ошибке
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': f'Ошибка импорта: {str(e)}'}), 500