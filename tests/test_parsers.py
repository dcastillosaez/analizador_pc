"""Tests de los parsers de salida de herramientas de Windows.

Son la parte más frágil del proyecto: dependen del idioma del sistema, del
ancho de columna y de la codificación. Aquí se prueban contra salidas fijadas,
sin tocar el sistema real, así que corren en cualquier máquina.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer import _shell, _smbios, _text, _version, bios, boot, defaults, maintenance, network, services, updates, wifi  # noqa: E402
from analyzer.certs import _common_name  # noqa: E402


# ── Decodificación de salida ──────────────────────────────────────────────────

class TestDecode:
    def test_utf8(self):
        assert _shell._decode("energía".encode("utf-8")) == "energía"

    def test_pagina_oem(self):
        # powercfg y netsh emiten en cp850/cp437, no en UTF-8.
        assert _shell._decode("energía".encode("cp850")) == "energía"

    def test_prefiere_oem_sobre_cp1252(self):
        # cp850 y cp1252 decodifican los mismos bytes de forma distinta y no hay
        # manera de distinguirlos: se elige OEM porque es lo que emiten las
        # herramientas de consola de Windows (winget, netsh, powercfg).
        assert _shell._decode("Señal".encode("cp850")) == "Señal"

    def test_vacio(self):
        assert _shell._decode(b"") == ""

    def test_bytes_invalidos_no_lanzan(self):
        assert isinstance(_shell._decode(b"\xff\xfe\x00\x01"), str)


class TestShellResult:
    def test_ok(self):
        assert _shell.ShellResult(returncode=0).ok

    def test_no_ok_con_timeout(self):
        assert not _shell.ShellResult(returncode=0, timed_out=True).ok

    @pytest.mark.parametrize("res", [
        _shell.ShellResult(returncode=740),
        _shell.ShellResult(returncode=1, stderr="Acceso denegado"),
        _shell.ShellResult(returncode=1, stdout="Error 0x80070005"),
        _shell.ShellResult(returncode=1, stderr="requires elevation"),
    ])
    def test_detecta_falta_de_privilegios(self, res):
        assert res.needs_admin

    def test_fallo_normal_no_es_de_privilegios(self):
        assert not _shell.ShellResult(returncode=1, stderr="no such device").needs_admin


# ── winget upgrade ────────────────────────────────────────────────────────────

WINGET_ES = """\
Nombre                         Id                      Versión      Disponible   Origen
-------------------------------------------------------------------------------------
7-Zip 23.01 (x64)              7zip.7zip               23.01        24.09        winget
Google Chrome                  Google.Chrome           131.0.6778   132.0.6834   winget
Visual Studio Code             Microsoft.VSCode        1.96.0       1.96.2       winget
3 actualizaciones disponibles.
"""

WINGET_EN = """\
Name                           Id                      Version      Available    Source
-------------------------------------------------------------------------------------
7-Zip 23.01 (x64)              7zip.7zip               23.01        24.09        winget
Google Chrome                  Google.Chrome           131.0.6778   132.0.6834   winget
2 upgrades available.
"""


class TestWingetParser:
    def test_encabezados_en_espanol(self):
        pkgs = updates._parse_upgrade_list(WINGET_ES)
        assert [p["id"] for p in pkgs] == ["7zip.7zip", "Google.Chrome", "Microsoft.VSCode"]

    def test_encabezados_en_ingles(self):
        pkgs = updates._parse_upgrade_list(WINGET_EN)
        assert [p["id"] for p in pkgs] == ["7zip.7zip", "Google.Chrome"]

    def test_extrae_versiones(self):
        chrome = next(p for p in updates._parse_upgrade_list(WINGET_ES) if p["id"] == "Google.Chrome")
        assert chrome["version"] == "131.0.6778"
        assert chrome["available"] == "132.0.6834"
        assert chrome["name"] == "Google Chrome"

    def test_descarta_la_linea_de_resumen(self):
        # "3 actualizaciones disponibles." no debe colarse como paquete.
        assert all("actualizaciones" not in p["name"] for p in updates._parse_upgrade_list(WINGET_ES))

    def test_salida_vacia(self):
        assert updates._parse_upgrade_list("") == []

    def test_sin_cabecera_reconocible(self):
        assert updates._parse_upgrade_list("algo\nque no es\nuna tabla") == []

    def test_no_lanza_con_lineas_truncadas(self):
        truncado = WINGET_ES.replace("23.01        24.09        winget", "23.01")
        updates._parse_upgrade_list(truncado)  # no debe lanzar


class TestWingetRunner:
    def test_marca_winget_ausente(self, monkeypatch):
        monkeypatch.setattr(updates, "run", lambda *a, **k: _shell.ShellResult(not_found=True))
        assert updates._run_winget(["list"]) == "__NO_WINGET__"

    def test_marca_timeout(self, monkeypatch):
        monkeypatch.setattr(updates, "run", lambda *a, **k: _shell.ShellResult(timed_out=True))
        assert updates._run_winget(["list"]) == "__TIMEOUT__"


# ── netsh wlan show networks ──────────────────────────────────────────────────

NETSH_ES = """
Interfaz  Wi-Fi : 3 redes visibles actualmente.

SSID 1 : MiRedCasa
    Tipo de red            : Infraestructura
    Autenticación          : WPA2-Personal
    Cifrado                : CCMP
    BSSID 1                 : aa:bb:cc:dd:ee:ff
         Señal              : 92%
         Tipo de radio      : 802.11ac
         Canal              : 36
    BSSID 2                 : aa:bb:cc:dd:ee:00
         Señal              : 61%
         Tipo de radio      : 802.11n
         Canal              : 6

SSID 2 : VecinoWiFi
    Tipo de red            : Infraestructura
    Autenticación          : WPA3-Personal
    Cifrado                : CCMP
    BSSID 1                 : 11:22:33:44:55:66
         Señal              : 38%
         Tipo de radio      : 802.11n
         Canal              : 11
"""


class TestWifiParser:
    def test_cuenta_los_bssid_no_los_ssid(self):
        assert len(wifi._parse_networks(NETSH_ES)) == 3

    def test_extrae_campos(self):
        red = wifi._parse_networks(NETSH_ES)[0]
        assert red["ssid"] == "MiRedCasa"
        assert red["bssid"] == "aa:bb:cc:dd:ee:ff"
        assert red["signal"] == 92
        assert red["channel"] == 36
        assert red["auth"] == "WPA2-Personal"

    def test_infiere_la_banda_por_canal(self):
        redes = wifi._parse_networks(NETSH_ES)
        assert redes[0]["band"] == "5 GHz"    # canal 36
        assert redes[1]["band"] == "2.4 GHz"  # canal 6

    def test_salida_vacia(self):
        assert wifi._parse_networks("") == []

    @pytest.mark.parametrize("raw,esperado", [("92%", 92), ("100%", 100), ("", 0), ("basura", 0)])
    def test_signal_pct(self, raw, esperado):
        assert wifi._signal_pct(raw) == esperado

    def test_canales_24ghz_solapan_a_menos_de_5(self):
        assert wifi._channels_collide_24(1, 3)
        assert not wifi._channels_collide_24(1, 6)

    def test_canales_5ghz_solo_colisionan_si_son_el_mismo(self):
        assert wifi._channels_collide_5(36, 36)
        assert not wifi._channels_collide_5(36, 40)


# ── schtasks ──────────────────────────────────────────────────────────────────

class TestSchtasksParser:
    def test_detecta_tarea_en_ruta_sospechosa(self):
        lineas = ['"\\MiTarea","C:\\Users\\dave\\AppData\\Local\\Temp\\x.exe","Listo"']
        items = maintenance._check_schtasks(lineas)
        assert items[0]["status"] == "danger"
        assert "MiTarea" in items[0]["name"]

    def test_tareas_normales_no_alertan(self):
        lineas = ['"\\Microsoft\\Windows\\Defrag\\ScheduledDefrag","C:\\Windows\\System32\\defrag.exe","Listo"']
        assert maintenance._check_schtasks(lineas)[0]["status"] == "ok"

    def test_lineas_malformadas_no_rompen(self):
        assert maintenance._check_schtasks(['"solo-un-campo"', "", "sin comillas"])

    def test_sin_tareas(self):
        assert maintenance._check_schtasks([])[0]["status"] == "ok"


# ── Servicios ─────────────────────────────────────────────────────────────────

class TestServicePaths:
    @pytest.mark.parametrize("path", [
        r"C:\Windows\System32\svchost.exe -k netsvcs",
        r'"C:\Program Files\App\service.exe"',
        "",
    ])
    def test_rutas_estandar(self, path):
        assert services._is_standard_path(path)

    @pytest.mark.parametrize("path", [
        r"C:\Users\dave\AppData\Local\Temp\raro.exe",
        r"D:\descargas\algo.exe",
    ])
    def test_rutas_fuera_de_lo_habitual(self, path):
        assert not services._is_standard_path(path)

    @pytest.mark.parametrize("name", [
        "xQ7zK9pLm2Wv", "kJ8mNp2LqRt7", "zxcvbnmqwrt", "wdfghjklzxcv",
    ])
    def test_nombre_generado_al_azar(self, name):
        assert services._is_suspicious_name(name)

    @pytest.mark.parametrize("name", [
        "Spooler", "LanmanWorkstation", "AudioEndpointBuilder",
        "SystemEventsBroker", "CoreMessagingRegistrar", "BrokerInfrastructure",
    ])
    def test_servicio_legitimo_no_es_sospechoso(self, name):
        assert not services._is_suspicious_name(name)


class TestHeuristicaDeNombres:
    """Los umbrales estan calibrados; si alguien los toca, esto salta."""

    def test_nombre_corto_nunca_se_marca(self):
        # Un nombre de 7 caracteres no da senal estadistica suficiente.
        assert not _text.looks_random("xQ7zK9p")

    def test_las_vocales_son_la_senal_que_separa(self):
        # Misma longitud y entropia parecida; solo cambian las vocales.
        assert _text.looks_random("wdfghjklzxcv")
        assert not _text.looks_random("aeioumaneras")

    def test_entropia_de_cadena_uniforme_es_cero(self):
        assert _text.shannon_entropy("aaaaaa") == 0.0

    def test_entropia_maxima_con_caracteres_distintos(self):
        assert _text.shannon_entropy("abcd") == pytest.approx(2.0)

    def test_entropia_de_cadena_vacia(self):
        assert _text.shannon_entropy("") == 0.0

    @pytest.mark.parametrize("text,esperado", [
        ("aeiou", 1.0), ("bcdfg", 0.0), ("", 0.0), ("casa", 0.5),
    ])
    def test_vowel_ratio(self, text, esperado):
        assert _text.vowel_ratio(text) == pytest.approx(esperado)


# ── Certificados ──────────────────────────────────────────────────────────────

class TestCommonName:
    def test_extrae_cn(self):
        assert _common_name("CN=DigiCert Root, O=DigiCert Inc, C=US") == "DigiCert Root"

    def test_cn_no_es_el_primer_campo(self):
        assert _common_name("O=Contoso, CN=Contoso CA, C=ES") == "Contoso CA"

    def test_sin_cn_devuelve_el_subject(self):
        assert _common_name("O=Contoso, C=ES") == "O=Contoso, C=ES"


# ── Conexiones salientes ──────────────────────────────────────────────────────

from analyzer import connections  # noqa: E402


class TestConexiones:
    @pytest.mark.parametrize("ip,esperado", [
        ("192.168.1.10", True), ("127.0.0.1", True), ("10.0.0.5", True),
        ("172.16.4.1", True), ("169.254.1.1", True), ("fe80::1", True),
        ("8.8.8.8", False), ("2606:4700::1111", False), ("no-es-una-ip", False),
    ])
    def test_distingue_la_red_local_de_internet(self, ip, esperado):
        assert connections._is_private(ip) is esperado

    def test_resolucion_fallida_devuelve_la_ip(self):
        # 192.0.2.1 es de la red reservada para documentación: nunca resuelve.
        assert connections._resolve("192.0.2.1") == "192.0.2.1"

    def test_proceso_sin_pid(self):
        assert connections._proc_name(None) == "desconocido"

    def test_proceso_inexistente(self):
        assert connections._proc_name(999_999_999) == "desconocido"

    def test_los_puertos_de_c2_conocidos_estan_cubiertos(self):
        # Metasploit (4444), IRC de botnets (6667) y Tor (9001/9030).
        assert {4444, 6667, 9001, 9030}.issubset(connections._SUSPICIOUS_PORTS)

    def test_los_puertos_web_no_son_sospechosos(self):
        assert not (connections._SAFE_PORTS & connections._SUSPICIOUS_PORTS)

    def test_etiqueta_de_puerto_conocido(self):
        assert "443" in connections._port_label(443) or connections._port_label(443)


# ── Procesos ──────────────────────────────────────────────────────────────────

from analyzer import processes  # noqa: E402


class TestProcesos:
    def test_no_se_puede_terminar_el_nucleo(self):
        # PID 0 y 4 son el kernel de Windows.
        assert processes.kill_process(4)["ok"] is False
        assert processes.kill_process(0)["ok"] is False

    def test_proceso_inexistente(self):
        res = processes.kill_process(999_999_999)
        assert res["ok"] is False and "ya no existe" in res["msg"]

    def test_los_criticos_no_se_ofrecen_como_terminables(self):
        criticos = {"lsass.exe", "csrss.exe", "services.exe", "smss.exe", "wininit.exe"}
        assert criticos.issubset(processes._SYSTEM_PROCS)

    def test_el_listado_marca_killable(self):
        datos = processes.get_top_processes()
        assert datos["title"] == "Procesos activos"
        for item in datos["items"]:
            assert "killable" in item and "pid" in item
            if item["name"] in processes._SYSTEM_PROCS:
                assert item["killable"] is False


# ── Firmas y protecciones de plataforma ───────────────────────────────────────

from analyzer import hardening, signatures  # noqa: E402


class TestFirmas:
    def test_extrae_el_editor_del_certificado(self):
        subject = "CN=Microsoft Windows, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"
        assert signatures._common_name(subject) == "Microsoft Windows"

    def test_subject_sin_cn(self):
        assert signatures._common_name("O=Contoso, C=ES") == "O=Contoso, C=ES"

    def test_las_rutas_con_comilla_se_escapan(self):
        # Una comilla simple sin escapar rompería el array de PowerShell.
        script = signatures._script([r"C:\o'brien\app.exe"])
        assert "o''brien" in script

    @pytest.mark.parametrize("estado,fragmento", [
        ("Valid", "Firmado por"),
        ("NotSigned", "No tiene firma"),
        ("HashMismatch", "modificado"),
    ])
    def test_mensajes_legibles(self, estado, fragmento):
        texto = signatures.describe({"status": estado, "signer": "Acme SL"})
        assert fragmento in texto

    def test_sin_informacion(self):
        assert "No se pudo" in signatures.describe({})


class TestProteccionesDePlataforma:
    def test_secure_boot_desactivado_es_aviso(self):
        assert hardening._check_secure_boot({"SecureBoot": False})["status"] == "warning"

    def test_secure_boot_activo(self):
        assert hardening._check_secure_boot({"SecureBoot": True})["status"] == "ok"

    def test_secure_boot_no_consultable_no_es_error(self):
        # En equipos con BIOS heredada la consulta simplemente no responde.
        assert hardening._check_secure_boot({"SecureBoot": None})["status"] == "warning"

    def test_disco_sin_cifrar(self):
        r = hardening._check_bitlocker({"BitLockerStatus": "Off", "BitLockerMount": "C:"})
        assert r["status"] == "warning" and "no está cifrada" in r["message"]

    def test_disco_cifrado(self):
        r = hardening._check_bitlocker({"BitLockerStatus": "On", "BitLockerMount": "C:", "BitLockerPct": 100})
        assert r["status"] == "ok" and r["value"] == "Cifrado 100%"

    def test_defender_apagado_es_critico(self):
        items = hardening._check_defender({"RealTimeProtection": False})
        assert items[0]["status"] == "danger"

    @pytest.mark.parametrize("cfa,esperado", [(1, "ok"), (2, "warning"), (0, "warning")])
    def test_proteccion_contra_ransomware(self, cfa, esperado):
        items = hardening._check_defender({"RealTimeProtection": True, "ControlledFolderAccess": cfa})
        ransomware = next(i for i in items if "ransomware" in i["name"])
        assert ransomware["status"] == esperado

    def test_definiciones_antiguas(self):
        items = hardening._check_defender({"RealTimeProtection": True, "AntivirusSignatureAge": 30})
        defs = next(i for i in items if "Definiciones" in i["name"])
        assert defs["status"] == "warning" and "30 días" in defs["message"]

    def test_tpm_ausente(self):
        assert hardening._check_tpm({"TpmPresent": False})["value"] == "Ausente"

    def test_tpm_presente_sin_inicializar(self):
        r = hardening._check_tpm({"TpmPresent": True, "TpmReady": False})
        assert r["status"] == "warning" and r["value"] == "Sin inicializar"


# ── Puntos de restauración ────────────────────────────────────────────────────

from analyzer import restore  # noqa: E402


class TestPuntosDeRestauracion:
    def test_la_descripcion_no_puede_romper_el_script(self):
        # Va dentro de comillas simples de PowerShell.
        assert "'" not in restore._clean("un 'punto' raro")

    def test_la_descripcion_se_recorta(self):
        assert len(restore._clean("x" * 500)) == 200

    def test_descripcion_vacia_tiene_respaldo(self):
        assert restore._clean("") == "Punto de PC Guardian"

    def test_sin_saltos_de_linea(self):
        limpio = restore._clean("linea1\nlinea2\rlinea3")
        assert "\n" not in limpio and "\r" not in limpio

    def test_falta_de_permisos_se_reconoce(self, monkeypatch):
        from analyzer import _shell
        monkeypatch.setattr(restore, "run_ps",
                            lambda *a, **k: _shell.ShellResult(returncode=1, stdout="ERR=Access is denied"))
        res = restore.create_restore_point("prueba")
        assert res["success"] is False and "administrador" in res["message"]

    def test_proteccion_desactivada_se_reconoce(self, monkeypatch):
        from analyzer import _shell
        monkeypatch.setattr(restore, "run_ps",
                            lambda *a, **k: _shell.ShellResult(returncode=1, stdout="ERR=System Restore is disabled"))
        res = restore.create_restore_point("prueba")
        assert "protección del sistema está desactivada" in res["message"]

    def test_creacion_correcta(self, monkeypatch):
        from analyzer import _shell
        monkeypatch.setattr(restore, "run_ps", lambda *a, **k: _shell.ShellResult(returncode=0, stdout="OK"))
        assert restore.create_restore_point("prueba")["success"] is True


class TestResolucionDeConexiones:
    """La resolución inversa es un adorno: no puede tumbar el módulo."""

    def test_una_ip_que_no_resuelve_se_devuelve_tal_cual(self):
        # 192.0.2.1 pertenece a la red reservada para documentación (RFC 5737).
        assert connections._resolve("192.0.2.1") == "192.0.2.1"

    def test_el_timeout_de_socket_se_restaura(self):
        import socket
        previo = socket.getdefaulttimeout()
        connections._resolve("192.0.2.1")
        assert socket.getdefaulttimeout() == previo

    def test_el_modulo_sobrevive_a_una_resolucion_lenta(self, monkeypatch):
        import time
        monkeypatch.setattr(connections, "_resolve",
                            lambda ip: (time.sleep(6), ip)[1])
        datos = connections.analyze_connections()
        assert datos["title"] == "Conexiones salientes"
        assert datos["status"] in ("ok", "warning", "danger")


# ── Ubicación de las bases de datos ───────────────────────────────────────────

from analyzer import _storage  # noqa: E402


class TestUbicacionDeDatos:
    """Las bases viven en el perfil del usuario, no junto al código.

    Junto al código fallaban en los dos escenarios reales: instaladas bajo
    Program Files (carpeta de solo lectura) y compiladas con PyInstaller, donde
    __file__ apunta a una carpeta temporal que Windows borra al cerrar.
    """

    def test_la_carpeta_de_datos_existe_y_es_escribible(self):
        carpeta = _storage.data_dir()
        assert carpeta.is_dir()
        prueba = carpeta / ".escritura_test"
        prueba.write_text("ok", encoding="utf-8")
        assert prueba.read_text(encoding="utf-8") == "ok"
        prueba.unlink()

    def test_la_ruta_queda_fuera_del_proyecto(self):
        proyecto = Path(_storage.__file__).resolve().parent.parent
        assert proyecto not in Path(_storage.db_path("history.db")).resolve().parents

    def test_migra_la_base_antigua_conservando_los_datos(self, tmp_path, monkeypatch):
        import sqlite3

        antigua = tmp_path / "proyecto" / "vieja.db"
        antigua.parent.mkdir()
        con = sqlite3.connect(antigua)
        con.execute("CREATE TABLE t (v TEXT)")
        con.execute("INSERT INTO t VALUES ('dato importante')")
        con.commit()
        con.close()

        destino_dir = tmp_path / "appdata"
        destino_dir.mkdir()
        monkeypatch.setattr(_storage, "data_dir", lambda: destino_dir)
        monkeypatch.setattr(_storage, "_rutas_antiguas", lambda nombre: [antigua])

        ruta = _storage.db_path("vieja.db")

        assert not antigua.exists()                    # se movió, no se copió
        assert Path(ruta).parent == destino_dir
        con = sqlite3.connect(ruta)
        assert con.execute("SELECT v FROM t").fetchone()[0] == "dato importante"
        con.close()

    def test_no_pisa_una_base_que_ya_existe_en_el_destino(self, tmp_path, monkeypatch):
        antigua = tmp_path / "vieja.db"
        antigua.write_text("origen", encoding="utf-8")
        destino_dir = tmp_path / "appdata"
        destino_dir.mkdir()
        (destino_dir / "vieja.db").write_text("destino", encoding="utf-8")

        monkeypatch.setattr(_storage, "data_dir", lambda: destino_dir)
        monkeypatch.setattr(_storage, "_rutas_antiguas", lambda nombre: [antigua])

        ruta = _storage.db_path("vieja.db")
        assert Path(ruta).read_text(encoding="utf-8") == "destino"
        assert antigua.exists()                        # la antigua no se toca

    def test_sin_base_antigua_no_falla(self, tmp_path, monkeypatch):
        destino_dir = tmp_path / "appdata"
        destino_dir.mkdir()
        monkeypatch.setattr(_storage, "data_dir", lambda: destino_dir)
        monkeypatch.setattr(_storage, "_rutas_antiguas", lambda nombre: [tmp_path / "no_existe.db"])
        assert _storage.db_path("nueva.db") == str(destino_dir / "nueva.db")


# ── Clasificación de puertos en escucha ───────────────────────────────────────

def _e(ip, port, proc="algo.exe", pid=1234):
    return {"ip": ip, "port": port, "pid": pid, "proc": proc}


class TestClasificarPuertos:
    def test_loopback_no_es_aviso(self):
        items = network._classify_ports([_e("127.0.0.1", 8765, "PCGuardian.exe")])
        assert all(i["status"] == "ok" for i in items)

    def test_loopback_ipv6_tampoco(self):
        items = network._classify_ports([_e("::1", 7679, "GoogleDriveFS.exe")])
        assert all(i["status"] == "ok" for i in items)

    def test_loopback_se_resume_en_un_solo_item(self):
        entries = [_e("127.0.0.1", p) for p in (5396, 6327, 13031, 22112)]
        items = network._classify_ports(entries)
        assert len(items) == 1
        assert "4" in items[0]["value"]

    def test_escucha_en_todas_las_interfaces_es_aviso(self):
        items = network._classify_ports([_e("0.0.0.0", 4444, "raro.exe")])
        avisos = [i for i in items if i["status"] == "warning"]
        assert len(avisos) == 1
        assert "4444" in avisos[0]["name"]

    def test_ip_de_lan_tambien_es_aviso(self):
        items = network._classify_ports([_e("192.168.1.50", 4444)])
        assert any(i["status"] == "warning" for i in items)

    def test_puerto_seguro_expuesto_no_avisa(self):
        items = network._classify_ports([_e("0.0.0.0", 443, "svchost.exe")])
        assert all(i["status"] == "ok" for i in items)

    def test_puerto_efimero_expuesto_no_avisa(self):
        items = network._classify_ports([_e("0.0.0.0", 51000)])
        assert all(i["status"] == "ok" for i in items)

    def test_sin_nada_en_escucha_devuelve_ok(self):
        items = network._classify_ports([])
        assert len(items) == 1 and items[0]["status"] == "ok"

    def test_mezcla_separa_loopback_de_expuesto(self):
        items = network._classify_ports([
            _e("127.0.0.1", 8765, "PCGuardian.exe"),
            _e("0.0.0.0", 4444, "raro.exe"),
        ])
        avisos = [i for i in items if i["status"] == "warning"]
        assert len(avisos) == 1 and "4444" in avisos[0]["name"]
        assert any(i["status"] == "ok" and "local" in i["name"].lower() for i in items)

    def test_el_aviso_no_dice_conexiones_externas_de_un_loopback(self):
        items = network._classify_ports([_e("127.0.0.1", 6327, "SteelSeriesGGEZ.exe")])
        assert "externas" not in items[0]["message"].lower()

    def test_tope_de_ocho_avisos(self):
        entries = [_e("0.0.0.0", 4000 + i) for i in range(12)]
        avisos = [i for i in network._classify_ports(entries) if i["status"] == "warning"]
        assert len(avisos) == 8

    def test_mismo_puerto_en_ipv4_e_ipv6_es_un_solo_aviso(self):
        items = network._classify_ports([
            _e("0.0.0.0", 3354, "node.exe"),
            _e("::", 3354, "node.exe"),
        ])
        avisos = [i for i in items if i["status"] == "warning"]
        assert len(avisos) == 1

    def test_mismo_puerto_distinto_proceso_son_dos_avisos(self):
        items = network._classify_ports([
            _e("0.0.0.0", 3354, "node.exe"),
            _e("0.0.0.0", 3354, "otro.exe"),
        ])
        assert len([i for i in items if i["status"] == "warning"]) == 2

    def test_netbios_y_wsd_son_estandar_de_windows(self):
        items = network._classify_ports([_e("0.0.0.0", 139), _e("::", 5357)])
        assert all(i["status"] == "ok" for i in items)


# ── Aplicaciones predeterminadas ──────────────────────────────────────────────

class TestExeDelComando:
    def test_ruta_entre_comillas_con_espacios(self):
        cmd = r'"C:\Program Files\Google\Chrome\chrome.exe" --single-argument %1'
        assert defaults._exe_from_command(cmd) == r"C:\Program Files\Google\Chrome\chrome.exe"

    def test_ruta_sin_comillas(self):
        assert defaults._exe_from_command(r"C:\Windows\notepad.exe %1") == r"C:\Windows\notepad.exe"

    def test_variables_de_entorno_se_expanden(self):
        exe = defaults._exe_from_command(r'"%SystemRoot%\system32\notepad.exe" %1')
        assert exe.lower().endswith("notepad.exe") and "%SystemRoot%" not in exe

    def test_comando_vacio(self):
        assert defaults._exe_from_command("") == ""

    def test_rundll32_conserva_el_ejecutable(self):
        cmd = r'"C:\Windows\system32\rundll32.exe" shell32.dll,OpenAs_RunDLL %1'
        assert defaults._exe_from_command(cmd).lower().endswith("rundll32.exe")


class TestNombreLegible:
    def test_usa_el_nombre_del_ejecutable(self):
        assert defaults._friendly_name("LoQueSea", r"C:\x\slack.exe") == "Slack"

    def test_progid_conocido_gana_al_ejecutable(self):
        assert defaults._friendly_name("Acrobat.Document.DC", r"C:\x\acrobat.exe") == "Adobe Acrobat"

    def test_sin_ejecutable_cae_al_progid(self):
        assert defaults._friendly_name("AppX4hxtad77", "") == "AppX4hxtad77"

    def test_sin_nada_devuelve_marcador(self):
        assert defaults._friendly_name("", "") == "Sin asignar"


class TestEvaluarAsociacion:
    def test_programa_normal_es_ok(self):
        assert defaults._evaluate("ChromeHTML", r"C:\Program Files\Google\chrome.exe")[0] == "ok"

    def test_sin_asociacion_avisa(self):
        assert defaults._evaluate("", "")[0] == "warning"

    def test_ejecutable_en_temp_es_peligroso(self):
        assert defaults._evaluate("Raro", r"C:\Users\x\AppData\Local\Temp\raro.exe")[0] == "danger"

    def test_ejecutable_en_descargas_es_peligroso(self):
        assert defaults._evaluate("Raro", r"C:\Users\x\Downloads\instalador.exe")[0] == "danger"

    def test_appx_del_store_sin_ruta_es_ok(self):
        assert defaults._evaluate("AppXd4nrz8ff68srnhf9t5a8sbjyar1cr723", "")[0] == "ok"

    def test_programa_instalado_en_appdata_es_ok(self):
        assert defaults._evaluate("Slack", r"C:\Users\x\AppData\Local\slack\slack.exe")[0] == "ok"


    def test_progid_que_no_resuelve_a_ninguna_app_avisa(self):
        st, motivo = defaults._evaluate("AppXydk58wgm44se4b399557yyyj1w7mbmvd", "", resuelto=False)
        assert st == "warning" and "registrada" in motivo.lower()

    def test_progid_que_si_resuelve_no_avisa(self):
        assert defaults._evaluate("AppXalgo", "", resuelto=True)[0] == "ok"


class TestUriDeAjustes:
    def test_sin_app_abre_la_pagina_general(self):
        assert defaults._settings_uri("") == "ms-settings:defaultapps"

    def test_con_app_apunta_a_su_ficha(self):
        assert defaults._settings_uri("Firefox") == "ms-settings:defaultapps?registeredAppUser=Firefox"

    def test_escapa_espacios(self):
        uri = defaults._settings_uri("Adobe Acrobat")
        assert " " not in uri and uri.endswith("Adobe%20Acrobat")

    def test_no_permite_arrastrar_parametros_extra(self):
        uri = defaults._settings_uri("x&cmd=calc.exe")
        assert uri.startswith("ms-settings:defaultapps?registeredAppUser=") and "&" not in uri


class TestNombreDeAppDelStore:
    def test_extrae_el_paquete_del_aumid(self):
        assert defaults._package_display("Microsoft.Windows.Photos_8wekyb3d8bbwe!App") == "Fotos"

    def test_paquete_desconocido_pierde_el_prefijo_y_el_hash(self):
        assert defaults._package_display("Contoso.SuperEditor_abcd1234!App") == "SuperEditor"

    def test_paquete_de_microsoft_desconocido(self):
        assert defaults._package_display("Microsoft.CosaRara_8wekyb3d8bbwe!App") == "CosaRara"

    def test_cadena_vacia(self):
        assert defaults._package_display("") == ""

    def test_recurso_indirecto_no_resuelto_no_se_muestra_crudo(self):
        crudo = "@{Microsoft.Windows.Photos_2026.1_x64__8wekyb3d8bbwe?ms-resource://X/Y}"
        assert defaults._clean_resource_string(crudo) == ""

    def test_nombre_normal_se_respeta(self):
        assert defaults._clean_resource_string("Fotos") == "Fotos"


class TestAsociacionHuerfana:
    def test_progid_muerto_no_muestra_el_hash_como_aplicacion(self, monkeypatch):
        monkeypatch.setattr(defaults, "_read_command", lambda progid: "")
        monkeypatch.setattr(defaults, "_appx_name", lambda progid: "")
        item = defaults._asociacion("Enlaces de correo", "AppXydk58wgm44se4b399557yyyj1w7mbmvd")
        assert item["status"] == "warning"
        assert item["value"] == "Sin aplicación válida"
        assert item["app"] == ""          # el botón abre la página general
        assert "AppXydk58" in item["detail"]   # el ProgId sigue visible como dato técnico


# ── Parser SMBIOS ─────────────────────────────────────────────────────────────

def _estructura(tipo, handle, campos, cadenas):
    """Construye una entrada SMBIOS: cabecera + campos + área de texto."""
    cuerpo = bytes([tipo, 4 + len(campos)]) + handle.to_bytes(2, "little") + bytes(campos)
    if cadenas:
        texto = b"".join(c.encode("latin-1") + bytes([0]) for c in cadenas) + bytes([0])
    else:
        texto = bytes([0, 0])
    return cuerpo + texto


class TestParserSmbios:
    def test_lee_una_estructura_con_cadenas(self):
        data = _estructura(0, 1, [0x01, 0x02], ["AMI", "0903"])
        t = _smbios.parse_tables(data)
        assert t[0][0].texto(4) == "AMI"
        assert t[0][0].texto(5) == "0903"

    def test_una_estructura_sin_cadenas_no_rompe_el_recorrido(self):
        # el fallo clásico: saltar un solo nulo desincroniza y se pierde el resto
        data = _estructura(4, 1, [0, 0]) if False else (
            _estructura(4, 1, [0, 0], []) + _estructura(17, 2, [0x01], ["Corsair"]))
        t = _smbios.parse_tables(data)
        assert 4 in t and 17 in t
        assert t[17][0].texto(4) == "Corsair"

    def test_varias_del_mismo_tipo_se_agrupan(self):
        data = (_estructura(17, 1, [0x01], ["A"]) +
                _estructura(17, 2, [0x01], ["B"]))
        t = _smbios.parse_tables(data)
        assert [e.texto(4) for e in t[17]] == ["A", "B"]

    def test_para_en_la_marca_de_fin(self):
        data = (_estructura(0, 1, [0x01], ["AMI"]) +
                _estructura(127, 2, [], []) +
                _estructura(17, 3, [0x01], ["fantasma"]))
        t = _smbios.parse_tables(data)
        assert 17 not in t

    def test_tabla_vacia(self):
        assert _smbios.parse_tables(b"") == {}

    def test_longitud_imposible_no_cuelga(self):
        assert _smbios.parse_tables(bytes([4, 2, 0, 0, 0, 0])) == {}

    def test_indice_de_cadena_fuera_de_rango(self):
        data = _estructura(0, 1, [0x09], ["solo una"])
        assert _smbios.parse_tables(data)[0][0].texto(4) == ""

    def test_campos_mas_alla_del_final_devuelven_cero(self):
        e = _smbios.parse_tables(_estructura(0, 1, [0x01], ["AMI"]))[0][0]
        assert e.byte(99) == 0 and e.word(99) == 0 and e.qword(99) == 0

    def test_word_y_qword_leen_little_endian(self):
        e = _smbios.parse_tables(_estructura(17, 1, [0x40, 0x08] + [0] * 6, []))[17][0]
        assert e.word(4) == 0x0840


# ── Comprobaciones de configuración de BIOS/UEFI ──────────────────────────────

def _mod(slot, part="CMK16GX4M1B3000C15", cap=16, speed=2133, conf=2133, fab="Corsair"):
    return {"slot": slot, "fabricante": fab, "part": part,
            "capacidad_gb": cap, "speed": speed, "configurada": conf}


class TestVelocidadNominal:
    def test_corsair(self):
        assert bios._velocidad_nominal("CMK16GX4M1B3000C15") == 3000

    def test_gskill(self):
        assert bios._velocidad_nominal("F4-3200C16-8GVKB") == 3200

    def test_kingston(self):
        assert bios._velocidad_nominal("KHX3200C16D4/8G") == 3200

    def test_ddr5(self):
        assert bios._velocidad_nominal("CMK32GX5M2B6000C36") == 6000

    def test_sin_velocidad_reconocible(self):
        assert bios._velocidad_nominal("M378A1K43CB2-CRC") is None

    def test_ignora_numeros_fuera_de_rango(self):
        assert bios._velocidad_nominal("ABC1234XYZ") is None

    def test_part_number_vacio(self):
        assert bios._velocidad_nominal("") is None


class TestMemoria:
    def test_xmp_desactivado_por_part_number(self):
        items = bios._check_memoria([_mod("ChannelA-DIMM2"), _mod("ChannelB-DIMM2")])
        xmp = [i for i in items if "XMP" in i["name"] or "velocidad" in i["name"].lower()]
        assert xmp and xmp[0]["status"] == "warning"
        assert "3000" in xmp[0]["message"] and "2133" in xmp[0]["message"]

    def test_xmp_activo_no_avisa(self):
        mods = [_mod("ChannelA-DIMM2", speed=3000, conf=3000),
                _mod("ChannelB-DIMM2", speed=3000, conf=3000)]
        assert all(i["status"] == "ok" for i in bios._check_memoria(mods))

    def test_spd_mayor_que_configurada_tambien_avisa(self):
        mods = [_mod("ChannelA-DIMM2", part="DESCONOCIDO", speed=3200, conf=2400)]
        assert any(i["status"] == "warning" for i in bios._check_memoria(mods))

    def test_dos_modulos_en_el_mismo_canal_es_single_channel(self):
        mods = [_mod("ChannelA-DIMM1", speed=3000, conf=3000),
                _mod("ChannelA-DIMM2", speed=3000, conf=3000)]
        canal = [i for i in bios._check_memoria(mods) if "canal" in i["name"].lower()]
        assert canal and canal[0]["status"] == "warning"

    def test_modulos_repartidos_son_dual_channel(self):
        mods = [_mod("ChannelA-DIMM2", speed=3000, conf=3000),
                _mod("ChannelB-DIMM2", speed=3000, conf=3000)]
        canal = [i for i in bios._check_memoria(mods) if "canal" in i["name"].lower()]
        assert canal and canal[0]["status"] == "ok"

    def test_un_solo_modulo_no_se_juzga_como_single_channel(self):
        mods = [_mod("ChannelA-DIMM2", speed=3000, conf=3000)]
        canal = [i for i in bios._check_memoria(mods) if "canal" in i["name"].lower()]
        assert not canal or canal[0]["status"] == "ok"

    def test_sin_modulos_no_lanza(self):
        assert isinstance(bios._check_memoria([]), list)


class TestNucleos:
    def test_todos_los_nucleos_activos(self):
        assert bios._check_nucleos({"nucleos": 8, "habilitados": 8, "hilos": 8})["status"] == "ok"

    def test_nucleos_deshabilitados_en_la_bios(self):
        item = bios._check_nucleos({"nucleos": 8, "habilitados": 4, "hilos": 4})
        assert item["status"] == "warning" and "4" in item["message"] and "8" in item["message"]

    def test_datos_ausentes_no_inventan_aviso(self):
        assert bios._check_nucleos({"nucleos": 0, "habilitados": 0, "hilos": 0})["status"] == "ok"


class TestSlotsPcie:
    def test_tarjeta_en_slot_estrecho_con_uno_ancho_libre(self):
        slots = [{"nombre": "PCIEX16_1", "ancho": "x16", "ocupado": False},
                 {"nombre": "PCIEX16_2", "ancho": "x8",  "ocupado": True}]
        item = bios._check_slots(slots)
        assert item["status"] == "warning"
        assert "PCIEX16_1" in item["message"] and "PCIEX16_2" in item["message"]

    def test_tarjeta_ya_en_el_slot_mas_ancho(self):
        slots = [{"nombre": "PCIEX16_1", "ancho": "x16", "ocupado": True},
                 {"nombre": "PCIEX16_2", "ancho": "x8",  "ocupado": False}]
        assert bios._check_slots(slots)["status"] == "ok"

    def test_no_avisa_por_slots_de_una_linea(self):
        slots = [{"nombre": "PCIEX16_1", "ancho": "x16", "ocupado": True},
                 {"nombre": "PCIEX1_1",  "ancho": "x1",  "ocupado": True}]
        assert bios._check_slots(slots)["status"] == "ok"

    def test_sin_slots_ocupados(self):
        assert bios._check_slots([])["status"] == "ok"


class TestAntiguedadBios:
    def test_bios_reciente(self):
        assert bios._check_bios_date("03/18/2026", hoy=(2026, 8, 30))["status"] == "ok"

    def test_bios_de_hace_siete_anos(self):
        item = bios._check_bios_date("03/18/2019", hoy=(2026, 8, 30))
        assert item["status"] == "warning" and "7" in item["value"]

    def test_fecha_ilegible_no_lanza(self):
        assert bios._check_bios_date("no es fecha", hoy=(2026, 8, 30))["status"] == "ok"

    def test_fecha_vacia(self):
        assert bios._check_bios_date("", hoy=(2026, 8, 30))["status"] == "ok"


class TestExtractoresSmbios:
    def _t17(self, slot, fab, part, tam=16384, speed=2133, conf=2133):
        """Un Memory Device. SMBIOS no admite cadenas vacías: van con índice 0."""
        cadenas = [c for c in (slot, fab, part) if c]
        campos = bytearray(0x20)
        campos[0x0C - 4:0x0E - 4] = tam.to_bytes(2, "little")
        campos[0x15 - 4:0x17 - 4] = speed.to_bytes(2, "little")
        campos[0x20 - 4:0x22 - 4] = conf.to_bytes(2, "little")
        campos[0x10 - 4] = 1 if slot else 0
        campos[0x17 - 4] = cadenas.index(fab) + 1 if fab else 0
        campos[0x1A - 4] = cadenas.index(part) + 1 if part else 0
        return _estructura(17, 1, list(campos) + [0, 0], cadenas)

    def test_lee_modulos_y_descarta_zocalos_vacios(self):
        vacio = self._t17("ChannelA-DIMM1", "", "", tam=0)
        lleno = self._t17("ChannelB-DIMM2", "Corsair", "CMK16GX4M1B3000C15")
        mods = bios._leer_modulos(_smbios.parse_tables(vacio + lleno))
        assert len(mods) == 1
        assert mods[0]["slot"] == "ChannelB-DIMM2"
        assert mods[0]["part"] == "CMK16GX4M1B3000C15"
        assert mods[0]["capacidad_gb"] == 16

    def test_lee_nucleos_de_la_cpu(self):
        campos = bytearray(0x24)
        campos[0x05 - 4] = 3          # ProcessorType: central processor
        campos[0x23 - 4] = 8          # CoreCount
        campos[0x24 - 4] = 6          # CoreEnabled
        campos[0x25 - 4] = 6          # ThreadCount  (fuera de rango -> se amplía abajo)
        datos = _estructura(4, 1, list(campos) + [6, 6], [])
        cpu = bios._leer_cpu(_smbios.parse_tables(datos))
        assert cpu["nucleos"] == 8 and cpu["habilitados"] == 6

    def test_lee_slots_con_su_ancho_y_ocupacion(self):
        campos = [1, 0, 13, 4] + [0] * 12      # designación, tipo, x16, ocupado
        datos = _estructura(9, 1, campos, ["PCIEX16_1"])
        slots = bios._leer_slots(_smbios.parse_tables(datos))
        assert slots == [{"nombre": "PCIEX16_1", "ancho": "x16", "ocupado": True}]

    def test_ignora_slots_de_ancho_desconocido(self):
        datos = _estructura(9, 1, [1, 0, 99, 3] + [0] * 12, ["RARO"])
        assert bios._leer_slots(_smbios.parse_tables(datos)) == []

    def test_sin_tablas_los_extractores_devuelven_vacio(self):
        assert bios._leer_modulos({}) == []
        assert bios._leer_cpu({}) == {}
        assert bios._leer_slots({}) == []
        assert bios._leer_bios({}) == {}


# ── Versión de la aplicación ──────────────────────────────────────────────────

class TestVersion:
    def test_sigue_el_formato_semver(self):
        import re as _re
        assert _re.fullmatch(r"\d+\.\d+\.\d+", _version.__version__)

    def test_cuaterna_para_el_recurso_de_windows(self):
        v = _version.version_tuple()
        assert len(v) == 4 and all(isinstance(n, int) for n in v)
        assert v[:3] == tuple(int(x) for x in _version.__version__.split("."))

    def test_el_version_info_lleva_la_version_vigente(self):
        contenido = _version.version_info_file()
        assert f"StringStruct('FileVersion', '{_version.__version__}')" in contenido
        assert "PCGuardian.exe" in contenido

    def test_el_version_info_es_evaluable_por_pyinstaller(self):
        # PyInstaller hace exec() del fichero: tiene que ser Python válido
        import ast
        cuerpo = _version.version_info_file()
        ast.parse(cuerpo)


# ── Rendimiento del arranque ──────────────────────────────────────────────────

def _ev(id_, data, time="2026-09-03T09:00:00"):
    return {"Id": id_, "Time": time, "Data": data}


def _ev100(main_ms, total_ms=None, time="2026-09-03T09:00:00"):
    return _ev(100, {"MainPathBootTime": str(main_ms),
                     "BootTime": str(total_ms if total_ms is not None else main_ms + 20000),
                     "BootNumStartupApps": "12"}, time)


class TestTiempoLegible:
    def test_segundos(self):
        assert boot._ms_a_texto(8200) == "8 s"

    def test_minutos_y_segundos(self):
        assert boot._ms_a_texto(95000) == "1 min 35 s"

    def test_minutos_exactos(self):
        assert boot._ms_a_texto(120000) == "2 min"

    def test_menos_de_un_segundo(self):
        assert boot._ms_a_texto(400) == "0,4 s"

    def test_cero(self):
        assert boot._ms_a_texto(0) == "0 s"


class TestArranque:
    def test_arranque_rapido_es_ok(self):
        items = boot._parse_boot_events([_ev100(18000)])
        assert items[0]["status"] == "ok" and "18 s" in items[0]["value"]

    def test_arranque_lento_avisa(self):
        items = boot._parse_boot_events([_ev100(62000)])
        assert items[0]["status"] == "warning"

    def test_arranque_muy_lento_es_grave(self):
        items = boot._parse_boot_events([_ev100(150000)])
        assert items[0]["status"] == "danger"

    def test_usa_el_arranque_mas_reciente(self):
        viejo = _ev100(150000, time="2026-08-01T09:00:00")
        nuevo = _ev100(15000, time="2026-09-03T09:00:00")
        items = boot._parse_boot_events([viejo, nuevo])
        assert items[0]["status"] == "ok"

    def test_lista_los_culpables_ordenados_por_tiempo(self):
        eventos = [
            _ev100(70000),
            _ev(101, {"Name": "OneDrive.exe", "TotalTime": "5000", "DegradationTime": "3000"}),
            _ev(103, {"Name": "SysMain", "TotalTime": "22000", "DegradationTime": "12000"}),
            _ev(102, {"Name": "raid.sys", "TotalTime": "9000", "DegradationTime": "4000"}),
        ]
        nombres = [i["name"] for i in boot._parse_boot_events(eventos)[1:]]
        assert nombres[0].startswith("SysMain")
        assert "raid.sys" in nombres[1] and "OneDrive.exe" in nombres[2]

    def test_distingue_el_tipo_de_cada_culpable(self):
        eventos = [_ev100(70000),
                   _ev(101, {"Name": "app.exe", "TotalTime": "9000"}),
                   _ev(102, {"Name": "drv.sys", "TotalTime": "8000"}),
                   _ev(103, {"Name": "svc", "TotalTime": "7000"}),
                   _ev(106, {"Name": "tarea", "TotalTime": "6000"})]
        tipos = [i["detail"] for i in boot._parse_boot_events(eventos)[1:]]
        assert any("plicaci" in t for t in tipos)
        assert any("ontrolador" in t for t in tipos)
        assert any("ervicio" in t for t in tipos)
        assert any("area" in t or "área" in t for t in tipos)

    def test_agrupa_el_mismo_nombre_quedandose_con_el_peor(self):
        eventos = [_ev100(70000),
                   _ev(101, {"Name": "OneDrive.exe", "TotalTime": "5000"}),
                   _ev(101, {"Name": "OneDrive.exe", "TotalTime": "18000"})]
        culpables = boot._parse_boot_events(eventos)[1:]
        assert len(culpables) == 1 and "18 s" in culpables[0]["value"]

    def test_un_retraso_pequeno_no_se_marca_como_aviso(self):
        eventos = [_ev100(20000), _ev(101, {"Name": "leve.exe", "TotalTime": "1200"})]
        assert boot._parse_boot_events(eventos)[1]["status"] == "ok"

    def test_ignora_eventos_de_tipos_no_contemplados(self):
        eventos = [_ev100(20000), _ev(999, {"Name": "raro", "TotalTime": "30000"})]
        assert len(boot._parse_boot_events(eventos)) == 1

    def test_sin_eventos_lo_dice_sin_inventar(self):
        items = boot._parse_boot_events([])
        assert len(items) == 1 and items[0]["status"] == "ok"
        assert "Sin datos" in items[0]["value"]
        assert "datos" in items[0]["message"].lower()

    def test_culpables_sin_evento_100_siguen_listandose(self):
        eventos = [_ev(103, {"Name": "SysMain", "TotalTime": "22000"})]
        items = boot._parse_boot_events(eventos)
        assert any("SysMain" in i["name"] for i in items)

    def test_tope_de_culpables_listados(self):
        eventos = [_ev100(70000)] + [
            _ev(101, {"Name": f"app{i}.exe", "TotalTime": str(9000 + i)}) for i in range(15)]
        assert len(boot._parse_boot_events(eventos)) - 1 == 8

    def test_datos_corruptos_no_lanzan(self):
        eventos = [_ev(100, {"MainPathBootTime": "no-es-un-numero"}),
                   _ev(101, {"Name": "", "TotalTime": None})]
        assert isinstance(boot._parse_boot_events(eventos), list)
