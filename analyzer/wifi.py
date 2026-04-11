"""
Analizador WiFi — redes cercanas, señal, canal, frecuencia y colisiones de canal.
Usa netsh wlan (siempre disponible en Windows sin dependencias externas).
"""
import subprocess
import re


def _run_netsh(args: list[str]) -> str:
    try:
        r = subprocess.run(
            ["netsh"] + args,
            capture_output=True, timeout=20,
        )
        for enc in ("utf-8", "oem", "cp1252", "latin-1"):
            try:
                return r.stdout.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return r.stdout.decode("latin-1")
    except Exception:
        return ""


def _field(text: str, *keys: str) -> str:
    """Extrae el valor de la primera clave que coincida (bilingüe)."""
    for key in keys:
        m = re.search(rf"^\s*{re.escape(key)}\s*:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _signal_pct(raw: str) -> int:
    m = re.search(r"(\d+)", raw)
    return int(m.group(1)) if m else 0


def _channel_int(raw: str) -> int:
    m = re.search(r"(\d+)", raw)
    return int(m.group(1)) if m else 0


def _channels_collide_24(ch1: int, ch2: int) -> bool:
    """En 2.4 GHz dos canales colisionan si están a menos de 5 canales de distancia."""
    return ch1 > 0 and ch2 > 0 and abs(ch1 - ch2) < 5


def _channels_collide_5(ch1: int, ch2: int) -> bool:
    """En 5 GHz con ancho 20 MHz solo colisionan si son el mismo canal."""
    return ch1 > 0 and ch2 > 0 and ch1 == ch2


# ── Interfaz conectada ────────────────────────────────────────────────────────

def _get_connected_interface() -> dict:
    out = _run_netsh(["wlan", "show", "interfaces"])
    if not out:
        return {}
    return {
        "ssid":       _field(out, "SSID", "SSID"),
        "bssid":      _field(out, "BSSID", "BSSID"),
        "signal":     _signal_pct(_field(out, "Signal", "Señal", "Se.al")),
        "channel":    _channel_int(_field(out, "Channel", "Canal")),
        "radio_type": _field(out, "Radio type", "Tipo de radio"),
        "rx_mbps":    _field(out, "Receive rate (Mbps)", "Velocidad de recepción (Mbps)", "Velocidad de recepci.n"),
        "tx_mbps":    _field(out, "Transmit rate (Mbps)", "Velocidad de envío (Mbps)", "Velocidad de env.o"),
        "auth":       _field(out, "Authentication", "Autenticación", "Autenticaci.n"),
        "state":      _field(out, "State", "Estado"),
        "adapter":    _field(out, "Description", "Descripción", "Descripci.n"),
        "profile":    _field(out, "Profile", "Perfil"),
    }


# ── Redes cercanas ────────────────────────────────────────────────────────────

def _parse_networks(out: str) -> list[dict]:
    """Parsea la salida de `netsh wlan show networks mode=bssid`."""
    networks: list[dict] = []

    # Dividir por bloques SSID
    ssid_blocks = re.split(r"\nSSID\s+\d+\s*:", out)
    for block in ssid_blocks[1:]:
        lines = block.splitlines()
        ssid = lines[0].strip() if lines else ""

        auth    = _field(block, "Authentication", "Autenticación", "Autenticaci.n")
        enc     = _field(block, "Encryption", "Cifrado")

        # Puede haber múltiples BSSIDs por SSID
        bssid_parts = re.split(r"\n\s*BSSID\s+\d+\s*:", block)
        for bpart in bssid_parts[1:]:
            bssid   = bpart.splitlines()[0].strip() if bpart.splitlines() else ""
            signal  = _signal_pct(_field(bpart, "Signal", "Señal", "Se.al"))
            radio   = _field(bpart, "Radio type", "Tipo de radio")
            band    = _field(bpart, "Band", "Banda")
            channel = _channel_int(_field(bpart, "Channel", "Canal"))

            # Inferir banda si no viene explícita
            if not band:
                band = "5 GHz" if channel > 14 else "2.4 GHz"

            networks.append({
                "ssid":    ssid,
                "bssid":   bssid,
                "signal":  signal,
                "channel": channel,
                "band":    band,
                "radio":   radio,
                "auth":    auth or "Desconocida",
                "enc":     enc or "",
            })

    return networks


# ── Detección de colisiones ───────────────────────────────────────────────────

def _detect_collisions(networks: list[dict], my_channel: int, my_band: str) -> list[str]:
    """Devuelve lista de SSIDs que colisionan con nuestra red."""
    collisions: list[str] = []
    is_24 = "2.4" in my_band
    for net in networks:
        if net["channel"] == 0:
            continue
        if is_24:
            if _channels_collide_24(my_channel, net["channel"]):
                collisions.append(net["ssid"] or net["bssid"])
        else:
            if _channels_collide_5(my_channel, net["channel"]):
                collisions.append(net["ssid"] or net["bssid"])
    return collisions


# ── Canal óptimo ──────────────────────────────────────────────────────────────

def _best_channel_24(networks: list[dict]) -> int:
    """Canales no solapantes de 2.4 GHz: 1, 6, 11. Devuelve el menos congestionado."""
    non_overlap = [1, 6, 11]
    usage: dict[int, int] = {ch: 0 for ch in non_overlap}
    for net in networks:
        if "2.4" in net.get("band", ""):
            for ch in non_overlap:
                if abs(net["channel"] - ch) < 5:
                    usage[ch] += 1
    return min(usage, key=lambda c: usage[c])


# ── Función principal ─────────────────────────────────────────────────────────

def analyze_wifi() -> dict:
    connected = _get_connected_interface()
    out = _run_netsh(["wlan", "show", "networks", "mode=bssid"])

    if not out or "SSID" not in out:
        return {
            "status":      "warning",
            "title":       "Analizador WiFi",
            "summary":     "No se detectó ninguna interfaz WiFi activa o no hay redes visibles.",
            "issue_count": 0,
            "items":       [],
            "networks":    [],
            "connected":   connected,
        }

    networks = _parse_networks(out)
    if not networks:
        return {
            "status":      "warning",
            "title":       "Analizador WiFi",
            "summary":     "No se encontraron redes WiFi cercanas.",
            "issue_count": 0,
            "items":       [],
            "networks":    [],
            "connected":   connected,
        }

    # Ordenar por señal descendente
    networks.sort(key=lambda n: n["signal"], reverse=True)

    my_channel = connected.get("channel", 0)
    my_band    = ""
    # Inferir banda del canal conectado
    if my_channel:
        my_band = "5 GHz" if my_channel > 14 else "2.4 GHz"

    # Colisiones con nuestra red
    my_ssid = connected.get("ssid", "")
    other_nets = [n for n in networks if n["ssid"] != my_ssid]
    collisions = _detect_collisions(other_nets, my_channel, my_band) if my_channel else []

    # Conteo por canal para detectar congestion
    channel_count: dict[int, int] = {}
    for net in networks:
        ch = net["channel"]
        if ch:
            channel_count[ch] = channel_count.get(ch, 0) + 1

    # Mejor canal 2.4 GHz (si aplica)
    nets_24 = [n for n in networks if "2.4" in n.get("band", "")]
    best_ch_24 = _best_channel_24(nets_24) if nets_24 else None

    # Construir items de diagnóstico
    items: list[dict] = []

    # 1 — Señal de la red conectada
    if connected.get("ssid"):
        sig = connected["signal"]
        if sig >= 70:
            sig_status, sig_msg = "ok",      f"Señal excelente — {sig}%"
        elif sig >= 40:
            sig_status, sig_msg = "warning",  f"Señal moderada — {sig}%"
        else:
            sig_status, sig_msg = "danger",   f"Señal débil — {sig}%"

        rx = connected.get("rx_mbps", "")
        tx = connected.get("tx_mbps", "")
        speed_detail = f"↓ {rx} Mbps  ↑ {tx} Mbps" if rx and tx else ""

        items.append({
            "name":   f"Red conectada: {connected['ssid']}",
            "status": sig_status,
            "value":  f"{sig}%",
            "message": sig_msg,
            "detail": f"Canal {my_channel} · {my_band} · {connected.get('radio_type','')}  {speed_detail}".strip(" ·"),
        })

    # 2 — Colisiones de canal
    if collisions:
        unique = list(dict.fromkeys(collisions))[:6]
        items.append({
            "name":   "Colisión de canal",
            "status": "warning",
            "value":  f"{len(collisions)} redes",
            "message": f"Hay {len(collisions)} red(es) cercana(s) que comparten o solapan tu canal ({my_channel}).",
            "detail": "Redes en conflicto: " + ", ".join(f'"{s}"' for s in unique),
        })
        if best_ch_24 and my_channel and "2.4" in my_band and best_ch_24 != my_channel:
            items.append({
                "name":   "Canal óptimo sugerido (2.4 GHz)",
                "status": "warning",
                "value":  f"Canal {best_ch_24}",
                "message": f"El canal {best_ch_24} está menos congestionado. Cámbialo en la configuración de tu router.",
                "detail": "",
            })

    # 3 — Redes sin cifrado
    open_nets = [n for n in networks if n["auth"] in ("Open", "Abierta", "Abierto", "") or "open" in n["auth"].lower()]
    if open_nets:
        items.append({
            "name":   "Redes abiertas detectadas",
            "status": "warning",
            "value":  f"{len(open_nets)} redes",
            "message": "Hay redes WiFi sin contraseña cercanas. No te conectes a ellas.",
            "detail": ", ".join(f'"{n["ssid"]}"' for n in open_nets[:5]),
        })

    # Resumen global
    danger_c  = sum(1 for i in items if i["status"] == "danger")
    warning_c = sum(1 for i in items if i["status"] == "warning")
    total_nets = len(networks)

    if danger_c:
        overall = "danger"
        summary = f"Señal WiFi débil. {total_nets} redes detectadas."
    elif warning_c:
        overall = "warning"
        summary = f"{total_nets} redes detectadas. {warning_c} aviso(s) de canal o seguridad."
    else:
        overall = "ok"
        summary = f"{total_nets} redes detectadas. Señal y canal en buen estado."

    return {
        "status":      overall,
        "title":       "Analizador WiFi",
        "summary":     summary,
        "issue_count": danger_c + warning_c,
        "items":       items,
        "networks":    networks,
        "connected":   connected,
        "channel_count": channel_count,
    }
