"""Aplicaciones predeterminadas — qué programa abre cada tipo de archivo y enlace.

Solo lectura, a propósito. Windows protege la clave `UserChoice` con un hash
sobre SID + extensión + ProgId cuyo algoritmo Microsoft nunca documentó: si se
escribe el ProgId sin ese hash, el sistema detecta la manipulación y revierte
la asociación. Por eso el módulo audita y lleva al usuario a la página de
Configuración correspondiente, en lugar de prometer un cambio que Windows
deshará por detrás.
"""
import ctypes
import os
import shlex
import urllib.parse
import winreg

# Protocolos de URL — HKCU\...\Shell\Associations\UrlAssociations\<proto>\UserChoice
URL_PROTOS = [
    ("http",   "Páginas web"),
    ("https",  "Páginas web (seguras)"),
    ("mailto", "Enlaces de correo"),
]

# Extensiones — HKCU\...\Explorer\FileExts\<ext>\UserChoice
FILE_EXTS = [
    (".pdf",  "Documentos PDF"),
    (".html", "Páginas HTML"),
    (".txt",  "Texto plano"),
    (".jpg",  "Imágenes JPG"),
    (".png",  "Imágenes PNG"),
    (".mp4",  "Vídeo MP4"),
    (".zip",  "Archivos ZIP"),
    (".docx", "Documentos Word"),
]

# ProgIds cuyo ejecutable no delata el nombre comercial del programa
PROGID_NAMES = {
    "Acrobat.Document.DC":   "Adobe Acrobat",
    "AcroExch.Document.DC":  "Adobe Acrobat",
    "ChromeHTML":            "Google Chrome",
    "MSEdgeHTM":             "Microsoft Edge",
    "MSEdgePDF":             "Microsoft Edge",
    "FirefoxURL":            "Mozilla Firefox",
    "FirefoxHTML":           "Mozilla Firefox",
    "OperaStable":           "Opera",
    "BraveHTML":             "Brave",
    "txtfile":               "Bloc de notas",
    "Windows.MSPaint":       "Paint",
    "WMP11.AssocFile.MP4":   "Reproductor de Windows Media",
    "CompressedFolder":      "Explorador de Windows",
    "Word.Document.12":      "Microsoft Word",
    "Outlook.URL.mailto.15": "Microsoft Outlook",
}

# Carpetas desde las que un programa predeterminado es señal de secuestro
SEP = "\\"

CARPETAS_VOLATILES = {"temp", "tmp", "downloads", "descargas",
                      "inetcache", "$recycle.bin"}


def _exe_from_command(command: str) -> str:
    """Extrae la ruta del ejecutable de una línea de comando del registro."""
    if not command:
        return ""
    cmd = os.path.expandvars(command.strip())
    if cmd.startswith('"'):
        exe = cmd[1:].split('"', 1)[0]
    else:
        try:
            partes = shlex.split(cmd, posix=False)
            exe = partes[0] if partes else ""
        except ValueError:
            exe = cmd.split(" ", 1)[0]
    return exe.strip('"')


PAQUETES_APPX = {
    "Microsoft.Windows.Photos":            "Fotos",
    "Microsoft.ZuneVideo":                 "Películas y TV",
    "Microsoft.ZuneMusic":                 "Reproductor multimedia",
    "Microsoft.WindowsNotepad":            "Bloc de notas",
    "Microsoft.Paint":                     "Paint",
    "microsoft.windowscommunicationsapps": "Correo de Windows",
    "Microsoft.OutlookForWindows":         "Outlook",
    "Microsoft.MicrosoftEdge":             "Microsoft Edge",
    "Microsoft.WindowsTerminal":           "Terminal de Windows",
}


def _clean_resource_string(valor: str) -> str:
    """Descarta los nombres sin resolver del tipo @{Paquete?ms-resource://...}."""
    valor = (valor or "").strip()
    return "" if valor.startswith("@{") else valor


def _package_display(aumid: str) -> str:
    """Nombre legible a partir de un AppUserModelID (Paquete_hash!Entrada)."""
    if not aumid:
        return ""
    paquete = aumid.split("!", 1)[0].split("_", 1)[0]
    if paquete in PAQUETES_APPX:
        return PAQUETES_APPX[paquete]
    corto = paquete.rsplit(".", 1)[-1]
    return corto or paquete


def _resolve_indirect(valor: str) -> str:
    """Resuelve un ms-resource:// con la API del shell. Devuelve '' si no puede."""
    if not valor.startswith("@{"):
        return valor
    try:
        buf = ctypes.create_unicode_buffer(1024)
        hr = ctypes.windll.shlwapi.SHLoadIndirectString(valor, buf, len(buf), None)
        return buf.value if hr == 0 else ""
    except Exception:
        return ""


def _appx_name(progid: str) -> str:
    """Nombre comercial de una app del Store a partir de su ProgId AppX…"""
    nombre = aumid = ""
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_CLASSES_ROOT):
        base = r"Software\Classes" if hive == winreg.HKEY_CURRENT_USER else ""
        ruta = rf"{base}\{progid}\Application" if base else rf"{progid}\Application"
        try:
            with winreg.OpenKey(hive, ruta, 0, winreg.KEY_READ) as k:
                for campo, destino in (("ApplicationName", "nombre"), ("AppUserModelID", "aumid")):
                    try:
                        valor, _ = winreg.QueryValueEx(k, campo)
                    except Exception:
                        continue
                    if destino == "nombre" and valor:
                        nombre = str(valor)
                    elif destino == "aumid" and valor:
                        aumid = str(valor)
        except Exception:
            continue
        if nombre or aumid:
            break

    resuelto = _clean_resource_string(_resolve_indirect(nombre))
    return resuelto or _package_display(aumid)


def _friendly_name(progid: str, exe: str) -> str:
    if progid in PROGID_NAMES:
        return PROGID_NAMES[progid]
    if exe:
        base = os.path.basename(exe)
        if base.lower().endswith(".exe"):
            base = base[:-4]
        if base:
            return base.capitalize() if base.islower() else base
    if progid.startswith("AppX"):
        appx = _appx_name(progid)
        if appx:
            return appx
    return progid or "Sin asignar"


def _evaluate(progid: str, exe: str, resuelto: bool = True) -> tuple[str, str]:
    """Devuelve (status, motivo) para una asociación.

    `resuelto` dice si el ProgId llegó a apuntar a algo real. Un ProgId que ya
    no existe en el registro (típico de una app del Store desinstalada) deja el
    tipo de archivo huérfano: al abrirlo no pasa nada o salta el diálogo de
    "elegir aplicación".
    """
    if not progid:
        return "warning", "No hay ninguna aplicación asignada para este tipo."
    if not resuelto:
        return "warning", ("La aplicación asignada ya no está registrada en el sistema "
                           "(seguramente se desinstaló). Asigna otra para que estos "
                           "archivos vuelvan a abrirse.")
    low = (exe or "").lower()
    carpetas = set(low.replace("/", SEP).split(SEP)[:-1])
    if carpetas & CARPETAS_VOLATILES:
        return "danger", ("El programa asignado vive en una carpeta temporal o de descargas. "
                          "Es el patrón habitual del secuestro de asociaciones.")
    return "ok", ""


def _settings_uri(app_name: str) -> str:
    """URI de Configuración para las apps predeterminadas.

    El nombre va escapado: llega desde el navegador y no puede arrastrar
    parámetros extra a la URI.
    """
    if not app_name:
        return "ms-settings:defaultapps"
    seguro = urllib.parse.quote(app_name, safe="")
    return f"ms-settings:defaultapps?registeredAppUser={seguro}"


def _read_progid(hive, path: str) -> str:
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
            valor, _ = winreg.QueryValueEx(k, "ProgId")
            return str(valor)
    except Exception:
        return ""


def _read_command(progid: str) -> str:
    if not progid:
        return ""
    for hive, base in ((winreg.HKEY_CURRENT_USER, r"Software\Classes"),
                       (winreg.HKEY_CLASSES_ROOT, "")):
        ruta = rf"{base}\{progid}\shell\open\command" if base else rf"{progid}\shell\open\command"
        try:
            with winreg.OpenKey(hive, ruta, 0, winreg.KEY_READ) as k:
                valor, _ = winreg.QueryValueEx(k, "")
                if valor:
                    return str(valor)
        except Exception:
            continue
    return ""


def _asociacion(nombre: str, progid: str) -> dict:
    exe    = _exe_from_command(_read_command(progid))
    app    = _friendly_name(progid, exe)
    resuelto = bool(exe) or app != progid
    status, motivo = _evaluate(progid, exe, resuelto=resuelto)
    return {
        "name":    nombre,
        "status":  status,
        "message": motivo or f"Se abre con {app}.",
        "value":   app if resuelto else "Sin aplicación válida",
        "detail":  exe or progid,
        "app":     app if (progid and resuelto) else "",
    }


def analyze_defaults() -> dict:
    items = []

    for proto, etiqueta in URL_PROTOS:
        progid = _read_progid(
            winreg.HKEY_CURRENT_USER,
            rf"SOFTWARE\Microsoft\Windows\Shell\Associations\UrlAssociations\{proto}\UserChoice",
        )
        items.append(_asociacion(etiqueta, progid))

    for ext, etiqueta in FILE_EXTS:
        progid = _read_progid(
            winreg.HKEY_CURRENT_USER,
            rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}\UserChoice",
        )
        items.append(_asociacion(f"{etiqueta} ({ext})", progid))

    danger  = sum(1 for i in items if i["status"] == "danger")
    warning = sum(1 for i in items if i["status"] == "warning")
    overall = "danger" if danger else ("warning" if warning else "ok")
    summaries = {
        "danger":  f"{danger} asociación(es) apuntan a programas en carpetas temporales. Revísalo.",
        "warning": f"{warning} tipo(s) de archivo sin una aplicación válida asignada.",
        "ok":      "Todos los tipos de archivo y enlace tienen una aplicación conocida asignada.",
    }
    return {"status": overall, "title": "Aplicaciones predeterminadas",
            "summary": summaries[overall], "issue_count": danger + warning,
            "items": items}


def open_default_apps_settings(app_name: str = "") -> dict:
    """Abre la página de Configuración de Windows donde se cambia la asociación.

    `os.startfile` y no `_shell.run`: el URI `ms-settings:` lo resuelve el
    propio shell, no hay proceso hijo que capturar y no abre ninguna consola.
    """
    uri = _settings_uri(app_name)
    try:
        os.startfile(uri)  # noqa: S606 — URI construida y escapada aquí mismo
        destino = f"la ficha de {app_name}" if app_name else "Aplicaciones predeterminadas"
        return {"ok": True, "msg": f"Se ha abierto Configuración en {destino}."}
    except Exception as e:
        return {"ok": False, "msg": f"No se pudo abrir Configuración: {str(e)[:100]}"}
