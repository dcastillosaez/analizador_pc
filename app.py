import os
import sys
import threading
import time
import webbrowser

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

if getattr(sys, "frozen", False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(_BASE, "templates"),
    static_folder=os.path.join(_BASE, "static"),
)


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


if __name__ == "__main__":
    if sys.platform == "win32":
        threading.Thread(target=_open_browser,  daemon=True).start()
        threading.Thread(target=_perf_recorder, daemon=True).start()
    app.run(debug=False, port=8765, use_reloader=False)
