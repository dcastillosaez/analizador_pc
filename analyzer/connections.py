"""Conexiones TCP establecidas hacia el exterior — psutil + resolución DNS."""
import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

import psutil

# Puertos cuya presencia en exterior es siempre esperada
_SAFE_PORTS = {80, 443, 853, 8080, 8443}

# Puertos conocidos por herramientas de C2/malware — danger directo
_SUSPICIOUS_PORTS = {4444, 1080, 31337, 6667, 6666, 9001, 9030}

_PRIV_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_loopback or addr.is_private or any(addr in net for net in _PRIV_NETS)
    except ValueError:
        return False


def _resolve(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ip


def _proc_name(pid) -> str:
    if not pid:
        return "desconocido"
    try:
        return psutil.Process(pid).name()
    except Exception:
        return "desconocido"


def analyze_connections() -> dict:
    try:
        conns = [
            c for c in psutil.net_connections(kind="tcp")
            if c.status == "ESTABLISHED" and c.raddr
            and not ipaddress.ip_address(c.raddr.ip).is_loopback
        ]
    except psutil.AccessDenied:
        return {
            "status": "warning", "title": "Conexiones salientes",
            "summary": "Se necesitan permisos de administrador para ver las conexiones TCP.",
            "issue_count": 1,
            "items": [{"name": "Acceso denegado", "status": "warning",
                        "message": "Ejecuta la app como administrador para ver las conexiones activas.",
                        "value": "Sin acceso", "detail": ""}],
        }
    except Exception as e:
        return {
            "status": "warning", "title": "Conexiones salientes",
            "summary": "No se pudieron obtener las conexiones TCP.",
            "issue_count": 1,
            "items": [{"name": "Error", "status": "warning",
                        "message": str(e)[:120], "value": "Error", "detail": ""}],
        }

    # Deduplicar por (pid, raddr)
    seen: set[tuple] = set()
    unique: list = []
    for c in conns:
        key = (c.pid, c.raddr.ip, c.raddr.port)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # Limitar y resolver nombres en paralelo (1 s de timeout por lookup)
    MAX = 40
    sample = unique[:MAX]
    ips = {c.raddr.ip for c in sample}

    resolved: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        fut_map = {ex.submit(_resolve, ip): ip for ip in ips}
        for fut in as_completed(fut_map, timeout=4):
            ip = fut_map[fut]
            try:
                resolved[ip] = fut.result(timeout=0)
            except Exception:
                resolved[ip] = ip

    items: list[dict] = []
    for c in sample:
        rip   = c.raddr.ip
        rport = c.raddr.port
        proc  = _proc_name(c.pid)
        host  = resolved.get(rip, rip)
        priv  = _is_private(rip)

        if rport in _SUSPICIOUS_PORTS:
            st = "danger"
        elif priv or rport in _SAFE_PORTS:
            st = "ok"
        else:
            st = "warning"

        label = f"{'LAN' if priv else 'WAN'} · {host if host != rip else rip}"
        port_label = _port_label(rport)
        detail = f"{rip} → :{rport}" + (f" ({host})" if host != rip else "")

        items.append({
            "name":    proc,
            "status":  st,
            "message": label,
            "value":   port_label,
            "detail":  detail,
        })

    # Ordenar: danger → warning → ok; dentro de cada grupo por puerto
    _priority = {"danger": 0, "warning": 1, "ok": 2}
    items.sort(key=lambda x: (_priority.get(x["status"], 3), x["value"]))

    danger  = sum(1 for i in items if i["status"] == "danger")
    warning = sum(1 for i in items if i["status"] == "warning")
    overall = "danger" if danger else ("warning" if warning else "ok")

    if not items:
        summary = "Sin conexiones TCP externas activas en este momento."
        overall = "ok"
    elif danger:
        summary = f"{danger} conexión(es) a puertos sospechosos detectadas."
    elif warning:
        summary = f"{len(items)} conexiones activas — {warning} a puertos no estándar."
    else:
        summary = f"{len(items)} conexión(es) TCP activas, todas a puertos conocidos."

    return {
        "status":      overall,
        "title":       "Conexiones salientes",
        "summary":     summary,
        "issue_count": danger + warning,
        "items":       items,
    }


def _port_label(port: int) -> str:
    labels = {
        80: "HTTP 80", 443: "HTTPS 443", 853: "DNS-TLS 853",
        8080: "HTTP 8080", 8443: "HTTPS 8443",
        21: "FTP 21", 22: "SSH 22", 23: "Telnet 23",
        25: "SMTP 25", 110: "POP3 110", 143: "IMAP 143",
        587: "SMTP 587", 993: "IMAPS 993", 995: "POP3S 995",
        3306: "MySQL 3306", 5432: "PG 5432", 27017: "Mongo 27017",
        3389: "RDP 3389", 5900: "VNC 5900",
        4444: "⚠ 4444", 1080: "SOCKS 1080",
    }
    return labels.get(port, f":{port}")
