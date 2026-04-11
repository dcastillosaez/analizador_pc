import subprocess
import json
import math
import re

SYSTEM_WHITELIST = {
    'AudioEndpointBuilder', 'Audiosrv', 'BFE', 'BrokerInfrastructure',
    'CoreMessagingRegistrar', 'CryptSvc', 'DcomLaunch', 'Dhcp', 'Dnscache',
    'DPS', 'EventLog', 'EventSystem', 'FontCache', 'gpsvc', 'LSM',
    'LanmanServer', 'LanmanWorkstation', 'MPSSVC', 'NlaSvc', 'nsi',
    'ProfSvc', 'RpcEptMapper', 'RpcSs', 'Schedule', 'SENS', 'SessionEnv',
    'SgrmBroker', 'ShellHWDetection', 'Spooler', 'SysMain', 'SystemEventsBroker',
    'Themes', 'TimeBrokerSvc', 'TrkWks', 'UserManager', 'UsoSvc',
    'W32Time', 'WSearch', 'WdNisSvc', 'WinDefend', 'Winmgmt',
    'WlanSvc', 'WpnService', 'wscsvc',
}

STANDARD_PATHS = (
    r'c:\windows\system32',
    r'c:\windows\syswow64',
    r'c:\program files',
    r'c:\program files (x86)',
    r'c:\programdata',
    r'c:\windows',
)


def _shannon_entropy(s: str) -> float:
    """Calcula la entropía de Shannon de una cadena."""
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _is_suspicious_name(name: str) -> bool:
    """Entropía alta en el nombre del servicio puede indicar algo generado aleatoriamente."""
    return _shannon_entropy(name) > 4.0 and len(name) > 8


def _is_standard_path(path: str) -> bool:
    if not path:
        return True  # sin ruta → probablemente driver interno
    clean = path.strip().strip('"').lower()
    # Extraer el ejecutable si hay argumentos
    if clean.startswith('"'):
        m = re.match(r'"([^"]+)"', clean)
        clean = m.group(1) if m else clean
    return any(clean.startswith(p) for p in STANDARD_PATHS)


def analyze_services() -> dict:
    cmd = (
        "Get-WmiObject Win32_Service | "
        "Where-Object { $_.State -eq 'Running' -and $_.StartMode -eq 'Auto' } | "
        "Select-Object Name, DisplayName, PathName, State, StartMode | "
        "ConvertTo-Json -Compress -Depth 2"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=30
        )
        raw = result.stdout.strip()
        if not raw:
            services_raw = []
        else:
            services_raw = json.loads(raw)
            if isinstance(services_raw, dict):
                services_raw = [services_raw]
    except Exception as exc:
        return {
            "status": "warning",
            "title": "Servicios de Windows",
            "summary": f"No se pudo obtener la lista de servicios: {exc}",
            "issue_count": 0,
            "items": [],
        }

    items = []
    warning_count = 0

    for svc in services_raw:
        name = svc.get("Name", "")
        display = svc.get("DisplayName", name)
        path = svc.get("PathName", "") or ""

        # Los de la whitelist se saltan (no añadimos ruido informativo)
        if name in SYSTEM_WHITELIST:
            continue

        # Clasificación
        if not _is_standard_path(path):
            status = "warning"
            message = "Ruta fuera de las rutas estándar del sistema"
            warning_count += 1
        elif _is_suspicious_name(name):
            status = "warning"
            message = "Nombre con patrón de alta entropía (posible nombre generado)"
            warning_count += 1
        else:
            status = "ok"
            message = "Servicio automático en ejecución"

        # Limpiar path para mostrar
        path_display = path.strip().strip('"')
        if len(path_display) > 80:
            path_display = "…" + path_display[-77:]

        items.append({
            "name": display,
            "status": status,
            "value": name,
            "message": message,
            "detail": path_display,
        })

        if len(items) >= 50:
            break

    # Ordenar: warnings primero
    STATUS_ORDER = {"warning": 0, "danger": 1, "ok": 2}
    items.sort(key=lambda x: STATUS_ORDER.get(x["status"], 3))

    total = len(items)
    if warning_count == 0:
        overall_status = "ok"
        summary = f"{total} servicio(s) automático(s) revisados. Ninguno sospechoso."
    else:
        overall_status = "warning"
        summary = f"{warning_count} servicio(s) con ruta o nombre sospechoso de {total} revisados."

    return {
        "status": overall_status,
        "title": "Servicios de Windows",
        "summary": summary,
        "issue_count": warning_count,
        "items": items,
    }
