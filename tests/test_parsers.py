"""Tests de los parsers de salida de herramientas de Windows.

Son la parte más frágil del proyecto: dependen del idioma del sistema, del
ancho de columna y de la codificación. Aquí se prueban contra salidas fijadas,
sin tocar el sistema real, así que corren en cualquier máquina.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer import _shell, _text, maintenance, services, updates, wifi  # noqa: E402
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


class TestClasificacionDeConexiones:
    """Lo importante aquí es no marcar como sospechosa media máquina."""

    @pytest.mark.parametrize("exe", [
        r"C:\Users\ana\AppData\Local\Temp\dropper.exe",
        r"C:\Users\ana\Downloads\setup.exe",
        r"C:\Users\ana\Descargas\instalador.exe",
        r"C:\Windows\Temp\svc.exe",
    ])
    def test_ejecutable_en_carpeta_temporal_o_descargas(self, exe):
        assert connections._classify(exe, "algo.exe", 443)[0] == "danger"

    @pytest.mark.parametrize("exe,name,port", [
        # Aplicaciones que se instalan en el perfil del usuario: normal hoy.
        (r"C:\Users\ana\AppData\Local\Programs\Slack\slack.exe", "slack.exe", 443),
        (r"C:\Users\ana\AppData\Local\Discord\app-1.0\Discord.exe", "Discord.exe", 443),
        (r"C:\Program Files\Google\Chrome\chrome.exe", "chrome.exe", 5228),
        (r"C:\Windows\System32\svchost.exe", "svchost.exe", 5353),
    ])
    def test_no_marca_aplicaciones_normales(self, exe, name, port):
        assert connections._classify(exe, name, port)[0] == "ok"

    def test_nombre_generado_al_azar(self):
        exe = r"C:\Users\ana\AppData\Roaming\App\wdfghjklzxcv.exe"
        assert connections._classify(exe, "wdfghjklzxcv.exe", 443)[0] == "warning"

    def test_puerto_raro_solo_avisa_fuera_de_rutas_de_sistema(self):
        assert connections._classify(r"C:\Windows\System32\x.exe", "x.exe", 47777)[0] == "ok"
        assert connections._classify(r"D:\juegos\x.exe", "x.exe", 47777)[0] == "warning"

    @pytest.mark.parametrize("ip,esperado", [
        ("8.8.8.8", True), ("192.168.1.10", False), ("127.0.0.1", False),
        ("10.0.0.5", False), ("169.254.1.1", False), ("2606:4700::1111", True),
        ("no-es-una-ip", False),
    ])
    def test_solo_cuenta_lo_que_sale_de_la_red_local(self, ip, esperado):
        assert connections._is_external(ip) is esperado

    def test_ipv6_se_formatea_con_corchetes(self):
        assert connections._fmt_endpoint("2606:4700::1111", 443) == "[2606:4700::1111]:443"
        assert connections._fmt_endpoint("8.8.8.8", 53) == "8.8.8.8:53"


# ── Procesos ──────────────────────────────────────────────────────────────────

from analyzer import processes  # noqa: E402


class TestProcesos:
    def test_no_se_puede_matar_el_nucleo(self):
        assert processes.kill_process(4)["success"] is False
        assert processes.kill_process(0)["success"] is False

    def test_pid_invalido(self):
        assert processes.kill_process("abc")["success"] is False

    def test_no_se_mata_a_si_mismo(self):
        import os
        res = processes.kill_process(os.getpid())
        assert res["success"] is False
        assert "PC Guardian" in res["message"]

    def test_el_proceso_inactivo_no_cuenta_como_consumo(self):
        # Mide la CPU libre: apareceria siempre el primero con un 80-90%.
        assert "system idle process" in processes.IGNORED

    @pytest.mark.parametrize("cpu,ram,esperado", [
        (0.5, 1.0, "ok"), (20.0, 1.0, "warning"), (50.0, 1.0, "danger"),
        (1.0, 10.0, "warning"), (1.0, 25.0, "danger"),
    ])
    def test_clasificacion_por_consumo(self, cpu, ram, esperado):
        assert processes._classify(cpu, ram) == esperado
