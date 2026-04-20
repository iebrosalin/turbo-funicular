from flask import Blueprint, request, jsonify, Response
from datetime import datetime
import xml.etree.ElementTree as ET

utilities_bp = Blueprint('utilities', __name__)

@utilities_bp.route('/utilities')
def utilities_page():
    from models import AssetGroup as Group; from utils import build_group_tree
    all_groups = Group.query.all()
    return render_template('utilities.html', group_tree=build_group_tree(all_groups), all_groups=all_groups)

@utilities_bp.route('/utilities/nmap-to-rustscan', methods=['POST'])
def nmap_to_rustscan():
    if 'file' not in request.files: return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'Файл не выбран'}), 400
    if not file.filename.endswith('.xml'): return jsonify({'error': 'Требуется XML файл'}), 400
    try:
        tree = ET.parse(file.stream); root = tree.getroot()
        ips = [addr.get('addr') for host in root.findall('host') if (status := host.find('status')) is not None and status.get('state') == 'up' and (addr := host.find('address')) is not None and addr.get('addr')]
        if not ips: return jsonify({'error': 'Не найдено активных хостов'}), 400
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return Response('\n'.join(ips), mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename=rustscan_targets_{timestamp}.txt'})
    except Exception as e: return jsonify({'error': f'Ошибка: {str(e)}'}), 500

@utilities_bp.route('/utilities/extract-ports', methods=['POST'])
def extract_ports():
    if 'file' not in request.files: return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'Файл не выбран'}), 400
    try:
        tree = ET.parse(file.stream); root = tree.getroot()
        all_ports, host_ports = set(), {}
        for host in root.findall('host'):
            status = host.find('status')
            if status is not None and status.get('state') == 'up':
                addr = host.find('address'); ip = addr.get('addr') if addr is not None else 'unknown'
                ports = []; ports_elem = host.find('ports')
                if ports_elem is not None:
                    for port in ports_elem.findall('port'):
                        state = port.find('state')
                        if state is not None and state.get('state') == 'open':
                            port_id, protocol = port.get('portid'), port.get('protocol')
                            service = port.find('service'); service_name = service.get('name') if service is not None else ''
                            port_str = f"{port_id}/{protocol}" + (f" ({service_name})" if service_name else '')
                            ports.append(port_str); all_ports.add(port_id)
                if ports: host_ports[ip] = ports
        content = "="*60 + "\nNMAP PORTS EXTRACTION REPORT\n" + f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n" + "="*60 + "\n\n"
        content += f"Total hosts: {len(host_ports)}\nUnique ports: {len(all_ports)}\n\n"
        content += "-"*60 + "\nUNIQUE PORTS (for rustscan -p):\n" + "-"*60 + "\n" + ','.join(sorted(all_ports, key=int)) + "\n\n"
        content += "-"*60 + "\nHOSTS WITH PORTS:\n" + "-"*60 + "\n"
        for ip, ports in host_ports.items(): content += f"\n{ip}:\n" + "".join(f"  - {p}\n" for p in ports)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return Response(content, mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename=nmap_ports_report_{timestamp}.txt'})
    except Exception as e: return jsonify({'error': f'Ошибка: {str(e)}'}), 500
