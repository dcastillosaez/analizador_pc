import os
import sys
import threading
import time
import webbrowser

from flask import Flask, jsonify, render_template, request

from analyzer._shell import is_admin, relaunch_as_admin

from analyzer.hardware      import analyze_hardware
from analyzer.startup       import analyze_startup
from analyzer.security      import analyze_security
from analyzer.drivers       import analyze_drivers, update_driver, uninstall_driver
from analyzer.protection    import analyze_protection
from analyzer.network       import analyze_network
from analyzer.maintenance   import analyze_maintenance
from analyzer.updates       import analyze_updates, update_package
from analyzer.performance   import snapshot as perf_snapshot
from analyzer.energy        import analyze_energy
from analyzer.connectivity  import analyze_connectivity, run_speedtest
from analyzer.privacy       import analyze_privacy, clean_temp
from analyzer.inventory     import analyze_inventory
from analyzer.wupdates      import check_windows_updates, apply_windows_update
from analyzer.wifi          import analyze_wifi
from analyzer.certs         import analyze_certs, delete_cert
from analyzer.services      import analyze_services
from analyzer.processes     import analyze_processes, kill_process
from analyzer.connections   import analyze_connections
from analyzer.hardening     import analyze_hardening
from analyzer.restore       import create_restore_point, restore_status
from analyzer import history

if getattr(sys, "frozen", False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(_BASE, "templates"),
    static_folder=os.path.join(_BASE, "static"),
)


# ── Registro de módulos de escaneo ────────────────────────────────────────────
# Un único endpoint despacha contra esta tabla en lugar de repetir una ruta
# idéntica por módulo. Los ids son los que usa el frontend en /api/scan/<id>.
SCANNERS = {
    "hardware":     analyze_hardware,
    "startup":      analyze_startup,
    "security":     analyze_security,
    "drivers":      analyze_drivers,
    "protection":   analyze_protection,
    "network":      analyze_network,
    "maintenance":  analyze_maintenance,
    "updates":      analyze_updates,
    "privacy":      analyze_privacy,
    "connectivity": analyze_connectivity,
    "energy":       analyze_energy,
    "inventory":    analyze_inventory,
    "certs":        analyze_certs,
    "wifi":         analyze_wifi,
    "wupdates":     check_windows_updates,
    "services":     analyze_services,
    "processes":    analyze_processes,
    "connections":  analyze_connections,
    "hardening":    analyze_hardening,
}

# Segundos que un resultado sigue considerándose válido. Evita relanzar consultas
# caras a WMI o al registro al navegar entre vistas. Las acciones explícitas del
# usuario ("Escanear Sistema", "Analizar módulo") piden ?fresh=1 y lo saltan.
CACHE_TTL = 60

_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()
_module_locks: dict[str, threading.Lock] = {}


def _module_lock(module_id: str) -> threading.Lock:
    with _cache_lock:
        return _module_locks.setdefault(module_id, threading.Lock())


def run_scanner(module_id: str, fresh: bool = False) -> dict:
    """Ejecuta un módulo reutilizando el resultado reciente si procede.

    El lock por módulo evita que dos peticiones simultáneas (escaneo global en
    paralelo, dos pestañas abiertas) disparen la misma consulta cara dos veces.
    """
    now = time.monotonic()
    if not fresh:
        entry = _cache.get(module_id)
        if entry and now - entry[0] < CACHE_TTL:
            return entry[1]

    with _module_lock(module_id):
        # Otra petición pudo resolverlo mientras esperábamos el lock.
        entry = _cache.get(module_id)
        if entry and time.monotonic() - entry[0] < CACHE_TTL and not fresh:
            return entry[1]

        data = SCANNERS[module_id]()
        _cache[module_id] = (time.monotonic(), data)
        return data


def invalidate_cache(*module_ids: str) -> None:
    """Descarta resultados cacheados tras una operación de escritura."""
    for mid in module_ids or tuple(_cache):
        _cache.pop(mid, None)


# ── Errores ───────────────────────────────────────────────────────────────────
@app.errorhandler(Exception)
def handle_any_error(exc):
    """Cualquier excepción no capturada sale como el esquema JSON estándar.

    Sin esto un fallo en un analyzer devuelve una página HTML de error 500 y el
    frontend rompe al parsear el JSON, mostrando "Unexpected token '<'".
    """
    code = getattr(exc, "code", 500)
    if not isinstance(code, int):
        code = 500

    if request.path.startswith("/api/"):
        if code >= 500:  # los 404/405 no son fallos que merezcan traza
            app.logger.exception("Fallo en %s", request.path)
        return jsonify({
            "status": "danger",
            "title": "Error interno",
            "summary": f"El módulo falló: {exc}",
            "issue_count": 1,
            "items": [{
                "name": request.path,
                "status": "danger",
                "message": "El análisis no pudo completarse por un error interno.",
                "value": type(exc).__name__,
                "detail": str(exc)[:400],
            }],
            "success": False,
            "message": str(exc)[:400],
        }), code

    return f"<h1>Error {code}</h1><p>{exc}</p>", code


# ── Estado de la aplicación ───────────────────────────────────────────────────
@app.route("/api/status/admin")
def status_admin():
    """Indica si la app corre elevada; el frontend avisa cuando no lo está."""
    return jsonify({"admin": is_admin()})


@app.route("/api/admin/elevate", methods=["POST"])
def admin_elevate():
    """Relanza la app pidiendo elevación por UAC y cierra la instancia actual."""
    if is_admin():
        return jsonify({"success": False, "message": "La aplicación ya se ejecuta como administrador."})

    if not relaunch_as_admin():
        return jsonify({"success": False, "message": "Windows rechazó la solicitud de elevación."})

    # Se da margen a que la respuesta llegue al navegador antes de salir.
    def _quit():
        time.sleep(1.0)
        os._exit(0)

    threading.Thread(target=_quit, daemon=True).start()
    return jsonify({"success": True, "message": "Reiniciando con permisos de administrador."})


# ── Vistas ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    bust = str(int(os.path.getmtime(os.path.join(_BASE, "static", "js", "app.js"))))
    return render_template("index.html", cache_bust=bust)


# ── Escaneo ───────────────────────────────────────────────────────────────────
@app.route("/api/scan/<module_id>")
def scan(module_id):
    if module_id not in SCANNERS:
        return jsonify({
            "status": "danger",
            "title": "Módulo desconocido",
            "summary": f"No existe ningún módulo llamado '{module_id}'.",
            "issue_count": 1,
            "items": [],
        }), 404

    fresh = request.args.get("fresh") == "1"
    return jsonify(run_scanner(module_id, fresh=fresh))


@app.route("/api/perf/snapshot")
def perf_snapshot_route():
    return jsonify(perf_snapshot())


@app.route("/api/connectivity/speedtest")
def connectivity_speedtest():
    return jsonify(run_speedtest())


# ── Operaciones de escritura ──────────────────────────────────────────────────
def _con_punto_de_restauracion(descripcion: str):
    """Crea un punto de restauración si el cliente lo pidió, sin bloquear nada.

    Desinstalar un controlador o instalar una actualización son cambios que
    cuesta deshacer. Si la protección del sistema está apagada o falta
    elevación, se sigue adelante y se informa en la respuesta.
    """
    body = request.get_json(silent=True) or {}
    if not body.get("restore_point"):
        return None
    return create_restore_point(descripcion)


@app.route("/api/restore/status")
def restore_status_route():
    return jsonify(restore_status())


@app.route("/api/restore/create", methods=["POST"])
def restore_create_route():
    body = request.get_json(silent=True) or {}
    return jsonify(create_restore_point(body.get("description") or "PC Guardian - punto manual"))



@app.route("/api/driver/update", methods=["POST"])
def do_driver_update():
    body = request.get_json(silent=True) or {}
    result = update_driver(body.get("device_id", ""))
    invalidate_cache("drivers")
    return jsonify(result)


@app.route("/api/driver/uninstall", methods=["POST"])
def do_driver_uninstall():
    body = request.get_json(silent=True) or {}
    restore = _con_punto_de_restauracion("PC Guardian - antes de desinstalar un controlador")
    result = uninstall_driver(body.get("device_id", ""))
    result["restore"] = restore
    invalidate_cache("drivers")
    return jsonify(result)


@app.route("/api/cert/delete", methods=["POST"])
def do_cert_delete():
    body = request.get_json(silent=True) or {}
    restore = _con_punto_de_restauracion("PC Guardian - antes de eliminar un certificado")
    result = delete_cert(body.get("store_path", ""), body.get("thumbprint", ""))
    result["restore"] = restore
    invalidate_cache("certs")
    return jsonify(result)


@app.route("/api/privacy/clean-temp", methods=["POST"])
def privacy_clean_temp():
    result = clean_temp()
    invalidate_cache("privacy", "hardware")
    return jsonify(result)


@app.route("/api/wupdate/apply/<path:update_id>", methods=["POST"])
def do_windows_update(update_id):
    restore = _con_punto_de_restauracion("PC Guardian - antes de instalar una actualizacion")
    result = apply_windows_update(update_id)
    result["restore"] = restore
    invalidate_cache("wupdates")
    return jsonify(result)


@app.route("/api/process/kill", methods=["POST"])
def do_kill_process():
    body = request.get_json(silent=True) or {}
    result = kill_process(body.get("pid"))
    invalidate_cache("processes", "connections", "hardware")
    return jsonify(result)


@app.route("/api/update/<path:package_id>", methods=["POST"])
def do_update(package_id):
    result = update_package(package_id)
    invalidate_cache("updates")
    return jsonify(result)


# ── Historial de escaneos ─────────────────────────────────────────────────────
@app.route("/api/history", methods=["GET"])
def history_list():
    return jsonify({"scans": history.list_scans(limit=int(request.args.get("limit", 50)))})


@app.route("/api/history", methods=["POST"])
def history_save():
    body = request.get_json(silent=True) or {}
    return jsonify(history.save_scan(body.get("results") or {}, body.get("score")))


@app.route("/api/history/<int:scan_id>", methods=["GET"])
def history_get(scan_id):
    scan = history.get_scan(scan_id)
    if scan is None:
        return jsonify({"success": False, "message": "Ese escaneo ya no existe."}), 404
    return jsonify(scan)


@app.route("/api/history/<int:scan_id>", methods=["DELETE"])
def history_delete(scan_id):
    return jsonify(history.delete_scan(scan_id))


@app.route("/api/history/clear", methods=["POST"])
def history_clear():
    return jsonify(history.clear_history())


@app.route("/api/history/diff")
def history_diff():
    try:
        a, b = int(request.args["a"]), int(request.args["b"])
    except (KeyError, ValueError):
        return jsonify({"success": False, "message": "Faltan los parámetros a y b."}), 400
    return jsonify(history.diff_scans(a, b))


# ── Arranque ──────────────────────────────────────────────────────────────────
PORT = 47832
HOST = "127.0.0.1"


def _open_browser():
    time.sleep(1.4)
    webbrowser.open(f"http://{HOST}:{PORT}")


def _serve():
    """Sirve la app. Prefiere waitress; cae al servidor de Flask si no está."""
    try:
        from waitress import serve
    except ImportError:
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)
        return
    # threads=8: el escaneo lanza varios módulos en paralelo desde el navegador.
    serve(app, host=HOST, port=PORT, threads=8, channel_timeout=900, ident="PC Guardian")


if __name__ == "__main__":
    if sys.platform == "win32":
        threading.Thread(target=_open_browser, daemon=True).start()
    _serve()
