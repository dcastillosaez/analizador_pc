"""
Privacidad y Limpieza — telemetría, permisos de apps, archivos temporales
y eventos críticos del sistema (BSODs, fallos de aplicación).
"""
import os
import re
import time
import datetime
import subprocess
import winreg
from pathlib import Path


# ── Telemetría ────────────────────────────────────────────────────────────────

def _check_telemetry() -> dict:
    LEVELS = {0: "Desactivada", 1: "Básica", 2: "Mejorada", 3: "Completa (máxima)"}
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        )
        val, _ = winreg.QueryValueEx(key, "AllowTelemetry")
        winreg.CloseKey(key)
        level = int(val)
    except FileNotFoundError:
        level = 3  # Sin política = nivel completo por defecto
    except Exception:
        return {"name": "Telemetría de Windows", "status": "ok",
                "message": "No se pudo leer la configuración de telemetría",
                "value": "Desconocido", "detail": ""}

    label  = LEVELS.get(level, f"Nivel {level}")
    status = "ok" if level <= 1 else "warning"
    detail = ("Nivel elevado — Windows envía datos de uso detallados a Microsoft."
              if status == "warning" else
              "Telemetría reducida al mínimo.")
    return {
        "name":    "Telemetría de Windows",
        "status":  status,
        "message": label,
        "value":   label,
        "detail":  detail,
    }


# ── Permisos de aplicaciones ──────────────────────────────────────────────────

_PERMS = {
    "microphone": "Micrófono",
    "webcam":     "Cámara",
    "location":   "Ubicación",
}

def _check_permissions() -> list[dict]:
    results = []
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
    for perm_id, label in _PERMS.items():
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{base}\{perm_id}")
            val, _ = winreg.QueryValueEx(key, "Value")
            winreg.CloseKey(key)
        except Exception:
            val = "Desconocido"

        if val == "Allow":
            status = "warning"
            desc   = "Acceso global habilitado para todas las apps"
        elif val == "Deny":
            status = "ok"
            desc   = "Acceso denegado a todas las apps"
        else:
            status = "ok"
            desc   = "Solo apps seleccionadas tienen acceso"

        results.append({
            "name":    label,
            "status":  status,
            "message": desc,
            "value":   val if val in ("Allow", "Deny") else "Selectivo",
            "detail":  "Revisa en Configuración › Privacidad" if status == "warning" else "",
        })
    return results


# ── Archivos temporales ───────────────────────────────────────────────────────

_TEMP_DIRS = [
    os.environ.get("TEMP", ""),
    os.environ.get("TMP",  ""),
    r"C:\Windows\Temp",
    r"C:\Windows\Prefetch",
]

def _scan_temp() -> dict:
    total_bytes = 0
    total_files = 0
    accessible_dirs = []

    for d in _TEMP_DIRS:
        if not d or not os.path.isdir(d):
            continue
        accessible_dirs.append(d)
        try:
            for entry in Path(d).rglob("*"):
                try:
                    if entry.is_file():
                        total_bytes += entry.stat().st_size
                        total_files += 1
                except Exception:
                    pass
        except PermissionError:
            pass

    gb   = total_bytes / 1024**3
    mb   = total_bytes / 1024**2
    size = f"{gb:.2f} GB" if gb >= 1 else f"{mb:.0f} MB"

    status = "danger" if gb >= 5 else "warning" if mb >= 500 else "ok"
    return {
        "bytes":  total_bytes,
        "files":  total_files,
        "size":   size,
        "status": status,
        "dirs":   accessible_dirs,
    }


def _temp_item(info: dict) -> dict:
    status = info["status"]
    msg_map = {
        "danger":  f"⚠ {info['size']} en archivos temporales ({info['files']:,} archivos)",
        "warning": f"{info['size']} en archivos temporales ({info['files']:,} archivos)",
        "ok":      f"{info['size']} en temporales — dentro de lo normal",
    }
    return {
        "name":    "Archivos temporales",
        "status":  status,
        "message": msg_map[status],
        "value":   info["size"],
        "detail":  " · ".join(info["dirs"][:3]) if info["dirs"] else "",
        "_bytes":  info["bytes"],
        "_files":  info["files"],
    }


# ── Eventos críticos (BSODs y fallos de app) ──────────────────────────────────

def _check_events() -> list[dict]:
    results = []

    # BSODs: contar volcados de memoria recientes (30 días)
    minidump = Path(r"C:\Windows\Minidump")
    if minidump.exists():
        try:
            dumps = list(minidump.glob("*.dmp"))
            cutoff = time.time() - 30 * 86400
            recent = [f for f in dumps if f.stat().st_mtime > cutoff]
            if recent:
                status = "danger" if len(recent) >= 3 else "warning"
                results.append({
                    "name":    "Pantallazos azules (BSOD)",
                    "status":  status,
                    "message": f"{len(recent)} volcado(s) de memoria en los últimos 30 días",
                    "value":   f"{len(recent)} BSOD",
                    "detail":  "Puede indicar fallo de hardware, driver o RAM",
                })
            else:
                results.append({
                    "name":    "Pantallazos azules (BSOD)",
                    "status":  "ok",
                    "message": "Sin crasheos detectados en los últimos 30 días",
                    "value":   "Sin BSOD",
                    "detail":  "",
                })
        except Exception:
            pass

    # Errores críticos del Visor de eventos (últimas 72 h) — uno por evento
    try:
        import json
        r = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                (
                    "Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;"
                    "StartTime=(Get-Date).AddHours(-72)} -MaxEvents 8 -ErrorAction SilentlyContinue"
                    " | Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,"
                    "@{n='Msg';e={$_.Message -replace '`n',' ' -replace '`r',' '}} "
                    " | ConvertTo-Json -Compress -Depth 2"
                ),
            ],
            capture_output=True, timeout=20,
        )
        raw = r.stdout.decode("utf-8", errors="ignore").strip()
        if raw and raw != "null":
            events = json.loads(raw)
            if isinstance(events, dict):
                events = [events]

            for ev in events:
                provider = ev.get("ProviderName") or "Sistema"
                level    = ev.get("LevelDisplayName") or "Error"
                ev_id    = ev.get("Id") or ""
                msg_raw  = ev.get("Msg") or ev.get("Message") or ""
                # Recortar el mensaje a la primera frase útil (max 120 chars)
                msg = " ".join(str(msg_raw).split())[:200]
                if len(msg) == 200:
                    msg = msg[:197] + "…"

                # Fecha legible
                tc = ev.get("TimeCreated") or ""
                try:
                    # PowerShell devuelve algo como "/Date(1234567890000)/"
                    ms = re.search(r"(\d{10,})", str(tc))
                    if ms:
                        ts = datetime.datetime.fromtimestamp(int(ms.group(1)) / 1000)
                        fecha = ts.strftime("%d/%m %H:%M")
                    else:
                        fecha = str(tc)[:16]
                except Exception:
                    fecha = str(tc)[:16]

                status = "danger" if level.lower() in ("critical", "crítico") else "warning"
                results.append({
                    "name":    f"{provider}",
                    "status":  status,
                    "message": msg or f"Evento {ev_id} sin descripción disponible",
                    "value":   level,
                    "detail":  f"ID {ev_id} · {fecha}",
                })
        else:
            results.append({
                "name":    "Errores críticos del sistema",
                "status":  "ok",
                "message": "Sin errores críticos del sistema en las últimas 72 horas",
                "value":   "Sin errores",
                "detail":  "",
            })
    except Exception:
        pass

    return results


# ── Punto de entrada ──────────────────────────────────────────────────────────

def analyze_privacy() -> dict:
    items: list[dict] = []

    items.append(_check_telemetry())
    items.extend(_check_permissions())
    temp_info = _scan_temp()
    items.append(_temp_item(temp_info))
    items.extend(_check_events())

    danger  = sum(1 for i in items if i["status"] == "danger")
    warning = sum(1 for i in items if i["status"] == "warning")

    if danger:
        overall = "danger"
        summary = f"{danger} problema(s) crítico(s) de privacidad o estabilidad."
    elif warning:
        overall = "warning"
        summary = f"{warning} elemento(s) de privacidad requieren atención."
    else:
        overall = "ok"
        summary = "Privacidad correcta y sistema sin errores críticos recientes."

    return {
        "status":      overall,
        "title":       "Privacidad y Limpieza",
        "summary":     summary,
        "issue_count": danger + warning,
        "items":       items,
        "temp_bytes":  temp_info["bytes"],
        "temp_files":  temp_info["files"],
        "temp_size":   temp_info["size"],
    }


# ── Limpieza de temporales (acción de escritura) ──────────────────────────────

def clean_temp() -> dict:
    deleted_bytes = 0
    deleted_files = 0
    errors = 0

    for d in _TEMP_DIRS:
        if not d or not os.path.isdir(d):
            continue
        try:
            for entry in Path(d).iterdir():
                try:
                    if entry.is_file():
                        size = entry.stat().st_size
                        entry.unlink()
                        deleted_bytes += size
                        deleted_files += 1
                    elif entry.is_dir():
                        import shutil
                        shutil.rmtree(entry, ignore_errors=True)
                except Exception:
                    errors += 1
        except Exception:
            errors += 1

    gb   = deleted_bytes / 1024**3
    mb   = deleted_bytes / 1024**2
    size = f"{gb:.2f} GB" if gb >= 1 else f"{mb:.0f} MB"

    return {
        "success":       True,
        "deleted_files": deleted_files,
        "deleted_size":  size,
        "errors":        errors,
        "message":       f"Eliminados {deleted_files:,} archivos ({size} liberados).",
    }
