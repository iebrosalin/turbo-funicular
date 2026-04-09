from datetime import datetime, timezone, timedelta

# 🔥 Московское время (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))

def to_moscow_time(dt):
    """Конвертирует datetime в московское время"""
    if not dt:
        return None
    if dt.tzinfo is None:
        # Если время без timezone, считаем что это UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MOSCOW_TZ)

def format_moscow_time(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """Форматирует datetime в строку с московским временем"""
    if not dt:
        return '—'
    moscow_dt = to_moscow_time(dt)
    return moscow_dt.strftime(format_str)