"""Antivirus y Firewall — una sola llamada PowerShell."""
import json

from ._shell import run, run_ps_json


_PS_AV = r"""
try {
  @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -EA Stop |
    Select-Object displayName, productState) | ConvertTo-Json -Compress
} catch { '[]' }
"""

def _get_av() -> list:
    """Antivirus vía CIM (única llamada PS)."""
    try:
        return run_ps_json(_PS_AV, timeout=12, default=[]) or []
    except Exception:
        return []

def _get_firewall() -> list:
    """Firewall vía netsh — nativo, sin arrancar PowerShell."""
    try:
        lines = run(["netsh", "advfirewall", "show", "allprofiles", "state"], timeout=6).stdout
        profiles = []
        current = None
        for line in lines.splitlines():
            line = line.strip()
            if "Profile Settings" in line:
                current = line.replace(" Settings:", "").strip()
            elif line.lower().startswith("state") and current:
                enabled = "on" in line.lower()
                profiles.append({"Name": current, "Enabled": enabled})
                current = None
        return profiles
    except Exception:
        return []


def analyze_protection() -> dict:
    import threading
    av_result, fw_result = [], []
    def fetch_av(): nonlocal av_result; av_result = _get_av()
    def fetch_fw(): nonlocal fw_result; fw_result = _get_firewall()
    t1 = threading.Thread(target=fetch_av, daemon=True)
    t2 = threading.Thread(target=fetch_fw, daemon=True)
    t1.start(); t2.start()
    t1.join(timeout=13); t2.join(timeout=8)

    items: list[dict] = []

    # ── Antivirus ─────────────────────────────────────────────────────────────
    av_list = av_result
    if isinstance(av_list, dict):
        av_list = [av_list]

    if not av_list:
        items.append({"name": "Antivirus", "status": "warning",
            "message": "No se pudo leer el estado del antivirus. Ejecuta como administrador para este check.",
            "value": "Desconocido", "detail": ""})
    else:
        for av in av_list:
            name = av.get("displayName", "Antivirus")
            state = int(av.get("productState") or 0)
            enabled = bool(state & 0x1000)
            updated = (state & 0x10) == 0
            if not enabled:
                items.append({"name": name, "status": "danger",
                    "message": f"'{name}' está DESACTIVADO. Tu equipo está desprotegido.",
                    "value": "Desactivado", "detail": f"productState: {state}"})
            elif not updated:
                items.append({"name": name, "status": "warning",
                    "message": f"'{name}' activo pero las definiciones pueden estar desactualizadas.",
                    "value": "Desactualizado", "detail": f"productState: {state}"})
            else:
                items.append({"name": name, "status": "ok",
                    "message": f"'{name}' está activo y actualizado. Buen trabajo.",
                    "value": "Protegido", "detail": ""})

    # ── Firewall ──────────────────────────────────────────────────────────────
    fw_list = fw_result
    if isinstance(fw_list, dict):
        fw_list = [fw_list]

    if fw_list:
        disabled = [p.get("Name", "?") for p in fw_list if not p.get("Enabled", True)]
        if disabled:
            items.append({"name": "Firewall de Windows", "status": "danger",
                "message": f"Firewall DESACTIVADO en los perfiles: {', '.join(disabled)}. Cualquier conexión entrante puede entrar.",
                "value": "Desactivado",
                "detail": "Perfiles: " + ", ".join(p.get("Name", "?") for p in fw_list)})
        else:
            items.append({"name": "Firewall de Windows", "status": "ok",
                "message": "Firewall activo en todos los perfiles (Dominio, Privado, Público).",
                "value": "Activo",
                "detail": "Perfiles: " + ", ".join(p.get("Name", "?") for p in fw_list)})

    danger  = sum(1 for i in items if i["status"] == "danger")
    warning = sum(1 for i in items if i["status"] == "warning")
    overall = "danger" if danger else ("warning" if warning else "ok")

    summaries = {
        "danger":  f"{danger} protección(es) crítica(s) desactivadas. Riesgo alto.",
        "warning": "Algún componente de protección necesita revisión.",
        "ok":      "Antivirus y Firewall activos y correctamente configurados.",
    }
    return {"status": overall, "title": "Protección", "summary": summaries[overall],
            "issue_count": danger + warning, "items": items}
