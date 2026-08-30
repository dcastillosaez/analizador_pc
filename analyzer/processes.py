"""Top procesos por CPU/RAM — psutil. Kill on demand."""
import os
import time

import psutil

_SYSTEM_PROCS = {
    'System', 'Registry', 'smss.exe', 'csrss.exe', 'wininit.exe',
    'services.exe', 'lsass.exe', 'MsMpEng.exe', 'svchost.exe',
}

# El "proceso inactivo" contabiliza la CPU que NO se está usando: aparecería
# siempre el primero con un 80-90% y no significa nada.
_IGNORED = {'system idle process', 'idle', 'memory compression'}

# Ventana de medición de CPU. psutil devuelve el acumulado desde el arranque del
# proceso en la primera lectura, que en la práctica sale 0.0 para todos; hay que
# leer dos veces separadas para obtener el uso real del intervalo.
_SAMPLE_SECONDS = 0.6


def _safe_user(proc) -> str:
    try:
        return proc.username() or ''
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return ''


def _sample() -> list[dict]:
    """Dos lecturas separadas para medir la CPU del intervalo, no el acumulado."""
    vistos = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            if p.info['pid'] in (0, 4):
                continue
            if (p.info.get('name') or '').lower() in _IGNORED:
                continue
            p.cpu_percent(None)          # primera lectura: fija el punto de partida
            vistos.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(_SAMPLE_SECONDS)

    cores = psutil.cpu_count() or 1
    filas = []
    for p in vistos:
        try:
            with p.oneshot():
                filas.append({
                    'pid':            p.pid,
                    'name':           p.name(),
                    # psutil da el % sobre un núcleo; se normaliza al total.
                    'cpu_percent':    p.cpu_percent(None) / cores,
                    'memory_percent': p.memory_percent(),
                    'memory_info':    p.memory_info(),
                    'username':       _safe_user(p),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return filas


def _is_killable(name: str, pid: int) -> bool:
    """Regla única para el listado y para el endpoint.

    Antes vivía solo en el listado, así que el botón desaparecía en pantalla
    pero /api/processes/<pid>/kill seguía aceptando el PID de lsass.exe, que
    provoca un cierre forzado de Windows.
    """
    return name not in _SYSTEM_PROCS and pid > 4 and pid != os.getpid()


def get_top_processes() -> dict:
    procs = _sample()

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
            'killable': _is_killable(name, pid),
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
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return {'ok': False, 'msg': 'PID no válido.'}

    if pid <= 4:
        return {'ok': False, 'msg': 'No se puede terminar procesos del sistema.'}
    if pid == os.getpid():
        return {'ok': False, 'msg': 'Ese es el propio PC Guardian.'}

    try:
        p    = psutil.Process(pid)
        name = p.name()
    except psutil.NoSuchProcess:
        return {'ok': False, 'msg': f'El proceso PID {pid} ya no existe.'}
    except psutil.AccessDenied:
        return {'ok': False, 'msg': 'Permiso denegado — ejecuta como administrador.'}

    # La comprobación se repite aquí a propósito: el listado solo oculta el
    # botón, y la ruta acepta cualquier PID que le llegue.
    if not _is_killable(name, pid):
        return {'ok': False,
                'msg': f'{name} es un proceso crítico de Windows. '
                       'Terminarlo forzaría el cierre del sistema.'}

    try:
        p.terminate()
        try:
            p.wait(timeout=4)        # cierre limpio
        except psutil.TimeoutExpired:
            p.kill()                 # no colaboró
            p.wait(timeout=3)
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        return {'ok': False, 'msg': 'Permiso denegado — ejecuta como administrador.'}
    except Exception as e:
        return {'ok': False, 'msg': str(e)[:120]}

    return {'ok': True, 'msg': f'Proceso {name} (PID {pid}) terminado.'}
