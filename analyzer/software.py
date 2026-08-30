"""Inventario de software instalado vía registro de Windows."""
import re
import subprocess
import winreg

_HIVES = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def _fmt_date(s: str) -> str:
    if len(s) == 8 and s.isdigit():
        return f"{s[6:8]}/{s[4:6]}/{s[:4]}"
    return s or "—"


def get_installed_software() -> dict:
    seen: set = set()
    programs: list = []

    for hive, path in _HIVES:
        try:
            reg_key = winreg.OpenKey(hive, path)
        except OSError:
            continue

        count = winreg.QueryInfoKey(reg_key)[0]
        for i in range(count):
            try:
                sub_name = winreg.EnumKey(reg_key, i)
                sub_key  = winreg.OpenKey(reg_key, sub_name)

                def _v(field, default=""):
                    try:
                        return str(winreg.QueryValueEx(sub_key, field)[0])
                    except OSError:
                        return default

                name = _v("DisplayName")
                if not name or name.lower() in seen:
                    winreg.CloseKey(sub_key)
                    continue
                seen.add(name.lower())

                size_kb = 0
                try:
                    size_kb = int(winreg.QueryValueEx(sub_key, "EstimatedSize")[0])
                except Exception:
                    pass

                programs.append({
                    "name":      name,
                    "version":   _v("DisplayVersion") or "—",
                    "publisher": _v("Publisher") or "—",
                    "date":      _fmt_date(_v("InstallDate")),
                    "size_mb":   round(size_kb / 1024, 1) if size_kb else 0,
                    "status":    "ok",
                    "message":   "",
                    "value":     f"{round(size_kb/1024,1)} MB" if size_kb else "—",
                    "detail":    "",
                })
                winreg.CloseKey(sub_key)
            except Exception:
                pass

        winreg.CloseKey(reg_key)

    programs.sort(key=lambda p: p["size_mb"], reverse=True)

    return {
        "status":      "ok",
        "title":       "Programas instalados",
        "summary":     f"{len(programs)} programas instalados.",
        "issue_count": 0,
        "items":       programs,
    }


def uninstall_software(name: str) -> dict:
    if not name or len(name) > 200 or re.search(r'[;&|`$<>]', name):
        return {"ok": False, "msg": "Nombre de programa no válido."}
    try:
        r = subprocess.run(
            ["winget", "uninstall", "--name", name,
             "--silent", "--accept-source-agreements"],
            capture_output=True, timeout=120,
        )
        if r.returncode == 0:
            return {"ok": True, "msg": f'"{name}" desinstalado correctamente.'}
        for enc in ("utf-8", "oem", "cp1252"):
            try:
                err = (r.stderr or r.stdout).decode(enc, errors="ignore").strip()
                break
            except Exception:
                err = ""
        return {"ok": False, "msg": f"winget (código {r.returncode}): {err[:180]}"}
    except FileNotFoundError:
        return {"ok": False, "msg": "winget no disponible en este equipo."}
    except subprocess.TimeoutExpired:
        return {"ok": False, "msg": "Tiempo de espera agotado (120 s)."}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}
