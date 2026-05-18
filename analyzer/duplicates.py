"""Archivos duplicados — búsqueda por hash MD5 con eliminación selectiva."""
import hashlib
import os
from collections import defaultdict

_MIN_SIZE  = 1024          # ignorar archivos < 1 KB
_MAX_FILES = 8000
_SKIP_DIRS = {"$RECYCLE.BIN", "System Volume Information", ".git",
              "node_modules", "__pycache__"}


def _md5(path: str) -> str | None:
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None


def _fmt(b: int) -> str:
    if b >= 1 << 30: return f"{b/(1<<30):.1f} GB"
    if b >= 1 << 20: return f"{b/(1<<20):.1f} MB"
    return f"{b/(1<<10):.1f} KB"


def find_duplicates(path: str) -> dict:
    path = os.path.abspath(os.path.expandvars(path or os.path.expanduser("~")))
    if not os.path.isdir(path):
        return {"error": f"Ruta no válida: {path}", "groups": [],
                "total_wasted": 0, "scanned": 0}

    # Paso 1: agrupar por tamaño
    by_size: dict[int, list] = defaultdict(list)
    scanned = 0

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            if scanned >= _MAX_FILES:
                break
            fpath = os.path.join(root, fname)
            try:
                sz = os.path.getsize(fpath)
                if sz >= _MIN_SIZE:
                    by_size[sz].append(fpath)
                    scanned += 1
            except OSError:
                pass

    # Paso 2: hashear solo los que comparten tamaño
    by_hash: dict[str, list] = defaultdict(list)
    for sz, paths in by_size.items():
        if len(paths) < 2:
            continue
        for p in paths:
            h = _md5(p)
            if h:
                by_hash[h].append(p)

    # Construir grupos
    groups = []
    total_wasted = 0

    for h, paths in by_hash.items():
        if len(paths) < 2:
            continue
        infos = []
        for p in paths:
            try:
                st = os.stat(p)
                infos.append({"path": p, "name": os.path.basename(p),
                               "size": st.st_size, "mtime": st.st_mtime,
                               "size_label": _fmt(st.st_size)})
            except OSError:
                infos.append({"path": p, "name": os.path.basename(p),
                               "size": 0, "mtime": 0, "size_label": "—"})

        infos.sort(key=lambda x: x["mtime"], reverse=True)  # más reciente primero
        wasted = sum(i["size"] for i in infos[1:])
        total_wasted += wasted

        groups.append({"hash": h[:8], "size": infos[0]["size"],
                       "size_label": infos[0]["size_label"],
                       "count": len(infos), "wasted": wasted,
                       "wasted_label": _fmt(wasted), "files": infos})

    groups.sort(key=lambda g: g["wasted"], reverse=True)

    return {
        "path":          path,
        "scanned":       scanned,
        "groups":        groups[:100],
        "total_groups":  len(groups),
        "total_wasted":  total_wasted,
        "wasted_label":  _fmt(total_wasted) if total_wasted else "0 KB",
    }


def delete_files(paths: list) -> dict:
    deleted, errors, freed = [], [], 0
    for p in paths:
        p = os.path.abspath(p)
        try:
            freed += os.path.getsize(p)
            os.unlink(p)
            deleted.append(p)
        except Exception as e:
            errors.append(f"{os.path.basename(p)}: {e}")
    return {
        "ok":      not errors,
        "deleted": len(deleted),
        "freed":   freed,
        "freed_label": _fmt(freed) if freed else "0 KB",
        "errors":  errors,
        "msg":     f"{len(deleted)} archivo(s) eliminado(s), {_fmt(freed)} liberados."
                   if deleted else "No se eliminó ningún archivo.",
    }
