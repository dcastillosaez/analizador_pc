import os
import sys
import threading
import time
import webbrowser

# Modo silencioso para escaneo al arrancar Windows (sin servidor Flask)
if "--silent" in sys.argv:
    from analyzer.notifications import run_silent_scan
    run_silent_scan()
    sys.exit(0)

from flask import Flask, jsonify, render_template, request

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
from analyzer.connections   import analyze_connections
from analyzer.processes     import get_top_processes, kill_process
from analyzer.history       import save_scan as hist_save, list_scans as hist_list, delete_scan as hist_delete
from analyzer.software      import get_installed_software, uninstall_software
from analyzer.quickfix      import set_energy_plan_high, disable_startup_item, disable_telemetry
from analyzer.dns           import analyze_dns, set_dns
from analyzer.firewall_rules import analyze_firewall_rules, delete_firewall_rule
from analyzer.perf_history  import record as perf_record, get_history as perf_get_history
from analyzer.benchmark     import run_benchmark, get_history as bench_get_history
from analyzer.diskmap       import scan_dir as diskmap_scan
from analyzer.duplicates    import find_duplicates, delete_files as dup_delete
from analyzer.notifications import (enable_startup, disable_startup,
                                    startup_status, send_toast)
from analyzer.hardening     import analyze_hardening
from analyzer.restore       import create_restore_point, restore_status
from analyzer.defaults      import analyze_defaults, open_default_apps_settings
from analyzer.bios          import analyze_bios
from analyzer.boot          import analyze_boot
from analyzer._version      import __version__, APP_NAME
from analyzer._shell        import is_admin, relaunch_as_admin

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
    """Cualquier excepción no capturada sale como JSON, no como página de error.

    Sin esto un fallo en un analyzer devuelve HTML y el frontend rompe al
    parsearlo, mostrando "Unexpected token '<'" en vez del problema real.
    """
    code = getattr(exc, "code", 500)
    if not isinstance(code, int):
        code = 500

    if request.path.startswith("/api/"):
        if code >= 500:          # los 404/405 no merecen traza
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
            "ok": False,
            "msg": str(exc)[:200],
        }), code

    return f"<h1>Error {code}</h1><p>{exc}</p>", code


@app.route("/api/status/admin")
def status_admin():
    """Varios módulos devuelven datos parciales sin elevación; el frontend avisa."""
    return jsonify({"admin": is_admin()})


@app.route("/api/admin/elevate", methods=["POST"])
def admin_elevate():
    """Relanza la app pidiendo elevación por UAC y cierra esta instancia."""
    if is_admin():
        return jsonify({"ok": False, "msg": "La aplicación ya se ejecuta como administrador."})
    if not relaunch_as_admin():
        return jsonify({"ok": False, "msg": "Windows rechazó la solicitud de elevación."})

    def _salir():
        time.sleep(1.0)          # margen para que la respuesta llegue al navegador
        os._exit(0)

    threading.Thread(target=_salir, daemon=True).start()
    return jsonify({"ok": True, "msg": "Reiniciando con permisos de administrador."})


@app.route("/api/scan/hardening")
def scan_hardening():
    return jsonify(analyze_hardening())


@app.route("/api/restore/status")
def restore_status_route():
    return jsonify(restore_status())


@app.route("/api/restore/create", methods=["POST"])
def restore_create_route():
    body = request.get_json(force=True, silent=True) or {}
    res = create_restore_point(body.get("description") or "PC Guardian - punto manual")
    return jsonify({"ok": res["success"], "msg": res["message"]})


def _punto_de_restauracion_si_procede(descripcion: str):
    """Crea un punto de restauración si el cliente lo pidió, sin bloquear nada.

    Best-effort a propósito: si la protección del sistema está apagada o falta
    elevación, la operación sigue adelante y se informa en la respuesta.
    """
    body = request.get_json(force=True, silent=True) or {}
    if not body.get("restore_point"):
        return None
    return create_restore_point(descripcion)


@app.route("/")
def index():
    bust = str(int(os.path.getmtime(os.path.join(_BASE, "static", "js", "app.js"))))
    return render_template("index.html", cache_bust=bust, app_version=__version__)


@app.route("/api/version")
def api_version():
    return jsonify({"name": APP_NAME, "version": __version__})


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
    restore = _punto_de_restauracion_si_procede(
        "PC Guardian - antes de desinstalar un controlador")
    result = uninstall_driver(body.get("device_id", ""))
    result["restore"] = restore
    return jsonify(result)

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

@app.route("/api/scan/connections")
def scan_connections():
    return jsonify(analyze_connections())

@app.route("/api/scan/processes")
def scan_processes():
    return jsonify(get_top_processes())

@app.route("/api/processes/<int:pid>/kill", methods=["POST"])
def do_kill_process(pid):
    return jsonify(kill_process(pid))

@app.route("/api/history/save", methods=["POST"])
def history_save():
    body  = request.get_json(force=True, silent=True) or {}
    score = int(body.get("score", 0))
    sid   = hist_save(score, body.get("results", {}))
    return jsonify({"ok": True, "id": sid})

@app.route("/api/history")
def history_get():
    return jsonify(hist_list())

@app.route("/api/history/<int:scan_id>", methods=["DELETE"])
def history_del(scan_id):
    hist_delete(scan_id)
    return jsonify({"ok": True})

@app.route("/api/scan/software")
def scan_software():
    return jsonify(get_installed_software())

@app.route("/api/software/uninstall", methods=["POST"])
def do_uninstall():
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(uninstall_software(body.get("name", "")))

@app.route("/api/scan/boot")
def scan_boot():
    return jsonify(analyze_boot())

@app.route("/api/scan/bios")
def scan_bios():
    return jsonify(analyze_bios())

@app.route("/api/scan/defaults")
def scan_defaults():
    return jsonify(analyze_defaults())

@app.route("/api/defaults/open-settings", methods=["POST"])
def defaults_open_settings():
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(open_default_apps_settings(body.get("app", "")))

@app.route("/api/quickfix/energy-high", methods=["POST"])
def qf_energy():
    return jsonify(set_energy_plan_high())

@app.route("/api/quickfix/disable-startup", methods=["POST"])
def qf_disable_startup():
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(disable_startup_item(
        body.get("hive", ""),
        body.get("key", ""),
        body.get("name", ""),
    ))

@app.route("/api/quickfix/telemetry-off", methods=["POST"])
def qf_telemetry():
    return jsonify(disable_telemetry())

@app.route("/api/scan/dns")
def scan_dns():
    return jsonify(analyze_dns())

@app.route("/api/dns/set", methods=["POST"])
def dns_set():
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(set_dns(body.get("interface", ""), body.get("dns1", ""), body.get("dns2", "")))

@app.route("/api/scan/firewall-rules")
def scan_firewall_rules():
    return jsonify(analyze_firewall_rules())

@app.route("/api/firewall-rules/delete", methods=["POST"])
def do_delete_fw_rule():
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(delete_firewall_rule(body.get("name", "")))

@app.route("/api/perf/history")
def perf_history_get():
    return jsonify(perf_get_history())

@app.route("/api/benchmark/run", methods=["POST"])
def benchmark_run():
    return jsonify(run_benchmark())

@app.route("/api/benchmark/history")
def benchmark_history():
    return jsonify(bench_get_history())

@app.route("/api/diskmap/scan", methods=["POST"])
def do_diskmap():
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(diskmap_scan(body.get("path", "")))

@app.route("/api/duplicates/scan", methods=["POST"])
def do_dup_scan():
    body = request.get_json(force=True, silent=True) or {}
    return jsonify(find_duplicates(body.get("path", "")))

@app.route("/api/duplicates/delete", methods=["POST"])
def do_dup_delete():
    body  = request.get_json(force=True, silent=True) or {}
    paths = body.get("paths", [])
    if not isinstance(paths, list):
        return jsonify({"ok": False, "msg": "Se esperaba una lista de rutas."})
    return jsonify(dup_delete(paths))

@app.route("/api/notifications/status")
def notif_status():
    return jsonify({"enabled": startup_status()})

@app.route("/api/notifications/enable", methods=["POST"])
def notif_enable():
    return jsonify(enable_startup())

@app.route("/api/notifications/disable", methods=["POST"])
def notif_disable():
    return jsonify(disable_startup())

@app.route("/api/notifications/test", methods=["POST"])
def notif_test():
    send_toast("PC Guardian — Prueba", "Las notificaciones están funcionando correctamente.")
    return jsonify({"ok": True, "msg": "Notificación de prueba enviada."})


@app.route("/api/update/<path:package_id>", methods=["POST"])
def do_update(package_id):
    return jsonify(update_package(package_id))


def _open_browser():
    time.sleep(1.4)
    webbrowser.open("http://127.0.0.1:8765")


def _perf_recorder():
    while True:
        time.sleep(300)  # cada 5 minutos
        try:
            snap = perf_snapshot()
            gpu_pct = None
            if snap.get("gpu"):
                gpu_pct = snap["gpu"].get("percent")
            perf_record(
                snap["cpu"]["percent"],
                snap["ram"]["percent"],
                snap["disk"]["percent"],
                gpu_pct,
            )
        except Exception:
            pass


def _serve():
    """Sirve la app. Prefiere waitress; cae al servidor de Flask si no está.

    El servidor de desarrollo de Flask no está pensado para uso continuado y
    encaja mal con las peticiones simultáneas del escaneo.
    """
    try:
        from waitress import serve
    except ImportError:
        app.run(host="127.0.0.1", port=8765, debug=False, use_reloader=False, threaded=True)
        return
    serve(app, host="127.0.0.1", port=8765, threads=8,
          channel_timeout=900, ident="PC Guardian")


if __name__ == "__main__":
    if sys.platform == "win32":
        threading.Thread(target=_open_browser,  daemon=True).start()
        threading.Thread(target=_perf_recorder, daemon=True).start()
    _serve()
