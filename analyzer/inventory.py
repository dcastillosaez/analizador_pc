import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from ._shell import run_ps_json


def _ps(cmd: str):
    """Ejecuta un comando PowerShell y devuelve el resultado como JSON parseado."""
    return run_ps_json(cmd, timeout=30, default=None)


def _query_baseboard():
    data = _ps(
        "Get-WmiObject Win32_BaseBoard | "
        "Select-Object Manufacturer, Product, SerialNumber | "
        "ConvertTo-Json -Compress"
    )
    if not data:
        return {}
    if isinstance(data, list):
        data = data[0]
    return {
        "Fabricante": data.get("Manufacturer", "—"),
        "Modelo": data.get("Product", "—"),
        "Número de serie": data.get("SerialNumber", "—"),
    }


def _query_bios():
    data = _ps(
        "Get-WmiObject Win32_BIOS | "
        "Select-Object Manufacturer, SMBIOSBIOSVersion, ReleaseDate | "
        "ConvertTo-Json -Compress"
    )
    if not data:
        return {}
    if isinstance(data, list):
        data = data[0]
    release = data.get("ReleaseDate", "")
    # El formato WMI es YYYYMMDD000000.000000+000; extraemos YYYY-MM-DD
    if release and len(release) >= 8:
        release = f"{release[:4]}-{release[4:6]}-{release[6:8]}"
    return {
        "Fabricante": data.get("Manufacturer", "—"),
        "Versión": data.get("SMBIOSBIOSVersion", "—"),
        "Fecha de lanzamiento": release or "—",
    }


def _query_gpu():
    data = _ps(
        "Get-WmiObject Win32_VideoController | "
        "Select-Object Name, AdapterRAM, DriverVersion, CurrentRefreshRate | "
        "ConvertTo-Json -Compress"
    )
    if not data:
        return []
    if isinstance(data, dict):
        data = [data]
    gpus = []
    for gpu in data:
        ram_bytes = gpu.get("AdapterRAM") or 0
        try:
            ram_gb = f"{round(int(ram_bytes) / (1024 ** 3), 1)} GB"
        except (ValueError, TypeError):
            ram_gb = "—"
        gpus.append({
            "Nombre": gpu.get("Name", "—"),
            "VRAM": ram_gb,
            "Driver": gpu.get("DriverVersion", "—"),
            "Frecuencia actual": f"{gpu.get('CurrentRefreshRate', '—')} Hz",
        })
    return gpus


def _query_ram():
    data = _ps(
        "Get-WmiObject Win32_PhysicalMemory | "
        "Select-Object BankLabel, Capacity, Speed, Manufacturer | "
        "ConvertTo-Json -Compress"
    )
    if not data:
        return []
    if isinstance(data, dict):
        data = [data]
    slots = []
    for slot in data:
        cap_bytes = slot.get("Capacity") or 0
        try:
            cap_gb = f"{round(int(cap_bytes) / (1024 ** 3), 1)} GB"
        except (ValueError, TypeError):
            cap_gb = "—"
        slots.append({
            "Slot": slot.get("BankLabel", "—"),
            "Capacidad": cap_gb,
            "Velocidad": f"{slot.get('Speed', '—')} MHz",
            "Fabricante": slot.get("Manufacturer", "—"),
        })
    return slots


def _query_cpu():
    data = _ps(
        "Get-WmiObject Win32_Processor | "
        "Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | "
        "ConvertTo-Json -Compress"
    )
    if not data:
        return {}
    if isinstance(data, list):
        data = data[0]
    mhz = data.get("MaxClockSpeed") or 0
    ghz = f"{round(int(mhz) / 1000, 2)} GHz" if mhz else "—"
    return {
        "Nombre": data.get("Name", "—"),
        "Núcleos físicos": str(data.get("NumberOfCores", "—")),
        "Hilos lógicos": str(data.get("NumberOfLogicalProcessors", "—")),
        "Frecuencia máx.": ghz,
    }


def _query_system():
    data = _ps(
        "Get-WmiObject Win32_ComputerSystem | "
        "Select-Object Manufacturer, Model, TotalPhysicalMemory | "
        "ConvertTo-Json -Compress"
    )
    if not data:
        return {}
    if isinstance(data, list):
        data = data[0]
    mem_bytes = data.get("TotalPhysicalMemory") or 0
    try:
        mem_gb = f"{round(int(mem_bytes) / (1024 ** 3), 1)} GB"
    except (ValueError, TypeError):
        mem_gb = "—"
    return {
        "Fabricante": data.get("Manufacturer", "—"),
        "Modelo": data.get("Model", "—"),
        "RAM total": mem_gb,
    }


def analyze_inventory() -> dict:
    queries = {
        "cpu":         _query_cpu,
        "gpu":         _query_gpu,
        "ram":         _query_ram,
        "motherboard": _query_baseboard,
        "bios":        _query_bios,
        "system":      _query_system,
    }

    sections = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): key for key, fn in queries.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                sections[key] = future.result()
            except Exception:
                sections[key] = {}

    cpu_name = sections.get("cpu", {}).get("Nombre", "CPU desconocida")
    system_model = sections.get("system", {}).get("Modelo", "")
    summary = f"{cpu_name}" + (f" — {system_model}" if system_model else "")

    return {
        "status": "ok",
        "title": "Inventario de Hardware",
        "summary": summary,
        "issue_count": 0,
        "sections": sections,
    }
