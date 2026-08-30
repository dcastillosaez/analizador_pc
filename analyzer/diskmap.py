"""Mapa de disco — árbol de carpetas por tamaño para treemap SVG."""
import os
import time


def _dir_size(path: str, depth: int, deadline: float) -> int:
    if depth < 0 or time.time() > deadline:
        return 0
    total = 0
    try:
        for e in os.scandir(path):
            try:
                if e.is_dir(follow_symlinks=False):
                    total += _dir_size(e.path, depth - 1, deadline)
                else:
                    total += e.stat(follow_symlinks=False).st_size
            except Exception:
                pass
    except Exception:
        pass
    return total


def _fmt_size(b: int) -> str:
    if b >= 1 << 30:
        return f"{b / (1 << 30):.1f} GB"
    if b >= 1 << 20:
        return f"{b / (1 << 20):.1f} MB"
    if b >= 1 << 10:
        return f"{b / (1 << 10):.1f} KB"
    return f"{b} B"


def scan_dir(path: str = "", timeout: int = 20) -> dict:
    path = os.path.abspath(os.path.expandvars(path or os.path.expanduser("~")))
    if not os.path.isdir(path):
        return {"error": f"Ruta no válida: {path}", "path": path,
                "children": [], "size": 0}

    deadline = time.time() + timeout
    children = []

    try:
        entries = list(os.scandir(path))
    except PermissionError:
        return {"path": path, "size": 0, "children": [],
                "parent": str(os.path.dirname(path)), "timed_out": False}

    for entry in entries:
        if time.time() > deadline:
            break
        try:
            if entry.is_dir(follow_symlinks=False):
                sz = _dir_size(entry.path, 2, deadline)
                children.append({
                    "name": entry.name, "path": entry.path,
                    "size": sz, "size_label": _fmt_size(sz),
                    "is_dir": True,
                })
            else:
                sz = entry.stat(follow_symlinks=False).st_size
                children.append({
                    "name": entry.name, "path": entry.path,
                    "size": sz, "size_label": _fmt_size(sz),
                    "is_dir": False,
                })
        except Exception:
            pass

    children.sort(key=lambda c: c["size"], reverse=True)
    total = sum(c["size"] for c in children)

    return {
        "path":       path,
        "size":       total,
        "size_label": _fmt_size(total),
        "children":   children[:80],
        "parent":     str(os.path.dirname(path)),
        "timed_out":  time.time() > deadline,
    }
