# Funcionalidades por implementar — PC Guardian

---

## Rendimiento y recursos

- [x] **Monitor en tiempo real** — gráficas de CPU/RAM/disco/GPU que se refrescan cada 2 segundos
- [x] **Historial de rendimiento** — guardar snapshots en SQLite y ver tendencias en el tiempo
- [x] **Procesos pesados** — lista en tiempo real de los 10 procesos que más CPU/RAM consumen, con PID, ruta y opción de terminarlos
- [x] **Benchmark rápido** — test de rendimiento de CPU (cálculo de primos) y disco (lectura/escritura secuencial) con puntuación comparable entre sesiones

---

## Sistema y diagnóstico

- [x] **Inventario de hardware** — CPU, GPU, RAM slot a slot, placa base y BIOS vía WMI (módulo manual)
- [x] **Servicios de Windows** — servicios automáticos en ejecución con detección de rutas sospechosas
- [x] **Actualizaciones de Windows** — búsqueda bajo demanda vía COM API de Windows Update, clasificadas por severidad; botón aplicar por actualización
- [x] **Puntuación global del PC** — número resumen 0-100 calculado a partir de todos los módulos analizados
- [x] **Comparar escaneos** — diff visual entre el escaneo actual y uno guardado anteriormente; muestra qué empeoró, mejoró o es nuevo

---

## Almacenamiento

- [x] **Mapa de disco** — visualización treemap de carpetas por tamaño (estilo WinDirStat en el navegador, canvas o SVG)
- [x] **Archivos duplicados** — búsqueda por hash MD5 en carpetas seleccionadas, con grupos de duplicados y opción de eliminar dejando uno
- [x] **Programas instalados** — inventario completo con versión, tamaño en disco y fecha de instalación; opción de desinstalar via winget o `msiexec`

---

## Energía y temperatura

- [x] **Temperaturas del sistema** — CPU, GPU, NVMe vía WMI u OpenHardwareMonitor
- [x] **Informe de batería** — capacidad actual vs diseño, estimación de vida restante (`powercfg /batteryreport`)
- [x] **Plan de energía activo** — detecta si está en modo ahorro cuando debería estar en rendimiento

---

## Privacidad y limpieza

- [x] **Auditoría de privacidad** — telemetría de Windows activa, permisos de apps (cámara, micrófono, ubicación)
- [x] **Limpieza de temporales** — preview del espacio a liberar y botón de limpieza (`%TEMP%`, `C:\Windows\Temp`, Prefetch)
- [x] **Eventos críticos del sistema** — Visor de eventos: un item por evento con proveedor, mensaje y timestamp (últimas 72 h)
- [x] **Acciones rápidas de optimización** — aplicar fixes con un clic desde los resultados: cambiar plan de energía, deshabilitar programa de inicio pesado, ajustar telemetría

---

## Conectividad

- [x] **Test de velocidad de internet** — descarga ~10 MB desde servidores públicos (Hetzner, OVH, Tele2), calcula Mbps y latencia
- [x] **Puertos abiertos** — puertos escuchando fuera del rango seguro con proceso asociado (cubierto en tarjeta Red)
- [x] **Analizador WiFi** — redes cercanas, canal, señal, frecuencia y colisión de canales vía `netsh wlan show networks`
- [x] **Certificados del sistema** — certificados del almacén de Windows próximos a caducar o ya caducados; opción de eliminar
- [x] **Conexiones activas salientes** — qué procesos tienen TCP establecido hacia el exterior ahora mismo, con IP remota y hostname resuelto

---

## Red y seguridad avanzada

- [x] **Reglas de firewall personalizadas** — lista de reglas no estándar añadidas por el usuario o por apps, con opción de eliminarlas
- [x] **DNS activo** — servidor DNS configurado, detección de DNS sobre HTTPS (DoH) y opción de cambiar a 1.1.1.1 o 8.8.8.8

---

## Controladores

- [x] **Categoría y ubicación en Administrador de dispositivos** — tipo de dispositivo y ruta exacta por cada controlador con aviso
- [x] **Actualizar controlador individual** — botón por controlador que lanza `pnputil /scan-devices`
- [x] **Desinstalar controlador individual** — botón por controlador que lanza `pnputil /remove-device`

---

## Actualizaciones de software

- [x] **Actualizar todos los programas** — botón "Actualizar todo" con progreso por paquete y mensajes de error inline

---

## UX / utilidad general

- [x] **Puntuación global del PC** — widget en el overview con score 0-100 y breakdown por categoría
- [x] **Exportar informe** — genera HTML autocontenido con el resultado completo del último escaneo; descarga directa desde el navegador
- [x] **Historial de escaneos** — guardar cada análisis en SQLite y mostrar línea de tiempo; ver si la salud mejora o empeora
- [x] **Notificaciones programadas** — escaneo silencioso al arrancar Windows con notificación toast si hay problemas críticos (tray icon via `pystray`)
- [x] **Modo claro / oscuro** — toggle de tema persistente en localStorage

---

## Seguridad de plataforma

- [x] **Protecciones del sistema** — BitLocker, Secure Boot, TPM, protección en tiempo real, protección contra manipulaciones, acceso controlado a carpetas (ransomware), antigüedad de las definiciones, UAC, SmartScreen y puntos de restauración
- [x] **Firma digital de ejecutables** — Authenticode en el análisis de seguridad: un binario en carpeta temporal es un instalador normal si está firmado, y la combinación típica de malware si no lo está
- [x] **Punto de restauración antes de escribir** — se ofrece crear uno antes de desinstalar un controlador
- [x] **Aviso de privilegios** — banner con reinicio por UAC en lugar de descubrir la falta de permisos módulo a módulo
- [ ] **Punto de restauración en el resto de operaciones** — instalar actualización de Windows, eliminar certificado, desinstalar programa
