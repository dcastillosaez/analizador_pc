# PC Guardian

Herramienta de diagnóstico local para Windows 10/11 con interfaz web. Analiza el estado del sistema e informa en lenguaje claro, sin jerga técnica.

**Versión 1.0.0** — la versión vive en `analyzer/_version.py` y de ahí sale el pie del sidebar, el endpoint `/api/version` y los metadatos del EXE.

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

El escaneo completo se lanza con **Escanear Sistema**. Cada módulo puede relanzarse individualmente desde su vista. Los módulos marcados con _(on-demand)_ no forman parte del escaneo global.

### 1. Hardware — `analyzer/hardware.py`
CPU, RAM y disco C:\ via `psutil`. Umbrales: warn ≥ 70 % / danger ≥ 90 %.

### 2. Arranque — `analyzer/startup.py`
Lee las claves `Run` del registro. Marca como peligrosas las entradas desde `%Temp%` o `AppData\Roaming`; como advertencia, apps pesadas conocidas. Botón **Deshabilitar** por entrada (elimina del registro).

### 3. Seguridad — `analyzer/security.py`
Detecta procesos desde rutas temporales, nombres con entropía de Shannon alta y duplicados de procesos críticos del sistema.

### 4. Controladores — `analyzer/drivers.py`
`Win32_PnPSignedDriver` para drivers sin firma. Categoría del dispositivo y ruta exacta. Botones **Actualizar** (`pnputil /scan-devices`) y **Desinstalar** (`pnputil /remove-device`).

### 5. Protección — `analyzer/protection.py`
Antivirus via `Get-CimInstance AntiVirusProduct` y firewall via `netsh advfirewall`, en paralelo.

### 6. Reglas de firewall _(on-demand)_ — `analyzer/firewall_rules.py`
Lista reglas habilitadas no estándar (sin grupo de Windows/Microsoft) via `Get-NetFirewallRule`. Botón **Eliminar** por regla.

### 7. Red — `analyzer/network.py`
Puertos escuchando fuera del rango seguro y entradas no estándar en el archivo `hosts`.

### 8. Conectividad — `analyzer/connectivity.py`
Resolución DNS, acceso HTTP, latencia y gateway. Test de velocidad bajo demanda con fallback automático entre servidores públicos (Hetzner, OVH, Tele2).

### 9. DNS activo — `analyzer/dns.py`
Servidores DNS configurados por interfaz de red, identificados por proveedor (Google, Cloudflare, Quad9…). Detecta si DoH está activo. Botones para cambiar DNS a Cloudflare (1.1.1.1) o Google (8.8.8.8) por interfaz.

### 10. Analizador WiFi _(on-demand)_ — `analyzer/wifi.py`
Escaneo via `netsh wlan show networks mode=bssid`. Red conectada con señal, canal y protocolo. Tabla de redes cercanas con barras de señal, banda y seguridad. Detecta colisiones de canal.

### 11. Certificados _(on-demand)_ — `analyzer/certs.py`
Almacenes `LocalMachine\My`, `LocalMachine\Root`, `LocalMachine\CA` y `CurrentUser\My`. Muestra caducados o que caducan en < 90 días con emisor y huella. Botón **Eliminar** para caducados.

### 12. Conexiones TCP activas _(on-demand)_ — `analyzer/connections.py`
Conexiones TCP establecidas hacia el exterior con proceso, IP remota y hostname resuelto. Detecta puertos sospechosos (4444, 1080, 31337…).

### 13. Mantenimiento — `analyzer/maintenance.py`
Estado SMART del disco, uptime (alerta > 7 días) y tareas programadas habilitadas.

### 14. Actualizaciones de software — `analyzer/updates.py`
`winget list --upgrade-available`. Parser bilingüe (es/en). Botón **Actualizar** individual y **Actualizar todo** con progreso inline.

### 15. Actualizaciones de Windows _(on-demand)_ — `analyzer/wupdates.py`
Búsqueda via COM API (`Microsoft.Update.Session`). Severidad, número KB con enlace y botón **Aplicar** por actualización.

### 16. Energía y Temperatura — `analyzer/energy.py`
Plan de energía activo, salud de batería (`powercfg /batteryreport`) y temperaturas via OpenHardwareMonitor WMI o ACPI. Botón **Aplicar Alto Rendimiento** cuando el plan no es óptimo.

### 17. Privacidad y Limpieza — `analyzer/privacy.py`
Telemetría, permisos de cámara/micrófono/ubicación, temporales con botón de limpieza, BSODs recientes y eventos críticos (últimas 72 h). Botón **Desactivar telemetría** con escritura en registro.

### 18. Procesos activos — `analyzer/processes.py`
Top 15 procesos ordenados por CPU + RAM. Botón **Terminar** por proceso (con confirmación). Excluye PIDs de sistema.

### 19. Programas instalados _(on-demand)_ — `analyzer/software.py`
Inventario completo vía registro de Windows (3 hives). Versión, fabricante, fecha y tamaño. Buscador en tiempo real. Botón **Desinstalar** vía `winget uninstall`.

### 20. Monitor de Rendimiento _(on-demand)_ — `analyzer/performance.py`
Polling cada 2 s a `/api/perf/snapshot`. Sparklines de CPU, RAM, disco y GPU sin librerías externas.

### 21. Tendencias de rendimiento — `analyzer/perf_history.py`
PC Guardian guarda automáticamente un snapshot cada 5 minutos en SQLite. La vista **Tendencias** muestra gráficas SVG de CPU, RAM, disco y GPU de las últimas 24 h.

### 22. Servicios — `analyzer/services.py`
Servicios automáticos en ejecución con detección de rutas sospechosas.

### 23. Inventario _(on-demand)_ — `analyzer/inventory.py`
CPU, GPU, RAM slot a slot, placa base y BIOS via WMI.

### 24. Aplicaciones predeterminadas _(on-demand)_ — `analyzer/defaults.py`
Qué programa abre cada tipo de archivo y de enlace: navegador, PDF, imágenes, vídeo, comprimidos y documentos. Resuelve el ProgId del registro a nombre comercial y ruta real del ejecutable, incluidos los nombres localizados de las apps del Store.

Marca en rojo los handlers que apuntan a `Temp` o `Downloads` — el patrón del secuestro de asociaciones — y avisa de los ProgId que ya no existen, que dejan el tipo de archivo huérfano.

Solo lectura, y no por pereza: Windows firma cada clave `UserChoice` con un hash sobre SID, extensión y ProgId cuyo algoritmo nunca documentó. Si se escribe el ProgId a mano, el sistema detecta la manipulación y revierte la asociación. El botón de cada fila abre `ms-settings:defaultapps` en la ficha de esa aplicación, que es donde el cambio sí se queda.

### 25. Configuración de BIOS/UEFI _(on-demand)_ — `analyzer/bios.py` + `analyzer/_smbios.py`
Lee la tabla SMBIOS/DMI que publica el firmware con `GetSystemFirmwareTable`, sin drivers ni privilegios, y evalúa doce aspectos del estado efectivo del equipo:

- **Memoria por debajo de su velocidad nominal** — el síntoma de tener el XMP/EXPO desactivado. Sin perfil aplicado, SMBIOS informa de la velocidad JEDEC base, así que la velocidad real del módulo se deduce de su part number.
- **Canales de memoria** — avisa si todos los módulos comparten canal pudiendo repartirse.
- **Núcleos de CPU habilitados frente a los presentes** — detecta un `Active Processor Cores` mal puesto en la BIOS.
- **Slots PCI Express** — el ancho eléctrico y la ocupación de cada uno. Avisa si hay una tarjeta en un slot estrecho habiendo otro más ancho libre.
- **Antigüedad de la BIOS**, modo de arranque UEFI o Legacy/CSM, GPT o MBR en el disco de sistema, virtualización, controlador de almacenamiento y límites de arranque heredados de `msconfig`.
- **Variables UEFI globales** — orden de arranque y Setup Mode, cuando la app corre elevada.

Las opciones del menú de setup no se pueden leer ni cambiar de forma genérica: viven en NVRAM con GUID propietario y formato binario opaco. El módulo detecta si el fabricante las expone por WMI (solo HP, Dell y Lenovo) y, cuando no, lo dice claramente.

---

## Funcionalidades transversales

### Escaneo global y puntuación
El botón **Escanear Sistema** ejecuta los módulos del escaneo general en secuencia y calcula una **puntuación 0-100** ponderada por categoría.

### Historial de escaneos
Cada escaneo global se guarda automáticamente en SQLite. La sección **Historial** muestra fecha, score y estado por módulo. Botón **Comparar** para ver diff visual entre un escaneo histórico y el actual (↑ Mejoró / ↓ Empeoró / → Sin cambio).

### Acciones rápidas (quickfix)
Desde los resultados del análisis, botones para aplicar fixes con un clic:
- **Energía:** cambiar a plan Alto Rendimiento
- **Privacidad:** desactivar telemetría de Windows
- **Arranque:** deshabilitar entrada del registro

### Exportar informe
El botón **Exportar informe** genera un `.html` autocontenido con todos los módulos escaneados. Descarga directa desde el navegador.

### Modo claro / oscuro
Toggle en la barra superior. Persiste en `localStorage`.

---

## Arquitectura de la interfaz

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ SIDEBAR (240 px) │ TOPBAR: breadcrumb | [☀/☾] [Exportar] [Escanear]    │
│                  ├──────────────────────────────────────────────────────┤
│ ● Resumen        │                                                      │
│                  │  OVERVIEW: tiles con estado de cada módulo.          │
│ SISTEMA          │                                                      │
│  Hardware    ●   │  MÓDULO: card completo con [← Resumen] [Analizar]   │
│  Arranque    ●   │                                                      │
│  Drivers     ●   │  HISTORIAL: tabla de escaneos + comparador           │
│  Inventario  ●   │                                                      │
│  Servicios   ●   │  TENDENCIAS: gráficas SVG CPU/RAM/disco 24 h        │
│  Programas   ●   │                                                      │
│                  │                                                      │
│ SEGURIDAD        │                                                      │
│  Seguridad   ●   │                                                      │
│  Protección  ●   │                                                      │
│  Firewall    ●   │                                                      │
│                  │                                                      │
│ RED              │                                                      │
│  Red         ●   │                                                      │
│  Conectividad●   │                                                      │
│  Certificados●   │                                                      │
│  WiFi        ●   │                                                      │
│  DNS activo  ●   │                                                      │
│  Conexiones  ●   │                                                      │
│                  │                                                      │
│ RENDIMIENTO      │                                                      │
│  Monitor     ●   │                                                      │
│  Energía     ●   │                                                      │
│  Procesos    ●   │                                                      │
│  Tendencias      │                                                      │
│                  │                                                      │
│ MANTENIMIENTO    │                                                      │
│  Mantenim.   ●   │                                                      │
│  Updates     ●   │                                                      │
│  Updates Win ●   │                                                      │
│                  │                                                      │
│ PRIVACIDAD       │                                                      │
│  Privacidad  ●   │                                                      │
│                  │                                                      │
│ HISTORIAL        │                                                      │
│  Historial       │                                                      │
└──────────────────┴──────────────────────────────────────────────────────┘
```

`●` = dot de estado (gris / verde / naranja / rojo).

---

## API endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/scan/hardware` | CPU, RAM, disco |
| GET | `/api/scan/startup` | Programas de inicio |
| GET | `/api/scan/security` | Procesos y anomalías |
| GET | `/api/scan/drivers` | Controladores |
| GET | `/api/scan/protection` | Antivirus y firewall |
| GET | `/api/scan/network` | Puertos y hosts |
| GET | `/api/scan/maintenance` | SMART, uptime, tareas |
| GET | `/api/scan/updates` | Paquetes desactualizados (winget) |
| GET | `/api/scan/wupdates` | Actualizaciones Windows (COM API) |
| GET | `/api/scan/connectivity` | DNS, ping, latencia, gateway |
| GET | `/api/scan/energy` | Plan de energía, batería, temps |
| GET | `/api/scan/privacy` | Telemetría, permisos, temporales, eventos |
| GET | `/api/scan/wifi` | Redes WiFi cercanas |
| GET | `/api/scan/certs` | Certificados del almacén de Windows |
| GET | `/api/scan/inventory` | Inventario hardware detallado |
| GET | `/api/scan/services` | Servicios de Windows |
| GET | `/api/scan/connections` | TCP establecido hacia el exterior |
| GET | `/api/scan/processes` | Top 15 procesos por CPU+RAM |
| GET | `/api/scan/software` | Inventario de programas instalados |
| GET | `/api/scan/dns` | Servidores DNS por interfaz + DoH |
| GET | `/api/scan/firewall-rules` | Reglas de firewall no estándar |
| GET | `/api/scan/defaults` | Aplicaciones predeterminadas por tipo |
| GET | `/api/scan/bios` | Configuración de BIOS/UEFI |
| GET | `/api/version` | Nombre y versión de la aplicación |
| GET | `/api/perf/snapshot` | Snapshot tiempo real (polling 2 s) |
| GET | `/api/perf/history` | Snapshots últimas 24 h |
| GET | `/api/connectivity/speedtest` | Test de descarga |
| GET | `/api/history` | Lista escaneos guardados |
| DELETE | `/api/history/<id>` | Elimina escaneo del historial |
| POST | `/api/history/save` | Guarda escaneo actual |
| POST | `/api/update/<package_id>` | Actualiza paquete winget ⚠️ |
| POST | `/api/wupdate/apply/<update_id>` | Aplica actualización Windows ⚠️ |
| POST | `/api/driver/update` | Actualiza controlador ⚠️ |
| POST | `/api/driver/uninstall` | Desinstala dispositivo ⚠️ |
| POST | `/api/cert/delete` | Elimina certificado ⚠️ |
| POST | `/api/privacy/clean-temp` | Vacía temporales ⚠️ |
| POST | `/api/processes/<pid>/kill` | Termina proceso ⚠️ |
| POST | `/api/software/uninstall` | Desinstala programa ⚠️ |
| POST | `/api/dns/set` | Cambia DNS de una interfaz ⚠️ |
| POST | `/api/firewall-rules/delete` | Elimina regla de firewall ⚠️ |
| POST | `/api/defaults/open-settings` | Abre Configuración de apps predeterminadas |
| POST | `/api/quickfix/energy-high` | Activa Alto Rendimiento ⚠️ |
| POST | `/api/quickfix/disable-startup` | Deshabilita entrada de arranque ⚠️ |
| POST | `/api/quickfix/telemetry-off` | Desactiva telemetría Windows ⚠️ |

⚠️ Operaciones de escritura — requieren confirmación explícita del usuario en la interfaz.

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
