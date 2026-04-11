import psutil


def _status(value, warn, danger):
    if value >= danger:
        return "danger"
    if value >= warn:
        return "warning"
    return "ok"


def analyze_hardware():
    items = []
    overall = "ok"

    # ── CPU ──────────────────────────────────────────────────────────────────
    cpu_pct = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=True)
    try:
        freq = psutil.cpu_freq()
        freq_str = f"{freq.current / 1000:.1f} GHz" if freq else "frecuencia desconocida"
    except Exception:
        freq_str = "frecuencia desconocida"

    cpu_st = _status(cpu_pct, 70, 90)
    if cpu_st == "danger":
        cpu_msg = (
            f"Tu procesador está al límite ({cpu_pct:.0f}% de uso). "
            "El equipo puede bloquearse o ir muy lento."
        )
        overall = "danger"
    elif cpu_st == "warning":
        cpu_msg = (
            f"El procesador trabaja con mucho esfuerzo ({cpu_pct:.0f}%). "
            "Cierra programas que no uses."
        )
        if overall != "danger":
            overall = "warning"
    else:
        cpu_msg = f"Procesador en buen estado ({cpu_pct:.0f}% de uso)."

    items.append(
        {
            "name": "Procesador (CPU)",
            "status": cpu_st,
            "message": cpu_msg,
            "value": f"{cpu_pct:.0f}%",
            "detail": f"{cpu_count} núcleos · {freq_str}",
        }
    )

    # ── RAM ──────────────────────────────────────────────────────────────────
    ram = psutil.virtual_memory()
    ram_pct = ram.percent
    ram_used = ram.used / 1024**3
    ram_total = ram.total / 1024**3

    ram_st = _status(ram_pct, 75, 90)
    if ram_st == "danger":
        ram_msg = (
            f"La memoria RAM está casi llena ({ram_used:.1f} GB de {ram_total:.0f} GB). "
            "El sistema usará el disco como RAM, lo que lo hace muy lento."
        )
        overall = "danger"
    elif ram_st == "warning":
        ram_msg = (
            f"La RAM está bastante ocupada ({ram_used:.1f} GB de {ram_total:.0f} GB). "
            "Considera cerrar aplicaciones pesadas."
        )
        if overall != "danger":
            overall = "warning"
    else:
        ram_msg = f"Memoria RAM en buen estado ({ram_used:.1f} GB usados de {ram_total:.0f} GB)."

    items.append(
        {
            "name": "Memoria RAM",
            "status": ram_st,
            "message": ram_msg,
            "value": f"{ram_pct:.0f}%",
            "detail": f"{ram_used:.1f} GB usados / {ram_total:.0f} GB total",
        }
    )

    # ── Disco C: ─────────────────────────────────────────────────────────────
    try:
        disk = psutil.disk_usage("C:\\")
        disk_pct = disk.percent
        disk_free = disk.free / 1024**3
        disk_total = disk.total / 1024**3

        disk_st = _status(disk_pct, 75, 90)
        if disk_st == "danger":
            disk_msg = (
                f"El disco C: casi no tiene espacio libre ({disk_free:.0f} GB libres). "
                "Windows no puede funcionar bien con tan poco espacio."
            )
            overall = "danger"
        elif disk_st == "warning":
            disk_msg = (
                f"El espacio en disco está reducido ({disk_free:.0f} GB libres de {disk_total:.0f} GB). "
                "Considera limpiar archivos o desinstalar programas."
            )
            if overall != "danger":
                overall = "warning"
        else:
            disk_msg = f"Disco con espacio suficiente ({disk_free:.0f} GB libres de {disk_total:.0f} GB)."

        items.append(
            {
                "name": "Disco Principal (C:)",
                "status": disk_st,
                "message": disk_msg,
                "value": f"{disk_pct:.0f}%",
                "detail": f"{disk_free:.0f} GB libres · {disk_total:.0f} GB total",
            }
        )
    except Exception:
        items.append(
            {
                "name": "Disco Principal (C:)",
                "status": "warning",
                "message": "No se pudo leer la información del disco principal.",
                "value": "N/A",
                "detail": "",
            }
        )

    issue_count = sum(1 for i in items if i["status"] != "ok")

    if overall == "ok":
        summary = "Todos los recursos del sistema funcionan con normalidad."
    elif overall == "warning":
        summary = f"{issue_count} recurso(s) bajo presión. El equipo puede ir más lento de lo normal."
    else:
        summary = f"¡Atención! {issue_count} recurso(s) en estado crítico. Requiere acción inmediata."

    return {
        "status": overall,
        "title": "Hardware",
        "summary": summary,
        "issue_count": issue_count,
        "items": items,
    }
