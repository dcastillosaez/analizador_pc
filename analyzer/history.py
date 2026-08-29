"""Historial de escaneos en SQLite.

Cada escaneo global se guarda entero (el JSON de todos los módulos) junto con
su puntuación. Eso permite dos cosas que la app no tenía: ver si la salud del
equipo mejora o empeora con el tiempo, y comparar dos escaneos para saber
exactamente qué cambió.

La base vive fuera del proyecto, en el perfil del usuario, para que sobreviva a
reinstalaciones y funcione igual desde el .exe compilado.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Cuántos escaneos se conservan. Un escaneo completo ocupa unas pocas decenas de
# KB, así que 200 son unos pocos MB y cubren meses de uso.
MAX_SCANS = 200

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT    NOT NULL,
    score        INTEGER,
    issue_count  INTEGER NOT NULL DEFAULT 0,
    module_count INTEGER NOT NULL DEFAULT 0,
    payload      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);
"""


def db_path() -> Path:
    """Ruta de la base de datos: %LOCALAPPDATA%\\PCGuardian\\history.db."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    folder = base / "PCGuardian"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "history.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# ── Escritura ─────────────────────────────────────────────────────────────────

def save_scan(results: dict, score=None) -> dict:
    """Guarda un escaneo completo. `results` es {module_id: respuesta del módulo}."""
    if not isinstance(results, dict) or not results:
        return {"success": False, "message": "No hay resultados que guardar."}

    modules = {k: v for k, v in results.items() if isinstance(v, dict) and v.get("title")}
    if not modules:
        return {"success": False, "message": "No hay resultados que guardar."}

    issue_count = sum(int(m.get("issue_count") or 0) for m in modules.values())

    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO scans (created_at, score, issue_count, module_count, payload)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                int(score) if score is not None else None,
                issue_count,
                len(modules),
                json.dumps(modules, ensure_ascii=False),
            ),
        )
        scan_id = cur.lastrowid
        # Poda: nos quedamos con los MAX_SCANS más recientes.
        conn.execute(
            "DELETE FROM scans WHERE id NOT IN"
            " (SELECT id FROM scans ORDER BY id DESC LIMIT ?)",
            (MAX_SCANS,),
        )

    return {"success": True, "id": scan_id, "message": "Escaneo guardado en el historial."}


def delete_scan(scan_id: int) -> dict:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    if cur.rowcount:
        return {"success": True, "message": "Escaneo eliminado del historial."}
    return {"success": False, "message": "Ese escaneo ya no existe."}


def clear_history() -> dict:
    with _connect() as conn:
        conn.execute("DELETE FROM scans")
    return {"success": True, "message": "Historial vaciado."}


# ── Lectura ───────────────────────────────────────────────────────────────────

def list_scans(limit: int = 50) -> list[dict]:
    """Línea de tiempo, del más reciente al más antiguo, sin el payload."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, score, issue_count, module_count"
            " FROM scans ORDER BY id DESC LIMIT ?",
            (max(1, min(limit, MAX_SCANS)),),
        ).fetchall()
    return [dict(r) for r in rows]


def get_scan(scan_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    try:
        data["modules"] = json.loads(data.pop("payload"))
    except (ValueError, TypeError):
        data["modules"] = {}
    return data


# ── Comparación ───────────────────────────────────────────────────────────────

_RANK = {"ok": 0, "warning": 1, "danger": 2}


def _item_key(module_id: str, item: dict) -> str:
    return f"{module_id}\x00{item.get('name', '')}"


def _flatten(modules: dict) -> dict[str, dict]:
    """Aplana {módulo: {items:[…]}} a {clave: item} para poder cruzarlos."""
    flat = {}
    for mid, mod in (modules or {}).items():
        if not isinstance(mod, dict):
            continue
        for item in mod.get("items") or []:
            if isinstance(item, dict) and item.get("name"):
                flat[_item_key(mid, item)] = {**item, "module": mid}
    return flat


def diff_scans(id_a: int, id_b: int) -> dict:
    """Compara dos escaneos. A es el antiguo (referencia), B el nuevo."""
    a = get_scan(id_a)
    b = get_scan(id_b)
    if not a or not b:
        return {"success": False, "message": "Uno de los escaneos ya no existe."}

    mods_a, mods_b = a["modules"], b["modules"]

    # Nivel módulo: cómo se movió el estado general de cada tarjeta.
    modules_diff = []
    for mid in sorted(set(mods_a) | set(mods_b)):
        ma, mb = mods_a.get(mid), mods_b.get(mid)
        if not ma or not mb:
            continue
        ra, rb = _RANK.get(ma.get("status"), 0), _RANK.get(mb.get("status"), 0)
        modules_diff.append({
            "module":  mid,
            "title":   mb.get("title") or mid,
            "before":  ma.get("status"),
            "after":   mb.get("status"),
            "trend":   "worse" if rb > ra else "better" if rb < ra else "same",
            "issues_before": int(ma.get("issue_count") or 0),
            "issues_after":  int(mb.get("issue_count") or 0),
        })

    # Nivel item: qué apareció, qué se arregló y qué cambió de gravedad.
    flat_a, flat_b = _flatten(mods_a), _flatten(mods_b)

    new_issues, fixed, changed = [], [], []
    for key, item in flat_b.items():
        prev = flat_a.get(key)
        if prev is None:
            if item.get("status") != "ok":
                new_issues.append(item)
        elif prev.get("status") != item.get("status"):
            entry = {**item, "before": prev.get("status")}
            if _RANK.get(item.get("status"), 0) < _RANK.get(prev.get("status"), 0):
                fixed.append(entry)
            else:
                changed.append(entry)

    for key, prev in flat_a.items():
        # Lo que estaba mal y ha desaparecido del todo también cuenta como resuelto.
        if key not in flat_b and prev.get("status") != "ok":
            fixed.append({**prev, "before": prev.get("status"), "status": "ok",
                          "message": "Ya no aparece en el escaneo."})

    score_a, score_b = a.get("score"), b.get("score")
    return {
        "success": True,
        "a": {"id": a["id"], "created_at": a["created_at"], "score": score_a,
              "issue_count": a["issue_count"]},
        "b": {"id": b["id"], "created_at": b["created_at"], "score": score_b,
              "issue_count": b["issue_count"]},
        "score_delta": (score_b - score_a) if (score_a is not None and score_b is not None) else None,
        "issue_delta": b["issue_count"] - a["issue_count"],
        "modules": modules_diff,
        "new_issues": new_issues,
        "fixed": fixed,
        "changed": changed,
    }
