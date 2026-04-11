import psutil


def _gpu_usage() -> dict | None:
    """Intenta obtener uso de GPU vía WMI (solo NVIDIA/AMD con drivers WMI)."""
    try:
        import wmi  # type: ignore
        w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
        sensors = w.Sensor()
        gpu_load = next(
            (float(s.Value) for s in sensors if s.SensorType == "Load" and "GPU" in s.Name),
            None,
        )
        if gpu_load is not None:
            return {"percent": round(gpu_load, 1)}
    except Exception:
        pass
    return None


def snapshot() -> dict:
    cpu = psutil.cpu_percent(interval=0.2)

    vm = psutil.virtual_memory()
    ram_total = vm.total
    ram_used  = vm.used
    ram_pct   = vm.percent

    disk = psutil.disk_usage("/")
    disk_total = disk.total
    disk_used  = disk.used
    disk_pct   = disk.percent

    # I/O acumulado (delta calculado en el cliente entre llamadas)
    try:
        io = psutil.disk_io_counters()
        io_read  = io.read_bytes  if io else 0
        io_write = io.write_bytes if io else 0
    except Exception:
        io_read = io_write = 0

    gpu = _gpu_usage()

    return {
        "cpu": {"percent": round(cpu, 1)},
        "ram": {
            "percent": round(ram_pct, 1),
            "used_gb": round(ram_used  / 1024**3, 2),
            "total_gb": round(ram_total / 1024**3, 2),
        },
        "disk": {
            "percent": round(disk_pct, 1),
            "used_gb": round(disk_used  / 1024**3, 1),
            "total_gb": round(disk_total / 1024**3, 1),
        },
        "io": {"read_bytes": io_read, "write_bytes": io_write},
        "gpu": gpu,
    }
