"""Reglas de firewall no estándar — PowerShell Get-NetFirewallRule."""
import json
import subprocess


def _run_ps(cmd: str, timeout: int = 25) -> str:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="ignore",
    )
    return (r.stdout or "").strip()


def analyze_firewall_rules() -> dict:
    try:
        raw = _run_ps(
            "Get-NetFirewallRule -Enabled True | "
            "Where-Object { $_.Group -notlike '@*' -and "
            "                $_.Group -notlike 'Windows*' -and "
            "                $_.Group -notlike 'Core*' -and "
            "                $_.Group -notlike 'Microsoft*' } | "
            "Select-Object DisplayName, Action, Direction, Profile | "
            "ConvertTo-Json -Compress -Depth 2"
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "warning", "title": "Reglas de firewall",
            "summary": "Tiempo de espera agotado al obtener las reglas.",
            "issue_count": 1, "items": [],
        }
    except Exception as e:
        return {
            "status": "warning", "title": "Reglas de firewall",
            "summary": f"No se pudo obtener las reglas: {e}",
            "issue_count": 1, "items": [],
        }

    if not raw:
        return {
            "status": "ok", "title": "Reglas de firewall",
            "summary": "No se encontraron reglas no estándar habilitadas.",
            "issue_count": 0, "items": [],
        }

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
    except Exception:
        data = []

    _ACTION = {"Allow": "Permitir", "Block": "Bloquear", "2": "Bloquear", "4": "Permitir"}
    _DIR    = {"Inbound": "Entrada", "Outbound": "Salida", "1": "Entrada", "2": "Salida"}

    items = []
    for rule in data:
        name   = (rule.get("DisplayName") or "").strip()
        action = str(rule.get("Action") or "").strip()
        direc  = str(rule.get("Direction") or "").strip()
        prof   = str(rule.get("Profile") or "").strip()
        if not name:
            continue

        action_lbl = _ACTION.get(action, action)
        dir_lbl    = _DIR.get(direc, direc)
        st         = "warning" if action_lbl == "Bloquear" else "ok"

        items.append({
            "name":      name,
            "status":    st,
            "message":   f"{action_lbl} · {dir_lbl} · Perfil: {prof}",
            "value":     action_lbl,
            "detail":    "",
            "rule_name": name,
        })

    items.sort(key=lambda i: (0 if i["status"] == "warning" else 1, i["name"]))

    block_n = sum(1 for i in items if i["status"] == "warning")
    overall = "warning" if block_n else "ok"
    summary = f"{len(items)} reglas no estándar habilitadas" + \
              (f" — {block_n} de bloqueo" if block_n else "") + "."

    return {
        "status":      overall,
        "title":       "Reglas de firewall",
        "summary":     summary,
        "issue_count": block_n,
        "items":       items,
    }


def delete_firewall_rule(name: str) -> dict:
    if not name or len(name) > 300:
        return {"ok": False, "msg": "Nombre de regla no válido."}
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"Remove-NetFirewallRule -DisplayName {json.dumps(name)}"],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="ignore",
        )
        if r.returncode == 0:
            return {"ok": True, "msg": f"Regla '{name}' eliminada."}
        err = (r.stderr or r.stdout or "")[:150].strip()
        return {"ok": False, "msg": f"Error al eliminar: {err}"}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}
