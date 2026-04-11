"""Red — puertos abiertos y archivo hosts. Sin subprocesos: psutil + lectura directa."""
import psutil

SAFE_PORTS = {
    80, 443, 135, 445, 1900, 3389, 5040, 5353,
    7680, 8080, 8443, 10243,
}


def _check_ports() -> list[dict]:
    try:
        listening = [c for c in psutil.net_connections(kind="inet")
                     if c.status == "LISTEN" and c.laddr]
        odd: list[dict] = []
        for c in listening:
            port = c.laddr.port
            if port in SAFE_PORTS or port >= 49152:
                continue
            try:
                proc = psutil.Process(c.pid).name() if c.pid else "desconocido"
            except Exception:
                proc = "desconocido"
            odd.append({"name": f"Puerto {port} abierto", "status": "warning",
                "message": f"El puerto {port} está escuchando conexiones externas (proceso: '{proc}'). Verifica si lo instalaste tú.",
                "value": f":{port}", "detail": f"PID {c.pid} · {proc}"})

        if odd:
            return odd[:8]
        return [{"name": "Puertos de red", "status": "ok",
            "message": f"No se detectaron puertos inusuales. {len(listening)} puertos activos en rangos normales.",
            "value": f"{len(listening)} activos", "detail": ""}]

    except psutil.AccessDenied:
        return [{"name": "Puertos de red", "status": "warning",
            "message": "Se necesitan permisos de administrador para analizar todos los puertos de red.",
            "value": "Sin acceso", "detail": "Ejecuta la app como administrador"}]
    except Exception as e:
        return [{"name": "Puertos de red", "status": "warning",
            "message": "No se pudo analizar los puertos de red.",
            "value": "Error", "detail": str(e)[:80]}]


def _check_hosts() -> list[dict]:
    path = r"C:\Windows\System32\drivers\etc\hosts"
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            active = [l.strip() for l in f
                      if l.strip() and not l.strip().startswith("#")]
        legit = {
            "127.0.0.1 localhost", "::1 localhost",
            "127.0.0.1       localhost", "::1             localhost",
        }
        suspicious = [l for l in active if l not in legit]
        if suspicious:
            return [{"name": "Archivo Hosts", "status": "warning",
                "message": (f"El archivo hosts tiene {len(suspicious)} entrada(s) personalizadas. "
                            "El malware lo modifica para redirigir webs como tu banco o email."),
                "value": f"{len(suspicious)} entradas",
                "detail": " | ".join(suspicious[:4]) + ("…" if len(suspicious) > 4 else "")}]
        return [{"name": "Archivo Hosts", "status": "ok",
            "message": "El archivo hosts no tiene modificaciones. Todo apunta a destinos legítimos.",
            "value": "Sin cambios", "detail": ""}]
    except Exception:
        return [{"name": "Archivo Hosts", "status": "warning",
            "message": "No se pudo leer el archivo hosts.",
            "value": "Sin acceso", "detail": ""}]


def analyze_network() -> dict:
    items = _check_ports() + _check_hosts()

    danger  = sum(1 for i in items if i["status"] == "danger")
    warning = sum(1 for i in items if i["status"] == "warning")
    overall = "danger" if danger else ("warning" if warning else "ok")

    summaries = {
        "danger":  f"{danger} alerta(s) crítica(s) de red detectadas.",
        "warning": f"{warning} elemento(s) de red requieren revisión.",
        "ok":      "Red sin puertos sospechosos ni redirecciones en el archivo hosts.",
    }
    return {"status": overall, "title": "Red", "summary": summaries[overall],
            "issue_count": danger + warning, "items": items}
