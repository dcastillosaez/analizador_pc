"""Mantenimiento — salud del disco, uptime y tareas programadas."""
import csv
import datetime
import io
import json
import threading

import psutil

from ._shell import run, run_ps


_PS_DISKS = r"""
try {
  Get-PhysicalDisk -EA Stop |
  Select-Object FriendlyName, MediaType, HealthStatus, OperationalStatus,
    @{N='SizeGB';E={[math]::Round($_.Size/1GB)}} |
  ConvertTo-Json -Compress
} catch { '[]' }
"""


def _run_ps(script: str, timeout: int = 12) -> str:
    return run_ps(script, timeout=timeout).stdout.strip()


def _run_schtasks(timeout: int = 10) -> list[str]:
    return run(["schtasks", "/query", "/fo", "CSV", "/nh"], timeout=timeout).stdout.splitlines()


def _check_disks(raw: str) -> list[dict]:
    try:
        data = json.loads(raw) if raw else []
        if isinstance(data, dict):
            data = [data]
    except Exception:
        return [{"name": "Salud del disco", "status": "warning",
            "message": "No se pudo leer el estado SMART de los discos.",
            "value": "Sin datos", "detail": ""}]

    items: list[dict] = []
    for d in data:
        name = d.get("FriendlyName", "Disco")
        health = (d.get("HealthStatus") or "").lower()
        media = d.get("MediaType", "")
        size = d.get("SizeGB", "?")
        detail = f"{media} · {size} GB"

        if health in ("unhealthy", "warning"):
            items.append({"name": name, "status": "danger",
                "message": f"'{name}' tiene salud deficiente ({health}). Haz una copia de seguridad urgente antes de que falle.",
                "value": health.capitalize(), "detail": detail})
        elif health == "healthy":
            items.append({"name": name, "status": "ok",
                "message": f"'{name}' en buen estado de salud.",
                "value": "Saludable", "detail": detail})
        else:
            items.append({"name": name, "status": "warning",
                "message": f"No se pudo determinar el estado de '{name}'.",
                "value": health or "?", "detail": detail})
    return items


def _check_uptime() -> list[dict]:
    try:
        delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
        days, hours = delta.days, delta.seconds // 3600
        boot_str = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%d/%m/%Y %H:%M")
        val = f"{days}d {hours}h"
        detail = f"Último reinicio: {boot_str}"
        if days >= 14:
            return [{"name": "Tiempo sin reiniciar", "status": "warning",
                "message": f"Tu PC lleva {days} días sin reiniciarse. Las actualizaciones y parches de seguridad no se aplican hasta que reinicias.",
                "value": val, "detail": detail}]
        if days >= 7:
            return [{"name": "Tiempo sin reiniciar", "status": "warning",
                "message": f"Llevas {days} días sin reiniciar. Considera hacerlo pronto.",
                "value": val, "detail": detail}]
        return [{"name": "Tiempo sin reiniciar", "status": "ok",
            "message": f"Frecuencia de reinicio correcta ({days} días, {hours} horas).",
            "value": val, "detail": detail}]
    except Exception:
        return []


SUSP_PATHS = ("\\temp\\", "appdata\\roaming\\", "\\tmp\\", "users\\public\\")

def _check_schtasks(lines: list[str]) -> list[dict]:
    suspicious: list[str] = []
    for line in lines:
        try:
            row = next(csv.reader(io.StringIO(line)))
            if len(row) < 2:
                continue
            name = row[0].strip('"')
            action = row[1].strip('"').lower().replace("/", "\\")
            if any(kw in action for kw in SUSP_PATHS):
                suspicious.append(name)
        except Exception:
            continue

    if suspicious:
        return [{"name": f"Tarea: {t}", "status": "danger",
            "message": f"La tarea programada '{t}' ejecuta archivos desde una ruta sospechosa. Es una técnica habitual de malware para persistir en el sistema.",
            "value": "Sospechosa", "detail": ""} for t in suspicious[:5]]
    return [{"name": "Tareas programadas", "status": "ok",
        "message": "No se detectaron tareas programadas con rutas sospechosas.",
        "value": "Sin alertas", "detail": ""}]


def analyze_maintenance() -> dict:
    disk_raw: list[str] = [""]
    schtasks_lines: list[str] = []

    def fetch_disks():
        disk_raw[0] = _run_ps(_PS_DISKS, timeout=12)

    def fetch_tasks():
        nonlocal schtasks_lines
        schtasks_lines = _run_schtasks(timeout=10)

    t1 = threading.Thread(target=fetch_disks, daemon=True)
    t2 = threading.Thread(target=fetch_tasks, daemon=True)
    t1.start(); t2.start()
    t1.join(timeout=14); t2.join(timeout=12)

    items: list[dict] = []
    items += _check_disks(disk_raw[0])
    items += _check_uptime()
    items += _check_schtasks(schtasks_lines)

    danger  = sum(1 for i in items if i["status"] == "danger")
    warning = sum(1 for i in items if i["status"] == "warning")
    overall = "danger" if danger else ("warning" if warning else "ok")

    summaries = {
        "danger":  f"{danger} problema(s) crítico(s) de mantenimiento detectados.",
        "warning": f"{warning} aspecto(s) de mantenimiento requieren atención.",
        "ok":      "Discos saludables, sin tareas sospechosas y reinicio reciente.",
    }
    return {"status": overall, "title": "Mantenimiento", "summary": summaries[overall],
            "issue_count": danger + warning, "items": items}
