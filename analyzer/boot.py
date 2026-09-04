"""Rendimiento del arranque — cuánto tarda el equipo en encender y por culpa de qué.

Windows lleva su propia contabilidad del arranque en el canal
`Microsoft-Windows-Diagnostics-Performance/Operational`: el evento 100 registra
los tiempos de cada arranque y los 101-106 señalan por nombre qué aplicación,
controlador, servicio o tarea se pasó de tiempo, con sus milisegundos.

Ese canal está restringido a administradores, así que sin elevación el módulo lo
dice en vez de fingir que no hay nada que contar.
"""
from ._shell import is_admin, run_ps_json

# Tiempos de MainPathBootTime (hasta que el escritorio responde), en ms
ARRANQUE_OK, ARRANQUE_MALO = 40_000, 90_000

# A partir de aquí un retraso individual merece aviso
RETRASO_AVISO = 4_000

TOPE_CULPABLES = 8

# Por tipo de evento: etiqueta, cómo nombrarlo en la frase y qué hacer con él.
# El consejo no puede ser el mismo para todos: un servicio no se quita desde el
# Administrador de tareas y un controlador no se quita en absoluto.
TIPOS = {
    101: ("Aplicación de inicio", "La aplicación",
          "Quítala del inicio desde el Administrador de tareas → pestaña Inicio "
          "si no la necesitas nada más encender."),
    102: ("Controlador", "El controlador",
          "Busca una versión más reciente del controlador en la web del fabricante."),
    103: ("Servicio", "El servicio",
          "Si no lo necesitas siempre, ponlo en inicio Manual desde services.msc."),
    106: ("Tarea programada", "La tarea programada",
          "Revísala en el Programador de tareas y cámbiale el disparador si no "
          "tiene que ejecutarse al encender."),
}

# Componentes de Windows: aparecen aquí a menudo y no se quitan del inicio.
# Decirle a alguien que desactive el motor antimalware sería un pésimo consejo.
COMPONENTES_WINDOWS = {
    "msmpeng.exe", "mpdefendercoreservice.exe", "nissrv.exe", "smartscreen.exe",
    "securityhealthservice.exe", "securityhealthsystray.exe",
    "searchindexer.exe", "searchhost.exe", "searchapp.exe",
    "tiworker.exe", "trustedinstaller.exe", "wuauclt.exe", "usoclient.exe",
    "mousocoreworker.exe", "compattelrunner.exe", "svchost.exe", "taskhostw.exe",
    "wmiprvse.exe", "dwm.exe", "explorer.exe", "ctfmon.exe", "sihost.exe",
    "runtimebroker.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
    "lockapp.exe", "backgroundtaskhost.exe", "fontdrvhost.exe", "audiodg.exe",
    "spoolsv.exe", "lsass.exe", "csrss.exe", "winlogon.exe", "services.exe",
}

# Rutas que delatan un componente del sistema cuando el nombre no basta
RUTAS_SISTEMA = ("\\windows\\", "\\system32\\", "\\syswow64\\")


# Runtimes que no arrancan solos: los lanza la aplicación que los usa. Mandar a
# alguien a la pestaña Inicio a buscarlos es mandarlo a un sitio donde no están.
RUNTIMES_COMPARTIDOS = {
    "msedgewebview2.exe": "las aplicaciones que usan WebView2",
    "electron.exe":       "las aplicaciones hechas con Electron",
    "javaw.exe":          "los programas Java que tengas instalados",
}


def _es_componente_windows(nombre: str, ruta: str) -> bool:
    if nombre.lower() in COMPONENTES_WINDOWS:
        return True
    ruta = (ruta or "").lower()
    return any(p in ruta for p in RUTAS_SISTEMA)


def _num(valor) -> int:
    try:
        return int(float(str(valor).strip()))
    except (TypeError, ValueError):
        return 0


def _ms_a_texto(ms: int) -> str:
    """Milisegundos en algo que se pueda leer en voz alta."""
    if ms <= 0:
        return "0 s"
    if ms < 1000:
        return f"{ms / 1000:.1f}".replace(".", ",") + " s"
    segundos = round(ms / 1000)
    if segundos < 60:
        return f"{segundos} s"
    minutos, resto = divmod(segundos, 60)
    return f"{minutos} min" if resto == 0 else f"{minutos} min {resto} s"


def _parse_boot_events(eventos: list[dict]) -> list[dict]:
    """Convierte los eventos del log de rendimiento en items del informe."""
    arranques = [e for e in eventos if e.get("Id") == 100]
    retrasos = [e for e in eventos if e.get("Id") in TIPOS]

    items: list[dict] = []

    if arranques:
        ultimo = max(arranques, key=lambda e: str(e.get("Time") or ""))
        datos = ultimo.get("Data") or {}
        principal = _num(datos.get("MainPathBootTime"))
        total = _num(datos.get("BootTime"))
        apps = _num(datos.get("BootNumStartupApps"))

        if not principal:
            estado, mensaje = "ok", "El registro de arranque no trae tiempos utilizables."
        elif principal <= ARRANQUE_OK:
            estado = "ok"
            mensaje = (f"El escritorio queda utilizable {_ms_a_texto(principal)} después de "
                       "encender. Es un arranque sano.")
        elif principal <= ARRANQUE_MALO:
            estado = "warning"
            mensaje = (f"El equipo tarda {_ms_a_texto(principal)} en dejar el escritorio "
                       "utilizable. Reducir los programas de inicio se notará al encender.")
        else:
            estado = "danger"
            mensaje = (f"El equipo tarda {_ms_a_texto(principal)} en arrancar del todo. "
                       "Está muy por encima de lo normal.")

        detalle = []
        if total:
            detalle.append(f"arranque completo {_ms_a_texto(total)}")
        if apps:
            detalle.append(f"{apps} programas de inicio")

        items.append({
            "name": "Tiempo de arranque",
            "status": estado,
            "message": mensaje,
            "value": _ms_a_texto(principal) if principal else "Sin dato",
            "detail": " · ".join(detalle),
        })
    elif not retrasos:
        items.append({
            "name": "Tiempo de arranque",
            "status": "ok",
            "message": ("Windows todavía no ha dejado datos de rendimiento del arranque. "
                        "Aparecen tras unos cuantos encendidos completos, no tras reanudar "
                        "desde suspensión."),
            "value": "Sin datos aún",
            "detail": "",
        })

    # Un mismo culpable aparece en varios arranques: nos quedamos con su peor marca
    peores: dict[tuple[int, str], int] = {}
    rutas: dict[str, str] = {}
    for e in retrasos:
        datos = e.get("Data") or {}
        nombre = (datos.get("Name") or "").strip()
        if not nombre:
            continue
        clave = (e["Id"], nombre)
        peores[clave] = max(peores.get(clave, 0), _num(datos.get("TotalTime")))
        if datos.get("PathName"):
            rutas.setdefault(nombre, str(datos["PathName"]))

    for (id_evento, nombre), ms in sorted(peores.items(), key=lambda kv: -kv[1])[:TOPE_CULPABLES]:
        etiqueta, sujeto, consejo = TIPOS[id_evento]
        tardanza = f"{sujeto} {nombre} tardó {_ms_a_texto(ms)} en cargar durante el arranque."

        runtime = RUNTIMES_COMPARTIDOS.get(nombre.lower())
        if runtime:
            items.append({
                "name": f"{nombre} retrasa el arranque",
                "status": "ok",
                "message": (f"{tardanza} No arranca por su cuenta: lo lanzan {runtime}, así que "
                            "el retraso hay que corregirlo en la aplicación que lo abre."),
                "value": _ms_a_texto(ms),
                "detail": f"{etiqueta} · runtime compartido",
            })
            continue

        if _es_componente_windows(nombre, rutas.get(nombre, "")):
            items.append({
                "name": f"{nombre} retrasa el arranque",
                "status": "ok",
                "message": (f"{tardanza} Es un componente de Windows, así que no se quita del "
                            "inicio: forma parte del propio sistema y su carga es normal."),
                "value": _ms_a_texto(ms),
                "detail": f"{etiqueta} · componente del sistema",
            })
            continue

        grave = ms >= RETRASO_AVISO
        items.append({
            "name": f"{nombre} retrasa el arranque",
            "status": "warning" if grave else "ok",
            "message": f"{tardanza} " + (consejo if grave else "Es un retraso menor."),
            "value": _ms_a_texto(ms),
            "detail": etiqueta,
        })

    return items


def analyze_boot() -> dict:
    """Lee el log de rendimiento del arranque y evalúa lo que encuentre."""
    # Dos consultas y no una: en un equipo con muchos retrasos, los eventos 101
    # copan el tope de resultados y expulsan al 100, que es el único que trae los
    # tiempos del arranque. Pidiéndolo aparte siempre viene.
    eventos = run_ps_json(
        "$log = 'Microsoft-Windows-Diagnostics-Performance/Operational'; "
        "function Traer($ids, $max) { "
        "  try { Get-WinEvent -FilterHashtable @{LogName=$log; Id=$ids} -MaxEvents $max -ErrorAction Stop } "
        "  catch { @() } } "
        "$b = Traer 100 5; $c = Traer @(101,102,103,106) 60; "
        "$out = foreach ($e in @($b) + @($c)) { "
        "  $x = [xml]$e.ToXml(); $d = @{}; "
        "  foreach ($n in $x.Event.EventData.Data) { $d[$n.Name] = $n.'#text' } "
        "  [pscustomobject]@{Id=$e.Id; Time=$e.TimeCreated.ToString('s'); Data=$d} } "
        "ConvertTo-Json -Depth 4 -Compress -InputObject @($out)",
        timeout=40, default=None,
    )

    if isinstance(eventos, dict):
        eventos = [eventos]

    # Sin eventos hay dos motivos posibles y el usuario necesita saber cuál: el canal
    # está cerrado a quien no es administrador, o el equipo aún no ha registrado nada.
    # PowerShell devuelve la misma excepción para ambos, así que lo decide is_admin().
    if not eventos and not is_admin():
        items = [{
            "name": "Rendimiento del arranque",
            "status": "ok",
            "message": ("El registro de rendimiento del arranque solo lo pueden leer los "
                        "administradores. Reinicia la app elevada para ver cuánto tarda el "
                        "equipo en encender y qué lo está frenando."),
            "value": "Requiere admin",
            "detail": "Microsoft-Windows-Diagnostics-Performance/Operational",
        }]
    else:
        items = _parse_boot_events(eventos or [])

    danger = sum(1 for i in items if i["status"] == "danger")
    warning = sum(1 for i in items if i["status"] == "warning")
    overall = "danger" if danger else ("warning" if warning else "ok")
    summaries = {
        "danger": "El arranque del equipo está claramente degradado.",
        "warning": f"{warning} elemento(s) están alargando el arranque.",
        "ok": "El arranque del equipo no muestra retrasos destacables.",
    }
    return {"status": overall, "title": "Rendimiento del arranque",
            "summary": summaries[overall], "issue_count": danger + warning,
            "items": items}
