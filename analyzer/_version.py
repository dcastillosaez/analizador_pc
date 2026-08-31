"""Versión de PC Guardian.

Fuente única: la usan la ruta índice para pintarla en el pie del sidebar, el
endpoint `/api/version` y el generador del EXE para los metadatos del binario
(`version_info.txt`, que se regenera con `python -m analyzer._version`).

Semver: MAYOR para cambios que rompen, MENOR para módulos o funciones nuevas,
PARCHE para correcciones.
"""

__version__ = "1.0.0"

APP_NAME = "PC Guardian"
APP_DESCRIPTION = "Diagnóstico local para Windows 10/11"
APP_COMPANY = "David Castillo"


def version_tuple() -> tuple[int, int, int, int]:
    """La versión como cuaterna, que es lo que pide el recurso VERSIONINFO."""
    partes = [int(p) for p in __version__.split(".")[:3]]
    while len(partes) < 3:
        partes.append(0)
    return (*partes, 0)


def version_info_file() -> str:
    """Contenido del `version_info.txt` que consume PyInstaller."""
    v = version_tuple()
    return f"""# Generado por analyzer/_version.py — no editar a mano.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v},
    prodvers={v},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040a04b0',
        [StringStruct('CompanyName', '{APP_COMPANY}'),
         StringStruct('FileDescription', '{APP_DESCRIPTION}'),
         StringStruct('FileVersion', '{__version__}'),
         StringStruct('InternalName', 'PCGuardian'),
         StringStruct('OriginalFilename', 'PCGuardian.exe'),
         StringStruct('ProductName', '{APP_NAME}'),
         StringStruct('ProductVersion', '{__version__}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1034, 1200])])
  ]
)
"""


if __name__ == "__main__":
    import pathlib

    destino = pathlib.Path(__file__).resolve().parent.parent / "version_info.txt"
    destino.write_text(version_info_file(), encoding="utf-8")
    print(f"{destino} -> {__version__}")
