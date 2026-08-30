"""DNS activo — servidores por interfaz, DoH, opción de cambiar."""
import json
import re
import winreg

from ._shell import run, run_ps_json

_KNOWN = {
    "8.8.8.8":           "Google DNS",
    "8.8.4.4":           "Google DNS",
    "1.1.1.1":           "Cloudflare",
    "1.0.0.1":           "Cloudflare",
    "9.9.9.9":           "Quad9",
    "149.112.112.112":   "Quad9",
    "208.67.222.222":    "OpenDNS",
    "208.67.220.220":    "OpenDNS",
    "94.140.14.14":      "AdGuard",
    "94.140.15.15":      "AdGuard",
}

_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def _get_interfaces() -> list:
    try:
        data = run_ps_json(
            "Get-DnsClientServerAddress -AddressFamily IPv4 | "
            "Where-Object {$_.ServerAddresses} | "
            "Select-Object InterfaceAlias, ServerAddresses | "
            "ConvertTo-Json -Compress -Depth 2",
            timeout=15, default=[],
        ) or []
        result = []
        for entry in data:
            iface = entry.get("InterfaceAlias", "")
            addrs = entry.get("ServerAddresses", [])
            if isinstance(addrs, str):
                addrs = [addrs]
            if addrs:
                result.append({"interface": iface, "servers": list(addrs)})
        return result
    except Exception:
        return []


def _detect_doh() -> bool:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Services\Dnscache\Parameters",
        )
        val, _ = winreg.QueryValueEx(key, "EnableAutoDoh")
        winreg.CloseKey(key)
        return int(val) == 2
    except Exception:
        return False


def analyze_dns() -> dict:
    interfaces = _get_interfaces()
    doh = _detect_doh()
    items = []

    for iface in interfaces:
        servers = iface["servers"]
        labeled = [f"{s} ({_KNOWN[s]})" if s in _KNOWN else s for s in servers]
        unknown = [s for s in servers if s not in _KNOWN]

        if unknown:
            st  = "warning"
            msg = f"Servidor(es) desconocidos: {', '.join(unknown)}"
        else:
            providers = list(dict.fromkeys(_KNOWN[s] for s in servers))
            st  = "ok"
            msg = f"Proveedor: {', '.join(providers)}"

        items.append({
            "name":         iface["interface"],
            "status":       st,
            "message":      msg,
            "value":        labeled[0] if labeled else "—",
            "detail":       " · ".join(labeled[1:]) if len(labeled) > 1 else "",
            "servers":      servers,
            "interface":    iface["interface"],
            "fix_available": True,
        })

    items.append({
        "name":    "DNS sobre HTTPS (DoH)",
        "status":  "ok" if doh else "warning",
        "message": "DoH automático activo — consultas DNS cifradas." if doh
                   else "DoH no detectado — consultas DNS en texto plano.",
        "value":   "Activo" if doh else "Inactivo",
        "detail":  "",
        "servers":       [],
        "interface":     "",
        "fix_available": False,
    })

    if not interfaces:
        items = [{
            "name": "Sin interfaces", "status": "warning",
            "message": "No se encontraron interfaces con DNS configurado.",
            "value": "—", "detail": "", "servers": [], "interface": "", "fix_available": False,
        }]

    warning = sum(1 for i in items if i["status"] == "warning")
    overall = "warning" if warning else "ok"

    if not interfaces:
        summary = "No se pudo obtener información DNS."
    elif warning:
        summary = f"{warning} elemento(s) requieren atención (DNS desconocido o sin DoH)."
    else:
        summary = f"{len(interfaces)} interfaz(ces) con DNS conocido. DoH {'activo' if doh else 'inactivo'}."

    return {
        "status":      overall,
        "title":       "DNS activo",
        "summary":     summary,
        "issue_count": warning,
        "items":       items,
    }


def set_dns(interface: str, dns1: str, dns2: str = "") -> dict:
    if not interface or len(interface) > 100:
        return {"ok": False, "msg": "Nombre de interfaz no válido."}
    if not _IP_RE.match(dns1 or ""):
        return {"ok": False, "msg": "Dirección DNS primaria no válida."}
    if dns2 and not _IP_RE.match(dns2):
        return {"ok": False, "msg": "Dirección DNS secundaria no válida."}
    r = run(["netsh", "interface", "ip", "set", "dns",
             f"name={interface}", "static", dns1, "primary"], timeout=10)
    if r.error:
        return {"ok": False, "msg": r.error[:120]}
    if r.returncode != 0:
        if r.needs_admin:
            return {"ok": False, "msg": "Cambiar el DNS necesita permisos de administrador."}
        return {"ok": False, "msg": f"netsh falló: {r.combined[:120]}"}

    if dns2:
        run(["netsh", "interface", "ip", "add", "dns",
             f"name={interface}", dns2, "index=2"], timeout=10)

    label = _KNOWN.get(dns1, dns1)
    return {"ok": True, "msg": f"DNS de '{interface}' cambiado a {label} ({dns1})."}
