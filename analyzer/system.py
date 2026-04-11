"""
Módulo: Estado General del Sistema
Una sola llamada PowerShell para todos los checks PS-dependientes.
Checks psutil/archivo son directos, sin subprocesos.
"""

import csv
import datetime
import io
import json
import os
import subprocess
import threading
import psutil

# ── Una sola llamada PowerShell ───────────────────────────────────────────────

_PS_ALL = r"""
$out = @{}

# Antivirus
try {
  $av = Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction Stop |
        Select-Object displayName, productState
  $out.antivirus = @($av)
} catch { $out.antivirus = @() }

# Firewall
try {
  $fw = Get-NetFirewallProfile -ErrorAction Stop | Select-Object Name, Enabled
  $out.firewall = @($fw)
} catch { $out.firewall = @() }

# Disco físico
try {
  $dk = Get-PhysicalDisk -ErrorAction Stop |
        Select-Object FriendlyName, MediaType, HealthStatus, OperationalStatus,
          @{N='SizeGB';E={[math]::Round($_.Size/1GB)}}
  $out.disks = @($dk)
} catch { $out.disks = @() }

$out | ConvertTo-Json -Compress -Depth 3
"""


def _run_ps_combined(timeout: int = 20) -> dict:
    try:
        r = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", _PS_ALL],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="ignore",
        )
        return json.loads(r.stdout.strip()) if r.stdout.strip() else {}
    except Exception:
        return {}


def _run_schtasks(timeout: int = 10) -> list[str]:
    """Usa el comando nativo schtasks (mucho más rápido que Get-ScheduledTask)."""
    try:
        r = subprocess.run(
            ["schtasks", "/query", "/fo", "CSV", "/nh"],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="ignore",
        )
        return r.stdout.splitlines() if r.stdout else []
    except Exception:
        return []


# ── Checks individuales ───────────────────────────────────────────────────────

def _check_antivirus(ps_data: dict) -> list[dict]:
    raw = ps_data.get("antivirus") or []
    if isinstance(raw, dict):
        raw = [raw]
    if not raw:
        return [{
            "name": "Antivirus",
            "status": "warning",
            "message": "No se pudo consultar el antivirus. Intenta ejecutar como administrador.",
            "value": "Desconocido", "detail": "",
        }]

    items = []
    for av in raw:
        name = av.get("displayName", "Antivirus")
        state = int(av.get("productState") or 0)
        enabled = bool(state & 0x1000)
        updated = (state & 0x10) == 0

        if not enabled:
            items.append({"name": name, "status": "danger",
                "message": f"'{name}' está DESACTIVADO. Tu equipo está expuesto.",
                "value": "Desactivado", "detail": f"productState: {state}"})
        elif not updated:
            items.append({"name": name, "status": "warning",
                "message": f"'{name}' activo pero sus definiciones pueden estar desactualizadas.",
                "value": "Desactualizado", "detail": f"productState: {state}"})
        else:
            items.append({"name": name, "status": "ok",
                "message": f"'{name}' está activo y actualizado.",
                "value": "Protegido", "detail": ""})
    return items


def _check_firewall(ps_data: dict) -> list[dict]:
    raw = ps_data.get("firewall") or []
    if isinstance(raw, dict):
        raw = [raw]
    if not raw:
        return []

    disabled = [p.get("Name", "?") for p in raw if not p.get("Enabled", True)]
    if disabled:
        return [{"name": "Firewall de Windows", "status": "danger",
            "message": f"Firewall DESACTIVADO en: {', '.join(disabled)}. Riesgo de acceso no autorizado.",
            "value": "Desactivado",
            "detail": "Perfiles: " + ", ".join(p.get("Name", "?") for p in raw)}]
    return [{"name": "Firewall de Windows", "status": "ok",
        "message": "Firewall activo en todos los perfiles de red.",
        "value": "Activo",
        "detail": "Perfiles: " + ", ".join(p.get("Name", "?") for p in raw)}]


def _check_disk_health(ps_data: dict) -> list[dict]:
    raw = ps_data.get("disks") or []
    if isinstance(raw, dict):
        raw = [raw]
    items = []
    for d in raw:
        name = d.get("FriendlyName", "Disco")
        health = (d.get("HealthStatus") or "").lower()
        media = d.get("MediaType", "")
        size = d.get("SizeGB", "?")

        if health in ("unhealthy", "warning"):
            items.append({"name": name, "status": "danger",
                "message": f"'{name}' reporta salud deficiente. Haz una copia de seguridad urgente.",
                "value": health.capitalize(), "detail": f"{media} · {size} GB"})
        elif health == "healthy":
            items.append({"name": name, "status": "ok",
                "message": f"'{name}' en buen estado.", "value": "Saludable",
                "detail": f"{media} · {size} GB"})
        else:
            items.append({"name": name, "status": "warning",
                "message": f"No se pudo determinar la salud de '{name}'.",
                "value": health or "?", "detail": f"{media} · {size} GB"})
    return items


def _check_uptime() -> list[dict]:
    try:
        delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
        days, hours = delta.days, delta.seconds // 3600
        boot_str = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%d/%m/%Y %H:%M")
        if days >= 14:
            return [{"name": "Tiempo sin reiniciar", "status": "warning",
                "message": f"Tu PC lleva {days} días sin reiniciarse. Las actualizaciones pendientes no se aplican hasta que reinicias.",
                "value": f"{days} días", "detail": f"Último reinicio: {boot_str}"}]
        elif days >= 7:
            return [{"name": "Tiempo sin reiniciar", "status": "warning",
                "message": f"Llevas {days} días sin reiniciar. Considera hacerlo pronto.",
                "value": f"{days} días", "detail": f"Último reinicio: {boot_str}"}]
        return [{"name": "Tiempo sin reiniciar", "status": "ok",
            "message": f"Frecuencia de reinicio correcta ({days}d {hours}h).",
            "value": f"{days}d {hours}h", "detail": f"Último reinicio: {boot_str}"}]
    except Exception:
        return []


def _check_hosts() -> list[dict]:
    path = r"C:\Windows\System32\drivers\etc\hosts"
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            active = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
        legit = {"127.0.0.1 localhost", "::1 localhost", "127.0.0.1       localhost"}
        suspicious = [l for l in active if l not in legit]
        if suspicious:
            return [{"name": "Archivo Hosts", "status": "warning",
                "message": f"{len(suspicious)} entrada(s) personalizadas en el archivo hosts. El malware lo modifica para redirigir webs.",
                "value": f"{len(suspicious)} entradas",
                "detail": " | ".join(suspicious[:4]) + ("…" if len(suspicious) > 4 else "")}]
        return [{"name": "Archivo Hosts", "status": "ok",
            "message": "El archivo hosts no tiene modificaciones sospechosas.",
            "value": "Sin cambios", "detail": ""}]
    except Exception:
        return []


SAFE_PORTS = {80, 443, 135, 445, 1900, 3389, 5040, 5353, 7680, 8080}

def _check_ports() -> list[dict]:
    try:
        listening = [c for c in psutil.net_connections(kind="inet") if c.status == "LISTEN" and c.laddr]
        odd = []
        for c in listening:
            p = c.laddr.port
            if p not in SAFE_PORTS and p < 49152:
                try:
                    proc = psutil.Process(c.pid).name() if c.pid else "?"
                except Exception:
                    proc = "?"
                odd.append((p, proc, c.pid))
        if odd:
            return [{"name": f"Puerto {p} abierto", "status": "warning",
                "message": f"Puerto {p} escuchando conexiones externas (proceso: '{proc}'). Verifica si es esperado.",
                "value": f":{p}", "detail": f"PID {pid} · {proc}"}
                for p, proc, pid in odd[:6]]
        return [{"name": "Puertos de red", "status": "ok",
            "message": "No se detectaron puertos inusuales abiertos.", "value": f"{len(listening)} activos", "detail": ""}]
    except psutil.AccessDenied:
        return [{"name": "Puertos de red", "status": "warning",
            "message": "Se necesitan permisos de administrador para analizar todos los puertos.",
            "value": "Sin acceso", "detail": ""}]


SUSP_PATHS = ("temp\\", "appdata\\roaming\\", "\\tmp\\", "users\\public\\")

def _check_schtasks(lines: list[str]) -> list[dict]:
    suspicious = []
    for line in lines:
        try:
            row = next(csv.reader(io.StringIO(line)))
            if len(row) < 2:
                continue
            task_name = row[0].strip('"')
            task_path = row[1].strip('"').lower().replace("/", "\\")
            if any(kw in task_path for kw in SUSP_PATHS):
                suspicious.append(task_name)
        except Exception:
            continue

    if suspicious:
        return [{"name": f"Tarea: {t}", "status": "danger",
            "message": f"La tarea '{t}' ejecuta algo desde una ruta sospechosa. Técnica habitual de persistencia de malware.",
            "value": "Sospechosa", "detail": ""} for t in suspicious[:5]]
    return [{"name": "Tareas programadas", "status": "ok",
        "message": "No se detectaron tareas programadas sospechosas.",
        "value": "Sin alertas", "detail": ""}]


# ── Punto de entrada con paralelismo ──────────────────────────────────────────

def analyze_system() -> dict:
    ps_result: dict = {}
    schtasks_lines: list[str] = []

    def fetch_ps():
        nonlocal ps_result
        ps_result = _run_ps_combined(timeout=18)

    def fetch_schtasks():
        nonlocal schtasks_lines
        schtasks_lines = _run_schtasks(timeout=10)

    t1 = threading.Thread(target=fetch_ps, daemon=True)
    t2 = threading.Thread(target=fetch_schtasks, daemon=True)
    t1.start(); t2.start()
    t1.join(timeout=20); t2.join(timeout=12)

    items: list[dict] = []
    items += _check_antivirus(ps_result)
    items += _check_firewall(ps_result)
    items += _check_disk_health(ps_result)
    items += _check_uptime()
    items += _check_hosts()
    items += _check_ports()
    items += _check_schtasks(schtasks_lines)

    danger  = sum(1 for i in items if i["status"] == "danger")
    warning = sum(1 for i in items if i["status"] == "warning")

    if danger:
        overall = "danger"
        summary = f"¡Atención! {danger} problema(s) crítico(s) detectados."
    elif warning:
        overall = "warning"
        summary = f"{warning} punto(s) de mejora detectados."
    else:
        overall = "ok"
        summary = "Estado general del sistema: sin alertas activas."

    return {"status": overall, "title": "Estado del Sistema",
            "summary": summary, "issue_count": danger + warning, "items": items}
