# CLAUDE.md — PC Guardian

Herramienta de diagnóstico local para Windows 10/11. Flask en backend, SPA vanilla en frontend. **Solo lectura** salvo las operaciones de escritura explícitas, todas confirmadas por el usuario en la UI: actualizar un paquete con winget, limpiar temporales, actualizar o desinstalar un controlador, instalar una actualización de Windows, eliminar un certificado, terminar un proceso y crear un punto de restauración.

## Stack

- **Backend:** Python + Flask (puerto 8765), un archivo por módulo en `analyzer/`
- **Frontend:** HTML/CSS/JS vanilla — sidebar colapsable + overview + vista de módulo individual
- **Dependencias:** `Flask`, `psutil`, `waitress`, `winreg`/`sqlite3` (stdlib), `wmi` (opcional, para temperaturas GPU), `pytest` (solo desarrollo)

## Estructura

```
app.py                      Rutas Flask — /api/scan/<id> despacha contra la tabla SCANNERS
analyzer/
  _shell.py                 Capa única de subprocess: CREATE_NO_WINDOW, decodificación
                            utf-8/oem/cp1252/latin-1, PowerShell vía -EncodedCommand,
                            timeouts sin excepciones, is_admin/relaunch_as_admin
  _text.py                  Heurística compartida de nombres generados al azar
                            (entropía + proporción de vocales, umbrales calibrados)
  hardware.py               CPU, RAM, disco — psutil
  startup.py                Claves Run del registro — winreg
  security.py               Procesos sospechosos: ruta + firma Authenticode
  signatures.py             Get-AuthenticodeSignature por lotes, con caché
  hardening.py              BitLocker, Secure Boot, TPM, Defender, UAC, SmartScreen,
                            puntos de restauración
  restore.py                Crear punto de restauración y consultar su estado
  processes.py              Top CPU/RAM sobre ventana real + terminar proceso
  connections.py            TCP salientes establecidas + DNS inverso en paralelo
  drivers.py                WMI Win32_PnPSignedDriver + winreg Uninstall
  protection.py             Antivirus (CIM) + Firewall (netsh), paralelo
  network.py                Puertos abiertos (psutil) + archivo hosts
  maintenance.py            SMART (Get-PhysicalDisk) + uptime + schtasks, paralelo
  updates.py                winget list --upgrade-available
  wupdates.py               Windows Update vía COM API
  connectivity.py           Ping, DNS, HTTP, gateway, test de velocidad
  energy.py                 Plan de energía (powercfg), batería, temperaturas
  privacy.py                Telemetría, permisos cam/mic/ubicación, temporales, eventos
  performance.py            Snapshot CPU/RAM/disco/GPU para el monitor en tiempo real
  inventory.py              CPU, GPU, RAM slot a slot, placa base y BIOS vía WMI
  services.py               Servicios automáticos en ejecución
  wifi.py                   Redes cercanas, canal, señal y colisiones (netsh wlan)
  certs.py                  Certificados del almacén de Windows
  history.py                Historial de escaneos en SQLite y diff entre dos
tests/test_parsers.py       Tests de parsers y heurísticas contra salidas fijadas
templates/index.html        SPA: sidebar + topbar + content-area
static/css/style.css        Tema oscuro por defecto + tema claro por tokens
static/js/app.js            Vanilla JS — navegación, escaneo en paralelo, renders
por_implementar.md          Backlog con estado actualizado
```

## API endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/scan/<id>` | Cualquier módulo de `SCANNERS`. `?fresh=1` salta la caché |
| GET | `/api/perf/snapshot` | Snapshot en tiempo real (polling 2 s) |
| GET | `/api/connectivity/speedtest` | Test de descarga ~10 MB |
| GET | `/api/status/admin` | Si la app corre elevada |
| GET | `/api/history` | Línea de tiempo de escaneos guardados |
| GET | `/api/history/<id>` | Un escaneo completo |
| GET | `/api/history/diff?a=&b=` | Diferencias entre dos escaneos |
| GET | `/api/restore/status` | Protección del sistema y último punto |
| POST | `/api/history` | Guarda el escaneo actual |
| POST | `/api/history/clear` | Vacía el historial |
| DELETE | `/api/history/<id>` | Borra un escaneo del historial |
| POST | `/api/admin/elevate` | Relanza la app con UAC (**escritura**) |
| POST | `/api/update/<package_id>` | Actualiza un paquete con winget (**escritura**) |
| POST | `/api/privacy/clean-temp` | Vacía carpetas temporales (**escritura**) |
| POST | `/api/driver/update` | `pnputil /scan-devices` (**escritura**) |
| POST | `/api/driver/uninstall` | `pnputil /remove-device` (**escritura**) |
| POST | `/api/cert/delete` | Elimina un certificado (**escritura**) |
| POST | `/api/wupdate/apply/<id>` | Instala una actualización (**escritura**) |
| POST | `/api/process/kill` | Termina un proceso (**escritura**) |
| POST | `/api/restore/create` | Crea un punto de restauración (**escritura**) |

Módulos de escaneo (`SCANNERS` en `app.py`): `hardware`, `startup`, `security`,
`drivers`, `protection`, `network`, `maintenance`, `updates`, `privacy`,
`connectivity`, `energy`, `inventory`, `certs`, `wifi`, `wupdates`, `services`,
`processes`, `connections`, `hardening`.

## Esquema JSON estándar de respuesta

Todos los módulos de escaneo devuelven:

```json
{
  "status": "ok | warning | danger",
  "title": "string",
  "summary": "string legible",
  "issue_count": 0,
  "items": [
    {
      "name": "string",
      "status": "ok | warning | danger",
      "message": "string legible",
      "value": "string corto (87%, 2 BSOD…)",
      "detail": "string técnico opcional"
    }
  ]
}
```

## Navegación (frontend)

- **Overview:** grid de tiles con estado de cada módulo. Clic en tile → vista de módulo.
- **Vista de módulo:** barra con botón "← Resumen" y botón "Analizar módulo" (escaneo individual sin lanzar todo).
- **Sidebar:** colapsable a 64 px (solo iconos). Cada item tiene un dot de estado (gris/verde/naranja/rojo) que se actualiza tras cada escaneo.
- **Escaneo global:** botón "Escanear Sistema" en topbar — ejecuta los módulos con un pool de 4 en paralelo.
- **Historial:** vista propia con la línea de tiempo de escaneos guardados y la comparación entre dos.
- **Tema:** botón en la topbar; arranca siguiendo la preferencia del sistema y recuerda la elección manual.

## Normas al editar

- Los módulos de `analyzer/` son **stateless**: reciben parámetros de configuración si los necesitan, no guardan estado entre llamadas.
- El monitor de rendimiento (`perf`) **no** forma parte del escaneo general — es on-demand desde su vista.
- **Nunca llames a `subprocess` directamente desde un módulo**: usa `run`, `run_ps` o `run_ps_json` de `analyzer/_shell.py`. Son las que ponen `CREATE_NO_WINDOW` (sin eso el .exe compilado abre una ventana negra por cada llamada), resuelven la codificación y no lanzan.
- Windows emite en la página OEM del sistema, no en UTF-8. La cadena `utf-8 → oem → cp1252 → latin-1` vive en `_shell._decode`. No la dupliques.
- PowerShell se invoca con `-EncodedCommand`: no hace falta escapar comillas y el shell no reinterpreta el contenido del script.
- Los encabezados de `winget` están en el idioma del sistema (español: `Nombre`, `Disponible`). El parser usa aliases bilingües.
- Toda operación de escritura requiere confirmación explícita del usuario en la UI, e invalida la caché de los módulos afectados (`invalidate_cache`).
- Las tres operaciones difíciles de deshacer (desinstalar controlador, instalar actualización, borrar certificado) ofrecen crear un punto de restauración antes. Es best-effort a propósito: si falla, la operación sigue y se informa.
- Los resultados se cachean 60 s por módulo (`CACHE_TTL`). Las acciones explícitas del usuario piden `?fresh=1`.
- El escaneo global corre con un pool de 4 peticiones simultáneas (`SCAN_CONCURRENCY` en `app.js`).
- Los tests (`python -m pytest tests/ -q`) no tocan el sistema: prueban parsers y heurísticas contra salidas fijadas. Si tocas un parser o un umbral, actualízalos.
- En CSS los velos se escriben `rgba(var(--tint), X)`, nunca `rgba(255,255,255, X)`: así el tema claro funciona sin tocar la regla.
- No añadas dependencias externas sin actualizar `requirements.txt` y este fichero.
