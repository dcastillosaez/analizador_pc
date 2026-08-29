"""Estado de las protecciones de plataforma de Windows.

Son las defensas que ya vienen con el sistema y que casi nadie comprueba:
cifrado de disco, arranque seguro, TPM, protección contra ransomware,
SmartScreen y UAC. Ninguna se ve desde la interfaz normal sin ir sitio por
sitio, y estar desactivadas no da ningún síntoma hasta que hace falta.

Todo se resuelve en una sola llamada a PowerShell: son consultas baratas pero
cada arranque del shell cuesta cerca de medio segundo.
"""

import winreg

from ._shell import run_ps_json
from .restore import restore_status

_PS = r"""
$out = @{}

try { $out.SecureBoot = [bool](Confirm-SecureBootUEFI -ErrorAction Stop) }
catch { $out.SecureBoot = $null }

try {
  $t = Get-Tpm -ErrorAction Stop
  $out.TpmPresent = [bool]$t.TpmPresent
  $out.TpmReady   = [bool]$t.TpmReady
} catch { $out.TpmPresent = $null; $out.TpmReady = $null }

try {
  $vols = Get-BitLockerVolume -ErrorAction Stop |
          Where-Object { $_.VolumeType -eq 'OperatingSystem' -or $_.MountPoint -eq $env:SystemDrive }
  $v = $vols | Select-Object -First 1
  if ($v) {
    $out.BitLockerMount  = $v.MountPoint
    $out.BitLockerStatus = $v.ProtectionStatus.ToString()
    $out.BitLockerPct    = $v.EncryptionPercentage
  }
} catch { $out.BitLockerStatus = $null }

try {
  $m = Get-MpComputerStatus -ErrorAction Stop
  $out.RealTimeProtection = [bool]$m.RealTimeProtectionEnabled
  $out.TamperProtection   = [bool]$m.IsTamperProtected
  $out.AntivirusSignatureAge = $m.AntivirusSignatureAge
} catch { $out.RealTimeProtection = $null }

try {
  $p = Get-MpPreference -ErrorAction Stop
  # 0 = desactivado, 1 = activado, 2 = solo auditoria
  $out.ControlledFolderAccess = [int]$p.EnableControlledFolderAccess
} catch { $out.ControlledFolderAccess = $null }

$out | ConvertTo-Json -Compress -Depth 3
"""


def _reg_dword(root, path: str, name: str):
    try:
        with winreg.OpenKey(root, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return int(value)
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return None


def _item(name, status, message, value, detail=""):
    return {"name": name, "status": status, "message": message,
            "value": value, "detail": detail}


def _check_secure_boot(d) -> dict:
    sb = d.get("SecureBoot")
    if sb is None:
        return _item("Arranque seguro (Secure Boot)", "warning",
                     "No se pudo consultar el estado. En equipos con BIOS antigua (MBR) no existe esta protección.",
                     "Desconocido",
                     "Confirm-SecureBootUEFI solo responde en equipos arrancados en modo UEFI.")
    if sb:
        return _item("Arranque seguro (Secure Boot)", "ok",
                     "Activo. Windows solo carga controladores y gestores de arranque firmados.",
                     "Activado")
    return _item("Arranque seguro (Secure Boot)", "warning",
                 "Desactivado. Sin él, un bootkit puede cargarse antes que Windows y el antivirus no lo vería.",
                 "Desactivado",
                 "Se activa en la configuración UEFI del equipo, no desde Windows.")


def _check_tpm(d) -> dict:
    presente, listo = d.get("TpmPresent"), d.get("TpmReady")
    if presente is None:
        return _item("Chip TPM", "warning",
                     "No se pudo consultar el TPM. Suele requerir permisos de administrador.",
                     "Desconocido")
    if not presente:
        return _item("Chip TPM", "warning",
                     "El equipo no tiene TPM. BitLocker y varias protecciones de Windows 11 dependen de él.",
                     "Ausente")
    if not listo:
        return _item("Chip TPM", "warning",
                     "El TPM existe pero no está preparado para usarse.",
                     "Sin inicializar",
                     "Se prepara desde tpm.msc.")
    return _item("Chip TPM", "ok",
                 "Presente y listo. Es lo que guarda las claves de cifrado fuera del alcance del sistema.",
                 "Listo")


def _check_bitlocker(d) -> dict:
    estado = d.get("BitLockerStatus")
    unidad = d.get("BitLockerMount") or "C:"
    if estado is None:
        return _item("Cifrado de disco (BitLocker)", "warning",
                     "No se pudo consultar. La edición Home de Windows no incluye BitLocker completo, "
                     "y la consulta necesita permisos de administrador.",
                     "Desconocido")
    if estado == "On":
        pct = d.get("BitLockerPct")
        return _item("Cifrado de disco (BitLocker)", "ok",
                     f"La unidad {unidad} está cifrada. Si alguien se lleva el disco, no puede leerlo.",
                     f"Cifrado {pct}%" if pct is not None else "Activo")
    return _item("Cifrado de disco (BitLocker)", "warning",
                 f"La unidad {unidad} no está cifrada. Cualquiera con acceso físico al disco puede "
                 "leer todos los archivos sacándolo del equipo.",
                 "Sin cifrar")


def _check_defender(d) -> list[dict]:
    items = []
    rtp = d.get("RealTimeProtection")
    if rtp is None:
        items.append(_item("Protección en tiempo real", "warning",
                           "No se pudo consultar el estado de Microsoft Defender.",
                           "Desconocido",
                           "Es normal si hay otro antivirus gestionando la protección."))
    elif rtp:
        items.append(_item("Protección en tiempo real", "ok",
                           "Microsoft Defender está vigilando archivos y procesos en tiempo real.",
                           "Activa"))
    else:
        items.append(_item("Protección en tiempo real", "danger",
                           "Desactivada. Nada está analizando los archivos que se abren o descargan.",
                           "Desactivada"))

    tamper = d.get("TamperProtection")
    if tamper is False:
        items.append(_item("Protección contra manipulaciones", "warning",
                           "Desactivada. Sin ella, un programa puede apagar el antivirus sin avisar.",
                           "Desactivada",
                           "Se activa en Seguridad de Windows › Protección antivirus."))
    elif tamper:
        items.append(_item("Protección contra manipulaciones", "ok",
                           "Activa. Ningún programa puede desactivar Defender por su cuenta.",
                           "Activa"))

    cfa = d.get("ControlledFolderAccess")
    if cfa == 1:
        items.append(_item("Protección contra ransomware", "ok",
                           "El acceso controlado a carpetas está activo: solo los programas autorizados "
                           "pueden modificar tus documentos.",
                           "Activa"))
    elif cfa == 2:
        items.append(_item("Protección contra ransomware", "warning",
                           "En modo auditoría: registra los intentos pero no los bloquea.",
                           "Solo auditoría"))
    elif cfa == 0:
        items.append(_item("Protección contra ransomware", "warning",
                           "El acceso controlado a carpetas está desactivado. Es la defensa específica "
                           "contra el cifrado de tus documentos por ransomware.",
                           "Desactivada",
                           "Seguridad de Windows › Protección contra ransomware."))

    edad = d.get("AntivirusSignatureAge")
    if isinstance(edad, int):
        if edad > 7:
            items.append(_item("Definiciones de antivirus", "warning",
                               f"Las definiciones tienen {edad} días. No reconocen amenazas recientes.",
                               f"{edad} días"))
        elif edad > 2:
            items.append(_item("Definiciones de antivirus", "ok",
                               f"Actualizadas hace {edad} días.", f"{edad} días"))
        else:
            items.append(_item("Definiciones de antivirus", "ok",
                               "Al día.", "Actualizadas"))
    return items


def _check_uac() -> dict:
    ruta = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
    habilitado = _reg_dword(winreg.HKEY_LOCAL_MACHINE, ruta, "EnableLUA")
    nivel = _reg_dword(winreg.HKEY_LOCAL_MACHINE, ruta, "ConsentPromptBehaviorAdmin")

    if habilitado == 0:
        return _item("Control de cuentas (UAC)", "danger",
                     "Desactivado. Cualquier programa puede hacer cambios de administrador sin preguntar.",
                     "Desactivado")
    if nivel == 0:
        return _item("Control de cuentas (UAC)", "warning",
                     "Está activo pero eleva sin pedir confirmación, que equivale a tenerlo apagado.",
                     "Sin aviso")
    if nivel in (1, 2):
        return _item("Control de cuentas (UAC)", "ok",
                     "Activo en el nivel más estricto: avisa siempre antes de elevar privilegios.",
                     "Máximo")
    return _item("Control de cuentas (UAC)", "ok",
                 "Activo. Avisa antes de que un programa haga cambios en el equipo.",
                 "Activado")


def _check_smartscreen() -> dict:
    valor = None
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer") as key:
            valor, _ = winreg.QueryValueEx(key, "SmartScreenEnabled")
    except (FileNotFoundError, OSError):
        pass

    if valor is None:
        return _item("SmartScreen", "ok",
                     "Con la configuración por defecto, que avisa ante archivos y sitios de mala reputación.",
                     "Por defecto")
    if str(valor).lower() == "off":
        return _item("SmartScreen", "warning",
                     "Desactivado. Windows ya no avisa al ejecutar archivos descargados de sitios desconocidos.",
                     "Desactivado")
    return _item("SmartScreen", "ok",
                 "Activo. Avisa antes de ejecutar archivos de reputación desconocida.",
                 str(valor))


def _check_restore() -> dict:
    """La red de seguridad para deshacer un cambio que salió mal."""
    estado = restore_status()
    if estado.get("enabled") and estado.get("last_creation"):
        return _item("Restaurar sistema", "ok",
                     "La protección del sistema está activa y hay puntos de restauración guardados.",
                     "Con puntos",
                     f"Último: {estado.get('last_description') or 'sin descripción'}")
    if estado.get("enabled"):
        return _item("Restaurar sistema", "warning",
                     "La protección está activa pero no hay ningún punto de restauración guardado: "
                     "no habría a dónde volver si un cambio sale mal.",
                     "Sin puntos")
    return _item("Restaurar sistema", "warning",
                 "No se detectan puntos de restauración. Si la protección del sistema está "
                 "desactivada, no hay forma de deshacer un cambio que rompa el equipo.",
                 "Desconocido",
                 "Propiedades del sistema › Protección del sistema.")


def analyze_hardening() -> dict:
    datos = run_ps_json(_PS, timeout=45, default={}) or {}
    if isinstance(datos, list):
        datos = datos[0] if datos else {}

    items = [
        _check_bitlocker(datos),
        _check_secure_boot(datos),
        _check_tpm(datos),
        *_check_defender(datos),
        _check_uac(),
        _check_smartscreen(),
        _check_restore(),
    ]

    peligros = sum(1 for i in items if i["status"] == "danger")
    avisos = sum(1 for i in items if i["status"] == "warning")

    if peligros:
        estado = "danger"
        resumen = f"{peligros} protección(es) crítica(s) desactivada(s) de {len(items)} comprobadas."
    elif avisos:
        estado = "warning"
        resumen = f"{avisos} de {len(items)} protecciones del sistema podrían reforzarse."
    else:
        estado = "ok"
        resumen = f"Las {len(items)} protecciones de plataforma están correctamente configuradas."

    return {
        "status": estado,
        "title": "Protecciones del sistema",
        "summary": resumen,
        "issue_count": peligros + avisos,
        "items": items,
    }
