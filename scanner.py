# scanner.py
import os
import subprocess
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from extensions import db
from models import ScanJob, Asset, ScanResult, ServiceInventory
from utils import log_asset_change

def run_rustscan_scan(scan_job_id, target, custom_args=''):
    scan_job = ScanJob.query.get(scan_job_id)
    if not scan_job: return
    try:
        scan_job.status = 'running'
        scan_job.started_at = datetime.utcnow()
        scan_job.progress = 10
        db.session.commit()
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        result_dir = os.path.join('scan_results', f'rustscan_{timestamp}')
        os.makedirs(result_dir, exist_ok=True)
        output_file = os.path.join(result_dir, 'output.txt')
        cmd = ['rustscan', '-a', target, '--greppable', '-o', output_file]
        if custom_args: cmd.extend(custom_args.split())
        if '--batch-size' not in custom_args: cmd.extend(['--batch-size', '1000'])
        if '--timeout' not in custom_args: cmd.extend(['--timeout', '1500'])
        
        print(f"🔍 Запуск rustscan: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        scan_job.progress = 50
        db.session.commit()
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            scan_job.progress = 90
            if os.path.exists(output_file):
                with open(output_file, 'r') as f: scan_job.rustscan_output = f.read()
            parse_rustscan_results(scan_job_id, scan_job.rustscan_output, target)
            scan_job.status = 'completed'
            scan_job.progress = 100
        else:
            scan_job.status = 'failed'
            scan_job.error_message = stderr or f"Exit code: {process.returncode}"
        scan_job.completed_at = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        scan_job.status = 'failed'
        scan_job.error_message = str(e)
        scan_job.completed_at = datetime.utcnow()
        db.session.commit()

def run_nmap_scan(scan_job_id, target, ports=None, custom_args=''):
    scan_job = ScanJob.query.get(scan_job_id)
    if not scan_job: return
    try:
        scan_job.status = 'running'
        scan_job.started_at = datetime.utcnow()
        scan_job.progress = 10
        db.session.commit()
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        result_dir = os.path.join('scan_results', f'nmap_{timestamp}')
        os.makedirs(result_dir, exist_ok=True)
        base_filename = os.path.join(result_dir, 'scan')
        cmd = ['nmap', target, '-oA', base_filename]
        if custom_args: cmd = ['nmap'] + custom_args.split() + [target, '-oA', base_filename]
        if ports and '-p' not in custom_args: cmd.extend(['-p', ports])
        if '-sV' not in custom_args: cmd.extend(['-sV'])
        if '-sC' not in custom_args: cmd.extend(['-sC'])
        if '-O' not in custom_args: cmd.extend(['-O'])
        
        print(f"🔍 Запуск nmap: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        scan_job.progress = 50
        db.session.commit()
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            scan_job.progress = 90
            scan_job.nmap_xml_path = f'{base_filename}.xml'
            scan_job.nmap_grep_path = f'{base_filename}.gnmap'
            scan_job.nmap_normal_path = f'{base_filename}.nmap'
            if os.path.exists(scan_job.nmap_xml_path):
                parse_nmap_results(scan_job_id, scan_job.nmap_xml_path)
            scan_job.status = 'completed'
            scan_job.progress = 100
        else:
            scan_job.status = 'failed'
            scan_job.error_message = stderr or f"Exit code: {process.returncode}"
        scan_job.completed_at = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        scan_job.status = 'failed'
        scan_job.error_message = str(e)
        scan_job.completed_at = datetime.utcnow()
        db.session.commit()

def parse_rustscan_results(scan_job_id, output, target):
    if not output: return
    lines = output.strip().split('\n')
    scan_job = ScanJob.query.get(scan_job_id)
    for line in lines:
        if '->' in line:
            try:
                parts = line.split('->')
                ip = parts[0].strip()
                ports_str = parts[1].strip() if len(parts) > 1 else ''
                new_ports = [p.strip() for p in ports_str.split(',') if p.strip()]
                asset = Asset.query.filter_by(ip_address=ip).first() 
                if not asset:
                    asset = Asset(ip_address=ip, status='up')
                    db.session.add(asset)
                    db.session.flush()
                    log_asset_change(asset.id, 'asset_created', 'ip_address', None, ip, scan_job_id, 'Создан через rustscan')
                else:
                    existing_ports = set(asset.open_ports.split(', ')) if asset.open_ports else set()
                    new_ports_set = set(new_ports)
                    added_ports = new_ports_set - existing_ports
                    removed_ports = existing_ports - new_ports_set
                    for port in added_ports: log_asset_change(asset.id, 'port_added', 'open_ports', None, port, scan_job_id)
                    for port in removed_ports: log_asset_change(asset.id, 'port_removed', 'open_ports', port, None, scan_job_id)
                    if new_ports:
                        all_ports = existing_ports.union(new_ports_set) if asset.open_ports else new_ports_set
                        asset.open_ports = ', '.join(sorted(all_ports, key=lambda x: int(x.split('/')[0]) if '/' in x else int(x)))
                asset.last_scanned = datetime.utcnow()
                scan_result = ScanResult(asset_id=asset.id, ip_address=ip, scan_job_id=scan_job_id, ports=json.dumps(new_ports), scanned_at=datetime.utcnow())
                db.session.add(scan_result)
            except Exception as e: print(f"⚠️ Ошибка парсинга строки: {line} - {e}")
    db.session.commit()

def parse_nmap_results(scan_job_id, xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        scan_job = ScanJob.query.get(scan_job_id)
        for host in root.findall('host'):
            status = host.find('status')
            if status is None or status.get('state') != 'up': continue
            addr = host.find('address')
            ip = addr.get('addr') if addr is not None else None
            if not ip: continue
            hostname = 'Unknown'
            hostnames = host.find('hostnames')
            if hostnames is not None:
                name_elem = hostnames.find('hostname')
                if name_elem is not None: hostname = name_elem.get('name')
            os_info = 'Unknown'
            os_elem = host.find('os')
            if os_elem is not None:
                os_match = os_elem.find('osmatch')
                if os_match is not None: os_info = os_match.get('name')
            ports, services = [], []
            ports_elem = host.find('ports')
            if ports_elem is not None:
                for port in ports_elem.findall('port'):
                    state = port.find('state')
                    if state is not None and state.get('state') == 'open':
                        port_id = port.get('portid')
                        protocol = port.get('protocol')
                        service = port.find('service')
                        service_name = service.get('name') if service is not None else ''
                        service_product = service.get('product') if service is not None else ''
                        service_version = service.get('version') if service is not None else ''
                        service_extrainfo = service.get('extrainfo') if service is not None else ''
                        service_cpe = service.get('cpe') if service is not None else ''
                        port_str = f"{port_id}/{protocol}"
                        ports.append(port_str)
                        script_output = [{'id': s.get('id'), 'output': s.get('output')} for s in port.findall('script')]
                        services.append({'port': port_str, 'name': service_name, 'product': service_product, 'version': service_version, 'extrainfo': service_extrainfo, 'cpe': service_cpe, 'scripts': script_output})
                        asset = Asset.query.filter_by(ip_address=ip).first()
                        if asset:
                            existing_service = ServiceInventory.query.filter_by(asset_id=asset.id, port=port_str).first()
                            if existing_service:
                                changes = []
                                if existing_service.service_name != service_name: changes.append(('service_name', existing_service.service_name, service_name))
                                if existing_service.product != service_product: changes.append(('product', existing_service.product, service_product))
                                if existing_service.version != service_version: changes.append(('version', existing_service.version, service_version))
                                for field, old, new in changes: log_asset_change(asset.id, 'service_updated', field, old, new, scan_job_id, f'Порт {port_str}')
                                existing_service.service_name = service_name
                                existing_service.product = service_product
                                existing_service.version = service_version
                                existing_service.extrainfo = service_extrainfo
                                existing_service.cpe = service_cpe
                                existing_service.script_output = json.dumps(script_output)
                                existing_service.last_seen = datetime.utcnow()
                                existing_service.is_active = True
                            else:
                                new_service = ServiceInventory(asset_id=asset.id, port=port_str, protocol=protocol, service_name=service_name, product=service_product, version=service_version, extrainfo=service_extrainfo, cpe=service_cpe, script_output=json.dumps(script_output))
                                db.session.add(new_service)
                                log_asset_change(asset.id, 'service_detected', 'service_inventory', None, service_name, scan_job_id, f'Новый сервис на порту {port_str}')
            asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset:
                asset = Asset(ip_address=ip, status='up')
                db.session.add(asset)
                db.session.flush()
                log_asset_change(asset.id, 'asset_created', 'ip_address', None, ip, scan_job_id, 'Создан через nmap')
            if asset.os_info != os_info and os_info != 'Unknown': log_asset_change(asset.id, 'os_changed', 'os_info', asset.os_info, os_info, scan_job_id)
            asset.hostname = hostname if hostname != 'Unknown' else asset.hostname
            asset.os_info = os_info if os_info != 'Unknown' else asset.os_info
            if ports: asset.open_ports = ', '.join(ports)
            asset.last_scanned = datetime.utcnow()
            scan_result = ScanResult(asset_id=asset.id, ip_address=ip, scan_job_id=scan_job_id, ports=json.dumps(ports), services=json.dumps(services), os_detection=os_info, scanned_at=datetime.utcnow())
            db.session.add(scan_result)
        db.session.commit()
    except Exception as e: print(f"❌ Ошибка парсинга nmap XML: {e}")