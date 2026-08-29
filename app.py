import os
import sys
import threading
import time
import webbrowser

from flask import Flask, jsonify, render_template, request

from analyzer._shell import is_admin

from analyzer.hardware    import analyze_hardware
from analyzer.startup     import analyze_startup
from analyzer.security    import analyze_security
from analyzer.drivers     import analyze_drivers, update_driver, uninstall_driver
from analyzer.protection  import analyze_protection
from analyzer.network     import analyze_network
from analyzer.maintenance import analyze_maintenance
from analyzer.updates     import analyze_updates, update_package
from analyzer.performance import snapshot as perf_snapshot
from analyzer.energy        import analyze_energy
from analyzer.connectivity  import analyze_connectivity, run_speedtest
from analyzer.privacy       import analyze_privacy, clean_temp
from analyzer.inventory     import analyze_inventory
from analyzer.wupdates      import check_windows_updates, apply_windows_update
from analyzer.wifi          import analyze_wifi
from analyzer.certs         import analyze_certs, delete_cert
from analyzer.services      import analyze_services

if getattr(sys, "frozen", False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(_BASE, "templates"),
    static_folder=os.path.join(_BASE, "static"),
)


@app.errorhandler(Exception)
def handle_any_error(exc):
    """Cualquier excepcion no capturada sale como el esquema JSON estandar.

    Sin esto un fallo en un analyzer devuelve una pagina HTML de error 500 y el
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
            "summary": f"El modulo fallo: {exc}",
            "issue_count": 1,
            "items": [{
                "name": request.path,
                "status": "danger",
                "message": "El analisis no pudo completarse por un error interno.",
                "value": type(exc).__name__,
                "detail": str(exc)[:400],
            }],
            "success": False,
            "message": str(exc)[:400],
        }), code

    return f"<h1>Error {code}</h1><p>{exc}</p>", code


@app.route("/api/status/admin")
def status_admin():
    """Indica si la app corre elevada; el frontend avisa cuando no lo esta."""
    return jsonify({"admin": is_admin()})


@app.route("/")
def index():
    bust = str(int(os.path.getmtime(os.path.join(_BASE, "static", "js", "app.js"))))
    return render_template("index.html", cache_bust=bust)


@app.route("/api/scan/hardware")
def scan_hardware():
    return jsonify(analyze_hardware())

@app.route("/api/scan/startup")
def scan_startup():
    return jsonify(analyze_startup())

@app.route("/api/scan/security")
def scan_security():
    return jsonify(analyze_security())

@app.route("/api/scan/drivers")
def scan_drivers():
    return jsonify(analyze_drivers())

@app.route("/api/driver/update", methods=["POST"])
def do_driver_update():
    body = request.get_json(silent=True) or {}
    device_id = body.get("device_id", "")
    return jsonify(update_driver(device_id))

@app.route("/api/driver/uninstall", methods=["POST"])
def do_driver_uninstall():
    body = request.get_json(silent=True) or {}
    device_id = body.get("device_id", "")
    return jsonify(uninstall_driver(device_id))

@app.route("/api/scan/protection")
def scan_protection():
    return jsonify(analyze_protection())

@app.route("/api/scan/network")
def scan_network():
    return jsonify(analyze_network())

@app.route("/api/scan/maintenance")
def scan_maintenance():
    return jsonify(analyze_maintenance())

@app.route("/api/scan/updates")
def scan_updates():
    return jsonify(analyze_updates())

@app.route("/api/scan/privacy")
def scan_privacy():
    return jsonify(analyze_privacy())

@app.route("/api/privacy/clean-temp", methods=["POST"])
def privacy_clean_temp():
    return jsonify(clean_temp())

@app.route("/api/scan/connectivity")
def scan_connectivity():
    return jsonify(analyze_connectivity())

@app.route("/api/connectivity/speedtest")
def connectivity_speedtest():
    return jsonify(run_speedtest())

@app.route("/api/scan/energy")
def scan_energy():
    return jsonify(analyze_energy())

@app.route("/api/perf/snapshot")
def perf_snapshot_route():
    return jsonify(perf_snapshot())

@app.route("/api/scan/inventory")
def scan_inventory():
    return jsonify(analyze_inventory())

@app.route("/api/scan/certs")
def scan_certs():
    return jsonify(analyze_certs())

@app.route("/api/cert/delete", methods=["POST"])
def do_cert_delete():
    body = request.get_json(silent=True) or {}
    return jsonify(delete_cert(body.get("store_path",""), body.get("thumbprint","")))

@app.route("/api/scan/wifi")
def scan_wifi():
    return jsonify(analyze_wifi())

@app.route("/api/scan/wupdates")
def scan_wupdates():
    return jsonify(check_windows_updates())

@app.route("/api/wupdate/apply/<path:update_id>", methods=["POST"])
def do_windows_update(update_id):
    return jsonify(apply_windows_update(update_id))

@app.route("/api/scan/services")
def scan_services():
    return jsonify(analyze_services())


@app.route("/api/update/<path:package_id>", methods=["POST"])
def do_update(package_id):
    return jsonify(update_package(package_id))


PORT = 47832
HOST = "127.0.0.1"


def _open_browser():
    time.sleep(1.4)
    webbrowser.open(f"http://{HOST}:{PORT}")


def _serve():
    """Sirve la app. Prefiere waitress; cae al servidor de Flask si no esta."""
    try:
        from waitress import serve
    except ImportError:
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)
        return
    # threads=8: el escaneo lanza varios modulos en paralelo desde el navegador.
    serve(app, host=HOST, port=PORT, threads=8, channel_timeout=900, ident="PC Guardian")


if __name__ == "__main__":
    if sys.platform == "win32":
        threading.Thread(target=_open_browser, daemon=True).start()
    _serve()
