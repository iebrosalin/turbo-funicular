"""
Асинхронный модуль сканирования Dig для интеграции с ScanQueueManager.
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.scan import ScanJob, ScanResult
from backend.models.asset import Asset
from backend.utils import MOSCOW_TZ
from backend.services.asset_manager import upsert_asset


class DigScanner:
    """Асинхронный класс для выполнения запросов через Dig"""
    
    async def scan(
        self,
        db: AsyncSession,
        job_id: int,
        target: str,
        record_type: str = 'A',
        custom_args: str = '',
        group_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Запуск запроса Dig."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[Dig DEBUG] scan вызван: job_id={job_id}, target={target}, record_type={record_type}")
        
        try:
            logger.info(f"[Dig DEBUG] Попытка получения задачи {job_id} из БД")
            job = await db.get(ScanJob, job_id)
            if not job:
                logger.error(f"[Dig DEBUG] Задача {job_id} не найдена в БД")
                raise ValueError(f"Задача сканирования {job_id} не найдена")
            
            logger.info(f"[Dig DEBUG] Задача найдена, статус: {job.status}")
            job.status = 'running'
            job.started_at = datetime.utcnow()
            await db.commit()
            logger.info(f"[Dig DEBUG] Статус задачи обновлён на 'running'")
            
            cmd = self._build_command(target, record_type, custom_args)
            logger.info(f"[Dig DEBUG] Команда dig: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            logger.info(f"[Dig DEBUG] Процесс запущен, PID: {process.pid}")
            
            output_lines = []
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_decoded = line.decode().strip()
                output_lines.append(line_decoded)
                logger.debug(f"[Dig DEBUG] Вывод dig: {line_decoded}")
            
            await process.wait()
            logger.info(f"[Dig DEBUG] Процесс завершен с кодом: {process.returncode}")
            
            if process.returncode != 0:
                logger.error(f"[Dig DEBUG] Dig завершился с ошибкой, код: {process.returncode}")
                raise Exception(f"Dig завершился с кодом {process.returncode}")
            
            # Парсим вывод
            parsed_result = self._parse_output(output_lines, record_type)
            logger.info(f"[Dig DEBUG] Результат парсинга: {parsed_result}")
            
            # Извлекаем IP адреса из результатов для создания актива
            ip_addresses = self._extract_ips(parsed_result)
            
            logger.info(f"[Dig] Найдено IP-адресов для создания активов: {len(ip_addresses)}")
            logger.info(f"[Dig DEBUG] IP-адреса: {ip_addresses}")
            
            # Создаём активы для найденных IP с использованием унифицированной функции
            created_assets = []
            for ip in ip_addresses:
                logger.info(f"[Dig DEBUG] Создание актива для IP: {ip}")
                try:
                    asset = await upsert_asset(
                        db=db,
                        ip_address=ip,
                        hostname=target,
                        scanner_name="Dig",
                        group_ids=group_ids
                    )
                    logger.info(f"[Dig] Создан/обновлен актив: {ip} (hostname: {target}, asset_id: {asset.id})")
                    created_assets.append(asset)
                except Exception as e:
                    logger.error(f"[Dig DEBUG] Ошибка создания актива для {ip}: {e}")
                    import traceback
                    logger.error(f"[Dig DEBUG] Трассировка: {traceback.format_exc()}")
            
            # Коммитим создание активов
            logger.info(f"[Dig DEBUG] Попытка коммита {len(created_assets)} активов в БД")
            try:
                await db.commit()
                logger.info(f"[Dig DEBUG] Активы успешно закоммичены в БД")
            except Exception as e:
                logger.error(f"[Dig DEBUG] Ошибка коммита: {e}")
                import traceback
                logger.error(f"[Dig DEBUG] Трассировка: {traceback.format_exc()}")
                await db.rollback()
                logger.info(f"[Dig DEBUG] Выполнен rollback транзакции")
            
            # Сохраняем результат сканирования
            # Получаем scan_id из job
            job = await db.get(ScanJob, job_id)
            current_scan_id = job.scan_id if job else None
            
            logger.info(f"[Dig DEBUG] Создание ScanResult: scan_id={current_scan_id}, job_id={job_id}")
            scan_result = ScanResult(
                scan_id=current_scan_id,
                scan_job_id=job_id,
                ip_address=target,
                hostname=target,
                ports=[],
                raw_output='\n'.join(output_lines),
                status='success',
                scanned_at=datetime.now(MOSCOW_TZ)
            )
            db.add(scan_result)
            logger.info(f"[Dig DEBUG] ScanResult добавлен в сессию БД")
            
            job = await db.get(ScanJob, job_id)
            if job:
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                job.progress = 100.0
                await db.commit()
                logger.info(f"[Dig DEBUG] Задача {job_id} помечена как completed и закоммичена")
            
            logger.info(f"[Dig] Сканирование {job_id} завершено: найдено {len(ip_addresses)} IP")
            return {
                "status": "completed",
                "job_id": job_id,
                "result": parsed_result,
                "raw_output": '\n'.join(output_lines)
            }
            
        except asyncio.CancelledError:
            logger.info(f"[Dig DEBUG] Задача {job_id} отменена")
            job = await db.get(ScanJob, job_id)
            if job:
                job.status = 'stopped'
                await db.commit()
            raise
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"[Dig DEBUG] Ошибка при сканировании {job_id}: {e}")
            logger.error(f"[Dig DEBUG] Трассировка: {error_traceback}")
            job = await db.get(ScanJob, job_id)
            if job:
                job.status = 'failed'
                job.error_message = str(e)
                await db.commit()
                logger.info(f"[Dig DEBUG] Задача {job_id} помечена как failed")
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
        import logging
        logger = logging.getLogger(__name__)
        
        ips = []
        answers = parsed_result.get('answers', [])
        
        for answer in answers:
            data = answer.get('data', '')
            rec_type = answer.get('type', '')
            
            # Для записей A и AAAA - извлекаем IP напрямую
            if rec_type in ['A', 'AAAA']:
                if ':' in data or (data.count('.') == 3 and all(p.isdigit() for p in data.split('.'))):
                    ips.append(data)
            # Для записей MX, NS - пытаемся извлечь доменное имя для последующего резолва
            elif rec_type in ['MX', 'NS', 'CNAME']:
                # Извлекаем доменное имя из данных записи
                parts = data.split()
                if parts:
                    hostname = parts[-1].rstrip('.')
                    logger.info(f"[Dig] Найдена запись {rec_type}: {hostname}")
        
        logger.info(f"[Dig] Извлечено IP-адресов: {len(ips)}")
        return ips
