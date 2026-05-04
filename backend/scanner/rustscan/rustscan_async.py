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
        # Используем абсолютный путь для директории вывода
        output_dir = os.path.join('/app', 'scanner_output', str(job_id))
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.join(output_dir, 'rustscan')
        raw_output_file = os.path.join(output_dir, 'rustscan.txt')
        
        try:
            job = await db.get(ScanJob, job_id)
            if not job:
                raise ValueError(f"Задача сканирования {job_id} не найдена")
            
            job.status = 'running'
            job.started_at = datetime.utcnow()
            await db.commit()
            
            final_targets = await self._prepare_targets(db, target, group_ids)
            cmd = self._build_command(final_targets, ports, custom_args, base_name)
            
            logger.info(f"[RustscanScanner] Запуск команды: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            logger.info(f"[RustscanScanner] Запущен процесс Rustscan для задачи {job_id}, PID: {process.pid}")
            
            # Собираем вывод и одновременно записываем в файл
            output_lines = []
            json_lines = []
            grepable_lines = []
            
            with open(raw_output_file, 'w', encoding='utf-8') as f:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    line_decoded = line.decode('utf-8', errors='ignore').strip()
                    if line_decoded:
                        logger.debug(f"[Rustscan] {line_decoded}")
                        f.write(line_decoded + '\n')
                        f.flush()  # Гарантируем запись на диск
                        output_lines.append(line_decoded)
                        
                        # Пытаемся определить тип строки для разделения по форматам
                        # JSON вывод обычно начинается с { или [
                        if line_decoded.startswith('{') or line_decoded.startswith('['):
                            json_lines.append(line_decoded)
                        # Grepable формат обычно содержит IP и порты в формате IP -> Port
                        elif '->' in line_decoded:
                            grepable_lines.append(line_decoded)
            
            await process.wait()
            
            logger.info(f"[RustscanScanner] Процесс Rustscan завершен с кодом {process.returncode}")
            
            if process.returncode != 0:
                raise Exception(f"Rustscan завершился с кодом {process.returncode}")
            
            # Парсим вывод для получения портов
            found_ports = self._parse_output(output_lines)
            
            # Создаём файлы для разных форматов из stdout
            # JSON файл
            json_output_file = os.path.join(output_dir, 'rustscan.json')
            with open(json_output_file, 'w', encoding='utf-8') as f:
                if json_lines:
                    f.write('\n'.join(json_lines))
                else:
                    # Если JSON не найден в выводе, создаём его из распарсенных данных
                    import json as json_module
                    f.write(json_module.dumps(found_ports if found_ports else {}))
            
            # Grepable файл
            grepable_output_file = os.path.join(output_dir, 'rustscan_grepable.txt')
            with open(grepable_output_file, 'w', encoding='utf-8') as f:
                if grepable_lines:
                    f.write('\n'.join(grepable_lines))
                else:
                    # Если grepable не найден, создаём из распарсенных данных
                    for ip, ports in (found_ports if found_ports else {}).items():
                        f.write(f"{ip} -> {','.join(map(str, ports))}\n")
            
            # Обновляем активы с найденными портами
            await self._update_assets(db, found_ports)
            
            # Если указан флаг run_nmap_after, запускаем Nmap после завершения сканирования
            if run_nmap_after and found_ports:
                logger.info(f"[Rustscan] Запуск Nmap после завершения сканирования")
                # Запускаем nmap для каждого найденного IP
                nmap_results = {}
                for ip, ports in found_ports.items():
                    ports_str = ','.join(map(str, ports))
                    logger.info(f"[Rustscan->Nmap] Запуск Nmap для {ip} с портами: {ports_str}")
                    from backend.scanner.nmap.nmap_async import NmapScanner
                    nmap_scanner = NmapScanner()
                    try:
                        result = await nmap_scanner.scan(
                            db=db,
                            job_id=job_id,
                            target=ip,
                            ports=ports_str,
                            scripts='',
                            custom_args=nmap_args,
                            known_ports_only=False,
                            group_ids=group_ids
                        )
                        nmap_results[ip] = result
                    except Exception as e:
                        logger.error(f"[Rustscan->Nmap] Ошибка при запуске Nmap для {ip}: {e}")
                        nmap_results[ip] = {"status": "failed", "error": str(e)}
                
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "result": {
                        "hostname": target,
                        "ports": {ip: ports for ip, ports in found_ports.items()}
                    },
                    "raw_output": '\n'.join(output_lines),
                    "output_file": raw_output_file,
                    "nmap_result": nmap_results
                }
            
            # Сохраняем результат сканирования для каждого найденного IP
            for ip, ports in found_ports.items():
                scan_result = ScanResult(
                    scan_job_id=job_id,
                    ip_address=ip,
                    ports=ports,
                    raw_output='\n'.join(output_lines),
                    scanned_at=datetime.now(MOSCOW_TZ)
                )
                db.add(scan_result)
            
            await db.commit()
            
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
                    "ports": found_ports if found_ports else {}
                },
                "raw_output": '\n'.join(output_lines),
                "output_file": raw_output_file
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
        # RustScan поддерживает следующие опции вывода через stdout:
        # --json - выводит результаты в JSON формате в stdout
        # Мы сохраняем stdout в raw файл, а затем парсим его для создания других форматов
        # Добавляем флаг --json для получения структурированного вывода
        cmd.append('--json')
        if custom_args:
            cmd.extend(custom_args.split())
        return cmd
    
    def _parse_output(self, output_lines):
        """Парсинг вывода rustscan для получения портов."""
        found_ports = {}
        
        for line in output_lines:
            if '->' in line:
                parts = line.split('->')
                if len(parts) == 2:
                    ip_part = parts[0].strip()
                    ports_part = parts[1].strip()
                    # Проверяем, что ports_part содержит цифры и запятые (список портов)
                    if ',' in ports_part or ports_part.isdigit():
                        port_list = [int(p.strip()) for p in ports_part.split(',') if p.strip().isdigit()]
                        if port_list and ip_part:
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
        """Запуск Nmap после Rustscan с найденными портами. Устаревший метод."""
        logger.warning("_run_nmap_after устарел и больше не используется")
        return {"status": "deprecated"}
    
    async def _update_assets(self, db, found_ports):
        """Обновление активов с найденными портами с использованием унифицированных функций."""
        
        for ip, ports in found_ports.items():
            # Создаем или обновляем актив
            asset = await upsert_asset(
                db=db,
                ip_address=ip,
                scanner_name="Rustscan"
            )
            
            # Обновляем порты
            update_asset_ports(asset, 'rustscan', ports, scanner_name="Rustscan")
        
        await db.commit()
