import json
import subprocess

# Mapeo de clase WMI → (etiqueta legible, categoría en Administrador de dispositivos)
_CLASS_MAP: dict[str, tuple[str, str]] = {
    "Net":             ("Adaptadores de red",                  "Adaptadores de red"),
    "Display":         ("Adaptadores de pantalla",             "Adaptadores de pantalla"),
    "Media":           ("Audio, vídeo y juegos",               "Controladoras de sonido, vídeo y juegos"),
    "USB":             ("Controladores USB",                   "Controladores de bus serie universal (USB)"),
    "DiskDrive":       ("Unidades de disco",                   "Unidades de disco"),
    "CDROM":           ("Unidades DVD/CD-ROM",                 "Unidades de DVD/CD-ROM"),
    "Keyboard":        ("Teclados",                            "Teclados"),
    "Mouse":           ("Ratones y punteros",                  "Ratones y otros dispositivos señaladores"),
    "Battery":         ("Baterías",                            "Baterías"),
    "Bluetooth":       ("Bluetooth",                           "Bluetooth"),
    "Camera":          ("Cámaras",                             "Cámaras"),
    "Processor":       ("Procesadores",                        "Procesadores"),
    "System":          ("Dispositivos del sistema",            "Dispositivos del sistema"),
    "Ports":           ("Puertos (COM y LPT)",                 "Puertos (COM y LPT)"),
    "Printer":         ("Impresoras",                          "Impresoras"),
    "HDC":             ("Controladoras IDE/SATA",              "Controladoras de ATA/ATAPI"),
    "SCSIAdapter":     ("Controladoras SCSI/RAID",             "Controladoras de almacenamiento"),
    "Volume":          ("Almacenamiento",                      "Almacenamiento"),
    "Firmware":        ("Firmware",                            "Dispositivos de firmware"),
    "HIDClass":        ("Dispositivos HID",                    "Dispositivos de interfaz humana"),
    "MTD":             ("Tarjetas de memoria",                 "Dispositivos de almacenamiento de memoria"),
    "SmartCardReader": ("Lector de tarjeta inteligente",       "Lectores de tarjeta inteligente"),
    "Biometric":       ("Dispositivos biométricos",            "Dispositivos biométricos"),
    "Sensor":          ("Sensores",                            "Sensores"),
    "1394":            ("Bus IEEE 1394",                       "Controladora de bus IEEE 1394"),
    "SecurityDevices": ("Dispositivos de seguridad",           "Dispositivos de seguridad"),
    "SoftwareDevice":  ("Dispositivos de software",            "Dispositivos de software"),
    "Extension":       ("Dispositivos de extensión",           "Dispositivos de extensión"),
    "Computer":        ("Equipo",                              "Equipo"),
}

_PS_DRIVERS = """
try {
  $d = Get-WmiObject Win32_PnPSignedDriver -ErrorAction Stop |
       Where-Object { $_.DeviceName } |
       Select-Object DeviceName, DriverVersion, IsSigned, Manufacturer, DriverDate,
         @{n='DeviceClass';e={$_.DeviceClass}},
         @{n='DeviceID';e={$_.DeviceID}},
         @{n='InfName';e={$_.InfName}}
  $d | ConvertTo-Json -Compress -Depth 2
} catch { '[]' }
"""

_PS_SOFTWARE = """
try {
  $paths = @(
    'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'
  )
  $apps = $paths | ForEach-Object { Get-ItemProperty $_ -ErrorAction SilentlyContinue } |
          Where-Object { $_.DisplayName } |
          Select-Object DisplayName, Publisher, DisplayVersion, InstallDate
  $apps | ConvertTo-Json -Compress -Depth 2
} catch { '[]' }
"""


def _run_ps(script: str) -> list:
    try:
        r = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=45,
            encoding="utf-8",
            errors="ignore",
        )
        raw = (r.stdout or "").strip()
        if not raw:
            return []
        data = json.loads(raw)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


def analyze_drivers() -> dict:
    items: list[dict] = []

    drivers = _run_ps(_PS_DRIVERS)
    for drv in drivers:
        if not isinstance(drv, dict):
            continue
        name = drv.get("DeviceName") or "Desconocido"
        is_signed = drv.get("IsSigned")
        version = drv.get("DriverVersion") or ""
        manufacturer = drv.get("Manufacturer") or "Fabricante desconocido"
        device_id = drv.get("DeviceID") or ""
        inf_name = drv.get("InfName") or ""

        # Categoría en Administrador de dispositivos
        raw_class = (drv.get("DeviceClass") or "").strip()
        class_key = next((k for k in _CLASS_MAP if k.lower() == raw_class.lower()), None)
        class_label, devmgr_category = _CLASS_MAP[class_key] if class_key else (raw_class or "Otros dispositivos", "Otros dispositivos")

        if is_signed is False:
            items.append(
                {
                    "name": name,
                    "status": "danger",
                    "message": (
                        f"Controlador sin firma digital válida. "
                        "Puede ser peligroso, estar corrupto o ser de origen desconocido."
                    ),
                    "value": "Sin firma",
                    "detail": f"{manufacturer} · v{version}" if version else manufacturer,
                    "device_id": device_id,
                    "inf_name": inf_name,
                    "class_label": class_label,
                    "devmgr_category": devmgr_category,
                }
            )
        elif not version:
            items.append(
                {
                    "name": name,
                    "status": "warning",
                    "message": (
                        "Controlador sin número de versión registrado. "
                        "Podría estar desactualizado o instalado de forma irregular."
                    ),
                    "value": "Sin versión",
                    "detail": manufacturer,
                    "device_id": device_id,
                    "inf_name": inf_name,
                    "class_label": class_label,
                    "devmgr_category": devmgr_category,
                }
            )

    # Software sin publisher (posible riesgo)
    software = _run_ps(_PS_SOFTWARE)
    no_publisher: list[str] = []
    for app in software:
        if not isinstance(app, dict):
            continue
        publisher = (app.get("Publisher") or "").strip()
        display = (app.get("DisplayName") or "").strip()
        if display and not publisher:
            no_publisher.append(display)

    if no_publisher:
        sample = no_publisher[:5]
        items.append(
            {
                "name": "Software sin editor verificado",
                "status": "warning",
                "message": (
                    f"Se encontraron {len(no_publisher)} programa(s) instalados sin "
                    "información de editor. Verifica que los instalaste tú: "
                    + ", ".join(f"'{a}'" for a in sample)
                    + ("…" if len(no_publisher) > 5 else ".")
                ),
                "value": f"{len(no_publisher)} apps",
                "detail": ", ".join(no_publisher[:15]),
            }
        )

    danger_count = sum(1 for i in items if i["status"] == "danger")
    warning_count = sum(1 for i in items if i["status"] == "warning")

    if danger_count > 0:
        overall = "danger"
        summary = (
            f"{danger_count} controlador(es) sin firma digital. "
            "Riesgo de inestabilidad o seguridad comprometida."
        )
    elif warning_count > 0:
        overall = "warning"
        summary = f"{warning_count} elemento(s) con información incompleta. Considera revisarlos."
    else:
        overall = "ok"
        summary = "Todos los controladores detectados están firmados y con versión registrada."

    return {
        "status": overall,
        "title": "Controladores y Software",
        "summary": summary,
        "issue_count": len(items),
        "items": items[:60],
    }


def _sanitize_device_id(device_id: str) -> str | None:
    """Valida que el DeviceID tenga el formato esperado de Windows PnP."""
    import re
    # Acepta letras, dígitos, \, /, &, -, _, punto, llaves y @
    if re.match(r'^[\w\\\-&{}@#./ ]+$', device_id) and len(device_id) < 300:
        return device_id
    return None


def update_driver(device_id: str) -> dict:
    """Fuerza una búsqueda de actualización para el dispositivo indicado via pnputil."""
    clean = _sanitize_device_id(device_id)
    if not clean:
        return {"success": False, "message": "ID de dispositivo no válido.", "output": ""}

    try:
        r = subprocess.run(
            ["pnputil", "/scan-devices", "/instanceid", clean],
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="ignore",
        )
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        # pnputil devuelve 0 si todo va bien
        if r.returncode == 0:
            return {
                "success": True,
                "message": "Búsqueda de actualización completada. Si hay un controlador más reciente disponible, Windows lo instalará automáticamente.",
                "output": out[-400:],
            }
        # Código 2 = no se encontró el dispositivo
        if r.returncode == 2:
            return {"success": False, "message": "Dispositivo no encontrado. Puede que ya no esté conectado.", "output": out[-400:]}
        # Código 740 = se requieren privilegios de administrador
        if r.returncode == 740 or "acceso" in out.lower() or "elevat" in out.lower():
            return {"success": False, "message": "Se necesitan permisos de administrador. Reinicia PC Guardian como administrador.", "output": out[-400:]}
        return {"success": False, "message": f"pnputil terminó con código {r.returncode}.", "output": out[-400:]}
    except FileNotFoundError:
        return {"success": False, "message": "pnputil no está disponible en este sistema.", "output": ""}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "La operación tardó demasiado y fue cancelada.", "output": ""}
    except Exception as exc:
        return {"success": False, "message": str(exc), "output": ""}


def uninstall_driver(device_id: str) -> dict:
    """Desinstala el dispositivo (elimina el dispositivo del árbol PnP).
    El controlador permanece en el sistema hasta que se elimine manualmente.
    Requiere privilegios de administrador.
    """
    clean = _sanitize_device_id(device_id)
    if not clean:
        return {"success": False, "message": "ID de dispositivo no válido.", "output": ""}

    try:
        r = subprocess.run(
            ["pnputil", "/remove-device", clean],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="ignore",
        )
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        if r.returncode == 0:
            return {
                "success": True,
                "message": "Dispositivo desinstalado correctamente. Puede reaparecer si Windows lo redetecta al reiniciar.",
                "output": out[-400:],
            }
        if r.returncode == 740 or "acceso" in out.lower() or "elevat" in out.lower():
            return {"success": False, "message": "Se necesitan permisos de administrador. Reinicia PC Guardian como administrador.", "output": out[-400:]}
        return {"success": False, "message": f"No se pudo desinstalar el dispositivo (código {r.returncode}).", "output": out[-400:]}
    except FileNotFoundError:
        return {"success": False, "message": "pnputil no está disponible en este sistema.", "output": ""}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "La operación tardó demasiado y fue cancelada.", "output": ""}
    except Exception as exc:
        return {"success": False, "message": str(exc), "output": ""}
