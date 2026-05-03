"""
Асинхронный модуль сканирования Rustscan для интеграции с ScanQueueManager.
"""
import asyncio
import os
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.scan import ScanJob, ScanResult
from backend.models.asset import Asset
from backend.models.group import AssetGroup
from backend.utils import MOSCOW_TZ
from backend.services.asset_manager import upsert_asset, update_asset_ports


logger = logging.getLogger(__name__)


class RustscanScanner:
    """Асинхронный класс для выполнения сканирования через Rustscan"""
    
    async def scan(
        self,
        db: AsyncSession,
        job_id: int,
        target: str,
        ports: str = '',
        custom_args: str = '',
        run_nmap_after: bool = False,
        nmap_args: str = '',
        group_ids: Optional[List[int]] = None
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
            
            logger.info(f"[RustscanScanner] Запущен процесс Rustscan для задачи {job_id}, PID: {process.pid}")
            
            output_lines = []
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_decoded = line.decode('utf-8', errors='ignore').strip()
                if line_decoded:
                    logger.debug(f"[Rustscan] {line_decoded}")
                output_lines.append(line_decoded)
            
            await process.wait()
            
            logger.info(f"[RustscanScanner] Процесс Rustscan завершен с кодом {process.returncode}")
            
            if process.returncode != 0:
                raise Exception(f"Rustscan завершился с кодом {process.returncode}")
            
            # Парсим вывод для получения портов
            found_ports = self._parse_output(output_lines)
            
            # Обновляем активы
            await self._update_assets(db, final_targets.split(), found_ports)
            
            # Если указан флаг run_nmap_after, запускаем Nmap с найденными портами
            if run_nmap_after and found_ports:
                logger.info(f"[Rustscan] Запуск Nmap после завершения сканирования для {target}")
                nmap_result = await self._run_nmap_after(
                    db=db,
                    job_id=job_id,
                    target=target,
                    found_ports=found_ports,
                    nmap_args=nmap_args,
                    group_ids=group_ids
                )
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "result": {
                        "hostname": target,
                        "ports": list(found_ports.values()) if found_ports else []
                    },
                    "raw_output": '\n'.join(output_lines),
                    "nmap_result": nmap_result
                }
            
            # Сохраняем результат
            scan_result = ScanResult(
                scan_job_id=job_id,
                ip_address=final_targets,
                ports=list(found_ports.values()),
                raw_output='\n'.join(output_lines),
                scanned_at=datetime.now()
            )
            db.add(scan_result)
            
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
                    "ports": list(found_ports.values()) if found_ports else []
                },
                "raw_output": '\n'.join(output_lines)
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
    
    async def _run_nmap_after(
        self,
        db: AsyncSession,
        job_id: int,
        target: str,
        found_ports: Dict[str, List[int]],
        nmap_args: str = '',
        group_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Запуск Nmap после Rustscan с найденными портами."""
        from backend.scanner.nmap.nmap_async import NmapScanner
        
        # Получаем порты для целевого хоста
        target_ports = found_ports.get(target, [])
        if not target_ports:
            # Пытаемся найти порты по другим ключам (IP может быть в другом формате)
            for ip, ports in found_ports.items():
                if ip in target or target in ip:
                    target_ports = ports
                    break
        
        if not target_ports:
            logger.warning(f"[Rustscan->Nmap] Не найдено портов для {target}")
            return {"status": "skipped", "reason": "no_ports"}
        
        # Формируем строку портов для nmap
        ports_str = ','.join(map(str, target_ports))
        logger.info(f"[Rustscan->Nmap] Запуск Nmap для {target} с портами: {ports_str}")
        
        # Создаем Nmap сканер и запускаем
        nmap_scanner = NmapScanner()
        
        try:
            result = await nmap_scanner.scan(
                db=db,
                job_id=job_id,
                target=target,
                ports=ports_str,
                scripts='',
                custom_args=nmap_args,
                known_ports_only=False,
                group_ids=group_ids
            )
            logger.info(f"[Rustscan->Nmap] Nmap завершен для {target}")
            return result
        except Exception as e:
            logger.error(f"[Rustscan->Nmap] Ошибка при запуске Nmap: {e}")
            return {"status": "failed", "error": str(e)}
    
    async def _update_assets(self, db, targets, found_ports):
        """Обновление активов с найденными портами с использованием унифицированных функций."""
        
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
