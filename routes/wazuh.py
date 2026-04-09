from flask import Blueprint, request, jsonify
from extensions import db
from models import Asset, WazuhConfig
from utils.wazuh_api import WazuhAPI
from datetime import datetime

wazuh_bp = Blueprint('wazuh', __name__)

@wazuh_bp.route('/api/wazuh/config', methods=['GET'])
def get_wazuh_config():
    cfg = WazuhConfig.query.first() or WazuhConfig()
    if not cfg.id: db.session.add(cfg); db.session.commit()
    return jsonify({'url': cfg.url, 'username': cfg.username, 'password': cfg.password, 'verify_ssl': cfg.verify_ssl, 'is_active': cfg.is_active})

@wazuh_bp.route('/api/wazuh/config', methods=['POST'])
def save_wazuh_config():
    data = request.json; cfg = WazuhConfig.query.first() or WazuhConfig()
    cfg.url = data.get('url', cfg.url); cfg.username = data.get('username', cfg.username)
    cfg.password = data.get('password', cfg.password); cfg.verify_ssl = data.get('verify_ssl', False); cfg.is_active = data.get('is_active', False)
    db.session.add(cfg); db.session.commit()
    return jsonify({'success': True})

@wazuh_bp.route('/api/wazuh/sync', methods=['POST'])
def sync_wazuh():
    cfg = WazuhConfig.query.first()
    if not cfg or not cfg.is_active: return jsonify({'error': 'Wazuh интеграция отключена'}), 400
    try:
        api = WazuhAPI(cfg.url, cfg.username, cfg.password, cfg.verify_ssl)
        agents = api.fetch_all_agents(); synced, updated = 0, 0
        for agent in agents:
            ip = agent.get('ip') or agent.get('registerIP')
            if not ip: continue
            asset = Asset.query.filter_by(wazuh_agent_id=agent['id']).first()
            if not asset: asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset: asset = Asset(ip_address=ip, data_source='wazuh'); db.session.add(asset); db.session.flush(); synced += 1
            else: updated += 1
            asset.wazuh_agent_id = agent['id']; asset.hostname = agent.get('name') or asset.hostname
            os_data = agent.get('os', {})
            if os_data: asset.os_info = f"{os_data.get('name','')} {os_data.get('version','')}".strip() or asset.os_info
            asset.status = 'up' if agent.get('status') == 'active' else 'down'
            if agent.get('lastKeepAlive'):
                try: asset.last_scanned = datetime.fromisoformat(agent['lastKeepAlive'].replace('Z','+00:00'))
                except: pass
            asset.data_source = 'wazuh'
        db.session.commit()
        return jsonify({'success': True, 'new': synced, 'updated': updated, 'total': len(agents)})
    except Exception as e: db.session.rollback(); return jsonify({'error': str(e)}), 500
