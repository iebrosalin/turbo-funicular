import re, json

OSQUERY_SCHEMA = {
    "system_info": ["hostname", "cpu_brand", "cpu_type", "cpu_logical_cores", "cpu_physical_cores", "physical_memory", "hardware_vendor", "hardware_model"],
    "os_version": ["name", "version", "major", "minor", "patch", "build", "platform", "platform_like", "codename"],
    "processes": ["pid", "name", "path", "cmdline", "state", "parent", "uid", "gid", "start_time", "resident_size", "total_size"],
    "users": ["uid", "gid", "username", "description", "directory", "shell", "uuid"],
    "network_connections": ["pid", "local_address", "local_port", "remote_address", "remote_port", "state", "protocol", "family"],
    "listening_ports": ["pid", "port", "address", "protocol", "family"],
    "kernel_info": ["version", "arguments", "path", "device", "driver"],
    "uptime": ["days", "hours", "minutes", "seconds", "total_seconds"],
    "hash": ["path", "md5", "sha1", "sha256", "ssdeep", "file_size"],
    "file": ["path", "filename", "directory", "mode", "type", "size", "last_accessed", "last_modified", "last_status_change", "uid", "gid"],
    "crontab": ["uid", "minute", "hour", "day_of_month", "month", "day_of_week", "command", "path"],
    "logged_in_users": ["type", "user", "tty", "host", "time", "pid"],
    "routes": ["destination", "gateway", "mask", "mtu", "metric", "type", "flags", "interface"],
    "groups": ["gid", "groupname"]
}

def validate_osquery_query(query):
    errors, warnings = [], []
    query = query.strip().rstrip(';')
    if not re.match(r'(?i)^\s*SELECT\s+', query): errors.append("Запрос должен начинаться с SELECT"); return errors, warnings
    from_match = re.search(r'(?i)\bFROM\s+([\w\.]+)', query)
    if not from_match: errors.append("Отсутствует таблица в FROM"); return errors, warnings
    table_name = from_match.group(1).split('.')[0].lower()
    select_match = re.search(r'(?i)SELECT\s+(.*?)\s+FROM', query, re.DOTALL)
    if not select_match: errors.append("Не удалось извлечь список колонок"); return errors, warnings
    cols_str = select_match.group(1).strip()
    if cols_str == '*': warnings.append("Использование SELECT * не рекомендуется"); return errors, warnings
    cols = [c.strip().split(' as ')[0].split(' AS ')[0].strip().split('(')[-1] for c in cols_str.split(',')]
    cols = [c for c in cols if c and c != ')']
    if table_name in OSQUERY_SCHEMA:
        valid_cols = [vc.lower() for vc in OSQUERY_SCHEMA[table_name]]
        for col in cols:
            if '(' in col or col.lower() in ['true', 'false']: continue
            if col.lower() not in valid_cols: errors.append(f"Колонка '{col}' не найдена в таблице '{table_name}'")
    else: warnings.append(f"Таблица '{table_name}' отсутствует в словаре валидации.")
    return errors, warnings

def validate_osquery_config(config_dict):
    errors, warnings = [], []
    for sec in ["options", "schedule"]:
        if sec not in config_dict: errors.append(f"Отсутствует обязательный раздел: '{sec}'")
    if errors: return errors, warnings
    for name, query_obj in config_dict.get("schedule", {}).items():
        if not isinstance(query_obj, dict) or "query" not in query_obj: errors.append(f"schedule.{name}: некорректная структура"); continue
        q_errors, q_warnings = validate_osquery_query(query_obj["query"])
        for e in q_errors: errors.append(f"schedule.{name}: {e}")
        for w in q_warnings: warnings.append(f"schedule.{name}: {w}")
    return errors, warnings
