import re
import psutil

from ._shell import run


# ── Plan de energía ───────────────────────────────────────────────────────────

_POWER_PLANS = {
    "381b4222-f694-41f0-9685-ff5bb260df2e": ("Equilibrado",          "ok"),
    "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c": ("Alto rendimiento",     "ok"),
    "a1841308-3541-4fab-bc81-f71556f20b4a": ("Ahorro de energía",    "warning"),
    "e9a42b02-d5df-448d-aa00-03f14749eb61": ("Alto rendimiento+",    "ok"),
}


def _get_power_plan() -> dict:
    try:
        text = run(["powercfg", "/getactivescheme"], timeout=10).stdout
        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", text, re.I)
        if not m:
            return {"name": "Desconocido", "guid": "", "status": "ok"}
        guid = m.group(1).lower()
        name_match = re.search(r"\((.+?)\)\s*$", text.strip())
        name = name_match.group(1).strip() if name_match else _POWER_PLANS.get(guid, ("Desconocido",))[0]
        _, status = _POWER_PLANS.get(guid, (name, "ok"))
        return {"name": name, "guid": guid, "status": status}
    except Exception:
        return {"name": "No disponible", "guid": "", "status": "ok"}


# ── Batería ───────────────────────────────────────────────────────────────────

def _get_battery() -> dict | None:
    batt = psutil.sensors_battery()
    if batt is None:
        return None

    pct = round(batt.percent, 1)
    plugged = batt.power_plugged

    if batt.secsleft in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN) or plugged:
        time_left = "Cargando" if plugged else "Calculando…"
    else:
        h, m = divmod(batt.secsleft // 60, 60)
        time_left = f"{h}h {m:02d}m restantes"

    if pct >= 80:
        status = "ok"
    elif pct >= 30:
        status = "warning"
    else:
        status = "danger"

    # Capacidad de diseño vs carga máxima actual (requiere powercfg /batteryreport)
    health = _battery_health()

    return {
        "percent":   pct,
        "plugged":   plugged,
        "time_left": time_left,
        "status":    status,
        "health":    health,
    }


def _battery_health() -> dict | None:
    """Extrae capacidad diseño vs. actual con powercfg /batteryreport."""
    import tempfile, os, pathlib
    try:
        tmp = pathlib.Path(tempfile.gettempdir()) / "pcguardian_batt.html"
        run(["powercfg", "/batteryreport", "/output", str(tmp), "/duration", "1"], timeout=20)
        if not tmp.exists():
            return None
        html = tmp.read_text(encoding="utf-8", errors="ignore")
        tmp.unlink(missing_ok=True)

        design = re.search(r"DESIGN CAPACITY.*?(\d[\d,]+)\s*m[Ww][Hh]", html)
        full   = re.search(r"FULL CHARGE CAPACITY.*?(\d[\d,]+)\s*m[Ww][Hh]", html)
        if design and full:
            d = int(design.group(1).replace(",", ""))
            f = int(full.group(1).replace(",", ""))
            pct = round(f / d * 100, 1) if d else None
            return {"design_mwh": d, "full_mwh": f, "health_pct": pct}
    except Exception:
        pass
    return None


# ── Temperaturas ──────────────────────────────────────────────────────────────

def _get_temperatures() -> tuple[list[dict], bool]:
    """
    Devuelve (lista_sensores, ohm_available).
    Intenta primero OpenHardwareMonitor WMI, luego MSAcpi WMI.
    """
    sensors: list[dict] = []

    # 1) OpenHardwareMonitor (más detallado)
    try:
        import wmi  # type: ignore
        w = wmi.WMI(namespace=r"root\OpenHardwareMonitor")
        for s in w.Sensor():
            if s.SensorType != "Temperature":
                continue
            val = float(s.Value)
            if val <= 0:
                continue
            status = "danger" if val >= 90 else "warning" if val >= 75 else "ok"
            sensors.append({
                "name":   s.Name,
                "value":  round(val, 1),
                "unit":   "°C",
                "status": status,
            })
        if sensors:
            return sensors, True
    except Exception:
        pass

    # 2) ACPI thermal zones (valores brutos en décimas de Kelvin)
    try:
        import wmi  # type: ignore
        w = wmi.WMI(namespace=r"root\WMI")
        for i, tz in enumerate(w.MSAcpi_ThermalZoneTemperature()):
            kelvin = float(tz.CurrentTemperature) / 10.0
            celsius = round(kelvin - 273.15, 1)
            if celsius <= 0:
                continue
            status = "danger" if celsius >= 90 else "warning" if celsius >= 75 else "ok"
            sensors.append({
                "name":   f"Zona térmica {i + 1}",
                "value":  celsius,
                "unit":   "°C",
                "status": status,
            })
        if sensors:
            return sensors, False
    except Exception:
        pass

    return [], False


# ── Punto de entrada ──────────────────────────────────────────────────────────

def analyze_energy() -> dict:
    plan  = _get_power_plan()
    batt  = _get_battery()
    temps, ohm = _get_temperatures()

    items: list[dict] = []
    issues = 0

    # — Plan de energía
    plan_status = plan["status"]
    items.append({
        "name":    "Plan de energía",
        "status":  plan_status,
        "message": plan["name"],
        "value":   plan["name"],
        "detail":  "Ahorro de energía puede limitar el rendimiento del CPU" if plan_status == "warning" else "",
    })
    if plan_status != "ok":
        issues += 1

    # — Batería
    if batt:
        items.append({
            "name":    "Batería",
            "status":  batt["status"],
            "message": f"{batt['percent']}% — {batt['time_left']}",
            "value":   f"{batt['percent']}%",
            "detail":  "Conectado a la corriente" if batt["plugged"] else "",
        })
        if batt["status"] != "ok":
            issues += 1

        if batt["health"] and batt["health"].get("health_pct") is not None:
            hp = batt["health"]["health_pct"]
            h_status = "ok" if hp >= 80 else "warning" if hp >= 60 else "danger"
            items.append({
                "name":    "Salud de la batería",
                "status":  h_status,
                "message": f"{hp}% de capacidad original",
                "value":   f"{hp}%",
                "detail":  f"Diseño: {batt['health']['design_mwh']} mWh  ·  Actual: {batt['health']['full_mwh']} mWh",
            })
            if h_status != "ok":
                issues += 1
    else:
        items.append({
            "name":    "Batería",
            "status":  "ok",
            "message": "No detectada (equipo de escritorio)",
            "value":   "N/A",
            "detail":  "",
        })

    # — Temperaturas
    temp_note = ""
    if not temps:
        temp_note = (
            "Para ver temperaturas instala y ejecuta "
            "OpenHardwareMonitor (libre) como administrador."
        )
    for s in temps:
        items.append({
            "name":    s["name"],
            "status":  s["status"],
            "message": f"{s['value']} {s['unit']}",
            "value":   f"{s['value']} {s['unit']}",
            "detail":  "",
        })
        if s["status"] != "ok":
            issues += 1

    # — Estado general
    all_statuses = [i["status"] for i in items]
    if "danger" in all_statuses:
        overall, summary = "danger", "Hay valores críticos de temperatura o batería."
    elif "warning" in all_statuses:
        overall = "warning"
        parts = []
        if plan["status"] == "warning":
            parts.append("plan de energía subóptimo")
        hot = [s for s in temps if s["status"] != "ok"]
        if hot:
            parts.append(f"{len(hot)} sensor(es) con temperatura elevada")
        summary = "Aviso: " + " · ".join(parts) if parts else "Revisa los valores marcados."
    else:
        overall = "ok"
        summary = "Energía y temperaturas en rangos normales."

    if not temps and temp_note:
        summary += f" {temp_note}"

    return {
        "status":      overall,
        "title":       "Energía y Temperatura",
        "summary":     summary,
        "issue_count": issues,
        "items":       items,
        "has_battery": batt is not None,
        "ohm_available": ohm,
        "temp_count":  len(temps),
    }
