# CLAUDE.md — PC Guardian

Herramienta de diagnóstico local para Windows 10/11. Flask en backend, SPA vanilla en frontend.

## Stack

- **Backend:** Python + Flask (puerto 8765), un archivo por módulo en `analyzer/`
- **Frontend:** HTML/CSS/JS vanilla — sidebar colapsable + overview + vista de módulo individual
- **Dependencias:** `Flask`, `psutil`, `winreg` (stdlib), `wmi` (opcional, para temperaturas GPU)
- **Persistencia:** SQLite — `history.db` (escaneos), `perf_history.db` (snapshots de rendimiento)

## Estructura

```
app.py                      Rutas Flask + thread perf recorder (cada 5 min)
analyzer/
  hardware.py               CPU, RAM, disco — psutil
  startup.py                Claves Run del registro — winreg; incluye fix_hive/fix_key/fix_name
  security.py               Procesos sospechosos, entropía de Shannon
  drivers.py                WMI Win32_PnPSignedDriver + winreg Uninstall
  protection.py             Antivirus (CIM) + Firewall (netsh), paralelo
  network.py                Puertos abiertos (psutil) + archivo hosts
  maintenance.py            SMART (Get-PhysicalDisk) + uptime + schtasks, paralelo
  updates.py                winget list --upgrade-available
  wupdates.py               Windows Update COM API
  connectivity.py           Ping, DNS, HTTP, gateway, test de velocidad (Cloudflare 10 MB)
  energy.py                 Plan de energía (powercfg), batería, temps (WMI/OHM)
  privacy.py                Telemetría (registro), permisos cam/mic/ubicación, temporales, eventos
  performance.py            Snapshot CPU/RAM/disco/GPU para el monitor en tiempo real
  inventory.py              CPU, GPU, RAM slot a slot, placa base y BIOS via WMI
  services.py               Servicios automáticos en ejecución, rutas sospechosas
  wifi.py                   netsh wlan show networks — redes cercanas, canal, colisiones
  certs.py                  Certificados del almacén de Windows caducados/próximos
  connections.py            TCP establecido hacia el exterior — psutil + resolución DNS
  processes.py              Top 15 procesos por CPU+RAM — kill on demand
  software.py               Inventario programas instalados vía winreg — uninstall vía winget
  dns.py                    Servidores DNS por interfaz, DoH, cambiar DNS (netsh)
  firewall_rules.py         Reglas no estándar habilitadas — PowerShell Get-NetFirewallRule
  quickfix.py               Acciones rápidas: plan energía, deshabilitar startup, telemetría
  history.py                Historial de escaneos en SQLite (save/list/delete)
  perf_history.py           Snapshots de rendimiento en SQLite — record/get_history
templates/index.html        SPA: sidebar + topbar + content-area + secciones history/perf-history
static/css/style.css        Dark theme + light theme; sin frameworks CSS externos
static/js/app.js            Vanilla JS — navegación, scan global/individual, renders por módulo
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
| GET | `/api/scan/wupdates` | Actualizaciones Windows (COM API) |
| GET | `/api/scan/connectivity` | Ping, DNS, latencia, gateway |
| GET | `/api/scan/energy` | Plan de energía, batería, temperaturas |
| GET | `/api/scan/privacy` | Telemetría, permisos, temporales, eventos |
| GET | `/api/scan/inventory` | Inventario hardware detallado |
| GET | `/api/scan/services` | Servicios de Windows |
| GET | `/api/scan/wifi` | Redes WiFi cercanas |
| GET | `/api/scan/certs` | Certificados del almacén de Windows |
| GET | `/api/scan/connections` | TCP establecido hacia el exterior |
| GET | `/api/scan/processes` | Top 15 procesos por CPU+RAM |
| GET | `/api/scan/software` | Inventario de programas instalados |
| GET | `/api/scan/dns` | Servidores DNS por interfaz + DoH |
| GET | `/api/scan/firewall-rules` | Reglas de firewall no estándar |
| GET | `/api/perf/snapshot` | Snapshot en tiempo real (polling 2 s) |
| GET | `/api/perf/history` | Snapshots últimas 24 h (SQLite) |
| GET | `/api/connectivity/speedtest` | Test de descarga ~10 MB |
| GET | `/api/history` | Lista de escaneos guardados |
| DELETE | `/api/history/<id>` | Elimina un escaneo del historial |
| POST | `/api/history/save` | Guarda escaneo actual con score |
| POST | `/api/update/<package_id>` | Actualiza paquete winget (**escritura**) |
| POST | `/api/wupdate/apply/<update_id>` | Aplica actualización Windows (**escritura**) |
| POST | `/api/driver/update` | Actualiza controlador pnputil (**escritura**) |
| POST | `/api/driver/uninstall` | Desinstala dispositivo pnputil (**escritura**) |
| POST | `/api/cert/delete` | Elimina certificado del almacén (**escritura**) |
| POST | `/api/privacy/clean-temp` | Vacía carpetas temporales (**escritura**) |
| POST | `/api/processes/<pid>/kill` | Termina proceso por PID (**escritura**) |
| POST | `/api/software/uninstall` | Desinstala programa vía winget (**escritura**) |
| POST | `/api/dns/set` | Cambia servidor DNS de una interfaz (**escritura**) |
| POST | `/api/firewall-rules/delete` | Elimina regla de firewall (**escritura**) |
| POST | `/api/quickfix/energy-high` | Activa plan Alto Rendimiento (**escritura**) |
| POST | `/api/quickfix/disable-startup` | Elimina entrada del registro Run (**escritura**) |
| POST | `/api/quickfix/telemetry-off` | Desactiva telemetría Windows (**escritura**) |

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
- **Vista de módulo:** barra con botón "← Resumen" y botón "Analizar módulo".
- **Sidebar:** colapsable a 64 px (solo iconos). Cada item tiene un dot de estado.
- **Escaneo global:** botón "Escanear Sistema" — ejecuta todos los módulos en secuencia.
- **Historial:** sección especial (no card) — tabla de escaneos pasados con comparador.
- **Tendencias:** sección especial — sparklines SVG de CPU/RAM/disco últimas 24 h.

## Normas al editar

- Los módulos de `analyzer/` son **stateless**: no guardan estado entre llamadas. Excepción: `history.py` y `perf_history.py` escriben a SQLite.
- El monitor de rendimiento (`perf`) **no** forma parte del escaneo general — es on-demand.
- `firewall-rules` y `software` tampoco están en el escaneo general (on-demand).
- `winget` emite en la página OEM del sistema, no en UTF-8. `updates.py` prueba `utf-8 → oem → cp1252 → latin-1`. No cambies esto.
- Los encabezados de `winget` están en el idioma del sistema. El parser usa aliases bilingües.
- Todas las operaciones de escritura requieren confirmación explícita del usuario en la UI.
- No añadas dependencias externas sin actualizar `requirements.txt` y este fichero.
- El thread `_perf_recorder` en `app.py` guarda un snapshot cada 300 s (5 min). Solo arranca con `__name__ == '__main__'`.
