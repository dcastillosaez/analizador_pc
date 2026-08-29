"""Capa única de ejecución de procesos externos.

Centraliza lo que antes estaba duplicado en cada módulo de `analyzer/`:

* `CREATE_NO_WINDOW` — sin esto, cada llamada a powershell/netsh/winget abre
  una ventana de consola parpadeante cuando la app corre compilada con
  `console=False`.
* Decodificación — Windows emite en la página OEM del sistema, no en UTF-8.
  Se prueba una cadena de codificaciones en lugar de asumir una.
* Timeouts y errores — nunca lanzan; se devuelve un `ShellResult` con
  `timed_out` o `error` marcados para que el módulo decida.
"""

import base64
import ctypes
import os
import subprocess
import sys
from dataclasses import dataclass, field

# Oculta la ventana de consola del proceso hijo. Solo existe en Windows.
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Orden de intento para decodificar la salida de herramientas de Windows.
_ENCODINGS = ("utf-8", "oem", "cp1252", "latin-1")


def _decode(raw: bytes) -> str:
    if not raw:
        return ""
    for enc in _ENCODINGS:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        # La página OEM decodifica casi cualquier byte, así que se acepta el
        # primer resultado que no venga plagado de caracteres de reemplazo.
        if "\ufffd" not in text:
            return text
    return raw.decode("latin-1", errors="replace")


@dataclass
class ShellResult:
    returncode: int = -1
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    not_found: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.error

    @property
    def combined(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()

    @property
    def needs_admin(self) -> bool:
        """Heurística compartida: ¿el fallo es por falta de privilegios?"""
        if self.returncode == 740:
            return True
        blob = self.combined.lower()
        return any(
            marker in blob
            for marker in ("0x80070005", "access is denied", "acceso denegado",
                           "denegado", "elevat", "requires elevation")
        )


def run(argv: list[str], timeout: int = 30) -> ShellResult:
    """Ejecuta un programa y devuelve su salida decodificada. Nunca lanza."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            timeout=timeout,
            creationflags=_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return ShellResult(timed_out=True, error="La operación tardó demasiado y fue cancelada.")
    except FileNotFoundError:
        return ShellResult(not_found=True, error=f"'{argv[0]}' no está disponible en este sistema.")
    except Exception as exc:  # PermissionError, OSError…
        return ShellResult(error=str(exc))

    return ShellResult(
        returncode=proc.returncode,
        stdout=_decode(proc.stdout),
        stderr=_decode(proc.stderr),
    )


def run_ps(script: str, timeout: int = 30) -> ShellResult:
    """Ejecuta un script de PowerShell vía -EncodedCommand.

    Codificar el script elimina toda la clase de problemas de comillas y
    escapado: el shell nunca reinterpreta el contenido. Además se fuerza la
    salida a UTF-8 para que los nombres con acentos no lleguen corruptos.
    """
    wrapped = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;" + script
    encoded = base64.b64encode(wrapped.encode("utf-16-le")).decode("ascii")
    return run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-EncodedCommand", encoded],
        timeout=timeout,
    )


def run_ps_json(script: str, timeout: int = 30, default=None):
    """Ejecuta PowerShell que termina en ConvertTo-Json y parsea el resultado.

    Devuelve siempre una lista cuando `default` es una lista: PowerShell
    serializa un único objeto como dict en lugar de lista de un elemento.
    """
    import json

    res = run_ps(script, timeout=timeout)
    raw = res.stdout.strip()
    if not raw:
        return default
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return default
    if isinstance(default, list) and not isinstance(data, list):
        return [data]
    return data


def is_admin() -> bool:
    """¿Corre el proceso actual con privilegios de administrador?"""
    if sys.platform != "win32":
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Relanza la aplicación pidiendo elevación por UAC. True si se lanzó."""
    if sys.platform != "win32" or is_admin():
        return False
    try:
        if getattr(sys, "frozen", False):
            exe, params = sys.executable, ""
        else:
            exe = sys.executable
            params = " ".join(f'"{a}"' for a in sys.argv)
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        return int(rc) > 32
    except Exception:
        return False
