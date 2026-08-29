"""Conexiones TCP salientes establecidas ahora mismo.

Responde a "¿qué está hablando con Internet en este momento y hacia dónde?".
Complementa a network.py, que mira puertos a la escucha (entrantes); aquí se
mira el sentido contrario, que es por donde se va la información.
"""

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor

import psutil

from ._text import looks_random

# Marcar como sospechosa toda ruta fuera de Program Files daba demasiados falsos
# positivos: media aplicación moderna (Chrome, Discord, Slack, cualquier Electron)
# se instala en el perfil del usuario. Se invierte la lógica: solo se avisa de
# las carpetas desde las que un programa legítimo casi nunca se ejecuta, que son
# justo donde cae lo que se descarga sin querer.
SUSPICIOUS_MARKERS = (
    "\\appdata\\local\\temp\\",
    "\\appdata\\locallow\\",
    "\\windows\\temp\\",
    "\\downloads\\",
    "\\descargas\\",
    "\\$recycle.bin\\",
    "\\temp\\",
    "\\tmp\\",
)

# Rutas de sistema: ahí un puerto poco común deja de ser llamativo.
TRUSTED_PREFIXES = (
    "c:\\windows\\",
    "c:\\program files\\",
    "c:\\program files (x86)\\",
)

# Puertos salientes habituales. Salir por uno raro no es malo en sí, pero
# merece una mirada cuando además el binario está en una ruta inusual.
COMMON_PORTS = {80, 443, 22, 53, 123, 587, 993, 995, 465, 5223, 8080, 8443, 3478}

# Resolver PTR es lo lento de este módulo; se acota en paralelo y con timeout.
_RESOLVE_WORKERS = 12
_RESOLVE_TIMEOUT = 1.5
_dns_cache: dict[str, str] = {}


def _fmt_endpoint(ip: str, port: int) -> str:
    """IPv6 va entre corchetes; si no, 'a:b:c::443' es ilegible."""
    return f"[{ip}]:{port}" if ":" in ip else f"{ip}:{port}"


def _is_external(ip: str) -> bool:
    """Descarta loopback, red local, multicast y direcciones reservadas."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_multicast
                or addr.is_link_local or addr.is_reserved or addr.is_unspecified)


def _resolve(ip: str) -> str:
    if ip in _dns_cache:
        return _dns_cache[ip]
    previo = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(_RESOLVE_TIMEOUT)
        host = socket.gethostbyaddr(ip)[0]
    except (OSError, socket.herror, socket.gaierror):
        host = ""
    finally:
        socket.setdefaulttimeout(previo)
    _dns_cache[ip] = host
    return host


def _proc_info(pid) -> tuple[str, str]:
    if not pid:
        return ("Sistema", "")
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            try:
                exe = proc.exe() or ""
            except (psutil.AccessDenied, OSError):
                exe = ""
            return (proc.name(), exe)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return (f"PID {pid}", "")


def _classify(exe: str, name: str, port: int) -> tuple[str, str]:
    """Devuelve (estado, motivo) para una conexión."""
    exe_low = (exe or "").lower()

    if any(marker in exe_low for marker in SUSPICIOUS_MARKERS):
        return ("danger", "El ejecutable corre desde una carpeta temporal o de descargas y está saliendo a Internet.")

    if looks_random(name):
        return ("warning", "El nombre del ejecutable parece generado al azar.")

    # Un puerto poco común solo llama la atención si además el binario no es de
    # sistema: los programas de usuario abren puertos propios continuamente.
    if (port not in COMMON_PORTS and port > 1024
            and exe_low and not exe_low.startswith(TRUSTED_PREFIXES)):
        return ("warning", f"Sale por el puerto {port}, que no es de los habituales.")

    return ("ok", "Conexión normal hacia un servicio de Internet.")


def analyze_connections() -> dict:
    try:
        conns = psutil.net_connections(kind="tcp")
    except (psutil.AccessDenied, PermissionError):
        return {
            "status": "warning",
            "title": "Conexiones salientes",
            "summary": "Se necesitan permisos de administrador para ver todas las conexiones.",
            "issue_count": 0,
            "items": [{
                "name": "Acceso restringido", "status": "warning",
                "message": "Windows solo muestra las conexiones de los procesos propios sin elevación.",
                "value": "Sin acceso",
                "detail": "Reinicia PC Guardian como administrador para ver el listado completo.",
            }],
        }

    # Una misma IP remota puede tener varias conexiones del mismo proceso;
    # se agrupan para no llenar la lista de duplicados.
    grupos: dict[tuple, dict] = {}
    for c in conns:
        if c.status != psutil.CONN_ESTABLISHED or not c.raddr:
            continue
        ip, port = c.raddr.ip, c.raddr.port
        if not _is_external(ip):
            continue

        name, exe = _proc_info(c.pid)
        key = (c.pid, ip, port)
        entry = grupos.get(key)
        if entry:
            entry["count"] += 1
        else:
            grupos[key] = {"pid": c.pid, "ip": ip, "port": port,
                           "name": name, "exe": exe, "count": 1}

    if not grupos:
        return {
            "status": "ok",
            "title": "Conexiones salientes",
            "summary": "Ningún proceso mantiene una conexión activa hacia Internet en este momento.",
            "issue_count": 0,
            "items": [],
        }

    # Resolución inversa en paralelo: en serie serían segundos por dirección.
    ips = sorted({g["ip"] for g in grupos.values()})
    with ThreadPoolExecutor(max_workers=_RESOLVE_WORKERS) as pool:
        hosts = dict(zip(ips, pool.map(_resolve, ips)))

    items, issues = [], 0
    for g in sorted(grupos.values(), key=lambda x: (x["name"].lower(), x["ip"])):
        status, motivo = _classify(g["exe"], g["name"], g["port"])
        if status != "ok":
            issues += 1

        host = hosts.get(g["ip"], "")
        destino = f"{host} ({g['ip']})" if host else g["ip"]
        repeticiones = f" · {g['count']} conexiones" if g["count"] > 1 else ""

        items.append({
            "name":    g["name"],
            "status":  status,
            "message": f"{motivo} Destino: {destino}.",
            "value":   _fmt_endpoint(g["ip"], g["port"]) + repeticiones,
            "detail":  g["exe"] or "Ruta no accesible",
            "pid":     g["pid"],
            "host":    host,
        })

    # Los avisos primero: es lo que interesa mirar.
    items.sort(key=lambda i: {"danger": 0, "warning": 1, "ok": 2}[i["status"]])

    total = len(items)
    if issues:
        summary = (f"{total} conexión(es) saliente(s) activa(s); {issues} merece(n) una mirada "
                   f"por la ruta del ejecutable o el puerto usado.")
        status = "danger" if any(i["status"] == "danger" for i in items) else "warning"
    else:
        summary = f"{total} conexión(es) saliente(s) activa(s), ninguna desde una ubicación sospechosa."
        status = "ok"

    return {
        "status": status,
        "title": "Conexiones salientes",
        "summary": summary,
        "issue_count": issues,
        "items": items,
    }
