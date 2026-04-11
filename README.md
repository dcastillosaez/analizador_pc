# PC Guardian

Herramienta de diagnóstico local para Windows 10/11 con interfaz web. Analiza el estado del sistema e informa en lenguaje claro, sin jerga técnica. **Solo lectura** — no modifica nada sin permiso explícito del usuario (salvo actualizar paquetes con winget o limpiar temporales, ambas acciones requieren clic manual).

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

El escaneo completo se lanza con "Escanear Sistema". Cada módulo también se puede relanzar individualmente desde su vista en el sidebar.

### 1. Hardware — `analyzer/hardware.py`
CPU, RAM y disco C:\ via `psutil`. Umbrales: warn ≥ 70 % / danger ≥ 90 %.

### 2. Arranque — `analyzer/startup.py`
Lee las tres claves `Run` del registro. Marca como peligrosas las entradas que arrancan desde `%Temp%` o `AppData\Roaming`; como advertencia, apps pesadas conocidas (Spotify, Discord, Steam).

### 3. Seguridad — `analyzer/security.py`
Detecta procesos ejecutándose desde rutas temporales, nombres con entropía de Shannon alta (ratio de vocales < 15 %) y duplicados de procesos críticos del sistema (`lsass.exe`, `csrss.exe`…).

### 4. Controladores — `analyzer/drivers.py`
`Get-WmiObject Win32_PnPSignedDriver` para drivers sin firma + lectura del registro `Uninstall\*` para software sin publisher.

### 5. Protección — `analyzer/protection.py`
Antivirus via `Get-CimInstance AntiVirusProduct` y firewall via `netsh advfirewall` (más rápido que `Get-NetFirewallProfile`). Ambas consultas en paralelo.

### 6. Red — `analyzer/network.py`
Puertos escuchando fuera del rango seguro (`psutil.net_connections`) y entradas no estándar en `C:\Windows\System32\drivers\etc\hosts`.

### 7. Mantenimiento — `analyzer/maintenance.py`
Estado SMART del disco (`Get-PhysicalDisk`), uptime del sistema (alerta si > 7 días sin reiniciar) y tareas programadas habilitadas (`schtasks /query`). Las dos últimas en paralelo.

### 8. Actualizaciones — `analyzer/updates.py`
```
winget list --upgrade-available --disable-interactivity --accept-source-agreements
```
Usa la caché local (sin refrescar fuentes). El parser reconoce encabezados en español e inglés. Cada programa tiene un botón "Actualizar" individual.

### 9. Conectividad — `analyzer/connectivity.py`
Resolución DNS, acceso HTTP a internet, latencia a 8.8.8.8 y latencia al router (detectado via `route print`). Test de velocidad bajo demanda: descarga ~10 MB desde `speed.cloudflare.com` y calcula Mbps.

### 10. Energía y Temperatura — `analyzer/energy.py`
- **Plan de energía:** `powercfg /getactivescheme` — avisa si está en "Ahorro de energía".
- **Batería:** `psutil.sensors_battery()` + `powercfg /batteryreport` para salud (capacidad diseño vs. actual).
- **Temperaturas:** OpenHardwareMonitor WMI (`root\OpenHardwareMonitor`) si está en ejecución; fallback a zonas ACPI (`root\WMI`).

### 11. Privacidad y Limpieza — `analyzer/privacy.py`
- **Telemetría:** nivel configurado en `HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection`.
- **Permisos:** acceso global a cámara, micrófono y ubicación via `CapabilityAccessManager\ConsentStore`.
- **Temporales:** tamaño de `%TEMP%`, `C:\Windows\Temp` y Prefetch con botón "Limpiar ahora".
- **BSODs:** volcados `.dmp` en `C:\Windows\Minidump` de los últimos 30 días.
- **Eventos críticos:** `Get-WinEvent` niveles 1 y 2 del log System (últimas 72 h), un item por evento con proveedor, mensaje y timestamp.

### 12. Monitor de Rendimiento — `analyzer/performance.py`
No forma parte del escaneo general. Se activa desde su vista en el sidebar. Polling cada 2 segundos a `/api/perf/snapshot`. Muestra CPU, RAM, disco y GPU (si OHM está activo) con sparklines canvas sin librerías externas.

---

## Arquitectura de la interfaz

```
┌──────────────────┬──────────────────────────────────────────┐
│ SIDEBAR (240 px) │ TOPBAR: breadcrumb | estado | [Scan]     │
│                  ├──────────────────────────────────────────┤
│ ● Resumen        │                                          │
│                  │  OVERVIEW: tiles con estado de cada      │
│ SISTEMA          │  módulo. Clic → vista de módulo.         │
│  Hardware    ●   │                                          │
│  Arranque    ●   │  MÓDULO: card completo +                 │
│  Drivers     ●   │  [← Resumen]  [Analizar módulo]          │
│                  │                                          │
│ SEGURIDAD        │                                          │
│  Seguridad   ●   │                                          │
│  Protección  ●   │                                          │
│                  │                                          │
│ RED              │                                          │
│  Red         ●   │                                          │
│  Conectividad●   │                                          │
│                  │                                          │
│ RENDIMIENTO      │                                          │
│  Monitor     ●   │                                          │
│  Energía     ●   │                                          │
│                  │                                          │
│ MANTENIMIENTO    │                                          │
│  Mantenim.   ●   │                                          │
│  Updates     ●   │                                          │
│                  │                                          │
│ PRIVACIDAD       │                                          │
│  Privacidad  ●   │                                          │
└──────────────────┴──────────────────────────────────────────┘
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
| GET | `/api/scan/updates` | Paquetes desactualizados |
| GET | `/api/scan/connectivity` | Ping, DNS, latencia |
| GET | `/api/scan/energy` | Plan de energía, batería, temps |
| GET | `/api/scan/privacy` | Telemetría, permisos, temporales, eventos |
| GET | `/api/perf/snapshot` | Snapshot en tiempo real |
| GET | `/api/connectivity/speedtest` | Test de descarga Cloudflare |
| POST | `/api/update/<package_id>` | Actualiza paquete con winget ⚠️ |
| POST | `/api/privacy/clean-temp` | Vacía carpetas temporales ⚠️ |

⚠️ Operaciones de escritura — requieren acción explícita del usuario.

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
