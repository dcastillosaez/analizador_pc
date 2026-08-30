"""Configuración de firmware — lee el estado efectivo de la BIOS/UEFI.

Las opciones del menú de setup (XMP, VT-d, CSM…) viven en variables NVRAM con
GUID propietario y formato binario opaco: no hay forma genérica de leerlas. Sí
la hay de leer el *resultado* de esas opciones, que para diagnosticar sirve
igual: si el XMP está desactivado, la RAM corre por debajo de su velocidad
nominal, y eso se ve.

Las fuentes son todas estándar y funcionan en cualquier PC: la tabla SMBIOS que
publica el firmware, el registro de Windows y las API del sistema.
"""
import ctypes
import datetime
import re
import winreg
from ctypes import wintypes

from . import _smbios
from ._shell import run, run_ps_json

# Velocidades DDR plausibles, para no confundir un número de serie con MT/s
VEL_MIN, VEL_MAX = 1600, 9000

ANOS_BIOS_VIEJA = 3


# ── Memoria ───────────────────────────────────────────────────────────────────

def _velocidad_nominal(part_number: str) -> int | None:
    """Velocidad que anuncia el módulo, deducida de su referencia.

    Sin XMP aplicado, SMBIOS informa de la velocidad JEDEC base tanto en `Speed`
    como en `ConfiguredMemorySpeed`, así que la única pista de a cuánto debería
    ir el módulo está en su part number (CMK16GX4M1B**3000**C15).
    """
    if not part_number:
        return None
    candidatos = [int(n) for n in re.findall(r"(?<!\d)(\d{4})(?!\d)", part_number)
                  if VEL_MIN <= int(n) <= VEL_MAX]
    return max(candidatos) if candidatos else None


def _canal(slot: str) -> str:
    """Canal al que pertenece un zócalo, a partir de su etiqueta."""
    etiqueta = slot.upper()
    m = re.search(r"CHANNEL\s*([A-D])", etiqueta)
    if m:
        return m.group(1)
    m = re.search(r"DIMM[_ ]?([A-D])(?!\d)", etiqueta)
    return m.group(1) if m else ""


def _check_memoria(modulos: list[dict]) -> list[dict]:
    items: list[dict] = []
    if not modulos:
        return items

    # 1. ¿Corre la RAM por debajo de lo que anuncian los módulos?
    lentos = []
    for m in modulos:
        conf = m.get("configurada") or m.get("speed") or 0
        objetivo = max(_velocidad_nominal(m.get("part", "")) or 0, m.get("speed") or 0)
        if conf and objetivo > conf:
            lentos.append((m, conf, objetivo))

    if lentos:
        m, conf, objetivo = lentos[0]
        ganancia = round((objetivo / conf - 1) * 100)
        items.append({
            "name": "Velocidad de la memoria (XMP/EXPO)",
            "status": "warning",
            "message": (f"La RAM corre a {conf} MHz pero los módulos admiten {objetivo} MHz. "
                        f"El perfil XMP/EXPO está desactivado: activarlo en la BIOS recupera "
                        f"cerca de un {ganancia}% de ancho de banda de memoria."),
            "value": f"{conf} de {objetivo} MHz",
            "detail": f"{m.get('fabricante', '')} {m.get('part', '')}".strip(),
        })
    else:
        conf = modulos[0].get("configurada") or modulos[0].get("speed") or 0
        items.append({
            "name": "Velocidad de la memoria (XMP/EXPO)",
            "status": "ok",
            "message": f"La memoria corre a {conf} MHz, la velocidad que anuncian los módulos.",
            "value": f"{conf} MHz",
            "detail": "",
        })

    # 2. ¿Están repartidos entre canales?
    if len(modulos) >= 2:
        canales = {_canal(m.get("slot", "")) for m in modulos}
        canales.discard("")
        zocalos = ", ".join(sorted(m.get("slot", "") for m in modulos))
        if len(canales) >= 2:
            items.append({
                "name": "Canales de memoria",
                "status": "ok",
                "message": f"Los {len(modulos)} módulos están repartidos entre {len(canales)} canales.",
                "value": "Dual channel" if len(canales) == 2 else f"{len(canales)} canales",
                "detail": zocalos,
            })
        elif canales:
            items.append({
                "name": "Canales de memoria",
                "status": "warning",
                "message": (f"Los {len(modulos)} módulos están en el mismo canal. Repartirlos "
                            "entre canales distintos duplica el ancho de banda; el manual de la "
                            "placa indica qué zócalos emparejar."),
                "value": "Single channel",
                "detail": zocalos,
            })

    return items


# ── CPU ───────────────────────────────────────────────────────────────────────

def _check_nucleos(cpu: dict) -> dict:
    presentes = cpu.get("nucleos") or 0
    activos = cpu.get("habilitados") or 0
    hilos = cpu.get("hilos") or 0
    if presentes and activos and activos < presentes:
        return {
            "name": "Núcleos de CPU habilitados",
            "status": "warning",
            "message": (f"El procesador tiene {presentes} núcleos pero solo {activos} están "
                        "habilitados. Revisa 'Active Processor Cores' en la BIOS."),
            "value": f"{activos} de {presentes}",
            "detail": f"{hilos} hilos" if hilos else "",
        }
    return {
        "name": "Núcleos de CPU habilitados",
        "status": "ok",
        "message": (f"Los {presentes} núcleos del procesador están habilitados."
                    if presentes else "El firmware no informa del recuento de núcleos."),
        "value": f"{activos or presentes} activos" if presentes else "Sin dato",
        "detail": f"{hilos} hilos" if hilos else "",
    }


# ── Slots PCIe ────────────────────────────────────────────────────────────────

def _lineas(ancho) -> int:
    try:
        return int(str(ancho).lower().lstrip("x"))
    except (ValueError, AttributeError):
        return 0


def _check_slots(slots: list[dict]) -> dict:
    """Avisa si una tarjeta ancha ocupa un slot estrecho habiendo otro mejor libre."""
    ocupados = [s for s in slots if s.get("ocupado") and _lineas(s.get("ancho")) >= 4]
    libres = [s for s in slots if not s.get("ocupado")]

    if ocupados and libres:
        peor = min(ocupados, key=lambda s: _lineas(s.get("ancho")))
        mejor = max(libres, key=lambda s: _lineas(s.get("ancho")))
        if _lineas(mejor.get("ancho")) > _lineas(peor.get("ancho")):
            return {
                "name": "Slots PCI Express",
                "status": "warning",
                "message": (f"Hay una tarjeta en {peor['nombre']} ({peor['ancho']}) mientras "
                            f"{mejor['nombre']} ({mejor['ancho']}) está libre. Cambiarla de "
                            "zócalo le da más líneas sin coste alguno."),
                "value": f"{peor['nombre']} {peor['ancho']}",
                "detail": " · ".join(f"{s['nombre']} {s['ancho']} "
                                     f"{'ocupado' if s.get('ocupado') else 'libre'}"
                                     for s in slots),
            }

    ocupado_txt = ", ".join(f"{s['nombre']} ({s['ancho']})" for s in ocupados) or "ninguno"
    return {
        "name": "Slots PCI Express",
        "status": "ok",
        "message": f"Tarjetas instaladas en zócalos adecuados: {ocupado_txt}.",
        "value": f"{len(ocupados)} en uso",
        "detail": " · ".join(f"{s['nombre']} {s['ancho']}" for s in slots),
    }


# ── BIOS ──────────────────────────────────────────────────────────────────────

def _check_bios_date(fecha: str, hoy: tuple[int, int, int] | None = None) -> dict:
    """Antigüedad de la BIOS. `hoy` se inyecta desde los tests."""
    desconocida = {
        "name": "Versión de la BIOS", "status": "ok", "value": "Sin fecha",
        "message": "El firmware no informa de la fecha de publicación de la BIOS.",
        "detail": fecha,
    }
    if not fecha:
        return desconocida
    try:
        mes, dia, ano = (int(x) for x in fecha.split("/")[:3])
        publicada = datetime.date(ano, mes, dia)
    except Exception:
        return desconocida

    ahora = datetime.date(*hoy) if hoy else datetime.date.today()
    anos = (ahora - publicada).days / 365.25
    legible = publicada.strftime("%d/%m/%Y")

    if anos >= ANOS_BIOS_VIEJA:
        return {
            "name": "Versión de la BIOS",
            "status": "warning",
            "message": (f"La BIOS es del {legible}, hace {anos:.0f} años. Las revisiones "
                        "posteriores suelen traer microcódigo de CPU con parches de seguridad "
                        "y mejor compatibilidad de memoria. Búscala en la web del fabricante."),
            "value": f"{anos:.0f} años",
            "detail": legible,
        }
    return {
        "name": "Versión de la BIOS",
        "status": "ok",
        "message": f"La BIOS es del {legible}, razonablemente reciente.",
        "value": f"{anos:.0f} años" if anos >= 1 else "Menos de 1 año",
        "detail": legible,
    }


# ── Extractores de la tabla SMBIOS ────────────────────────────────────────────
# Offsets de la especificación DMTF DSP0134. Cada fabricante rellena las
# estructuras que quiere, así que todo lo que falte sale como 0 o cadena vacía.

def _leer_modulos(tablas: dict) -> list[dict]:
    """Type 17 — Memory Device, un registro por zócalo (vacíos incluidos)."""
    modulos = []
    for e in tablas.get(17, []):
        tam = e.word(0x0C)
        if not tam:                       # zócalo vacío
            continue
        modulos.append({
            "slot":         e.texto(0x10),
            "fabricante":   e.texto(0x17),
            "part":         e.texto(0x1A),
            "capacidad_gb": round(tam / 1024) if tam != 0x7FFF else 0,
            "speed":        e.word(0x15),
            "configurada":  e.word(0x20),
        })
    return modulos


def _leer_zocalos_totales(tablas: dict) -> tuple[int, int]:
    """Type 16 — zócalos que tiene la placa y capacidad máxima en GB."""
    for e in tablas.get(16, []):
        zocalos = e.word(0x0D)
        max_kb = int.from_bytes(e.datos[0x07:0x0B], "little") if len(e.datos) > 0x0B else 0
        if max_kb == 0x80000000 and len(e.datos) > 0x17:      # usa el campo extendido
            max_gb = round(e.qword(0x0F) / 1024)
        else:
            max_gb = round(max_kb / 1024 / 1024)
        return zocalos, max_gb
    return 0, 0


def _leer_cpu(tablas: dict) -> dict:
    """Type 4 — Processor Information."""
    for e in tablas.get(4, []):
        if e.byte(0x05) not in (3, 0xCD):     # ProcessorType: 3 = Central Processor
            continue
        return {
            "nombre":      e.texto(0x10),
            "socket":      e.texto(0x04),
            "bclk":        e.word(0x12),
            "max_mhz":     e.word(0x14),
            "actual_mhz":  e.word(0x16),
            "nucleos":     e.byte(0x23),
            "habilitados": e.byte(0x24),
            "hilos":       e.byte(0x25),
        }
    return {}


def _leer_slots(tablas: dict) -> list[dict]:
    """Type 9 — System Slots. Solo los PCI Express con más de una línea."""
    slots = []
    for e in tablas.get(9, []):
        ancho = _smbios.ANCHOS_SLOT.get(e.byte(0x06))
        if not ancho:
            continue
        slots.append({
            "nombre":  e.texto(0x04),
            "ancho":   ancho,
            "ocupado": e.byte(0x07) == _smbios.SLOT_OCUPADO,
        })
    return slots


def _leer_bios(tablas: dict) -> dict:
    """Type 0 — BIOS Information."""
    for e in tablas.get(0, []):
        return {
            "fabricante": e.texto(0x04),
            "version":    e.texto(0x05),
            "fecha":      e.texto(0x08),
            "rom_kb":     (e.byte(0x09) + 1) * 64,
        }
    return {}


# ── Estado del arranque y del firmware ────────────────────────────────────────

GUID_GLOBAL = "{8be4df61-93ca-11d2-aa0d-00e098032b8c}"
ERROR_INVALID_FUNCTION = 1
ERROR_PRIVILEGE_NOT_HELD = 1314


def _uefi_var(nombre: str) -> tuple[bytes | None, int]:
    """Lee una variable del namespace global de UEFI. Devuelve (valor, error).

    Las variables globales están estandarizadas por la especificación UEFI, así
    que valen en cualquier equipo — pero leerlas exige el privilegio
    SE_SYSTEM_ENVIRONMENT_NAME, es decir, ejecutar elevado. En un arranque
    Legacy la API responde ERROR_INVALID_FUNCTION.
    """
    try:
        k = ctypes.windll.kernel32
        k.GetFirmwareEnvironmentVariableW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD]
        k.GetFirmwareEnvironmentVariableW.restype = wintypes.DWORD
        buf = ctypes.create_string_buffer(4096)
        n = k.GetFirmwareEnvironmentVariableW(nombre, GUID_GLOBAL, buf, len(buf))
        if n:
            return buf.raw[:n], 0
        return None, ctypes.GetLastError()
    except Exception:
        return None, -1


def _es_uefi() -> bool:
    """UEFI o BIOS heredada, sin necesidad de privilegios.

    El truco documentado: con un nombre de variable vacío, la API contesta
    ERROR_INVALID_FUNCTION en un arranque Legacy y cualquier otro error (falta
    de privilegio, normalmente) cuando el firmware es UEFI.
    """
    _, err = _uefi_var("")
    return err != ERROR_INVALID_FUNCTION


def _check_modo_arranque() -> list[dict]:
    uefi = _es_uefi()
    items = [{
        "name": "Modo de arranque del firmware",
        "status": "ok" if uefi else "warning",
        "message": ("El equipo arranca en modo UEFI, que es lo correcto: permite Secure Boot, "
                    "discos de más de 2 TB y arranques más rápidos."
                    if uefi else
                    "El equipo arranca en modo Legacy/CSM. Sin UEFI no hay Secure Boot y el "
                    "disco de sistema queda atado a MBR. Migrar exige convertir el disco a GPT "
                    "(mbr2gpt) antes de cambiar el ajuste en la BIOS."),
        "value": "UEFI" if uefi else "Legacy/CSM",
        "detail": "",
    }]

    estilo = run_ps_json(
        "Get-Partition -DriveLetter C | Get-Disk | "
        "Select-Object -First 1 Number,PartitionStyle,FriendlyName | ConvertTo-Json -Compress",
        timeout=15, default=None,
    )
    if isinstance(estilo, dict) and estilo.get("PartitionStyle"):
        gpt = str(estilo["PartitionStyle"]).upper() == "GPT"
        items.append({
            "name": "Partición del disco de sistema",
            "status": "ok" if gpt or not uefi else "warning",
            "message": ("El disco de sistema usa GPT, el esquema que corresponde a un arranque UEFI."
                        if gpt else
                        "El disco de sistema usa MBR. En un equipo que arranca por UEFI conviene "
                        "convertirlo a GPT con mbr2gpt para no depender del modo de compatibilidad."),
            "value": str(estilo["PartitionStyle"]),
            "detail": str(estilo.get("FriendlyName", "")),
        })
    return items


def _check_virtualizacion() -> dict:
    """VT-x / AMD-V.

    Ojo con el falso positivo: cuando el hipervisor de Windows está en marcha,
    Win32_Processor informa de VirtualizationFirmwareEnabled=False porque la
    consulta ya pasa por el hipervisor. Si hay hipervisor, la virtualización
    está necesariamente activa en el firmware.
    """
    datos = run_ps_json(
        "$cs = Get-CimInstance Win32_ComputerSystem; "
        "$p = Get-CimInstance Win32_Processor | Select-Object -First 1; "
        "[pscustomobject]@{Hypervisor=$cs.HypervisorPresent;"
        "Firmware=$p.VirtualizationFirmwareEnabled} | ConvertTo-Json -Compress",
        timeout=20, default=None,
    )
    if not isinstance(datos, dict):
        return {"name": "Virtualización (VT-x / AMD-V)", "status": "ok",
                "message": "No se pudo consultar el estado de la virtualización.",
                "value": "Sin dato", "detail": ""}

    activa = bool(datos.get("Hypervisor")) or bool(datos.get("Firmware"))
    return {
        "name": "Virtualización (VT-x / AMD-V)",
        "status": "ok" if activa else "warning",
        "message": ("La virtualización por hardware está habilitada en el firmware."
                    if activa else
                    "La virtualización por hardware está desactivada en la BIOS. Sin ella no "
                    "funcionan Hyper-V, WSL2, los emuladores de Android ni la seguridad basada "
                    "en virtualización de Windows."),
        "value": "Activa" if activa else "Desactivada",
        "detail": "Hipervisor en marcha" if datos.get("Hypervisor") else "",
    }


def _check_almacenamiento() -> dict:
    """Modo del controlador SATA. En IDE/RAID el driver AHCI queda deshabilitado."""
    estados = {}
    for servicio in ("storahci", "stornvme", "iaStorV", "iaStorAC"):
        try:
            ruta = rf"SYSTEM\CurrentControlSet\Services\{servicio}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta, 0, winreg.KEY_READ) as k:
                estados[servicio] = winreg.QueryValueEx(k, "Start")[0]
        except Exception:
            continue

    arrancan = [s for s, v in estados.items() if v in (0, 1, 2)]
    ahci_ok = any(s in arrancan for s in ("storahci", "stornvme"))
    return {
        "name": "Controlador de almacenamiento",
        "status": "ok" if ahci_ok else "warning",
        "message": ("El controlador de disco arranca en modo AHCI/NVMe, que es el que da todo "
                    "el rendimiento y soporte de TRIM."
                    if ahci_ok else
                    "No hay ningún controlador AHCI ni NVMe activo. Si el SATA está en modo IDE "
                    "o RAID en la BIOS, los SSD pierden rendimiento y TRIM."),
        "value": ", ".join(s for s in arrancan if s in ("storahci", "stornvme")) or "Sin AHCI",
        "detail": " · ".join(f"{s}: Start={v}" for s, v in estados.items()),
    }


def _check_limites_arranque() -> dict:
    """Límites impuestos por el gestor de arranque (msconfig deja estos rastros)."""
    r = run(["bcdedit", "/enum", "{current}"], timeout=15)
    salida = (r.combined or "").lower()
    limites = [clave for clave in ("numproc", "truncatememory", "removememory", "maxproc")
               if clave in salida]
    if limites:
        return {
            "name": "Límites del gestor de arranque",
            "status": "warning",
            "message": ("El arranque de Windows tiene límites artificiales activos "
                        f"({', '.join(limites)}). Suelen quedarse puestos tras trastear en "
                        "msconfig y recortan núcleos o memoria disponibles. Quítalos con "
                        "'bcdedit /deletevalue {current} <opción>'."),
            "value": ", ".join(limites),
            "detail": "",
        }
    return {
        "name": "Límites del gestor de arranque",
        "status": "ok",
        "message": "Windows arranca sin límites artificiales de núcleos ni de memoria.",
        "value": "Sin límites",
        "detail": "",
    }


def _check_uefi_globales() -> list[dict]:
    """Variables UEFI estandarizadas. Requieren privilegios de administrador."""
    valor, err = _uefi_var("SetupMode")
    if err == ERROR_PRIVILEGE_NOT_HELD:
        return [{
            "name": "Variables UEFI",
            "status": "ok",
            "message": ("El orden de arranque y el modo de Secure Boot solo se pueden leer con "
                        "permisos de administrador. Reinicia la app elevada para verlos."),
            "value": "Requiere admin",
            "detail": "",
        }]
    if err == ERROR_INVALID_FUNCTION or valor is None:
        return []

    items = []
    if valor and valor[0] == 1:
        items.append({
            "name": "Modo de configuración de Secure Boot",
            "status": "warning",
            "message": ("El firmware está en Setup Mode: las claves de Secure Boot no están "
                        "instaladas, así que la verificación de arranque no protege nada. "
                        "Restaura las claves de fábrica en la BIOS."),
            "value": "Setup Mode",
            "detail": "",
        })

    orden, err_orden = _uefi_var("BootOrder")
    if orden and not err_orden:
        entradas = [f"Boot{orden[i + 1] << 8 | orden[i]:04X}" for i in range(0, len(orden) - 1, 2)]
        items.append({
            "name": "Orden de arranque",
            "status": "ok",
            "message": f"El firmware tiene {len(entradas)} entradas de arranque configuradas.",
            "value": f"{len(entradas)} entradas",
            "detail": " → ".join(entradas[:8]),
        })
    return items


def _check_ajustes_oem() -> dict:
    """¿Expone el fabricante sus ajustes de BIOS por WMI?

    Solo HP, Dell y Lenovo publican interfaces WMI para el setup. En placas
    retail (ASUS, MSI, Gigabyte) no existe nada equivalente.
    """
    encontrado = run_ps_json(
        "$r = @(); "
        "if (Get-CimClass -Namespace root\\HP\\InstrumentedBIOS -ClassName HP_BIOSSetting "
        "-ErrorAction SilentlyContinue) { $r += 'HP' } "
        "if (Get-CimClass -Namespace root\\DCIM\\SYSMAN -ClassName DCIM_BIOSEnumeration "
        "-ErrorAction SilentlyContinue) { $r += 'Dell' } "
        "if (Get-CimClass -Namespace root\\WMI -ClassName Lenovo_BiosSetting "
        "-ErrorAction SilentlyContinue) { $r += 'Lenovo' } "
        "ConvertTo-Json -Compress -InputObject @($r)",
        timeout=25, default=[],
    )
    marcas = [m for m in (encontrado or []) if m]
    if marcas:
        return {
            "name": "Ajustes del fabricante por WMI",
            "status": "ok",
            "message": (f"El firmware expone sus ajustes por WMI ({', '.join(marcas)}). En estos "
                        "equipos sí se pueden consultar y cambiar opciones concretas del setup."),
            "value": ", ".join(marcas),
            "detail": "",
        }
    return {
        "name": "Ajustes del fabricante por WMI",
        "status": "ok",
        "message": ("Esta placa no publica sus opciones de setup por WMI, como ocurre en casi "
                    "todas las placas de sobremesa. Los cambios hay que hacerlos entrando en la "
                    "BIOS al arrancar."),
        "value": "No disponible",
        "detail": "Solo HP, Dell y Lenovo lo ofrecen",
    }


# ── Ensamblado ────────────────────────────────────────────────────────────────

def analyze_bios() -> dict:
    tablas = _smbios.load()
    items: list[dict] = []

    info = _leer_bios(tablas)
    if info:
        items.append({
            "name": "Firmware instalado",
            "status": "ok",
            "message": f"{info['fabricante']} versión {info['version']}.",
            "value": info["version"] or "Desconocida",
            "detail": f"ROM de {info['rom_kb']} KB",
        })
        items.append(_check_bios_date(info.get("fecha", "")))

    items.extend(_check_modo_arranque())
    items.extend(_check_memoria(_leer_modulos(tablas)))

    zocalos, max_gb = _leer_zocalos_totales(tablas)
    modulos = _leer_modulos(tablas)
    if zocalos and modulos:
        instalada = sum(m.get("capacidad_gb", 0) for m in modulos)
        libres = zocalos - len(modulos)
        items.append({
            "name": "Ampliación de memoria",
            "status": "ok",
            "message": (f"{instalada} GB instalados en {len(modulos)} de {zocalos} zócalos."
                        + (f" Quedan {libres} libres y la placa admite hasta {max_gb} GB."
                           if libres and max_gb else "")),
            "value": f"{instalada} GB",
            "detail": f"{zocalos} zócalos · máximo {max_gb} GB" if max_gb else "",
        })

    cpu = _leer_cpu(tablas)
    if cpu:
        items.append(_check_nucleos(cpu))

    slots = _leer_slots(tablas)
    if slots:
        items.append(_check_slots(slots))

    items.append(_check_virtualizacion())
    items.append(_check_almacenamiento())
    items.append(_check_limites_arranque())
    items.extend(_check_uefi_globales())
    items.append(_check_ajustes_oem())

    if not tablas:
        items.insert(0, {
            "name": "Tabla SMBIOS",
            "status": "warning",
            "message": ("El firmware no publicó su tabla SMBIOS, así que no se puede leer la "
                        "configuración de memoria, CPU ni slots."),
            "value": "No disponible",
            "detail": "",
        })

    danger = sum(1 for i in items if i["status"] == "danger")
    warning = sum(1 for i in items if i["status"] == "warning")
    overall = "danger" if danger else ("warning" if warning else "ok")
    summaries = {
        "danger": f"{danger} problema(s) graves de configuración del firmware.",
        "warning": (f"{warning} ajuste(s) del firmware pueden mejorarse. "
                    "Los cambios se hacen entrando en la BIOS al arrancar."),
        "ok": "La configuración del firmware es correcta en todo lo que se puede comprobar.",
    }
    return {"status": overall, "title": "Configuración de BIOS/UEFI",
            "summary": summaries[overall], "issue_count": danger + warning,
            "items": items}
