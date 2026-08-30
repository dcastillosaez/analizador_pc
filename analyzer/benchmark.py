"""Benchmark rápido — CPU (criba Eratóstenes) + disco (R/W secuencial 32 MB)."""
import os
import sqlite3
import tempfile
import time
from datetime import datetime

from ._storage import db_path

_DB = db_path('benchmark.db')


# ── Persistencia ──────────────────────────────────────────────────────────────

def _open() -> sqlite3.Connection:
    con = sqlite3.connect(_DB)
    con.execute(
        'CREATE TABLE IF NOT EXISTS results ('
        '  id            INTEGER PRIMARY KEY AUTOINCREMENT,'
        '  ts            TEXT    NOT NULL,'
        '  cpu_ms        REAL,'
        '  disk_write    REAL,'
        '  disk_read     REAL,'
        '  score         INTEGER'
        ')'
    )
    return con


def _save(cpu_ms: float, write_mbs: float, read_mbs: float, score: int):
    with _open() as con:
        con.execute(
            'INSERT INTO results (ts,cpu_ms,disk_write,disk_read,score) VALUES (?,?,?,?,?)',
            (datetime.now().isoformat(timespec='seconds'), cpu_ms, write_mbs, read_mbs, score),
        )
        # Conservar solo las últimas 50 entradas
        con.execute(
            'DELETE FROM results WHERE id NOT IN '
            '(SELECT id FROM results ORDER BY id DESC LIMIT 50)'
        )


def get_history() -> list:
    try:
        with _open() as con:
            rows = con.execute(
                'SELECT id,ts,cpu_ms,disk_write,disk_read,score '
                'FROM results ORDER BY id DESC LIMIT 20'
            ).fetchall()
        return [
            {'id': r[0], 'ts': r[1], 'cpu_ms': r[2],
             'disk_write': r[3], 'disk_read': r[4], 'score': r[5]}
            for r in rows
        ]
    except Exception:
        return []


# ── Tests ──────────────────────────────────────────────────────────────────────

def _bench_cpu() -> dict:
    """Criba de Eratóstenes hasta 10 000 000."""
    N = 10_000_000
    t0 = time.perf_counter()

    sieve = bytearray([1]) * (N + 1)
    sieve[0] = sieve[1] = 0
    for i in range(2, int(N ** 0.5) + 1):
        if sieve[i]:
            sieve[i * i :: i] = bytearray(len(sieve[i * i :: i]))
    prime_count = sum(sieve)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return {'elapsed_ms': round(elapsed_ms, 1), 'primes': prime_count}


def _bench_disk() -> dict:
    """Escritura y lectura secuencial de 32 MB con fsync."""
    SIZE = 32 * 1024 * 1024
    data = os.urandom(SIZE)
    tmp  = None

    try:
        fd, tmp = tempfile.mkstemp(suffix='.pcg_bench')

        # Escritura
        t0 = time.perf_counter()
        os.write(fd, data)
        os.fsync(fd)
        write_s = time.perf_counter() - t0
        os.close(fd)

        # Lectura
        t0 = time.perf_counter()
        with open(tmp, 'rb') as f:
            _ = f.read()
        read_s = time.perf_counter() - t0

    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass

    write_mbs = round(SIZE / write_s / 1_048_576, 1)
    read_mbs  = round(SIZE / read_s  / 1_048_576, 1)
    return {'write_mbs': write_mbs, 'read_mbs': read_mbs}


def _score(cpu_ms: float, write_mbs: float, read_mbs: float) -> int:
    """Score 0-100 basado en umbrales de referencia."""
    # CPU: 500 ms → 100 pts / 3000 ms → 0 pts (lineal inversa)
    cpu_pts  = max(0, min(100, round((3000 - cpu_ms)  / 25)))
    # Disco: 500 MB/s → 100 pts / 0 MB/s → 0 pts (media de R+W)
    disk_avg = (write_mbs + read_mbs) / 2
    disk_pts = max(0, min(100, round(disk_avg / 5)))
    return round((cpu_pts + disk_pts) / 2)


# ── Punto de entrada ───────────────────────────────────────────────────────────

def run_benchmark() -> dict:
    cpu  = _bench_cpu()
    disk = _bench_disk()

    cpu_ms     = cpu['elapsed_ms']
    write_mbs  = disk['write_mbs']
    read_mbs   = disk['read_mbs']
    score      = _score(cpu_ms, write_mbs, read_mbs)

    _save(cpu_ms, write_mbs, read_mbs, score)
    history = get_history()

    # Comparación con la ejecución anterior (si existe)
    prev = history[1] if len(history) > 1 else None
    delta_score = None
    if prev and prev['score'] is not None:
        delta_score = score - prev['score']

    return {
        'cpu_ms':      cpu_ms,
        'primes':      cpu['primes'],
        'disk_write':  write_mbs,
        'disk_read':   read_mbs,
        'score':       score,
        'delta_score': delta_score,
        'history':     history,
    }
