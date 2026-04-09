# routes/scans.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, send_file
from extensions import db
from models import Group, Asset, ScanJob
from utils import build_group_tree
from scanner import run_rustscan_scan, run_nmap_scan
from datetime import datetime
import os
import threading
import json

# 🔥 Явное определение Blueprint 🔥
scans_bp = Blueprint('scans', __name__)

@scans_bp.route('/scans')
def scans_page():
    all_groups = Group.query.all()
    group_tree = build_group_tree(all_groups)
    scan_jobs = ScanJob.query.order_by(ScanJob.created_at.desc()).limit(50).all()
    return render_template('scans.html', scan_jobs=scan_jobs, group_tree=group_tree, all_groups=all_groups)

def get_assets_for_group(group_id):
    if group_id == 'ungrouped':
        return Asset.query.filter(Asset.group_id.is_(None)).all(), "Без группы"
    
    group = Group.query.get(group_id)
    if not group:
        return None, None
    
    def get_child_group_ids(parent_id, all_groups, result=[]):
        children = [g for g in all_groups if g.parent_id == parent_id]
        for child in children:
            result.append(child.id)
            get_child_group_ids(child.id, all_groups, result)
        return result
    
    all_groups = Group.query.all()
    group_ids = [group_id] + get_child_group_ids(group_id, all_groups)
    return Asset.query.filter(Asset.group_id.in_(group_ids)).all(), group.name

@scans_bp.route('/api/scans/rustscan', methods=['POST'])
def start_rustscan():
    data = request.json
    target = data.get('target', '')
    group_id = data.get('group_id')
    custom_args = data.get('custom_args', '')
    
    if group_id:
        assets, group_name = get_assets_for_group(group_id)
        if not assets:
            return jsonify({'error': 'В группе нет активов'}), 400
        target = ' '.join([a.ip_address for a in assets])
        target_description = f"Группа: {group_name} ({len(assets)} активов)"
    else:
        if not target:
            return jsonify({'error': 'Цель сканирования не указана'}), 400
        target_description = target
        
    scan_job = ScanJob(scan_type='rustscan', target=target_description, status='pending', rustscan_output=custom_args if custom_args else None)
    db.session.add(scan_job)
    db.session.commit()
    
    thread = threading.Thread(target=run_rustscan_scan, args=(scan_job.id, target, custom_args))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'job_id': scan_job.id, 'message': f'Rustscan запущен для {target_description}'})

@scans_bp.route('/api/scans/nmap', methods=['POST'])
def start_nmap():
    data = request.json
    target = data.get('target', '')
    group_id = data.get('group_id')
    ports = data.get('ports', '')
    custom_args = data.get('custom_args', '')
    
    if group_id:
        assets, group_name = get_assets_for_group(group_id)
        if not assets:
            return jsonify({'error': 'В группе нет активов'}), 400
        target = ' '.join([a.ip_address for a in assets])
        target_description = f"Группа: {group_name} ({len(assets)} активов)"
    else:
        if not target:
            return jsonify({'error': 'Цель сканирования не указана'}), 400
        target_description = target
        
    scan_job = ScanJob(scan_type='nmap', target=target_description, status='pending', rustscan_output=f'Ports: {ports}' if ports else None)
    if custom_args:
        scan_job.error_message = f'Custom args: {custom_args}'
        
    db.session.add(scan_job)
    db.session.commit()
    
    thread = threading.Thread(target=run_nmap_scan, args=(scan_job.id, target, ports, custom_args))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'job_id': scan_job.id, 'message': f'Nmap запущен для {target_description}'})

@scans_bp.route('/api/scans/<int:job_id>')
def get_scan_status(job_id):
    scan_job = ScanJob.query.get_or_404(job_id)
    return jsonify(scan_job.to_dict())

@scans_bp.route('/api/scans/<int:job_id>/results')
def get_scan_results(job_id):
    scan_job = ScanJob.query.get_or_404(job_id)
    results = []
    for r in scan_job.results:
        results.append({
            'ip': r.ip_address,
            'ports': json.loads(r.ports) if r.ports else [],
            'services': json.loads(r.services) if r.services else [],
            'os': r.os_detection,
            'scanned_at': r.scanned_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({'job': scan_job.to_dict(), 'results': results})

@scans_bp.route('/scans/<int:job_id>/download/<format_type>')
def download_scan_results(job_id, format_type):
    scan_job = ScanJob.query.get_or_404(job_id)
    
    if scan_job.scan_type == 'rustscan':
        if format_type == 'greppable':
            if not scan_job.rustscan_output:
                flash('Результаты недоступны', 'danger')
                return redirect(url_for('scans.scans_page'))
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            return Response(scan_job.rustscan_output, mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename=rustscan_{timestamp}.txt'})
            
    elif scan_job.scan_type == 'nmap':
        file_path, mimetype, filename = None, 'text/plain', ''
        if format_type == 'xml':
            file_path, mimetype, filename = scan_job.nmap_xml_path, 'application/xml', 'nmap_results.xml'
        elif format_type == 'greppable':
            file_path, filename = scan_job.nmap_grep_path, 'nmap_results.gnmap'
        elif format_type == 'normal':
            file_path, filename = scan_job.nmap_normal_path, 'nmap_results.txt'
            
        if file_path and os.path.exists(file_path):
            return send_file(file_path, mimetype=mimetype, as_attachment=True, download_name=filename)
        else:
            flash('Файл результатов не найден', 'danger')
            return redirect(url_for('scans.scans_page'))
            
    flash('Неподдерживаемый формат', 'danger')
    return redirect(url_for('scans.scans_page'))

@scans_bp.route('/api/scans/<int:job_id>/control', methods=['POST'])
def control_scan_job(job_id):
    data = request.json
    action = data.get('action')
    scan_job = ScanJob.query.get_or_404(job_id)
    
    try:
        if action == 'stop':
            if scan_job.status in ['running', 'paused']:
                scan_job.status = 'stopped'
                scan_job.error_message = "Остановлено пользователем."
                scan_job.completed_at = datetime.utcnow()
                db.session.commit()
                return jsonify({'success': True, 'message': 'Команда остановки отправлена'})
            return jsonify({'error': f'Нельзя остановить задание в статусе: {scan_job.status}'}), 400
            
        elif action == 'pause':
            if scan_job.status == 'running':
                scan_job.status = 'paused'
                db.session.commit()
                return jsonify({'success': True, 'message': 'Сканирование приостановлено'})
            return jsonify({'error': f'Нельзя приостановить задание в статусе: {scan_job.status}'}), 400
            
        elif action == 'resume':
            if scan_job.status == 'paused':
                scan_job.status = 'running'
                db.session.commit()
                return jsonify({'success': True, 'message': 'Сканирование возобновлено'})
            return jsonify({'error': f'Нельзя возобновить задание в статусе: {scan_job.status}'}), 400
            
        elif action == 'delete':
            if scan_job.status in ['pending', 'completed', 'failed', 'stopped']:
                for f in [scan_job.nmap_xml_path, scan_job.nmap_grep_path, scan_job.nmap_normal_path]:
                    if f and os.path.exists(f):
                        try: os.remove(f)
                        except: pass
                db.session.delete(scan_job)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Задание удалено'})
            return jsonify({'error': 'Нельзя удалить активное задание. Сначала остановите его.'}), 400
            
        return jsonify({'error': 'Неизвестная команда'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@scans_bp.route('/api/scans/status')
def get_active_scans_status():
    active_jobs = ScanJob.query.filter(ScanJob.status.in_(['pending', 'running'])).order_by(ScanJob.created_at.desc()).limit(10).all()
    return jsonify({'active': [job.to_dict() for job in active_jobs], 'total_active': len(active_jobs)})

@scans_bp.route('/api/scans/history')
def get_scan_history():
    """API для получения истории сканирований"""
    scan_jobs = ScanJob.query.order_by(ScanJob.created_at.desc()).limit(50).all()
    
    return jsonify([{
        'id': job.id,
        'scan_type': job.scan_type,
        'target': job.target,
        'status': job.status,
        'progress': job.progress,
        'started_at': job.started_at.strftime('%Y-%m-%d %H:%M') if job.started_at else '-',
        'completed_at': job.completed_at.strftime('%Y-%m-%d %H:%M') if job.completed_at else '-',
        'error_message': job.error_message
    } for job in scan_jobs])