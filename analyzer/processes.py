"""Top procesos por CPU/RAM — psutil. Kill on demand."""
import psutil

_SYSTEM_PROCS = {
    'System', 'Registry', 'smss.exe', 'csrss.exe', 'wininit.exe',
    'services.exe', 'lsass.exe', 'MsMpEng.exe', 'svchost.exe',
}


def get_top_processes() -> dict:
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent',
                                   'memory_info', 'username']):
        try:
            info = p.info
            if info['pid'] in (0, 4):
                continue
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(
        key=lambda p: (p.get('cpu_percent') or 0) + (p.get('memory_percent') or 0) * 2,
        reverse=True,
    )

    items = []
    for info in procs[:15]:
        cpu  = round(info.get('cpu_percent') or 0, 1)
        mem  = round(info.get('memory_percent') or 0, 1)
        name = info.get('name') or 'desconocido'
        pid  = info.get('pid', 0)
        mi   = info.get('memory_info')
        mb   = (mi.rss // (1024 * 1024)) if mi else 0

        if cpu > 30 or mem > 25:
            st = 'danger'
        elif cpu > 10 or mem > 10:
            st = 'warning'
        else:
            st = 'ok'

        items.append({
            'name':     name,
            'status':   st,
            'message':  f'CPU {cpu:.1f}%  ·  RAM {mem:.1f}% ({mb} MB)',
            'value':    f'PID {pid}',
            'detail':   info.get('username') or '',
            'pid':      pid,
            'cpu':      cpu,
            'mem_mb':   mb,
            'killable': name not in _SYSTEM_PROCS and pid > 4,
        })

    danger  = sum(1 for i in items if i['status'] == 'danger')
    warning = sum(1 for i in items if i['status'] == 'warning')
    overall = 'danger' if danger else ('warning' if warning else 'ok')

    if not items:
        summary = 'No se pudieron obtener procesos.'
        overall = 'warning'
    elif danger:
        summary = f'{danger} proceso(s) con consumo elevado de CPU o RAM.'
    elif warning:
        summary = f'{warning} proceso(s) con consumo moderado detectado.'
    else:
        summary = f'{len(items)} procesos analizados — consumo normal.'

    return {
        'status':      overall,
        'title':       'Procesos activos',
        'summary':     summary,
        'issue_count': danger + warning,
        'items':       items,
    }


def kill_process(pid: int) -> dict:
    if pid <= 4:
        return {'ok': False, 'msg': 'No se puede terminar procesos del sistema.'}
    try:
        p    = psutil.Process(pid)
        name = p.name()
        p.terminate()
        return {'ok': True, 'msg': f'Proceso {name} (PID {pid}) terminado.'}
    except psutil.NoSuchProcess:
        return {'ok': False, 'msg': f'El proceso PID {pid} ya no existe.'}
    except psutil.AccessDenied:
        return {'ok': False, 'msg': 'Permiso denegado — ejecuta como administrador.'}
    except Exception as e:
        return {'ok': False, 'msg': str(e)[:120]}
