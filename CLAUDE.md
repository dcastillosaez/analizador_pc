# CLAUDE.md — PC Guardian

Herramienta de diagnóstico local para Windows 10/11. Flask en backend, SPA vanilla en frontend. **Solo lectura** salvo las dos operaciones explícitas de escritura: actualizar un paquete con winget y limpiar archivos temporales.

## Stack

- **Backend:** Python + Flask (puerto 8765), un archivo por módulo en `analyzer/`
- **Frontend:** HTML/CSS/JS vanilla — sidebar colapsable + overview + vista de módulo individual
- **Dependencias:** `Flask`, `psutil`, `winreg` (stdlib), `wmi` (opcional, para temperaturas GPU)

## Estructura

```
app.py                      Rutas Flask — un endpoint GET /api/scan/<id> por módulo
analyzer/
  hardware.py               CPU, RAM, disco — psutil
  startup.py                Claves Run del registro — winreg
  security.py               Procesos sospechosos, entropía de Shannon
  drivers.py                WMI Win32_PnPSignedDriver + winreg Uninstall
  protection.py             Antivirus (CIM) + Firewall (netsh), paralelo
  network.py                Puertos abiertos (psutil) + archivo hosts
  maintenance.py            SMART (Get-PhysicalDisk) + uptime + schtasks, paralelo
  updates.py                winget list --upgrade-available
  connectivity.py           Ping, DNS, HTTP, gateway, test de velocidad (Cloudflare 10 MB)
  energy.py                 Plan de energía (powercfg), batería (psutil + batteryreport), temps (WMI/OHM)
  privacy.py                Telemetría (registro), permisos cam/mic/ubicación, temporales, Visor de eventos
  performance.py            Snapshot CPU/RAM/disco/GPU para el monitor en tiempo real
templates/index.html        SPA: sidebar + topbar + content-area (overview o módulo individual)
static/css/style.css        Dark theme, sin frameworks CSS externos
static/js/app.js            Vanilla JS — navegación sidebar, scan global/individual, renders por módulo
por_implementar.md          Backlog con estado actualizado (✓ = implementado)
```

## API endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/scan/hardware` | CPU, RAM, disco |
| GET | `/api/scan/startup` | Programas de inicio |
| GET | `/api/scan/security` | Procesos y anomalías |
| GET | `/api/scan/drivers` | Controladores y software |
| GET | `/api/scan/protection` | Antivirus y firewall |
| GET | `/api/scan/network` | Puertos y archivo hosts |
| GET | `/api/scan/maintenance` | Disco SMART, uptime, tareas |
| GET | `/api/scan/updates` | Paquetes desactualizados (winget) |
| GET | `/api/scan/connectivity` | Ping, DNS, latencia, gateway |
| GET | `/api/scan/energy` | Plan de energía, batería, temperaturas |
| GET | `/api/scan/privacy` | Telemetría, permisos, temporales, eventos |
| GET | `/api/perf/snapshot` | Snapshot en tiempo real (polling 2 s) |
| GET | `/api/connectivity/speedtest` | Test de descarga ~10 MB Cloudflare |
| POST | `/api/update/<package_id>` | Actualiza un paquete con winget (**escritura**) |
| POST | `/api/privacy/clean-temp` | Vacía carpetas temporales (**escritura**) |

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
- **Escaneo global:** botón "Escanear Sistema" en topbar — ejecuta todos los módulos en secuencia.

## Normas al editar

- Los módulos de `analyzer/` son **stateless**: reciben parámetros de configuración si los necesitan, no guardan estado entre llamadas.
- El monitor de rendimiento (`perf`) **no** forma parte del escaneo general — es on-demand desde su vista.
- `winget` emite la salida en la página OEM del sistema, no en UTF-8. `updates.py` prueba `utf-8 → oem → cp1252 → latin-1`. No cambies esto.
- Los encabezados de `winget` están en el idioma del sistema (español: `Nombre`, `Disponible`). El parser usa aliases bilingües.
- Las dos operaciones de escritura requieren confirmación explícita del usuario en la UI antes de ejecutarse.
- No añadas dependencias externas sin actualizar `requirements.txt` y este fichero.
