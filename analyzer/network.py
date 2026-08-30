"""Red — puertos abiertos y archivo hosts. Sin subprocesos: psutil + lectura directa."""
import psutil

SAFE_PORTS = {
    80, 443, 135, 139, 445, 1900, 3389, 5040, 5353,
    5357, 7680, 8080, 8443, 10243,
}


LOOPBACK = {"127.0.0.1", "::1"}


def _classify_ports(entries: list[dict]) -> list[dict]:
    """Separa lo que solo escucha en el propio equipo de lo que expone a la red.

    Un socket en 127.0.0.1 o ::1 no es alcanzable desde fuera de la máquina:
    ni el router lo reenvía ni otro equipo de la LAN llega a él. Tratarlo como
    "puerto abierto a internet" llenaba el informe de falsos positivos (el
    propio PC Guardian, que escucha en 127.0.0.1, salía acusado en su lista).
    """
    locales, expuestos = [], []
    for e in entries:
        (locales if e.get("ip") in LOOPBACK else expuestos).append(e)

    avisos = []
    vistos = set()
    for e in expuestos:
        port = e["port"]
        if port in SAFE_PORTS or port >= 49152:
            continue
        ip   = e.get("ip") or ""
        proc = e.get("proc") or "desconocido"
        # Un mismo servicio suele escuchar en IPv4 e IPv6 a la vez: un aviso basta
        if (port, proc) in vistos:
            continue
        vistos.add((port, proc))
        alcance = ("todas las interfaces de red" if ip in ("0.0.0.0", "::")
                   else f"la interfaz {ip}")
        avisos.append({
            "name": f"Puerto {port} abierto a la red",
            "status": "warning",
            "message": (f"El puerto {port} escucha en {alcance}, así que otros equipos "
                        f"pueden conectarse (proceso: '{proc}'). Verifica si lo instalaste tú."),
            "value": f":{port}",
            "detail": f"PID {e.get('pid')} · {proc} · {ip}",
        })

    items = avisos[:8]

    if locales:
        procesos = sorted({e.get("proc") or "desconocido" for e in locales})
        items.append({
            "name": "Puertos solo locales",
            "status": "ok",
            "message": (f"{len(locales)} puerto(s) escuchan únicamente en este equipo "
                        "(127.0.0.1 / ::1). No son accesibles desde la red."),
            "value": f"{len(locales)} locales",
            "detail": ", ".join(procesos[:6]) + ("…" if len(procesos) > 6 else ""),
        })

    if not items:
        items.append({
            "name": "Puertos de red",
            "status": "ok",
            "message": "Ningún puerto inusual expuesto a la red.",
            "value": "Sin exposición",
            "detail": "",
        })
    return items


def _check_ports() -> list[dict]:
    try:
        entries = []
        for c in psutil.net_connections(kind="inet"):
            if c.status != "LISTEN" or not c.laddr:
                continue
            try:
                proc = psutil.Process(c.pid).name() if c.pid else "desconocido"
            except Exception:
                proc = "desconocido"
            entries.append({"ip": c.laddr.ip, "port": c.laddr.port,
                            "pid": c.pid, "proc": proc})
        return _classify_ports(entries)

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
