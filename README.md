# PC Guardian

Herramienta de diagnóstico local para Windows 10/11 con interfaz web. Analiza el estado del sistema e informa en lenguaje claro, sin jerga técnica. **Solo lectura** — no modifica nada sin permiso explícito del usuario.

> © 2026 David Castillo

---

## Instalación y ejecución

```bash
pip install -r requirements.txt
python app.py
```

El navegador se abre automáticamente en `http://127.0.0.1:8765`.

### EXE portable (sin Python)

```bash
COMPILAR_EXE.bat        # genera dist/PCGuardian.exe
```

### PC ajena (instalación automática de Python)

```bash
INSTALAR_Y_EJECUTAR.bat
```

---

## Dependencias

| Paquete | Uso |
|---------|-----|
| Flask | Servidor web local (puerto 8765) |
| psutil | CPU, RAM, disco, red, batería, procesos |
| winreg | Registro de Windows (stdlib) |
| wmi | Temperaturas GPU via OpenHardwareMonitor (opcional) |

---

## Módulos de análisis

El escaneo completo se lanza con **Escanear Sistema**. Cada módulo también se puede relanzar individualmente desde su vista en el sidebar.

### 1. Hardware — `analyzer/hardware.py`
CPU, RAM y disco C:\ via `psutil`. Umbrales: warn ≥ 70 % / danger ≥ 90 %.

### 2. Arranque — `analyzer/startup.py`
Lee las claves `Run` del registro. Marca como peligrosas las entradas desde `%Temp%` o `AppData\Roaming`; como advertencia, apps pesadas conocidas.

### 3. Seguridad — `analyzer/security.py`
Detecta procesos desde rutas temporales, nombres con entropía de Shannon alta y duplicados de procesos críticos del sistema.

### 4. Controladores — `analyzer/drivers.py`
`Win32_PnPSignedDriver` para drivers sin firma. Muestra categoría del dispositivo y su ubicación exacta en el Administrador de dispositivos. Botones **Actualizar** (`pnputil /scan-devices`) y **Desinstalar** (`pnputil /remove-device`) por controlador.

### 5. Protección — `analyzer/protection.py`
Antivirus via `Get-CimInstance AntiVirusProduct` y firewall via `netsh advfirewall`, en paralelo.

### 6. Red — `analyzer/network.py`
Puertos escuchando fuera del rango seguro y entradas no estándar en el archivo `hosts`.

### 7. Mantenimiento — `analyzer/maintenance.py`
Estado SMART del disco, uptime (alerta si > 7 días sin reiniciar) y tareas programadas habilitadas.

### 8. Actualizaciones de software — `analyzer/updates.py`
`winget list --upgrade-available`. Parser bilingüe (español/inglés). Botón **Actualizar** individual y botón **Actualizar todo** con progreso y errores inline por paquete.

### 9. Actualizaciones de Windows — `analyzer/wupdates.py`
Búsqueda bajo demanda via COM API (`Microsoft.Update.Session`). Muestra severidad, número KB con enlace al soporte de Microsoft, descripción técnica y botón **Aplicar actualización** por cada entrada.

### 10. Conectividad — `analyzer/connectivity.py`
Resolución DNS (con servidores configurados identificados por proveedor), acceso HTTP, latencia y gateway. Test de velocidad bajo demanda con fallback automático entre varios servidores públicos (Hetzner, OVH, Tele2).

### 11. Analizador WiFi — `analyzer/wifi.py`
Escaneo via `netsh wlan show networks mode=bssid`. Muestra red conectada con señal, canal, protocolo y velocidad de enlace. Tabla de todas las redes cercanas con barras de señal, banda, protocolo y seguridad. Detecta colisiones de canal y sugiere el canal óptimo en 2.4 GHz.

### 12. Certificados del sistema — `analyzer/certs.py`
Consulta los almacenes `LocalMachine\My`, `LocalMachine\Root`, `LocalMachine\CA` y `CurrentUser\My`. Muestra certificados caducados o que caducan en menos de 90 días con emisor, ruta del almacén y huella digital. Botón **Eliminar** para certificados caducados (requiere admin).

### 13. Energía y Temperatura — `analyzer/energy.py`
Plan de energía activo, salud de batería (`powercfg /batteryreport`) y temperaturas via OpenHardwareMonitor WMI o zonas ACPI.

### 14. Privacidad y Limpieza — `analyzer/privacy.py`
Telemetría, permisos de cámara/micrófono/ubicación, temporales con botón de limpieza, BSODs recientes y eventos críticos del sistema (últimas 72 h).

### 15. Monitor de Rendimiento — `analyzer/performance.py`
On-demand desde el sidebar. Polling cada 2 s a `/api/perf/snapshot`. Sparklines de CPU, RAM, disco y GPU sin librerías externas.

### 16. Servicios — `analyzer/services.py`
Servicios automáticos en ejecución con detección de rutas sospechosas.

### 17. Inventario — `analyzer/inventory.py`
CPU, GPU, RAM slot a slot, placa base y BIOS via WMI.

---

## Exportar informe

El botón **Exportar informe** en la barra superior genera un archivo `.html` autocontenido con todos los módulos escaneados, tablas por módulo y estados con color. Se descarga directamente desde el navegador sin pasar por el servidor.

---

## Arquitectura de la interfaz

```
┌──────────────────┬──────────────────────────────────────────────────┐
│ SIDEBAR (240 px) │ TOPBAR: breadcrumb | [Exportar informe] [Scan]   │
│                  ├──────────────────────────────────────────────────┤
│ ● Resumen        │                                                  │
│                  │  OVERVIEW: tiles con estado de cada módulo.      │
│ SISTEMA          │  Clic → vista de módulo.                         │
│  Hardware    ●   │                                                  │
│  Arranque    ●   │  MÓDULO: card completo +                         │
│  Drivers     ●   │  [← Resumen]  [Analizar módulo]                  │
│  Inventario  ●   │                                                  │
│  Servicios   ●   │                                                  │
│                  │                                                  │
│ SEGURIDAD        │                                                  │
│  Seguridad   ●   │                                                  │
│  Protección  ●   │                                                  │
│                  │                                                  │
│ RED              │                                                  │
│  Red         ●   │                                                  │
│  Conectividad●   │                                                  │
│  Certificados●   │                                                  │
│  WiFi        ●   │                                                  │
│                  │                                                  │
│ RENDIMIENTO      │                                                  │
│  Monitor     ●   │                                                  │
│  Energía     ●   │                                                  │
│                  │                                                  │
│ MANTENIMIENTO    │                                                  │
│  Mantenim.   ●   │                                                  │
│  Updates     ●   │                                                  │
│  Updates Win ●   │                                                  │
│                  │                                                  │
│ PRIVACIDAD       │                                                  │
│  Privacidad  ●   │                                                  │
└──────────────────┴──────────────────────────────────────────────────┘
```

`●` = dot de estado (gris pendiente / verde ok / naranja warning / rojo danger).
El sidebar colapsa a 64 px (solo iconos con tooltip). En móvil es un drawer off-canvas.

---

## API endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/scan/hardware` | CPU, RAM, disco |
| GET | `/api/scan/startup` | Programas de inicio |
| GET | `/api/scan/security` | Procesos y anomalías |
| GET | `/api/scan/drivers` | Controladores y software |
| GET | `/api/scan/protection` | Antivirus y firewall |
| GET | `/api/scan/network` | Puertos y archivo hosts |
| GET | `/api/scan/maintenance` | SMART, uptime, tareas |
| GET | `/api/scan/updates` | Paquetes desactualizados (winget) |
| GET | `/api/scan/wupdates` | Actualizaciones Windows (COM API) |
| GET | `/api/scan/connectivity` | DNS, ping, latencia, gateway |
| GET | `/api/scan/energy` | Plan de energía, batería, temps |
| GET | `/api/scan/privacy` | Telemetría, permisos, temporales, eventos |
| GET | `/api/scan/wifi` | Redes WiFi cercanas |
| GET | `/api/scan/certs` | Certificados del almacén de Windows |
| GET | `/api/scan/inventory` | Inventario de hardware detallado |
| GET | `/api/scan/services` | Servicios de Windows |
| GET | `/api/perf/snapshot` | Snapshot en tiempo real (polling 2 s) |
| GET | `/api/connectivity/speedtest` | Test de velocidad de descarga |
| POST | `/api/update/<package_id>` | Actualiza paquete con winget ⚠️ |
| POST | `/api/wupdate/apply/<update_id>` | Aplica actualización de Windows ⚠️ |
| POST | `/api/driver/update` | Busca actualización de controlador ⚠️ |
| POST | `/api/driver/uninstall` | Desinstala dispositivo ⚠️ |
| POST | `/api/cert/delete` | Elimina certificado del almacén ⚠️ |
| POST | `/api/privacy/clean-temp` | Vacía carpetas temporales ⚠️ |

⚠️ Operaciones de escritura — requieren acción explícita del usuario en la interfaz.

---

## Esquema JSON de respuesta

Todos los módulos de escaneo devuelven:

```json
{
  "status": "ok | warning | danger",
  "title": "string",
  "summary": "string en lenguaje humano",
  "issue_count": 3,
  "items": [
    {
      "name": "string",
      "status": "ok | warning | danger",
      "message": "string en lenguaje humano",
      "value": "string corto (87%, 2 BSOD…)",
      "detail": "string técnico opcional"
    }
  ]
}
```
