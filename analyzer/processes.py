"""Procesos que más consumen, con opción de terminarlos.

Es la vista que uno abre cuando el equipo va lento y hoy obligaba a salir al
Administrador de tareas. Mide CPU sobre una ventana real (dos lecturas
separadas) en vez de devolver el acumulado desde el arranque, que no dice nada
sobre lo que está pasando ahora.
"""

import os
import time

import psutil

# Procesos que Windows necesita para seguir en pie. Terminarlos provoca un
# pantallazo azul o un reinicio forzado, así que ni se ofrecen.
PROTECTED = {
    "system", "system idle process", "registry", "memory compression",
    "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "svchost.exe", "fontdrvhost.exe", "dwm.exe", "sihost.exe",
    "ctfmon.exe", "explorer.exe",
}

# El "proceso inactivo" contabiliza la CPU que NO se está usando: aparecería
# siempre el primero con un 80-90% y no significa nada.
IGNORED = {"system idle process", "idle", "memory compression"}

# Ventana de medición de CPU. Suficiente para distinguir un pico real de un
# parpadeo, sin dejar la petición colgada.
SAMPLE_SECONDS = 0.6

# Umbrales sobre el total de la máquina, no sobre un núcleo.
CPU_WARN, CPU_DANGER = 15.0, 40.0
RAM_WARN, RAM_DANGER = 8.0, 20.0


def _classify(cpu: float, ram: float) -> str:
    if cpu >= CPU_DANGER or ram >= RAM_DANGER:
        return "danger"
    if cpu >= CPU_WARN or ram >= RAM_WARN:
        return "warning"
    return "ok"


def _sample() -> list[dict]:
    """Dos lecturas separadas para obtener el uso de CPU del intervalo."""
    procs = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if (p.info.get("name") or "").lower() in IGNORED:
                continue
            p.cpu_percent(None)   # primera lectura: fija el punto de partida
            procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(SAMPLE_SECONDS)

    cores = psutil.cpu_count() or 1
    total_ram = psutil.virtual_memory().total
    rows = []
    for p in procs:
        try:
            with p.oneshot():
                # psutil devuelve % sobre un núcleo; se normaliza al total.
                cpu = p.cpu_percent(None) / cores
                mem = p.memory_info().rss
                rows.append({
                    "pid":  p.pid,
                    "name": p.info.get("name") or f"PID {p.pid}",
                    "cpu":  round(cpu, 1),
                    "ram_mb": round(mem / (1024 * 1024), 1),
                    "ram_pct": round(mem / total_ram * 100, 1) if total_ram else 0.0,
                    "exe":  _safe_exe(p),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return rows


def _safe_exe(proc) -> str:
    try:
        return proc.exe() or ""
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return ""


def analyze_processes(limit: int = 10) -> dict:
    rows = _sample()
    if not rows:
        return {
            "status": "warning",
            "title": "Procesos activos",
            "summary": "No se pudo leer la lista de procesos.",
            "issue_count": 0,
            "items": [],
        }

    # Un proceso puede destacar por CPU o por RAM; se unen ambos rankings.
    by_cpu = sorted(rows, key=lambda r: r["cpu"], reverse=True)[:limit]
    by_ram = sorted(rows, key=lambda r: r["ram_mb"], reverse=True)[:limit]

    seen, top = set(), []
    for r in by_cpu + by_ram:
        if r["pid"] in seen:
            continue
        seen.add(r["pid"])
        top.append(r)
    top.sort(key=lambda r: (r["cpu"], r["ram_pct"]), reverse=True)

    items, issues = [], 0
    for r in top:
        status = _classify(r["cpu"], r["ram_pct"])
        if status != "ok":
            issues += 1

        protegido = r["name"].lower() in PROTECTED
        if status == "danger":
            msg = "Está consumiendo una parte importante del equipo ahora mismo."
        elif status == "warning":
            msg = "Consumo notable, aunque dentro de lo razonable."
        else:
            msg = "Consumo normal."

        items.append({
            "name":    r["name"],
            "status":  status,
            "message": msg,
            "value":   f"{r['cpu']:.1f}% CPU · {r['ram_mb']:.0f} MB",
            "detail":  r["exe"] or "Ruta no accesible",
            # Campos extra que consume el frontend para el botón de terminar
            "pid":       r["pid"],
            "cpu":       r["cpu"],
            "ram_mb":    r["ram_mb"],
            "ram_pct":   r["ram_pct"],
            "protected": protegido,
        })

    if issues == 0:
        summary = f"Ningún proceso está acaparando el equipo. {len(rows)} procesos en ejecución."
        status = "ok"
    else:
        peor = items[0]
        summary = (f"{issues} proceso(s) con consumo alto. El que más pide es "
                   f"{peor['name']} ({peor['cpu']:.1f}% CPU, {peor['ram_mb']:.0f} MB).")
        status = "danger" if any(i["status"] == "danger" for i in items) else "warning"

    return {
        "status": status,
        "title": "Procesos activos",
        "summary": summary,
        "issue_count": issues,
        "items": items,
        "total_processes": len(rows),
    }


def kill_process(pid) -> dict:
    """Termina un proceso. Operación de escritura: la confirma la UI."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return {"success": False, "message": "PID no válido."}

    if pid <= 4:
        return {"success": False, "message": "Ese PID pertenece al núcleo de Windows."}
    if pid == os.getpid():
        return {"success": False, "message": "Ese es el propio PC Guardian."}

    try:
        proc = psutil.Process(pid)
        name = proc.name()
    except psutil.NoSuchProcess:
        return {"success": False, "message": "El proceso ya no existe."}
    except psutil.AccessDenied:
        return {"success": False, "message": "Sin permisos para acceder a ese proceso. Reinicia PC Guardian como administrador."}

    if name.lower() in PROTECTED:
        return {"success": False,
                "message": f"'{name}' es un proceso crítico de Windows. Terminarlo provocaría un cierre forzado del sistema."}

    try:
        proc.terminate()
        try:
            proc.wait(timeout=4)          # cierre limpio
        except psutil.TimeoutExpired:
            proc.kill()                   # no colaboró
            proc.wait(timeout=3)
    except psutil.AccessDenied:
        return {"success": False,
                "message": f"Windows no permite terminar '{name}' sin privilegios de administrador."}
    except psutil.NoSuchProcess:
        pass
    except Exception as exc:
        return {"success": False, "message": str(exc)}

    return {"success": True, "message": f"Proceso '{name}' (PID {pid}) terminado."}
