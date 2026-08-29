import psutil

from ._text import looks_random, shannon_entropy
from .signatures import check_signatures, describe

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
    candidatos: list[dict] = []   # procesos fuera de rutas de sistema
    rutas_a_firmar: list[str] = []

    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            info = proc.info
            raw_name = info.get("name") or ""
            name_lo = raw_name.lower()
            exe_raw = info.get("exe") or ""
            exe = exe_raw.lower().replace("/", "\\")
            pid = info.get("pid")

            if not name_lo:
                continue

            proc_counts[name_lo] = proc_counts.get(name_lo, 0) + 1

            fuera_de_sistema = exe and not any(exe.startswith(p) for p in SAFE_PREFIXES)
            ruta_insegura = fuera_de_sistema and any(kw in exe for kw in SUSPICIOUS_PATHS)
            nombre_raro = name_lo not in CRITICAL_PROCS and _looks_random(raw_name)

            if ruta_insegura or nombre_raro:
                candidatos.append({
                    "name": raw_name, "pid": pid, "exe": exe, "exe_raw": exe_raw,
                    "ruta_insegura": ruta_insegura, "nombre_raro": nombre_raro,
                })
                # Solo se pide la firma de lo que ya resulta llamativo: pedirla
                # para los cien y pico procesos de un equipo normal añadía diez
                # segundos al escaneo sin cambiar ningún veredicto.
                if exe_raw:
                    rutas_a_firmar.append(exe_raw)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # ── Firma digital ────────────────────────────────────────────────────────
    # Se consulta de golpe para todos los candidatos: es la señal que decide si
    # un binario en una ruta rara es un instalador normal o algo que esconderse.
    firmas = check_signatures(rutas_a_firmar) if rutas_a_firmar else {}

    for c in candidatos:
        firma = firmas.get(c["exe"], {})
        firmado = firma.get("signed", False)
        firmante = firma.get("signer", "")
        detalle_firma = describe(firma) if firma else ""
        detalle = f"PID {c['pid']} · {c['exe'][:90] if c['exe'] else 'ruta desconocida'}"
        if detalle_firma:
            detalle += f" · {detalle_firma}"

        # Un archivo cuya firma no cuadra con su contenido ha sido manipulado
        # después de firmarse. Eso no admite interpretación benigna.
        if firma.get("status") == "HashMismatch":
            threats.append({
                "name": c["name"], "status": "danger",
                "message": (f"El ejecutable de '{c['name']}' ha sido modificado después de "
                            "firmarse: su firma digital ya no coincide con el archivo."),
                "value": "Firma rota", "detail": detalle,
            })
            continue

        if c["ruta_insegura"]:
            if firmado:
                # Los instaladores se descomprimen en Temp y se ejecutan desde
                # ahí: con firma válida es lo normal, no una amenaza.
                threats.append({
                    "name": c["name"], "status": "warning",
                    "message": (f"'{c['name']}' se ejecuta desde una carpeta temporal, aunque "
                                f"está firmado por {firmante or 'un editor conocido'}. "
                                "Es lo habitual en instaladores."),
                    "value": "Temporal, firmado", "detail": detalle,
                })
            else:
                threats.append({
                    "name": c["name"], "status": "danger",
                    "message": (f"Se detectó '{c['name']}' ejecutándose desde una carpeta "
                                "temporal y sin firma digital. Es la combinación típica "
                                "de un archivo malicioso."),
                    "value": "Ruta peligrosa", "detail": detalle,
                })
            continue

        if c["nombre_raro"]:
            if firmado:
                continue   # nombre generado pero binario firmado: no es señal
            threats.append({
                "name": c["name"], "status": "warning",
                "message": (f"El proceso '{c['name']}' tiene un nombre de aspecto aleatorio y "
                            "no está firmado digitalmente, táctica habitual del malware."),
                "value": "Nombre sospechoso", "detail": detalle,
            })

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
                    "detail": "Proceso crítico del sistema con instancias inesperadas",
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
