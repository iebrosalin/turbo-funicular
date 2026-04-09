import os, re, subprocess, time, json, xml.etree.ElementTree as ET
from datetime import datetime
from extensions import db
from models import ScanJob, Asset, ScanResult, ServiceInventory
from utils import log_asset_change, detect_device_role_and_tags

def update_job(job_id, **kwargs):
    try:
        with db.session.no_autoflush:
            job = ScanJob.query.get(job_id)
            if not job: return
            for k, v in kwargs.items(): setattr(job, k, v)
            db.session.commit()
    except Exception: db.session.rollback()

def parse_targets(target_str): return [t.strip() for t in re.split('[,\s]+', target_str) if t.strip()]

def run_rustscan_scan(scan_job_id, target, custom_args=''):
    targets = parse_targets(target)
    update_job(scan_job_id, progress=5, total_hosts=len(targets), hosts_processed=0, current_target='Инициализация...')
    try:
        cmd = ['rustscan', '-a', target, '--greppable']
        cmd.extend(custom_args.split() if custom_args else [])
        if '-o' not in custom_args and '--output' not in custom_args:
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            res_dir = os.path.join('scan_results', f'rustscan_{ts}')
            os.makedirs(res_dir, exist_ok=True)
            cmd.extend(['-o', os.path.join(res_dir, 'output.txt')])
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        processed = 0
        for line in iter(process.stdout.readline, ''):
            db.session.remove()
            job = ScanJob.query.get(scan_job_id)
            if not job or job.status == 'stopped':
                process.terminate(); update_job(scan_job_id, status='stopped', error_message='Остановлено пользователем', completed_at=datetime.utcnow()); return
            if job.status == 'paused': time.sleep(0.5); continue
            match = re.match(r'^(\S+)\s+->', line)
            if match:
                processed += 1
                update_job(scan_job_id, progress=min(95, 10 + (processed/len(targets))*85), current_target=match.group(1), hosts_processed=processed)
        process.wait()
        job = ScanJob.query.get(scan_job_id)
        if not job: return
        if process.returncode == 0 and job.status != 'stopped':
            update_job(scan_job_id, progress=98, current_target='Парсинг результатов...')
            out_f = cmd[-1]
            if os.path.exists(out_f):
                with open(out_f, 'r') as f: job.rustscan_output = f.read()
            parse_rustscan_results(scan_job_id, job.rustscan_output, target)
            update_job(scan_job_id, progress=100, status='completed', current_target='Готово', completed_at=datetime.utcnow())
        elif job.status != 'stopped':
            update_job(scan_job_id, status='failed', error_message=f'Exit code: {process.returncode}', completed_at=datetime.utcnow())
    except Exception as e: update_job(scan_job_id, status='failed', error_message=str(e), completed_at=datetime.utcnow())

def run_nmap_scan(scan_job_id, target, ports=None, custom_args=''):
    targets = parse_targets(target)
    update_job(scan_job_id, progress=5, total_hosts=len(targets), hosts_processed=0, current_target='Инициализация...')
    try:
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        res_dir = os.path.join('scan_results', f'nmap_{ts}')
        os.makedirs(res_dir, exist_ok=True)
        base = os.path.join(res_dir, 'scan')
        cmd = ['nmap', target]
        cmd.extend(custom_args.split() if custom_args else [])
        if '-p' not in custom_args and ports: cmd.extend(['-p', ports])
        for def_arg in ['-sV', '-sC', '-O', '-v']:
            if def_arg not in custom_args: cmd.append(def_arg)
        if not any(a in custom_args for a in ['-oA', '-oX', '-oG', '-oN']): cmd.extend(['-oA', base])
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in iter(process.stdout.readline, ''):
            db.session.remove()
            job = ScanJob.query.get(scan_job_id)
            if not job or job.status == 'stopped':
                process.terminate(); update_job(scan_job_id, status='stopped', error_message='Остановлено пользователем', completed_at=datetime.utcnow()); return
            if job.status == 'paused':
                if os.name != 'nt':
                    os.kill(process.pid, 19)
                    while ScanJob.query.get(scan_job_id).status == 'paused': time.sleep(0.5)
                    os.kill(process.pid, 18)
                else:
                    while ScanJob.query.get(scan_job_id).status == 'paused': time.sleep(0.5)
                continue
            hm = re.search(r'Nmap scan report for (.+)', line)
            if hm: update_job(scan_job_id, current_target=hm.group(1))
            sm = re.search(r'(\d+(?:\.\d+)?)%.*?(\d+)\s+hosts scanned', line)
            pm = re.search(r'(\d+(?:\.\d+)?)%', line)
            if sm: update_job(scan_job_id, progress=int(float(sm.group(1))), hosts_processed=int(sm.group(2)))
            elif pm: update_job(scan_job_id, progress=int(float(pm.group(1))))
        process.wait()
        job = ScanJob.query.get(scan_job_id)
        if not job: return
        if process.returncode == 0 and job.status != 'stopped':
            update_job(scan_job_id, progress=98, current_target='Парсинг XML...')
            job.nmap_xml_path = f'{base}.xml'; job.nmap_grep_path = f'{base}.gnmap'; job.nmap_normal_path = f'{base}.nmap'
            if os.path.exists(job.nmap_xml_path): parse_nmap_results(scan_job_id, job.nmap_xml_path)
            update_job(scan_job_id, progress=100, status='completed', current_target='Готово', completed_at=datetime.utcnow())
        elif job.status != 'stopped': update_job(scan_job_id, status='failed', error_message=f'Exit code: {process.returncode}', completed_at=datetime.utcnow())
    except Exception as e: update_job(scan_job_id, status='failed', error_message=str(e), completed_at=datetime.utcnow())

def parse_rustscan_results(scan_job_id, output, target):
    if not output: return
    for line in output.strip().split('\n'):
        if '->' in line:
            try:
                parts = line.split('->'); ip = parts[0].strip()
                ports_str = parts[1].strip() if len(parts)>1 else ''
                new_ports = [p.strip() for p in ports_str.split(',') if p.strip()]
                asset = Asset.query.filter_by(ip_address=ip).first()
                if not asset:
                    asset = Asset(ip_address=ip, status='up'); db.session.add(asset); db.session.flush()
                    log_asset_change(asset.id, 'asset_created', 'ip_address', None, ip, scan_job_id, 'Создан через rustscan')
                else:
                    existing = set(asset.open_ports.split(', ')) if asset.open_ports else set()
                    added, removed = set(new_ports)-existing, existing-set(new_ports)
                    for p in added: log_asset_change(asset.id, 'port_added', 'open_ports', None, p, scan_job_id)
                    for p in removed: log_asset_change(asset.id, 'port_removed', 'open_ports', p, None, scan_job_id)
                    if new_ports:
                        asset.open_ports = ', '.join(sorted((existing|set(new_ports)), key=lambda x: int(x.split('/')[0]) if '/' in x else int(x)))
                        asset.device_role, asset.device_tags = detect_device_role_and_tags(asset.open_ports)
                asset.last_scanned = datetime.utcnow()
                scanners = json.loads(asset.scanners_used) if asset.scanners_used else []
                if 'rustscan' not in scanners: scanners.append('rustscan')
                asset.scanners_used = json.dumps(scanners)
                db.session.add(ScanResult(asset_id=asset.id, ip_address=ip, scan_job_id=scan_job_id, ports=json.dumps(new_ports), scanned_at=datetime.utcnow()))
            except Exception as e: print(f"⚠️ Ошибка парсинга rustscan: {e}")
    db.session.commit()

def parse_nmap_results(scan_job_id, xml_path):
    try:
        tree = ET.parse(xml_path); root = tree.getroot()
        for host in root.findall('host'):
            st = host.find('status')
            if st is None or st.get('state') != 'up': continue
            addr = host.find('address')
            ip = addr.get('addr') if addr is not None else None
            if not ip: continue
            hostname, os_info = 'Unknown', 'Unknown'
            hn = host.find('hostnames')
            if hn is not None:
                ne = hn.find('hostname')
                if ne is not None: hostname = ne.get('name')
            oe = host.find('os')
            if oe is not None:
                om = oe.find('osmatch')
                if om is not None: os_info = om.get('name')
            ports, services = [], []
            pe = host.find('ports')
            if pe is not None:
                for port in pe.findall('port'):
                    state = port.find('state')
                    if state is not None and state.get('state') == 'open':
                        pid, proto = port.get('portid'), port.get('protocol')
                        svc = port.find('service')
                        s = {'name': svc.get('name') if svc is not None else '', 'product': svc.get('product') if svc is not None else '', 'version': svc.get('version') if svc is not None else '', 'extrainfo': svc.get('extrainfo') if svc is not None else ''}
                        pstr = f"{pid}/{proto}"; ports.append(pstr); services.append(s)
                        asset = Asset.query.filter_by(ip_address=ip).first()
                        if asset:
                            ex = ServiceInventory.query.filter_by(asset_id=asset.id, port=pstr).first()
                            if ex: ex.service_name, ex.product, ex.version, ex.extrainfo, ex.last_seen, ex.is_active = s['name'], s['product'], s['version'], s['extrainfo'], datetime.utcnow(), True
                            else:
                                db.session.add(ServiceInventory(asset_id=asset.id, port=pstr, protocol=proto, service_name=s['name'], product=s['product'], version=s['version'], extrainfo=s['extrainfo']))
                                log_asset_change(asset.id, 'service_detected', 'service_inventory', None, s['name'], scan_job_id, f'Порт {pstr}')
            asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset: asset = Asset(ip_address=ip, status='up'); db.session.add(asset); db.session.flush()
            if asset.os_info != os_info and os_info != 'Unknown': log_asset_change(asset.id, 'os_changed', 'os_info', asset.os_info, os_info, scan_job_id)
            asset.hostname, asset.os_info = (hostname if hostname!='Unknown' else asset.hostname), (os_info if os_info!='Unknown' else asset.os_info)
            if ports:
                asset.open_ports = ', '.join(ports)
                asset.device_role, asset.device_tags = detect_device_role_and_tags(asset.open_ports, services)
            asset.last_scanned = datetime.utcnow()
            scanners = json.loads(asset.scanners_used) if asset.scanners_used else []
            if 'nmap' not in scanners: scanners.append('nmap')
            asset.scanners_used = json.dumps(scanners)
            db.session.add(ScanResult(asset_id=asset.id, ip_address=ip, scan_job_id=scan_job_id, ports=json.dumps(ports), services=json.dumps(services), os_detection=os_info, scanned_at=datetime.utcnow()))
        db.session.commit()
    except Exception as e: print(f"❌ Ошибка парсинга nmap XML: {e}")
