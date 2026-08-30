"""Acciones rápidas de optimización del sistema."""
from ._shell import run
import winreg

_HP_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"


def set_energy_plan_high() -> dict:
    try:
        r = run(["powercfg", "/setactive", _HP_GUID], timeout=10)
        if r.returncode == 0:
            return {"ok": True, "msg": "Plan de energía cambiado a Alto Rendimiento."}
        # Alias por si el GUID no existe en este equipo
        r2 = run(["powercfg", "/setactive", "SCHEME_MIN"], timeout=10)
        if r2.returncode == 0:
            return {"ok": True, "msg": "Plan de energía cambiado a Alto Rendimiento."}
        err = r.combined[:100]
        return {"ok": False, "msg": f"Error al cambiar plan: {err}"}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}


def disable_startup_item(hive_str: str, key_path: str, name: str) -> dict:
    hive = winreg.HKEY_CURRENT_USER if hive_str == "HKCU" else winreg.HKEY_LOCAL_MACHINE
    try:
        key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
        return {"ok": True, "msg": f"'{name}' eliminado del arranque automático."}
    except FileNotFoundError:
        return {"ok": False, "msg": f"'{name}' ya no existe en el registro."}
    except PermissionError:
        return {"ok": False, "msg": "Permiso denegado. Ejecuta como administrador."}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}


def disable_telemetry() -> dict:
    path = r"SOFTWARE\Policies\Microsoft\Windows\DataCollection"
    try:
        key = winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE, path, 0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "AllowTelemetry", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        return {
            "ok": True,
            "msg": "Telemetría desactivada (AllowTelemetry=0). Reinicia Windows para aplicar el cambio.",
        }
    except PermissionError:
        return {"ok": False, "msg": "Permiso denegado. Ejecuta como administrador."}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}
