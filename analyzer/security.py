import psutil

from ._text import looks_random, shannon_entropy

# Número esperado de instancias (min, max)
CRITICAL_PROCS = {
    "lsass.exe":    (1, 1),
    "csrss.exe":    (1, 4),
    "winlogon.exe": (1, 4),
    "services.exe": (1, 1),
    "smss.exe":     (1, 3),
    "wininit.exe":  (1, 1),
}

SUSPICIOUS_PATHS = (
    "appdata\\local\\temp",
    "appdata\\roaming\\",
    "\\temp\\",
    "\\tmp\\",
    "$recycle.bin",
    "users\\public\\",
    "programdata\\temp",
    "downloads\\",
)

SAFE_PREFIXES = (
    "c:\\windows\\",
    "c:\\program files\\",
    "c:\\program files (x86)\\",
    "c:\\programdata\\microsoft\\",
)


# Heuristica compartida con services.py (ver analyzer/_text.py para los umbrales).
_entropy = shannon_entropy
_looks_random = looks_random


def analyze_security() -> dict:
    threats = []
    proc_counts: dict[str, int] = {}

    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            info = proc.info
            raw_name = info.get("name") or ""
            name_lo = raw_name.lower()
            exe = (info.get("exe") or "").lower().replace("/", "\\")
            pid = info.get("pid")

            if not name_lo:
                continue

            proc_counts[name_lo] = proc_counts.get(name_lo, 0) + 1

            # ── Ruta sospechosa ──────────────────────────────────────────────
            if exe:
                is_safe = any(exe.startswith(p) for p in SAFE_PREFIXES)
                if not is_safe:
                    for kw in SUSPICIOUS_PATHS:
                        if kw in exe:
                            threats.append(
                                {
                                    "name": raw_name,
                                    "status": "danger",
                                    "message": (
                                        f"Se detectó '{raw_name}' ejecutándose desde una "
                                        "carpeta temporal sospechosa. Las amenazas se ocultan "
                                        "habitualmente en estas rutas."
                                    ),
                                    "value": "Ruta peligrosa",
                                    "detail": f"PID {pid} · {exe[:90]}",
                                }
                            )
                            break

            # ── Nombre de aspecto aleatorio ──────────────────────────────────
            if name_lo not in CRITICAL_PROCS and _looks_random(raw_name):
                threats.append(
                    {
                        "name": raw_name,
                        "status": "warning",
                        "message": (
                            f"El proceso '{raw_name}' tiene un nombre de aspecto aleatorio, "
                            "táctica habitual del malware para pasar desapercibido."
                        ),
                        "value": "Nombre sospechoso",
                        "detail": f"PID {pid} · {exe[:90] if exe else 'ruta desconocida'}",
                    }
                )

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # ── Duplicados de procesos críticos ──────────────────────────────────────
    for proc_name, (mn, mx) in CRITICAL_PROCS.items():
        count = proc_counts.get(proc_name, 0)
        if count > mx:
            threats.append(
                {
                    "name": proc_name,
                    "status": "danger",
                    "message": (
                        f"Hay {count} copias de '{proc_name}' activas cuando lo normal es "
                        f"entre {mn} y {mx}. Esto puede indicar una suplantación de proceso crítico."
                    ),
                    "value": f"{count} instancias",
                    "detail": f"Proceso crítico del sistema con instancias inesperadas",
                }
            )

    # Quitar duplicados exactos por nombre+ruta
    seen_keys: set[str] = set()
    unique: list[dict] = []
    for t in threats:
        key = f"{t['name']}|{t['detail']}"
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(t)

    danger_count = sum(1 for t in unique if t["status"] == "danger")
    warning_count = sum(1 for t in unique if t["status"] == "warning")

    if danger_count > 0:
        overall = "danger"
        summary = f"¡ALERTA! {danger_count} amenaza(s) detectadas. Se recomienda revisar con un antivirus."
    elif warning_count > 0:
        overall = "warning"
        summary = f"{warning_count} proceso(s) con comportamiento inusual. Revisa los detalles."
    else:
        overall = "ok"
        summary = "No se detectaron amenazas activas. Tu sistema parece limpio."

    return {
        "status": overall,
        "title": "Seguridad del Sistema",
        "summary": summary,
        "issue_count": len(unique),
        "items": unique,
    }
