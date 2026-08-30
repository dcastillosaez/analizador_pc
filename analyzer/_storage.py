"""Dónde viven las bases de datos locales de la aplicación.

Antes se guardaban junto al código (`analyzer/../history.db`). Eso falla en los
dos escenarios reales de uso:

* Instalada bajo `Program Files`, la carpeta es de solo lectura y la escritura
  revienta.
* Compilada con PyInstaller, `__file__` apunta a `sys._MEIPASS`, una carpeta
  temporal que Windows borra al cerrar la app: el historial no sobrevivía ni a
  un reinicio del programa.

Ahora van a `%LOCALAPPDATA%\\PCGuardian`, que es escribible, persiste entre
versiones y no se pierde al recompilar. La primera vez que se pide una base se
mueve la que hubiera en la ubicación antigua, con sus datos intactos.
"""

import os
import shutil
import sys
from pathlib import Path

_APP = "PCGuardian"

# Ficheros auxiliares que SQLite deja al lado en modo WAL. Si existen hay que
# moverlos con la base o se pierden transacciones no consolidadas.
_SIDECARS = ("-wal", "-shm", "-journal")


def data_dir() -> Path:
    """Carpeta de datos del usuario, creada si hace falta."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    carpeta = base / _APP
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _rutas_antiguas(nombre: str) -> list[Path]:
    """Sitios donde pudo quedar una base de una versión anterior."""
    candidatas = [Path(__file__).resolve().parent.parent / nombre]
    if getattr(sys, "frozen", False):
        # Junto al .exe, por si alguna vez se ejecutó desde ahí sin congelar.
        candidatas.append(Path(sys.executable).resolve().parent / nombre)
    return candidatas


def _migrar(origen: Path, destino: Path) -> None:
    """Mueve una base y sus ficheros auxiliares. Nunca lanza."""
    try:
        shutil.move(str(origen), str(destino))
    except Exception:
        return
    for sufijo in _SIDECARS:
        acompanante = origen.with_name(origen.name + sufijo)
        if acompanante.exists():
            try:
                shutil.move(str(acompanante), str(destino.with_name(destino.name + sufijo)))
            except Exception:
                pass


def db_path(nombre: str) -> str:
    """Ruta de la base `nombre`, migrando la versión antigua la primera vez.

    Si ya existe una base en el destino no se toca nada: la de la ubicación
    antigua se deja donde está en lugar de sobrescribir datos buenos.
    """
    destino = data_dir() / nombre
    if not destino.exists():
        for antigua in _rutas_antiguas(nombre):
            if antigua.exists() and antigua.resolve() != destino.resolve():
                _migrar(antigua, destino)
                break
    return str(destino)
