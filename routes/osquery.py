from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from extensions import db
from models import Asset, OsqueryInventory
from utils.osquery_validator import validate_osquery_config
import os, json
from datetime import datetime

osquery_bp = Blueprint('osquery', __name__)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'configs', 'osquery', 'osquery.conf')

@osquery_bp.route('/osquery')
def dashboard(): return render_template('osquery_dashboard.html', assets=Asset.query.filter(Asset.osquery_node_key.isnot(None)).all())

@osquery_bp.route('/osquery/api/register', methods=['POST'])
def register_node():
    data = request.json; ip = request.remote_addr; node_key = data.get('node_key')
    asset = Asset.query.filter_by(ip_address=ip).first()
    if not asset: asset = Asset(ip_address=ip, status='up'); db.session.add(asset); db.session.flush()
    asset.osquery_node_key = node_key; asset.osquery_status = 'pending'; db.session.commit()
    return jsonify({'status': 'registered'}), 200

@osquery_bp.route('/osquery/api/ingest', methods=['POST'])
def ingest_inventory():
    data = request.json; asset = Asset.query.filter_by(osquery_node_key=data.get('node_key')).first()
    if not asset: return jsonify({'error': 'Node key not found'}), 404
    asset.osquery_version = data.get('osquery_version', 'unknown'); asset.osquery_status = 'online'; asset.osquery_last_seen = datetime.utcnow()
    asset.osquery_cpu = data.get('cpu_model'); asset.osquery_ram = f"{int(data.get('memory_total', 0) / (1024**3))} GB" if data.get('memory_total') else None
    asset.osquery_disk = f"{int(data.get('disk_total', 0) / (1024**3))} GB" if data.get('disk_total') else None
    asset.osquery_os = data.get('os_name'); asset.osquery_kernel = data.get('kernel_version'); asset.osquery_uptime = data.get('uptime_seconds')
    db.session.add(OSqueryInventory(asset_id=asset.id, cpu_model=data.get('cpu_model'), memory_total=data.get('memory_total'), disk_total=data.get('disk_total'), os_name=data.get('os_name'), kernel_version=data.get('kernel_version'), uptime_seconds=data.get('uptime_seconds')))
    db.session.commit()
    return jsonify({'status': 'ok'}), 200

@osquery_bp.route('/osquery/deploy')
def deploy_page(): return render_template('osquery_deploy.html')

@osquery_bp.route('/osquery/instructions')
def instructions_page(): return render_template('osquery_instructions.html')

@osquery_bp.route('/osquery/config-editor')
def config_editor(): return render_template('osquery_config_editor.html')

@osquery_bp.route('/osquery/api/config', methods=['GET'])
def get_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f: return jsonify(json.load(f))
    except Exception as e: return jsonify({'error': str(e)}), 500

@osquery_bp.route('/osquery/api/config/validate', methods=['POST'])
def validate_config():
    data = request.json
    if not data: return jsonify({'valid': False, 'errors': ['Пустой запрос']}), 400
    try:
        config = json.loads(json.dumps(data))
        errors, warnings = validate_osquery_config(config)
        return jsonify({'valid': len(errors) == 0, 'errors': errors, 'warnings': warnings})
    except json.JSONDecodeError as e: return jsonify({'valid': False, 'errors': [f"JSON ошибка: {str(e)}"]}), 400
    except Exception as e: return jsonify({'valid': False, 'errors': [f"Внутренняя ошибка: {str(e)}"]}), 500

@osquery_bp.route('/osquery/api/config', methods=['POST'])
def save_config():
    try:
        config = request.json
        errors, _ = validate_osquery_config(config)
        if errors: return jsonify({'error': 'Конфигурация содержит ошибки', 'errors': errors}), 400
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f: json.dump(config, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True})
    except Exception as e: return jsonify({'error': str(e)}), 500
