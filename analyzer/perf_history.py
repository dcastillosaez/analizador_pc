"""Historial de rendimiento en SQLite — snapshots automáticos cada 5 min."""
import os
import sqlite3
from datetime import datetime, timedelta

_DB = os.path.join(os.path.dirname(__file__), '..', 'perf_history.db')


def _open() -> sqlite3.Connection:
    con = sqlite3.connect(_DB)
    con.execute(
        'CREATE TABLE IF NOT EXISTS snap ('
        '  id   INTEGER PRIMARY KEY AUTOINCREMENT,'
        '  ts   TEXT NOT NULL,'
        '  cpu  REAL,'
        '  ram  REAL,'
        '  disk REAL,'
        '  gpu  REAL'
        ')'
    )
    return con


def record(cpu: float, ram: float, disk: float, gpu=None):
    ts = datetime.now().isoformat(timespec='minutes')
    with _open() as con:
        con.execute('INSERT INTO snap (ts,cpu,ram,disk,gpu) VALUES (?,?,?,?,?)',
                    (ts, cpu, ram, disk, gpu))
        cutoff = (datetime.now() - timedelta(hours=48)).isoformat(timespec='minutes')
        con.execute('DELETE FROM snap WHERE ts < ?', (cutoff,))


def get_history(hours: int = 24) -> list:
    try:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat(timespec='minutes')
        with _open() as con:
            rows = con.execute(
                'SELECT ts, cpu, ram, disk, gpu FROM snap WHERE ts >= ? ORDER BY ts',
                (cutoff,),
            ).fetchall()
        return [{'ts': r[0], 'cpu': r[1], 'ram': r[2], 'disk': r[3], 'gpu': r[4]}
                for r in rows]
    except Exception:
        return []
