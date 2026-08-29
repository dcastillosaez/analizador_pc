"""
Conectividad — estado de internet, latencia y test de velocidad de descarga.
El análisis básico (ping + DNS + gateway) se ejecuta con el escaneo general.
El test de velocidad es bajo demanda (/api/connectivity/speedtest).
"""
import socket
import time
import urllib.request
import re
import psutil

from ._shell import run, run_ps_json


# ── Utilidades ────────────────────────────────────────────────────────────────

def _ping_ms(host: str, count: int = 4) -> float | None:
    """Devuelve latencia media en ms, o None si falla."""
    try:
        text = run(["ping", "-n", str(count), host], timeout=15).stdout
        m = re.search(r"[Mm]edia\s*=\s*(\d+)\s*ms|[Aa]verage\s*=\s*(\d+)\s*ms", text)
        if m:
            return float(m.group(1) or m.group(2))
        # formato alternativo: "Mínimo = Xms, Máximo = Xms, Media = Xms"
        m2 = re.findall(r"(\d+)ms", text)
        if m2:
            vals = [int(v) for v in m2]
            return float(sum(vals) / len(vals))
    except Exception:
        pass
    return None


def _dns_ok(host: str = "www.google.com") -> bool:
    try:
        socket.setdefaulttimeout(5)
        socket.gethostbyname(host)
        return True
    except Exception:
        return False


def _default_gateway() -> str | None:
    try:
        gws = psutil.net_if_stats()
        # Obtener gateway del sistema via route
        text = run(["route", "print", "0.0.0.0"], timeout=8).stdout
        m = re.search(r"0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)", text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


# ── Análisis básico (se ejecuta con el escaneo general) ──────────────────────

def analyze_connectivity() -> dict:
    items: list[dict] = []

    # 1 — DNS
    dns = _dns_ok()
    dns_ifaces = _get_system_dns()
    # Construir detalle con todos los servidores DNS configurados
    dns_detail_parts = []
    for iface_data in dns_ifaces:
        servers = iface_data["servers"]
        labels = []
        for s in servers:
            lbl = _dns_label(s)
            labels.append(f"{s} ({lbl})" if lbl else s)
        dns_detail_parts.append(f"{iface_data['interface']}: {', '.join(labels)}")
    dns_detail = "  ·  ".join(dns_detail_parts) if dns_detail_parts else "Prueba con google.com"

    items.append({
        "name":    "Resolución DNS",
        "status":  "ok" if dns else "danger",
        "message": "Resolución de nombres correcta" if dns else "No se puede resolver nombres de dominio",
        "value":   "OK" if dns else "Sin DNS",
        "detail":  dns_detail,
    })

    # 2 — Internet (HTTP)
    internet_ok = False
    if dns:
        try:
            urllib.request.urlopen("https://www.google.com", timeout=6)
            internet_ok = True
        except Exception:
            pass
    items.append({
        "name":    "Acceso a internet",
        "status":  "ok" if internet_ok else "danger",
        "message": "Conexión a internet disponible" if internet_ok else "Sin acceso a internet",
        "value":   "Conectado" if internet_ok else "Sin conexión",
        "detail":  "",
    })

    # 3 — Latencia 8.8.8.8
    lat_ext = _ping_ms("8.8.8.8", count=4) if internet_ok else None
    if lat_ext is not None:
        if lat_ext < 30:
            lat_status = "ok"
        elif lat_ext < 80:
            lat_status = "warning"
        else:
            lat_status = "danger"
        items.append({
            "name":    "Latencia (internet)",
            "status":  lat_status,
            "message": f"Ping a 8.8.8.8: {lat_ext:.0f} ms",
            "value":   f"{lat_ext:.0f} ms",
            "detail":  "< 30 ms excelente · < 80 ms normal · > 80 ms elevada",
        })
    elif internet_ok:
        items.append({
            "name":    "Latencia (internet)",
            "status":  "warning",
            "message": "No se pudo medir la latencia",
            "value":   "—",
            "detail":  "",
        })

    # 4 — Gateway
    gw = _default_gateway()
    if gw:
        lat_gw = _ping_ms(gw, count=3)
        gw_status = "ok"
        gw_detail = f"{lat_gw:.0f} ms al router" if lat_gw else "sin respuesta"
        items.append({
            "name":    "Puerta de enlace",
            "status":  gw_status,
            "message": f"Router: {gw} — {gw_detail}",
            "value":   gw,
            "detail":  "",
        })

    # Estado general
    danger  = sum(1 for i in items if i["status"] == "danger")
    warning = sum(1 for i in items if i["status"] == "warning")
    if danger:
        overall = "danger"
        summary = "Sin conexión a internet o problemas graves de red."
    elif warning:
        overall = "warning"
        summary = "Conexión disponible pero con latencia elevada."
    else:
        overall = "ok"
        lat_txt = f" · Latencia {lat_ext:.0f} ms" if lat_ext else ""
        summary = f"Conexión a internet correcta.{lat_txt}"

    return {
        "status":      overall,
        "title":       "Conectividad",
        "summary":     summary,
        "issue_count": danger + warning,
        "items":       items,
    }


# ── DNS del sistema ───────────────────────────────────────────────────────────

def _get_system_dns() -> list[dict]:
    """Devuelve las DNS activas configuradas en las interfaces de red."""
    try:
        data = run_ps_json(
            "Get-DnsClientServerAddress -AddressFamily IPv4 | "
            "Where-Object {$_.ServerAddresses} | "
            "Select-Object InterfaceAlias, ServerAddresses | "
            "ConvertTo-Json -Compress -Depth 2",
            timeout=15, default=[],
        ) or []
        results = []
        for entry in data:
            iface = entry.get("InterfaceAlias", "")
            addrs = entry.get("ServerAddresses", [])
            if isinstance(addrs, str):
                addrs = [addrs]
            if addrs:
                results.append({"interface": iface, "servers": addrs})
        return results
    except Exception:
        return []


def _dns_label(ip: str) -> str:
    """Devuelve el nombre del proveedor DNS conocido, o cadena vacía."""
    known = {
        "8.8.8.8":   "Google DNS",
        "8.8.4.4":   "Google DNS",
        "1.1.1.1":   "Cloudflare",
        "1.0.0.1":   "Cloudflare",
        "9.9.9.9":   "Quad9",
        "149.112.112.112": "Quad9",
        "208.67.222.222": "OpenDNS",
        "208.67.220.220": "OpenDNS",
        "76.76.19.19":    "Alternate DNS",
        "94.140.14.14":   "AdGuard DNS",
        "94.140.15.15":   "AdGuard DNS",
    }
    return known.get(ip, "")


# ── Test de velocidad (bajo demanda) ─────────────────────────────────────────

# Servidores públicos de prueba — HTTP para evitar problemas de SSL/certificados
_SPEEDTEST_CANDIDATES = [
    ("Hetzner DE",  "http://speed.hetzner.de/10MB.bin"),
    ("Hetzner FSN", "http://fsn1-speed.hetzner.com/10MB.bin"),
    ("Hetzner NBG", "http://nbg1-speed.hetzner.com/10MB.bin"),
    ("OVH",         "http://proof.ovh.net/files/10Mb.dat"),
    ("Tele2",       "http://speedtest.tele2.net/10MB.zip"),
    ("BelWue",      "http://speedtest.belwue.net/random4000.bin"),
]
_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept":          "*/*",
    "Accept-Encoding": "identity",
    "Connection":      "keep-alive",
}


def _try_download(url: str) -> tuple[int, float]:
    """Descarga url y devuelve (bytes_descargados, segundos). Lanza excepción si falla."""
    req = urllib.request.Request(url, headers=_HEADERS)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as resp:
        downloaded = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            downloaded += len(chunk)
    return downloaded, time.perf_counter() - t0


def run_speedtest() -> dict:
    """Descarga ~10 MB desde varios servidores públicos y calcula velocidad de bajada."""
    lat = _ping_ms("1.1.1.1", count=4)

    errors: list[str] = []
    for server_name, url in _SPEEDTEST_CANDIDATES:
        try:
            downloaded, elapsed = _try_download(url)
            if elapsed <= 0 or downloaded < 500_000:
                errors.append(f"{server_name}: descarga incompleta ({downloaded} bytes)")
                continue

            mbps = round((downloaded * 8) / elapsed / 1_000_000, 2)

            if mbps >= 50:
                speed_status, speed_label = "ok",      "Muy rápida"
            elif mbps >= 10:
                speed_status, speed_label = "ok",      "Buena"
            elif mbps >= 3:
                speed_status, speed_label = "warning",  "Normal"
            else:
                speed_status, speed_label = "danger",   "Lenta"

            return {
                "success":       True,
                "download_mbps": mbps,
                "speed_label":   speed_label,
                "speed_status":  speed_status,
                "latency_ms":    round(lat, 1) if lat is not None else None,
                "bytes":         downloaded,
                "elapsed_s":     round(elapsed, 2),
                "server":        server_name,
            }
        except Exception as e:
            errors.append(f"{server_name}: {e}")
            continue

    error_detail = " | ".join(errors)
    return {
        "success": False,
        "error": "Todos los servidores fallaron.",
        "error_detail": error_detail,
    }
