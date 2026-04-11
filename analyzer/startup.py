import winreg

STARTUP_KEYS = [
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
]

# Palabras clave → categoría de app "pesada pero segura"
HEAVY_APPS = {
    "spotify":      "Reproductor de música",
    "discord":      "Chat y comunidades",
    "slack":        "Mensajería de trabajo",
    "zoom":         "Videoconferencias",
    "teams":        "Colaboración Microsoft",
    "steam":        "Plataforma de videojuegos",
    "epic":         "Tienda de videojuegos",
    "dropbox":      "Sincronización en la nube",
    "googledrive":  "Google Drive",
    "onedrive":     "Microsoft OneDrive",
    "skype":        "Videollamadas",
    "telegram":     "Mensajería",
    "whatsapp":     "Mensajería",
    "adobe":        "Suite creativa Adobe",
    "cortana":      "Asistente Windows",
}

SYSTEM_PATHS = ("\\windows\\", "\\system32\\", "\\syswow64\\", "\\windowsapps\\")
SUSPICIOUS_PATHS = (
    "appdata\\local\\temp",
    "appdata\\roaming\\temp",
    "\\temp\\",
    "\\tmp\\",
    "users\\public\\",
    "$recycle.bin",
    "programdata\\temp",
)


def _classify(name: str, command: str) -> dict:
    name_lo = name.lower()
    cmd_lo = command.lower().replace("/", "\\")

    # Ruta sospechosa → peligro
    for sp in SUSPICIOUS_PATHS:
        if sp in cmd_lo:
            return {
                "name": name,
                "status": "danger",
                "message": (
                    f"'{name}' se ejecuta al inicio desde una carpeta temporal sospechosa. "
                    "Este es un patrón habitual en malware."
                ),
                "value": "Sospechoso",
                "detail": command[:120],
            }

    # Componente del sistema → ok
    for sp in SYSTEM_PATHS:
        if sp in cmd_lo:
            return {
                "name": name,
                "status": "ok",
                "message": f"'{name}' es un componente del sistema. No se recomienda tocarlo.",
                "value": "Sistema",
                "detail": command[:120],
            }

    # App conocida pero pesada → advertencia
    for keyword, category in HEAVY_APPS.items():
        if keyword in name_lo or keyword in cmd_lo:
            return {
                "name": name,
                "status": "warning",
                "message": (
                    f"'{name}' ({category}) ralentiza el arranque. "
                    "Puedes desactivarlo si no lo necesitas nada más encender el PC."
                ),
                "value": "Opcional",
                "detail": command[:120],
            }

    # Desconocido
    return {
        "name": name,
        "status": "warning",
        "message": (
            f"'{name}' es un programa de inicio desconocido. "
            "Verifica si lo instalaste tú o si puede ser no deseado."
        ),
        "value": "Desconocido",
        "detail": command[:120],
    }


def analyze_startup() -> dict:
    items = []
    seen: set[str] = set()

    for hive, key_path in STARTUP_KEYS:
        try:
            key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ)
            idx = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, idx)
                    if name.lower() not in seen:
                        seen.add(name.lower())
                        items.append(_classify(name, str(value)))
                    idx += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except Exception:
            pass

    danger_count = sum(1 for i in items if i["status"] == "danger")
    warning_count = sum(1 for i in items if i["status"] == "warning")
    total = len(items)

    if danger_count > 0:
        overall = "danger"
        summary = "Se detectaron entradas de inicio sospechosas. Revisión urgente recomendada."
    elif warning_count > 6 or total > 18:
        overall = "warning"
        summary = (
            f"{total} programas al inicio, {warning_count} son pesados o desconocidos. "
            "Reducirlos acelerará notablemente el arranque."
        )
    elif warning_count > 0:
        overall = "warning"
        summary = (
            f"{total} programas al inicio. {warning_count} son opcionales y se pueden desactivar."
        )
    else:
        overall = "ok"
        summary = f"{total} programas al inicio. Todo parece correcto."

    return {
        "status": overall,
        "title": "Arranque del Sistema",
        "summary": summary,
        "issue_count": danger_count + warning_count,
        "items": items,
    }
