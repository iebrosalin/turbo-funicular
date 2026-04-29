"""
Асинхронный модуль сканирования Dig для интеграции с ScanQueueManager.
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.scan import ScanJob, ScanResult
from backend.models.asset import Asset
from backend.utils import create_asset_if_not_exists, MOSCOW_TZ


class DigScanner:
    """Асинхронный класс для выполнения запросов через Dig"""
    
    async def scan(
        self,
        db: AsyncSession,
        job_id: int,
        target: str,
        record_type: str = 'A',
        custom_args: str = ''
    ) -> Dict[str, Any]:
        """Запуск запроса Dig."""
        try:
            job = await db.get(ScanJob, job_id)
            if not job:
                raise ValueError(f"Задача сканирования {job_id} не найдена")
            
            job.status = 'running'
            job.started_at = datetime.utcnow()
            await db.commit()
            
            cmd = self._build_command(target, record_type, custom_args)
            print(f"🔍 Запуск Dig: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            output_lines = []
            async for line in process.stdout:
                line_decoded = line.decode().strip()
                output_lines.append(line_decoded)
                print(line_decoded)
            
            await process.wait()
            
            if process.returncode != 0:
                raise Exception(f"Dig завершился с кодом {process.returncode}")
            
            # Парсим вывод
            parsed_result = self._parse_output(output_lines, record_type)
            
            # Извлекаем IP адреса из результатов для создания актива
            ip_addresses = self._extract_ips(parsed_result)
            
            # Создаём активы для найденных IP
            for ip in ip_addresses:
                await create_asset_if_not_exists(
                    db=db,
                    ip_address=ip,
                    hostname=target
                )
            
            # Коммитим создание активов
            await db.commit()
            
            # Сохраняем результат сканирования
            scan_result = ScanResult(
                scan_job_id=job_id,
                ip_address=target,
                hostname=target,
                ports=[],
                raw_output='\n'.join(output_lines),
                status='success',
                scanned_at=datetime.now(MOSCOW_TZ)
            )
            db.add(scan_result)
            
            job = await db.get(ScanJob, job_id)
            if job:
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                job.progress = 100.0
                await db.commit()
            
            return {"status": "completed", "job_id": job_id, "result": parsed_result}
            
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
    
    def _build_command(self, target, record_type, custom_args):
        """Построение команды dig."""
        cmd = ['dig', target, record_type]
        if custom_args:
            cmd.extend(custom_args.split())
        return cmd
    
    def _parse_output(self, output_lines, record_type):
        """Парсинг вывода dig."""
        answers = []
        in_answer_section = False
        
        for line in output_lines:
            if 'ANSWER SECTION:' in line:
                in_answer_section = True
                continue
            
            if in_answer_section:
                if line.startswith(';') or not line.strip():
                    if line.startswith(';;'):
                        in_answer_section = False
                    continue
                
                parts = line.split()
                if len(parts) >= 5:
                    answers.append({
                        'name': parts[0],
                        'ttl': parts[1],
                        'class': parts[2],
                        'type': parts[3],
                        'data': ' '.join(parts[4:])
                    })
        
        return {'record_type': record_type, 'answers': answers}
    
    def _extract_ips(self, parsed_result: Dict[str, Any]) -> List[str]:
        """Извлечение IP адресов из результатов Dig."""
        ips = []
        answers = parsed_result.get('answers', [])
        
        for answer in answers:
            data = answer.get('data', '')
            rec_type = answer.get('type', '')
            if rec_type in ['A', 'AAAA']:
                if ':' in data or (data.count('.') == 3 and all(p.isdigit() for p in data.split('.'))):
                    ips.append(data)
        
        return ips
