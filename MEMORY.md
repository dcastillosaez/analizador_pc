# MEMORY — PC Guardian

> Proyecto: F:/Documentos/IA/Analisis_PC
> Creado: 2026-04-11

## Descripción del proyecto

Herramienta de diagnóstico local para Windows 10/11. Backend Python (Flask) + frontend HTML/CSS/JS (Dark Glassmorphism). Solo lectura: audita e informa, nunca modifica el sistema sin permiso.

## Arquitectura

```
app.py                     ← Flask: servidor + 4 rutas /api/scan/<módulo>
analyzer/
  hardware.py              ← psutil → CPU, RAM, Disco C:
  startup.py               ← winreg → HKCU/HKLM Run keys
  security.py              ← psutil → procesos sospechosos, rutas peligrosas, duplicados críticos
  drivers.py               ← PowerShell WMI → drivers sin firma, software sin publisher
templates/index.html       ← SPA con 4 tarjetas + barra de progreso
static/css/style.css       ← Dark Glassmorphism, variables CSS, responsive
static/js/app.js           ← Vanilla JS: fetch secuencial, renderizado dinámico
```

## Esquema JSON de respuesta (todos los módulos)

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
      "value": "string corto (ej: '87%', 'Sin firma')",
      "detail": "string técnico opcional"
    }
  ]
}
```

## Paleta de colores y estados

| Estado  | Color    | Hex       |
|---------|----------|-----------|
| ok      | Verde    | #2ed573   |
| warning | Naranja  | #ffa502   |
| danger  | Rojo     | #ff4757   |
| primary | Azul     | #4f8ef7   |
| bg      | Oscuro   | #070b16   |

## Decisiones de diseño

- **Scan secuencial**: los 4 módulos se llaman uno tras otro para mostrar progreso real (25% por módulo).
- **Hardware con gauges**: el módulo de hardware renderiza barras de progreso visuales además de los items.
- **Máx. 6 items visibles**: el resto se oculta detrás de "Mostrar más…" para no saturar la UI.
- **No se usa librería de UI externa**: CSS puro para minimizar dependencias.
- **PowerShell con `-NonInteractive -NoProfile`**: para mayor seguridad y velocidad en las consultas WMI.

## Posibles mejoras futuras

- [ ] Exportar informe a PDF
- [ ] Comparar escaneos en el tiempo
- [ ] Botón "Aplicar corrección" con confirmación (para deshabilitar inicio, etc.)
- [ ] Análisis de puertos de red abiertos
- [ ] Integración con Windows Defender via PowerShell

## Comandos clave

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python app.py
# → Abre http://127.0.0.1:5000 automáticamente
```
