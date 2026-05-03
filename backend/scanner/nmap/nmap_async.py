"""
Асинхронный модуль сканирования Nmap для интеграции с ScanQueueManager.
"""
import asyncio
import os
import xml.etree.ElementTree as ET
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.asset import Asset
from backend.models.service import ServiceInventory
from backend.models.scan import ScanJob, ScanResult
from backend.models.group import AssetGroup
from backend.utils import MOSCOW_TZ
from backend.services.asset_manager import upsert_asset, upsert_service, update_asset_ports


class NmapScanner:
    """Асинхронный класс для выполнения сканирования через Nmap"""
    
    async def scan(
        self,
        db: AsyncSession,
        job_id: int,
        target: str,
        ports: str = '',
        scripts: str = '',
        custom_args: str = '',
        known_ports_only: bool = False,
        group_ids: Optional[List[int]] = None,
        save_assets: bool = True
    ) -> Dict[str, Any]:
        """Запуск сканирования Nmap."""
        output_dir = os.path.join(os.getcwd(), 'scanner_output', str(job_id))
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.join(output_dir, 'nmap')
        
        try:
            job = await db.get(ScanJob, job_id)
            if not job:
                raise ValueError(f"Задача сканирования {job_id} не найдена")
            
            job.status = 'running'
            job.started_at = datetime.utcnow()
            await db.commit()
            
            final_targets, final_ports, targets_map = await self._prepare_targets(
                db, target, ports, known_ports_only, group_ids
            )
            
            cmd = self._build_command(final_targets, final_ports, scripts, custom_args, base_name)
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            logger.info(f"[NmapScanner] Запущен процесс Nmap для задачи {job_id}, PID: {process.pid}")
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode('utf-8', errors='ignore').strip()
                if line_str:
                    logger.debug(f"[Nmap] {line_str}")
                # Nmap вывод обрабатывается позже через parse_output
            
            await process.wait()
            
            logger.info(f"[NmapScanner] Процесс Nmap завершен с кодом {process.returncode}")
            
            if process.returncode > 1:
                raise Exception(f"Nmap завершился с кодом {process.returncode}")
            
            xml_file = f'{base_name}.xml'
            if os.path.exists(xml_file):
                await self._parse_results(db, job_id, xml_file)
            else:
                raise Exception("Файл XML результатов не создан")
            
            job = await db.get(ScanJob, job_id)
            if job:
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                job.progress = 100.0
                await db.commit()
            
            return {
                "status": "completed",
                "job_id": job_id,
                "result": {
                    "hostname": target,
                    "ports": []
                },
                "raw_output": f"Nmap scan completed. Output saved to {xml_file}"
            }
            
        except asyncio.CancelledError:
            job = await db.get(ScanJob, job_id)
            if job:
                job.status = 'stopped'
                await db.commit()
            raise
        except Exception as e:
            job = await db.get(ScanJob, job_id)
            if job:
                job.status = 'failed'
                job.error_message = str(e)
                await db.commit()
            return {"status": "failed", "job_id": job_id, "error": str(e)}
    
    async def _prepare_targets(self, db, target, ports, known_ports_only, group_ids):
        """Подготовка целей сканирования."""
        if not (known_ports_only and group_ids):
            return target, ports, {}
        
        stmt = select(AssetGroup).where(AssetGroup.id.in_(group_ids))
        result = await db.execute(stmt)
        groups = result.scalars().all()
        
        asset_ids = set()
        for g in groups:
            for a in g.assets:
                asset_ids.add(a.id)
        
        stmt = select(Asset).where(Asset.id.in_(asset_ids))
        result = await db.execute(stmt)
        assets = result.scalars().all()
        
        targets_map = {}
        all_ips, all_known_ports = set(), set()
        
        for asset in assets:
            if asset.open_ports:
                targets_map[asset.ip_address] = asset.open_ports
                all_ips.add(asset.ip_address)
                all_known_ports.update(asset.open_ports)
        
        if not all_ips:
            raise Exception("Не найдено активов с открытыми портами в выбранных группах")
        
        return ' '.join(all_ips), ','.join(map(str, sorted(all_known_ports))), targets_map
    
    def _build_command(self, targets, ports, scripts, custom_args, base_name):
        """Построение команды nmap."""
        cmd = ['nmap']
        if ports:
            cmd.extend(['-p', ports])
        if scripts:
            cmd.extend(['--script', scripts])
        if '-sV' not in custom_args:
            cmd.append('-sV')
        if '-O' not in custom_args:
            cmd.append('-O')
        cmd.extend(['-oX', f'{base_name}.xml', '-oN', f'{base_name}.nmap'])
        if custom_args:
            cmd.extend(custom_args.split())
        cmd.extend(targets.split())
        return cmd
    
    async def _parse_results(self, db: AsyncSession, job_id: int, xml_file: str, save_assets: bool = True):
        """Парсинг XML и обновление БД с использованием унифицированных функций."""
        import logging
        logger = logging.getLogger(__name__)
        
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        for host in root.findall('host'):
            status_elem = host.find('status')
            if status_elem is None or status_elem.get('state') != 'up':
                continue
            
            addr = host.find('address')
            if addr is None:
                continue
            ip = addr.get('addr')
            
            hostname = None
            hostnames = host.find('hostnames')
            if hostnames is not None:
                h_elem = hostnames.find('hostname')
                if h_elem is not None:
                    hostname = h_elem.get('name')
            
            os_match = None
            os_elem = host.find('os')
            if os_elem is not None:
                os_match_elem = os_elem.find('osmatch')
                if os_match_elem is not None:
                    os_match = os_match_elem.get('name')
            
            # Парсим OS детали
            os_family = None
            os_version = None
            if os_match:
                parts = os_match.split()
                os_family = parts[0] if parts else None
                os_version = ' '.join(parts[1:]) if len(parts) > 1 else None
            
            found_ports = []
            ports_elem = host.find('ports')
            if ports_elem is not None:
                for port in ports_elem.findall('port'):
                    state_elem = port.find('state')
                    if state_elem is None or state_elem.get('state') != 'open':
                        continue
                    
                    port_num = int(port.get('portid'))
                    protocol = port.get('protocol')
                    found_ports.append(port_num)
                    
                    service_elem = port.find('service')
                    service_data = {}
                    if service_elem is not None:
                        service_data = {
                            'name': service_elem.get('name', 'unknown'),
                            'product': service_elem.get('product', ''),
                            'version': service_elem.get('version', ''),
                            'extra_info': service_elem.get('extrainfo', ''),
                        }
                        
                        for script in service_elem.findall('script'):
                            if script.get('id') == 'ssl-cert':
                                output = script.get('output', '')
                                service_data['script_output'] = output
                                
                                subj = re.search(r'Subject: (.+?)(?:\n|Issuer:|$)', output)
                                if subj:
                                    service_data['ssl_subject'] = subj.group(1).strip()
                                
                                iss = re.search(r'Issuer: (.+?)(?:\n|Validity|$)', output)
                                if iss:
                                    service_data['ssl_issuer'] = iss.group(1).strip()
                    
                    # Создаем или обновляем актив только если save_assets=True
                    if save_assets:
                        asset = await upsert_asset(
                            db=db,
                            ip_address=ip,
                            hostname=hostname,
                            os_family=os_family,
                            os_version=os_version,
                            scanner_name="Nmap"
                        )
                        
                        # Обновляем порты
                        update_asset_ports(asset, 'nmap', [port_num], scanner_name="Nmap")
                        
                        # Создаем или обновляем сервис
                        await upsert_service(
                            db=db,
                            asset=asset,
                            port=port_num,
                            protocol=protocol,
                            state='open',
                            service_name=service_data.get('name', 'unknown'),
                            product=service_data.get('product', ''),
                            version=service_data.get('version', ''),
                            extra_info=service_data.get('extra_info', ''),
                            script_output=service_data.get('script_output', ''),
                            ssl_subject=service_data.get('ssl_subject'),
                            ssl_issuer=service_data.get('ssl_issuer'),
                            scanner_name="Nmap"
                        )
            
            scan_result = ScanResult(
                scan_job_id=job_id,
                asset_ip=ip,
                hostname=hostname,
                ports=found_ports,
                raw_output=f"Nmap scan completed for {ip}",
                scanned_at=datetime.now(MOSCOW_TZ)
            )
            db.add(scan_result)
        
        await db.commit()
