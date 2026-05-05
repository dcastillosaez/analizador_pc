import subprocess


def _run_winget(args: list[str], timeout: int = 90) -> str:
    try:
        r = subprocess.run(
            ["winget"] + args,
            capture_output=True,
            timeout=timeout,
        )
        raw = r.stdout or b""
        # winget emite en la página OEM del sistema; probar varias codificaciones
        for enc in ("utf-8", "oem", "cp1252", "latin-1"):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("latin-1")
    except FileNotFoundError:
        return "__NO_WINGET__"
    except subprocess.TimeoutExpired:
        return "__TIMEOUT__"
    except Exception:
        return ""


def _parse_upgrade_list(output: str) -> list[dict]:
    """Parsea la salida tabular de `winget upgrade` usando posiciones de cabecera."""
    lines = output.splitlines()

    # Mapeo de columnas en varios idiomas → clave interna
    COL_ALIASES = {
        "Name": "Name", "Nombre": "Name",
        "Id": "Id",
        "Version": "Version", "Versión": "Version", "Version disponible": "Version",
        "Available": "Available", "Disponible": "Available",
        "Source": "Source", "Origen": "Source",
    }

    # Buscar línea de cabecera (contiene la columna Id y al menos Name/Nombre)
    header_idx = None
    for i, line in enumerate(lines):
        has_id = "Id" in line
        has_name = "Name" in line or "Nombre" in line
        has_avail = "Available" in line or "Disponible" in line
        if has_id and has_name and has_avail:
            header_idx = i
            break

    if header_idx is None:
        return []

    header = lines[header_idx]

    # Detectar posiciones de columna usando aliases
    col_positions: dict[str, int] = {}
    for alias, key in COL_ALIASES.items():
        pos = header.find(alias)
        if pos >= 0 and key not in col_positions:
            col_positions[key] = pos

    required = {"Name", "Id", "Available"}
    if not required.issubset(col_positions):
        return []

    ordered = sorted(col_positions.keys(), key=lambda k: col_positions[k])
    min_len = col_positions.get("Available", 0) + 1

    packages: list[dict] = []
    # Saltar cabecera + separador
    for line in lines[header_idx + 2 :]:
        stripped = line.strip()
        if not stripped or stripped.startswith("-") or stripped.startswith("─"):
            continue
        if len(line) < min_len:
            continue

        try:
            pkg: dict[str, str] = {}
            for i, col in enumerate(ordered):
                start = col_positions[col]
                end = col_positions[ordered[i + 1]] if i + 1 < len(ordered) else len(line)
                pkg[col] = line[start:end].strip()

            name = pkg.get("Name", "")
            pkg_id = pkg.get("Id", "")
            available = pkg.get("Available", "")

            # Filtrar líneas de resumen que winget añade al final
            if name and pkg_id and available and len(pkg_id) > 2 and "." in pkg_id:
                packages.append(
                    {
                        "name": name,
                        "id": pkg_id,
                        "version": pkg.get("Version", "desconocida"),
                        "available": available,
                    }
                )
        except Exception:
            continue

    return packages


def analyze_updates() -> dict:
    # --upgrade-available usa caché local, no refresca fuentes → muy rápido
    output = _run_winget([
        "list",
        "--upgrade-available",
        "--disable-interactivity",
        "--accept-source-agreements",
    ])

    if output == "__NO_WINGET__":
        return {
            "status": "warning",
            "title": "Actualizaciones de Software",
            "summary": "winget no está disponible en este equipo. Actualiza Windows a la versión 1809 o superior para habilitarlo.",
            "issue_count": 0,
            "items": [],
            "winget_available": False,
        }

    if output == "__TIMEOUT__":
        return {
            "status": "warning",
            "title": "Actualizaciones de Software",
            "summary": "El análisis tardó demasiado. Inténtalo de nuevo.",
            "issue_count": 0,
            "items": [],
            "winget_available": True,
        }

    packages = _parse_upgrade_list(output)
    items: list[dict] = []

    for pkg in packages:
        items.append(
            {
                "name": pkg["name"],
                "status": "warning",
                "message": f"Versión actual: {pkg['version']}  →  Disponible: {pkg['available']}",
                "value": pkg["available"],
                "detail": f"ID: {pkg['id']}",
                "package_id": pkg["id"],
            }
        )

    count = len(items)
    if count == 0:
        overall, summary = "ok", "Todos tus programas instalados están actualizados."
    elif count <= 5:
        overall = "warning"
        summary = f"{count} programa(s) con actualización disponible."
    else:
        overall = "warning"
        summary = f"{count} programas desactualizados. Actualizar mejora seguridad y rendimiento."

    return {
        "status": overall,
        "title": "Actualizaciones de Software",
        "summary": summary,
        "issue_count": count,
        "items": items,
        "winget_available": True,
    }


def update_package(package_id: str) -> dict:
    """Actualiza un paquete concreto. Esta es la única operación de escritura de la app."""
    # Sanidad básica: el ID de winget solo contiene alfanuméricos, puntos y guiones
    import re
    if not re.match(r"^[\w.\-\+]+$", package_id):
        return {"success": False, "message": "ID de paquete no válido.", "output": ""}

    try:
        r = subprocess.run(
            [
                "winget", "upgrade",
                "--id", package_id,
                "--silent",
                "--force",
                "--disable-interactivity",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            encoding="utf-8",
            errors="ignore",
        )
        success = r.returncode == 0
        raw = (r.stdout or "") + (r.stderr or "")
        return {
            "success": success,
            "message": "Actualización completada correctamente." if success else "La actualización no pudo completarse.",
            "output": raw[-600:].strip(),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "La actualización tardó demasiado y se canceló.", "output": ""}
    except Exception as e:
        return {"success": False, "message": str(e), "output": ""}
