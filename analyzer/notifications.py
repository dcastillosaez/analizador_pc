"""Notificaciones programadas — inicio automático + toast Windows."""
import os
import subprocess
import sys
import winreg

_APP_NAME = "PCGuardian"
_RUN_KEY  = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"


def _launch_cmd() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --silent'
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
    return f'"{sys.executable}" "{script}" --silent'


def enable_startup() -> dict:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _launch_cmd())
        winreg.CloseKey(key)
        return {"ok": True, "msg": "PC Guardian se ejecutará silenciosamente al arrancar Windows."}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}


def disable_startup() -> dict:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, _APP_NAME)
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        return {"ok": True, "msg": "PC Guardian eliminado del inicio automático."}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}


def startup_status() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def send_toast(title: str, message: str):
    """Toast via PowerShell + NotifyIcon (sin dependencias externas)."""
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$n = New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon = [System.Drawing.SystemIcons]::Shield;"
        f'$n.BalloonTipTitle = "{title.replace(chr(34), "")}";"'
        f'$n.BalloonTipText  = "{message.replace(chr(34), "")}";"'
        "$n.Visible = $true;"
        "$n.ShowBalloonTip(8000);"
        "Start-Sleep -Seconds 9;"
        "$n.Dispose()"
    )
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
        creationflags=flags,
    )


def run_silent_scan() -> dict:
    """Escaneo ligero para notificaciones al arrancar."""
    from analyzer.security    import analyze_security
    from analyzer.protection  import analyze_protection
    from analyzer.updates     import analyze_updates
    from analyzer.maintenance import analyze_maintenance
    from analyzer.privacy     import analyze_privacy

    results = {}
    for name, fn in [
        ("security",    analyze_security),
        ("protection",  analyze_protection),
        ("updates",     analyze_updates),
        ("maintenance", analyze_maintenance),
        ("privacy",     analyze_privacy),
    ]:
        try:
            results[name] = fn()
        except Exception:
            pass

    danger  = sum(1 for r in results.values() if r.get("status") == "danger")
    warning = sum(1 for r in results.values() if r.get("status") == "warning")

    if danger:
        send_toast("⚠ PC Guardian — Problemas críticos",
                   f"{danger} problema(s) crítico(s) detectados. Abre PC Guardian.")
    elif warning:
        send_toast("PC Guardian — Advertencias",
                   f"{warning} módulo(s) requieren atención.")

    return {"danger": danger, "warning": warning}
