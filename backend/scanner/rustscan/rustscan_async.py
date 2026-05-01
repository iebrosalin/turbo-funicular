"""
Асинхронный модуль сканирования Rustscan для интеграции с ScanQueueManager.
"""
import asyncio
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.scan import ScanJob, ScanResult
from backend.models.asset import Asset
from backend.models.group import AssetGroup
from backend.utils import MOSCOW_TZ
from backend.services.asset_manager import upsert_asset, update_asset_ports


class RustscanScanner:
    """Асинхронный класс для выполнения сканирования через Rustscan"""
    
    async def scan(
        self,
        db: AsyncSession,
        job_id: int,
        target: str,
        ports: str = '',
        custom_args: str = '',
        group_ids: Optional[List[int]] = None,
        run_nmap_after: bool = False,
        nmap_args: Optional[str] = None
    ) -> Dict[str, Any]:
        """Запуск сканирования Rustscan с опциональным запуском Nmap после."""
        output_dir = os.path.join(os.getcwd(), 'scanner_output', str(job_id))
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.join(output_dir, 'rustscan')
        
        try:
            job = await db.get(ScanJob, job_id)
            if not job:
                raise ValueError(f"Задача сканирования {job_id} не найдена")
            
            job.status = 'running'
            job.started_at = datetime.utcnow()
            await db.commit()
            
            final_targets = await self._prepare_targets(db, target, group_ids)
            cmd = self._build_command(final_targets, ports, custom_args, base_name)
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            output_lines = []
            async for line in process.stdout:
                line_decoded = line.decode().strip()
                output_lines.append(line_decoded)
            
            await process.wait()
            
            if process.returncode != 0:
                raise Exception(f"Rustscan завершился с кодом {process.returncode}")
            
            # Парсим вывод для получения портов
            found_ports = self._parse_output(output_lines)
            
            # Обновляем активы
            await self._update_assets(db, final_targets.split(), found_ports)
            
            # Сохраняем результат
            scan_result = ScanResult(
                scan_job_id=job_id,
                asset_ip=final_targets,
                ports=list(found_ports.values()),
                raw_output='\n'.join(output_lines),
                scanned_at=datetime.now()
            )
            db.add(scan_result)
            
            # Если запрошено, запускаем Nmap по найденным портам
            if run_nmap_after and found_ports:
                logger.info(f"[Rustscan] Запуск Nmap для {target} с аргументами: {nmap_args}")
                await self._trigger_nmap_scan(db, target, found_ports, nmap_args)
            
            job = await db.get(ScanJob, job_id)
            if job:
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                job.progress = 100.0
                await db.commit()
            
            return {"status": "completed", "job_id": job_id, "ports_found": found_ports}
            
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
    
    async def _prepare_targets(self, db, target, group_ids):
        """Подготовка целей сканирования."""
        if not group_ids:
            return target
        
        stmt = select(AssetGroup).where(AssetGroup.id.in_(group_ids))
        result = await db.execute(stmt)
        groups = result.scalars().all()
        
        asset_ips = set()
        for g in groups:
            for a in g.assets:
                asset_ips.add(a.ip_address)
        
        return ' '.join(asset_ips) if asset_ips else target
    
    def _build_command(self, targets, ports, custom_args, base_name):
        """Построение команды rustscan."""
        cmd = ['rustscan', '-a', targets]
        if ports:
            cmd.extend(['-p', ports])
        if custom_args:
            cmd.extend(custom_args.split())
        return cmd
    
    def _parse_output(self, output_lines):
        """Парсинг вывода rustscan для получения портов."""
        found_ports = {}
        current_ip = None
        
        for line in output_lines:
            if '->' in line and ':' in line:
                parts = line.split('->')
                if len(parts) == 2:
                    ip_part = parts[0].strip()
                    ports_part = parts[1].strip()
                    if ',' in ports_part:
                        port_list = [int(p.strip()) for p in ports_part.split(',') if p.strip().isdigit()]
                        found_ports[ip_part] = port_list
        
        return found_ports
    
    async def _update_assets(self, db, targets, found_ports):
        """Обновление активов с найденными портами с использованием унифицированных функций."""
        import logging
        logger = logging.getLogger(__name__)
        
        for ip in targets:
            # Создаем или обновляем актив
            asset = await upsert_asset(
                db=db,
                ip_address=ip,
                scanner_name="Rustscan"
            )
            
            if ip in found_ports:
                # Обновляем порты
                update_asset_ports(asset, 'rustscan', found_ports[ip], scanner_name="Rustscan")
            else:
                logger.info(f"[Rustscan] Актив {ip} проверен, новые порты не найдены")
        
        await db.commit()

    async def _trigger_nmap_scan(self, db: AsyncSession, target: str, found_ports: Dict[str, List[int]], nmap_args: Optional[str]):
        """Создание задачи Nmap для сканирования найденных портов."""
        from backend.models.scan import Scan, ScanJob
        from datetime import datetime
        
        # Формируем список портов через запятую
        all_ports = set()
        for ports in found_ports.values():
            all_ports.update(ports)
        ports_str = ','.join(map(str, sorted(all_ports)))
        
        # Создаем новую запись Scan
        new_scan = Scan(
            target=target,
            scan_type='nmap',
            profile='custom',
            status='pending',
            progress=0.0,
            created_at=datetime.utcnow()
        )
        db.add(new_scan)
        await db.flush()  # Получаем ID
        
        # Создаем задачу ScanJob
        new_job = ScanJob(
            scan_id=new_scan.id,
            job_type='nmap',
            status='pending',
            priority=5,
            created_at=datetime.utcnow(),
            parameters={
                'target': target,
                'ports': ports_str,
                'custom_args': nmap_args or '',
                'source': 'rustscan_auto'
            }
        )
        db.add(new_job)
        await db.commit()
        
        logger.info(f"[Rustscan] Создана задача Nmap (job_id={new_job.id}) для портов: {ports_str}")
        
        # Запускаем задачу немедленно через ScanQueueManager
        from backend.services.scan_queue_manager import scan_queue_manager
        # Добавляем задачу в очередь, откуда она будет подхвачена воркером
        asyncio.create_task(scan_queue_manager.add_scan_simple(
            job_id=new_job.id,
            scan_type='nmap',
            target=target,
            ports=ports_str,
            custom_args=nmap_args or ''
        ))
