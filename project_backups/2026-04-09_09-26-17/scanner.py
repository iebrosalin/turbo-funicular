# scanner.py

from extensions import db
from models import ScanJob, Asset, ScanResult, ServiceInventory
from utils import log_asset_change
from app import app  # 🔥 Импортируем app для app_context() 🔥

def run_rustscan_scan(scan_job_id, target, custom_args=''):
    # 🔥 Входим в app_context для доступа к db 🔥
    with app.app_context():
        # 🔥 Очищаем сессию для безопасной работы в потоке 🔥
        db.session.remove()
        
        scan_job = ScanJob.query.get(scan_job_id)
        if not scan_job:
            print(f"❌ ScanJob {scan_job_id} not found")
            return
        
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
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            scan_job.progress = 50
            db.session.commit()
            
            last_commit = time.time()
            last_progress = 50
            start_time = time.time()
            
            for line in iter(process.stdout.readline, ''):
                db.session.remove()  # 🔥 Очищаем сессию перед каждым запросом 🔥
                
                # Проверка статуса
                job = ScanJob.query.get(scan_job_id)
                if not job: break
                if job.status == 'stopped':
                    process.terminate()
                    try: process.wait(timeout=5)
                    except: process.kill()
                    job.status = 'stopped'
                    job.error_message = 'Остановлено пользователем'
                    job.completed_at = datetime.utcnow()
                    db.session.commit()
                    return
                if job.status == 'paused':
                    while ScanJob.query.get(scan_job_id).status == 'paused':
                        time.sleep(0.5)
                    continue
                
                # Прогресс (аппроксимация для rustscan)
                elapsed = time.time() - start_time
                estimated = min(90, 15 + (elapsed / 200) * 75)
                if estimated > last_progress + 0.5 and (time.time() - last_commit) > 1.0:
                    last_progress = estimated
                    job = ScanJob.query.get(scan_job_id)
                    if job:
                        job.progress = int(last_progress)
                        db.session.commit()
                        last_commit = time.time()
            
            process.wait()
            job = ScanJob.query.get(scan_job_id)
            if not job: return
            
            if process.returncode == 0 and job.status not in ['stopped', 'failed']:
                if os.path.exists(output_file):
                    with open(output_file, 'r') as f:
                        job.rustscan_output = f.read()
                job.progress = 95
                db.session.commit()
                parse_rustscan_results(scan_job_id, job.rustscan_output, target)
                job.status = 'completed'
                job.progress = 100
            elif job.status not in ['stopped']:
                job.status = 'failed'
                job.error_message = f'Exit code: {process.returncode}'
            
            job.completed_at = datetime.utcnow()
            db.session.commit()
            print(f"✅ Rustscan job {scan_job_id} completed: {job.status}")
            
        except Exception as e:
            db.session.rollback()
            job = ScanJob.query.get(scan_job_id)
            if job:
                job.status = 'failed'
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.session.commit()
            print(f"❌ Error in rustscan job {scan_job_id}: {e}")


def run_nmap_scan(scan_job_id, target, ports=None, custom_args=''):
    with app.app_context():
        db.session.remove()
        
        scan_job = ScanJob.query.get(scan_job_id)
        if not scan_job:
            print(f"❌ ScanJob {scan_job_id} not found")
            return
        
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
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            scan_job.progress = 50
            db.session.commit()
            
            last_commit = time.time()
            last_progress = 50
            
            for line in iter(process.stdout.readline, ''):
                db.session.remove()
                
                job = ScanJob.query.get(scan_job_id)
                if not job: break
                if job.status == 'stopped':
                    process.terminate()
                    try: process.wait(timeout=5)
                    except: process.kill()
                    job.status = 'stopped'
                    job.error_message = 'Остановлено пользователем'
                    job.completed_at = datetime.utcnow()
                    db.session.commit()
                    return
                if job.status == 'paused':
                    if os.name != 'nt':
                        os.kill(process.pid, 19)  # SIGSTOP
                        while ScanJob.query.get(scan_job_id).status == 'paused':
                            time.sleep(0.5)
                        os.kill(process.pid, 18)  # SIGCONT
                    else:
                        while ScanJob.query.get(scan_job_id).status == 'paused':
                            time.sleep(0.5)
                    continue
                
                # Парсинг прогресса из вывода nmap
                match = re.search(r'(\d+(?:\.\d+)?)%', line)
                if match:
                    prog = float(match.group(1))
                    if prog > last_progress and (time.time() - last_commit) > 1.0:
                        last_progress = prog
                        job = ScanJob.query.get(scan_job_id)
                        if job:
                            job.progress = int(last_progress)
                            db.session.commit()
                            last_commit = time.time()
            
            process.wait()
            job = ScanJob.query.get(scan_job_id)
            if not job: return
            
            if process.returncode == 0 and job.status not in ['stopped', 'failed']:
                job.progress = 95
                job.nmap_xml_path = f'{base_filename}.xml'
                job.nmap_grep_path = f'{base_filename}.gnmap'
                job.nmap_normal_path = f'{base_filename}.nmap'
                db.session.commit()
                
                if os.path.exists(job.nmap_xml_path):
                    parse_nmap_results(scan_job_id, job.nmap_xml_path)
                
                job.status = 'completed'
                job.progress = 100
            elif job.status not in ['stopped']:
                job.status = 'failed'
                job.error_message = f'Exit code: {process.returncode}'
            
            job.completed_at = datetime.utcnow()
            db.session.commit()
            print(f"✅ Nmap job {scan_job_id} completed: {job.status}")
            
        except Exception as e:
            db.session.rollback()
            job = ScanJob.query.get(scan_job_id)
            if job:
                job.status = 'failed'
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.session.commit()
            print(f"❌ Error in nmap job {scan_job_id}: {e}")