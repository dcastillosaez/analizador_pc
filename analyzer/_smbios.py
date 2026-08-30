"""Lectura y decodificación de la tabla SMBIOS (DMI) del firmware.

`GetSystemFirmwareTable` entrega la tabla tal cual la publica la BIOS: es un
estándar DMTF que implementa cualquier PC con Windows, no hace falta driver ni
privilegios. Da bastante más detalle que WMI, que solo expone un subconjunto ya
digerido — por ejemplo los núcleos habilitados frente a los presentes, o el
ancho eléctrico de cada slot PCIe.

Qué estructuras rellena cada fabricante varía, así que todo lo de aquí devuelve
None o listas vacías cuando falta el dato, nunca lanza.
"""
import ctypes
import struct

RSMB = 0x52534D42  # 'RSMB' — firmware table provider signature

# Type 9 — SlotDataBusWidth (DMTF DSP0134, tabla 7.10.2)
ANCHOS_SLOT = {8: "x1", 9: "x2", 10: "x4", 11: "x8", 12: "x12", 13: "x16", 14: "x32"}

# Type 9 — CurrentUsage
SLOT_LIBRE, SLOT_OCUPADO = 3, 4

NUL = bytes([0])


class Estructura:
    """Una entrada de la tabla: cabecera + campos fijos + cadenas."""

    __slots__ = ("tipo", "handle", "datos", "cadenas")

    def __init__(self, tipo: int, handle: int, datos: bytes, cadenas: list[str]):
        self.tipo    = tipo
        self.handle  = handle
        self.datos   = datos
        self.cadenas = cadenas

    def texto(self, offset: int) -> str:
        """Cadena referenciada por el byte que hay en `offset` (índice 1-based)."""
        idx = self.byte(offset)
        if idx and 0 < idx <= len(self.cadenas):
            return self.cadenas[idx - 1].strip()
        return ""

    def byte(self, offset: int) -> int:
        return self.datos[offset] if offset < len(self.datos) else 0

    def word(self, offset: int) -> int:
        if offset + 2 > len(self.datos):
            return 0
        return struct.unpack_from("<H", self.datos, offset)[0]

    def qword(self, offset: int) -> int:
        if offset + 8 > len(self.datos):
            return 0
        return struct.unpack_from("<Q", self.datos, offset)[0]


def _leer_cadenas(blob: bytes, off: int) -> tuple[list[str], int]:
    """Cadenas de una estructura y offset donde empieza la siguiente.

    El área de texto termina en dos nulos seguidos, y una estructura sin
    cadenas son justo esos dos nulos. Saltar solo uno desincroniza el recorrido
    entero: a partir de ahí no se reconoce ningún tipo más.
    """
    cadenas: list[str] = []
    i = off
    if blob[i:i + 2] == NUL * 2:
        return cadenas, i + 2
    actual = b""
    while i < len(blob):
        if blob[i] == 0:
            if actual:
                cadenas.append(actual.decode("latin-1", "replace"))
                actual = b""
            if blob[i + 1:i + 2] == NUL:
                return cadenas, i + 2
        else:
            actual += blob[i:i + 1]
        i += 1
    return cadenas, i


def parse_tables(data: bytes) -> dict[int, list[Estructura]]:
    """Trocea el flujo de estructuras SMBIOS, agrupadas por tipo."""
    tablas: dict[int, list[Estructura]] = {}
    i = 0
    while i + 4 <= len(data):
        tipo, longitud = data[i], data[i + 1]
        if longitud < 4 or i + longitud > len(data):
            break
        handle = struct.unpack_from("<H", data, i + 2)[0]
        cuerpo = data[i:i + longitud]
        cadenas, siguiente = _leer_cadenas(data, i + longitud)
        tablas.setdefault(tipo, []).append(Estructura(tipo, handle, cuerpo, cadenas))
        if tipo == 127:          # End-of-table
            break
        if siguiente <= i:       # defensa contra tablas corruptas
            break
        i = siguiente
    return tablas


def read_raw_table() -> bytes:
    """Tabla SMBIOS cruda, sin la cabecera de 8 bytes que añade Windows."""
    try:
        k = ctypes.windll.kernel32
        k.GetSystemFirmwareTable.restype = ctypes.c_uint
        tam = k.GetSystemFirmwareTable(RSMB, 0, None, 0)
        if not tam:
            return b""
        buf = ctypes.create_string_buffer(tam)
        escrito = k.GetSystemFirmwareTable(RSMB, 0, buf, tam)
        if not escrito:
            return b""
        return buf.raw[8:escrito]
    except Exception:
        return b""


def load() -> dict[int, list[Estructura]]:
    datos = read_raw_table()
    return parse_tables(datos) if datos else {}
