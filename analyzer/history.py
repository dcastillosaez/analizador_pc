"""Historial de escaneos en SQLite."""
import json
import os
import sqlite3
from datetime import datetime

_DB = os.path.join(os.path.dirname(__file__), '..', 'history.db')


def _open() -> sqlite3.Connection:
    con = sqlite3.connect(_DB)
    con.execute(
        'CREATE TABLE IF NOT EXISTS scans ('
        '  id      INTEGER PRIMARY KEY AUTOINCREMENT,'
        '  ts      TEXT    NOT NULL,'
        '  score   INTEGER,'
        '  modules TEXT'
        ')'
    )
    return con


def save_scan(score: int, results: dict) -> int:
    modules = {
        k: {
            'status':      v.get('status', 'ok'),
            'summary':     v.get('summary', ''),
            'issue_count': v.get('issue_count', 0),
        }
        for k, v in results.items() if isinstance(v, dict)
    }
    with _open() as con:
        cur = con.execute(
            'INSERT INTO scans (ts, score, modules) VALUES (?, ?, ?)',
            (datetime.now().isoformat(timespec='seconds'), score, json.dumps(modules)),
        )
        return cur.lastrowid


def list_scans(limit: int = 50) -> list:
    try:
        with _open() as con:
            rows = con.execute(
                'SELECT id, ts, score, modules FROM scans ORDER BY id DESC LIMIT ?',
                (limit,),
            ).fetchall()
        return [
            {'id': r[0], 'ts': r[1], 'score': r[2],
             'modules': json.loads(r[3] or '{}')}
            for r in rows
        ]
    except Exception:
        return []


def delete_scan(scan_id: int):
    with _open() as con:
        con.execute('DELETE FROM scans WHERE id = ?', (scan_id,))
