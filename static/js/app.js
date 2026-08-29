'use strict';

/* ══════════════════════════════════════════════════════════════════════════
   NAVEGACIÓN — Sidebar + Overview + Module View
   (Se añade al inicio; no modifica las funciones existentes)
   ══════════════════════════════════════════════════════════════════════════ */

// ── Metadatos de módulos ─────────────────────────────────────────────────────
const MODULE_META = {
  hardware:     { label: 'Hardware',         group: 'Sistema',       emoji: '💻', color: '#4f8ef7' },
  startup:      { label: 'Arranque',         group: 'Sistema',       emoji: '🚀', color: '#f7a34f' },
  drivers:      { label: 'Controladores',    group: 'Sistema',       emoji: '⚙️', color: '#a29bfe' },
  security:     { label: 'Seguridad',        group: 'Seguridad',     emoji: '🛡️', color: '#ff4757' },
  protection:   { label: 'Protección',       group: 'Seguridad',     emoji: '🔒', color: '#fd79a8' },
  network:      { label: 'Red',              group: 'Red',           emoji: '🌐', color: '#00cec9' },
  connectivity: { label: 'Conectividad',     group: 'Red',           emoji: '📶', color: '#0984e3' },
  perf:         { label: 'Monitor vivo',     group: 'Rendimiento',   emoji: '📊', color: '#00b894' },
  energy:       { label: 'Energía y Temp.',  group: 'Rendimiento',   emoji: '⚡', color: '#e17055' },
  maintenance:  { label: 'Mantenimiento',    group: 'Mantenimiento', emoji: '🔧', color: '#fdcb6e' },
  updates:      { label: 'Actualizaciones',  group: 'Mantenimiento', emoji: '🔄', color: '#2ed573' },
  privacy:      { label: 'Privacidad',       group: 'Privacidad',    emoji: '🔐', color: '#6c5ce7' },
  inventory:    { label: 'Inventario',       group: 'Sistema',       emoji: '🖥️', color: '#636e72' },
  services:     { label: 'Servicios',        group: 'Sistema',       emoji: '⚙️', color: '#00b894' },
  wupdates:     { label: 'Updates Windows',  group: 'Mantenimiento', emoji: '🪟', color: '#0078d4' },
  wifi:         { label: 'Analizador WiFi', group: 'Red',           emoji: '📶', color: '#00cec9' },
  certs:        { label: 'Certificados',   group: 'Red',           emoji: '🏅', color: '#fdcb6e' },
  processes:    { label: 'Procesos',        group: 'Rendimiento',   emoji: '🖥️', color: '#00b894' },
  connections:  { label: 'Conexiones',      group: 'Red',           emoji: '🔗', color: '#0984e3' },
  hardening:    { label: 'Protecciones',    group: 'Seguridad',     emoji: '🔐', color: '#fd79a8' },
};

// IDs del escaneo general (excluye perf que es on-demand)
const SCAN_MODULE_IDS = ['hardware','startup','security','drivers','protection','network','maintenance','updates','connectivity','energy','privacy','services','connections','hardening'];

// Estado de navegación
let activeView = 'overview';

// ── Helpers de DOM ───────────────────────────────────────────────────────────
function _qs(sel) { return document.querySelector(sel); }
function _id(id)  { return document.getElementById(id); }

// ── Sidebar toggle ───────────────────────────────────────────────────────────
function toggleSidebar() {
  const shell = _id('app-shell');
  const isMobile = window.innerWidth <= 900;
  if (isMobile) {
    shell.classList.toggle('mobile-open');
  } else {
    shell.classList.toggle('collapsed');
  }
}

function closeSidebar() {
  _id('app-shell').classList.remove('mobile-open');
}

// ── Navegación principal ─────────────────────────────────────────────────────
function navigateTo(id) {
  activeView = id;

  // Breadcrumb
  const crumb = _id('breadcrumb-label');
  if (crumb) {
    crumb.textContent = id === 'overview'
      ? 'Resumen'
      : id === 'history'
        ? 'Historial de escaneos'
        : (MODULE_META[id] ? MODULE_META[id].label : id);
  }

  // Sidebar footer — última vez escaneado
  // (actualizado en updateLastScan)

  // Marcar nav-item activo
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const navItem = _id(`nav-item-${id}`);
  if (navItem) navItem.classList.add('active');

  // Render vista
  if (id === 'overview') {
    renderOverview();
  } else if (id === 'history') {
    renderHistoryView();
  } else {
    showModuleView(id);
  }

  // En móvil cerrar sidebar al navegar
  if (window.innerWidth <= 900) closeSidebar();
}

// ── Renderiza el grid de resumen ─────────────────────────────────────────────
function renderOverview() {
  const area = _id('content-area');
  if (!area) return;

  // Devolver cualquier card que esté en content-area al pool
  _returnCardsToPool();

  const tileIDs = Object.keys(MODULE_META);
  const tiles = tileIDs.map(id => {
    const meta   = MODULE_META[id];
    // scanResults viene del código existente (declarado justo después)
    const result = (typeof scanResults !== 'undefined') ? scanResults[id] : null;
    const status = result ? result.status : 'pending';
    const issues = result ? (result.issue_count || 0) : null;

    const dotClass = `overview-tile-dot dot-${status}`;
    const tileClass = `overview-tile tile-${status}`;

    let subText = 'Pendiente de análisis';
    if (result) {
      subText = issues > 0
        ? `${issues} punto${issues > 1 ? 's' : ''} a revisar`
        : (status === 'ok' ? 'Sin problemas detectados' : result.summary || '');
    }

    return `
      <div class="${tileClass}" onclick="navigateTo('${id}')" tabindex="0" role="button" aria-label="Ver ${meta.label}">
        <div class="overview-tile-header">
          <span class="overview-tile-emoji">${meta.emoji}</span>
          <span class="${dotClass}"></span>
        </div>
        <div class="overview-tile-label">${meta.label}</div>
        <div class="overview-tile-sub">${escHtml(subText)}</div>
        <div class="overview-tile-footer">
          <button class="overview-tile-btn" onclick="event.stopPropagation();navigateTo('${id}')">Ver detalles</button>
        </div>
      </div>`;
  }).join('');

  area.innerHTML = `<div class="overview-grid">${tiles}</div>`;
}

// ── Muestra un módulo individual en content-area ─────────────────────────────
function showModuleView(id) {
  const area = _id('content-area');
  if (!area) return;

  _returnCardsToPool();

  const card = _id(`card-${id}`);
  if (!card) return;

  const wrapper = document.createElement('div');
  wrapper.className = 'module-view';

  // Barra superior: volver + escanear módulo
  const bar = document.createElement('div');
  bar.className = 'module-view-bar';

  const backBtn = document.createElement('button');
  backBtn.className = 'module-back-btn';
  backBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg> Resumen`;
  backBtn.onclick = () => navigateTo('overview');

  const scanBtn = document.createElement('button');
  scanBtn.className = 'module-scan-btn';
  scanBtn.id = `module-scan-btn-${id}`;
  scanBtn.innerHTML = _scanBtnIcon() + _scanBtnLabel(id);
  scanBtn.onclick = () => _triggerModuleScan(id);

  bar.appendChild(backBtn);
  bar.appendChild(scanBtn);
  wrapper.appendChild(bar);
  wrapper.appendChild(card);
  area.appendChild(wrapper);
}

function _scanBtnIcon() {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" width="14" height="14"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`;
}

function _scanBtnLabel(id) {
  if (id === 'perf')      return ' Iniciar monitor';
  if (id === 'updates')   return ' Analizar';
  if (id === 'inventory') return ' Escanear inventario';
  if (id === 'wupdates')  return ' Comprobar';
  if (id === 'wifi')      return ' Analizar';
  if (id === 'certs')     return ' Analizar';
  return ' Analizar módulo';
}

async function _triggerModuleScan(id) {
  const btn = _id(`module-scan-btn-${id}`);

  if (id === 'perf')     { if (typeof togglePerf   === 'function') togglePerf();   return; }
  if (id === 'updates')  { if (typeof scanUpdates  === 'function') scanUpdates();  return; }
  if (id === 'wupdates') { if (typeof checkWindowsUpdates === 'function') checkWindowsUpdates(); return; }
  if (id === 'wifi')     { if (typeof scanWifi  === 'function') scanWifi();  return; }
  if (id === 'certs')    { if (typeof scanCerts === 'function') scanCerts(); return; }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Analizando…`;
  }
  try {
    const data = await fetchModule(id, { fresh: true });
    if (typeof renderCard === 'function') renderCard(id, data);
    if (typeof scanResults !== 'undefined') scanResults[id] = data;
    calculateScore();
  } catch(e) {
    console.warn('_triggerModuleScan error:', id, e);
  }
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = _scanBtnIcon() + _scanBtnLabel(id);
  }
}

// ── Devuelve todos los cards del content-area al pool ────────────────────────
function _returnCardsToPool() {
  const area = _id('content-area');
  const pool = _id('cards-pool');
  if (!area || !pool) return;

  // Mover de vuelta al pool los cards que estén en content-area
  const ids = Object.keys(MODULE_META).concat(['perf', 'inventory', 'wupdates', 'services']);
  ids.forEach(id => {
    const card = _id(`card-${id}`);
    if (card && area.contains(card)) {
      pool.appendChild(card);
    }
  });

  area.innerHTML = '';
}

// ── Actualiza el dot del nav sidebar ─────────────────────────────────────────
function updateNavDot(id, status) {
  const dot = _id(`nav-dot-${id}`);
  if (!dot) return;
  dot.className = `nav-dot dot-${status}`;
}

// ── Escaneo individual desde overview ────────────────────────────────────────
async function scanSingleModule(id) {
  if (id === 'perf') {
    navigateTo('perf');
    if (typeof togglePerf === 'function') togglePerf();
    return;
  }
  try {
    const data = await fetchModule(id);
    if (typeof renderCard === 'function') renderCard(id, data);
    updateNavDot(id, data.status);
    if (typeof scanResults !== 'undefined') scanResults[id] = data;
    if (activeView === 'overview') renderOverview();
  } catch (e) {
    console.warn('scanSingleModule error:', id, e);
  }
}

// ── Inicialización ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  navigateTo('overview');
});

/* ─────────────────────────────────────────────────────────────────────────────
   Patch de renderCard: después del render original actualiza nav dots y overview
   ───────────────────────────────────────────────────────────────────────────── */
// Se ejecuta después de que el código legacy defina renderCard,
// por lo que usamos un MutationObserver diferido o simplemente lo aplicamos
// al final de DOMContentLoaded cuando las funciones ya existen.
// Alternativa limpia: wrappear renderCard una vez que exista.
(function patchRenderCard() {
  // Esperamos a que renderCard esté definida (está en el mismo archivo, más abajo)
  // La estrategia más fiable: sobreescribimos en DOMContentLoaded, cuando todo está parsado.
  window.addEventListener('DOMContentLoaded', () => {
    const _origRenderCard = window.renderCard || renderCard;
    if (typeof _origRenderCard !== 'function') return;

    // renderCard ya es la función global del código legacy; la envolvemos
    // usando una variable local para no crear recursión.
    const _wrapped = function(id, data) {
      _origRenderCard(id, data);
      // Actualizar dot del sidebar
      if (data && data.status) updateNavDot(id, data.status);
      // Refrescar overview si está activo
      if (activeView === 'overview') renderOverview();
      // Actualizar sidebar footer con hora
      _updateSidebarTime();
    };

    // Solo asignar si renderCard es una función global accesible
    try { window.renderCard = _wrapped; } catch(e) { /* strict mode */ }
  });
})();

function _updateSidebarTime() {
  const el = _id('sidebar-last-scan');
  if (!el) return;
  const now = new Date();
  el.textContent = `Último: ${now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`;
}

/* ══════════════════════════════════════════════════════════════════════════ */

/* ── Configuración de módulos ────────────────────────────────────────────── */
const MODULES = [
  { id: 'hardware',     label: 'Analizando hardware…',                   step: 'pstep-hardware'     },
  { id: 'startup',      label: 'Revisando programas de inicio…',         step: 'pstep-startup'      },
  { id: 'security',     label: 'Buscando amenazas en procesos…',         step: 'pstep-security'     },
  { id: 'drivers',      label: 'Verificando controladores…',             step: 'pstep-drivers'      },
  { id: 'protection',   label: 'Comprobando antivirus y firewall…',      step: 'pstep-protection'   },
  { id: 'network',      label: 'Analizando puertos y red…',              step: 'pstep-network'      },
  { id: 'maintenance',  label: 'Revisando disco y tareas programadas…',  step: 'pstep-maintenance'  },
  { id: 'updates',      label: 'Consultando actualizaciones (winget)…',  step: 'pstep-updates'      },
  { id: 'connectivity', label: 'Comprobando conexión a internet y latencia…', step: 'pstep-connectivity' },
  { id: 'energy',       label: 'Leyendo sensores de energía y temperatura…',  step: 'pstep-energy'       },
  { id: 'privacy',      label: 'Auditando privacidad y archivos temporales…', step: 'pstep-privacy'      },
  { id: 'services',     label: 'Inspeccionando servicios de Windows…',       step: 'pstep-services'     },
  { id: 'connections',  label: 'Revisando conexiones salientes activas…',    step: 'pstep-connections'  },
  { id: 'hardening',    label: 'Comprobando protecciones de Windows…',       step: 'pstep-hardening'    },
];

let scanResults = {};
let scanning    = false;

// Comandos que muestra el terminal por módulo
const MODULE_CMDS = {
  hardware:    ['psutil.cpu_percent(interval=1)', 'psutil.virtual_memory()', 'psutil.disk_usage("C:\\\\")'],
  startup:     ['winreg HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run', 'winreg HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run'],
  security:    ['psutil.process_iter(["pid","name","exe"])', 'entropy_check(process_names)', 'powershell Get-AuthenticodeSignature', 'critical_process_count()'],
  drivers:     ['powershell Get-WmiObject Win32_PnPSignedDriver', 'winreg HKLM:\\Software\\...\\Uninstall\\*'],
  protection:  ['powershell Get-CimInstance AntiVirusProduct', 'powershell Get-NetFirewallProfile'],
  network:     ['psutil.net_connections(kind="inet")', 'open("C:\\\\Windows\\\\System32\\\\drivers\\\\etc\\\\hosts")'],
  maintenance: ['powershell Get-PhysicalDisk', 'psutil.boot_time()', 'schtasks /query /fo CSV /nh'],
  updates:     ['winget list --upgrade-available --source winget'],
  connectivity: ['ping -n 4 8.8.8.8', 'socket.gethostbyname("www.google.com")', 'route print 0.0.0.0'],
  energy:       ['powercfg /getactivescheme', 'psutil.sensors_battery()', 'wmi.WMI(namespace="root\\\\OpenHardwareMonitor").Sensor()'],
  processes:    ['psutil.process_iter(["pid","name"])', 'proc.cpu_percent(interval=0.6)', 'proc.memory_info().rss'],
  connections:  ['psutil.net_connections(kind="tcp")', 'socket.gethostbyaddr(remote_ip)'],
  hardening:    ['powershell Confirm-SecureBootUEFI', 'powershell Get-BitLockerVolume', 'powershell Get-MpComputerStatus', 'winreg HKLM\\...\\Policies\\System EnableLUA'],
  privacy:      ['winreg HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection', 'winreg HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore', 'Get-WinEvent -FilterHashtable @{LogName="System";Level=1,2}'],
};

/* ── Punto de entrada ────────────────────────────────────────────────────── */
// Modulos simultaneos durante el escaneo global. Varios tardan segundos
// esperando a WMI, winget o la red; en serie el escaneo completo se va a
// minutos. Con 4 en vuelo el cuello de botella pasa a ser el modulo mas lento.
const SCAN_CONCURRENCY = 4;

/** Ejecuta `worker` sobre cada elemento con como mucho `limit` en vuelo. */
async function runPool(items, limit, worker) {
  let next = 0;
  const lanes = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const i = next++;
      await worker(items[i], i);
    }
  });
  await Promise.all(lanes);
}

async function startScan() {
  if (scanning) return;
  scanning = true;
  scanResults = {};

  setScanningUI(true);
  showProgress(true);
  hideSummary();
  clearTerminal();
  resetSteps();

  termLog('info', '=== PC Guardian — análisis iniciado ===');

  let done = 0;
  const total = MODULES.length;

  await runPool(MODULES, SCAN_CONCURRENCY, async (mod) => {
    setProgress(mod.label, Math.round((done / total) * 100));
    setStepState(mod.step, 'active');

    const t0 = performance.now();
    const cmds = MODULE_CMDS[mod.id] || [];
    cmds.forEach(c => termLog('cmd', `> ${c}`));

    try {
      const data = await fetchModule(mod.id, { fresh: true });
      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
      scanResults[mod.id] = data;
      renderCard(mod.id, data);
      setStepDone(mod.step, mod.id, elapsed);
      const icon = data.status === 'ok' ? '✓' : data.status === 'danger' ? '✗' : '~';
      termLog(data.status === 'danger' ? 'error' : data.status === 'warning' ? 'warn' : 'ok',
        `${icon} ${data.title} completado en ${elapsed}s — ${data.summary}`);
    } catch (err) {
      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
      renderCardError(mod.id, err.message);
      setStepState(mod.step, 'error');
      termLog('error', `✗ Error en ${mod.id} (${elapsed}s): ${err.message}`);
    }

    done++;
    setProgress(null, Math.round((done / total) * 100));
  });

  termLog('info', '=== Análisis completado ===');
  setScanningUI(false);
  showProgress(false);
  renderSummary();
  updateLastScan();
  calculateScore();
  if (typeof saveScanToHistory === 'function') saveScanToHistory();
  scanning = false;
}

/* ── Fetch ───────────────────────────────────────────────────────────────── */
// fresh:true salta la cache del servidor. Se usa en las acciones explicitas
// del usuario (escaneo global, boton "Analizar modulo"); la navegacion normal
// reutiliza el resultado reciente en lugar de repetir consultas caras a WMI.
async function fetchModule(id, { fresh = false } = {}) {
  const res = await fetch(`/api/scan/${id}${fresh ? '?fresh=1' : ''}`);
  let data = null;
  try { data = await res.json(); } catch (e) { /* respuesta no JSON */ }
  if (!res.ok) throw new Error((data && data.message) || `HTTP ${res.status}`);
  return data;
}

/* ── Render de tarjeta ───────────────────────────────────────────────────── */
function renderCard(id, data) {
  const body  = document.getElementById(`body-${id}`);
  const badge = document.getElementById(`badge-${id}`);
  const card  = document.getElementById(`card-${id}`);

  // Estado general de la tarjeta
  card.className = `card ${data.status}-card`;

  // Badge
  badge.innerHTML = badgeHTML(data.status, data.issue_count);

  // Cuerpo
  if (id === 'hardware') {
    body.innerHTML = renderHardware(data);
  } else if (id === 'drivers') {
    body.innerHTML = renderDrivers(data);
  } else if (id === 'updates') {
    renderUpdates(data, body, badge);
    return;
  } else if (id === 'connectivity') {
    body.innerHTML = renderGeneric(data);
    document.getElementById('btn-speedtest').style.display = '';
  } else if (id === 'energy') {
    body.innerHTML = renderEnergy(data);
  } else if (id === 'privacy') {
    body.innerHTML = renderPrivacy(data);
  } else if (id === 'inventory') {
    body.innerHTML = renderInventory(data);
  } else if (id === 'wupdates') {
    body.innerHTML = renderWupdates(data);
    const btnW = document.getElementById('btn-wupdates');
    if (btnW) btnW.style.display = '';
  } else if (id === 'wifi') {
    body.innerHTML = renderWifi(data);
    const btnWifi = document.getElementById('btn-wifi');
    if (btnWifi) btnWifi.style.display = '';
  } else if (id === 'processes') {
    body.innerHTML = renderProcesses(data);
  } else if (id === 'connections') {
    body.innerHTML = renderConnections(data);
  } else if (id === 'certs') {
    body.innerHTML = renderCerts(data);
    const btnC = document.getElementById('btn-certs');
    if (btnC) btnC.style.display = '';
  } else {
    body.innerHTML = renderGeneric(data);
  }

  // Bind "mostrar más"
  const showBtn = body.querySelector('.show-more-btn');
  if (showBtn) {
    showBtn.addEventListener('click', () => {
      body.querySelectorAll('.item.hidden-item').forEach(el => {
        el.classList.remove('hidden-item');
        el.style.display = '';
      });
      showBtn.remove();
    });
  }
}

function renderCardError(id, msg) {
  const body = document.getElementById(`body-${id}`);
  body.innerHTML = `
    <div class="empty-state">
      <span class="empty-emoji">⚠️</span>
      <p>No se pudo completar el análisis${msg ? ': ' + msg : '.'}</p>
    </div>`;
}

/* ── HTML de hardware (con gauges) ──────────────────────────────────────── */
function renderHardware(data) {
  const summary = `<div class="card-summary">${escHtml(data.summary)}</div>`;
  const gauges = data.items.map(item => `
    <div class="gauge-row" title="${escHtml(item.detail || '')}">
      <span class="gauge-label">${escHtml(item.name)}</span>
      <div class="gauge-track">
        <div class="gauge-fill ${item.status}" style="width:${escHtml(item.value)}"></div>
      </div>
      <span class="gauge-val ${item.status}">${escHtml(item.value)}</span>
    </div>
  `).join('');

  const msgs = data.items.map(item => itemHTML(item)).join('');

  return `${summary}
    <div style="padding: 12px 0 8px;">${gauges}</div>
    <div class="items-list">${msgs}</div>`;
}

/* ── HTML genérico para el resto de tarjetas ─────────────────────────────── */
const STATUS_PRIORITY = { danger: 0, warning: 1, ok: 2 };

function renderGeneric(data) {
  if (!data.items || data.items.length === 0) {
    const icon = data.status === 'ok' ? '✅' : '📋';
    return `<div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:24px">
        <span class="empty-emoji">${icon}</span>
        <p>${escHtml(data.summary)}</p>
      </div>`;
  }

  const sorted = [...data.items].sort(
    (a, b) => (STATUS_PRIORITY[a.status] ?? 3) - (STATUS_PRIORITY[b.status] ?? 3)
  );
  const MAX_VISIBLE = 6;
  const visible  = sorted.slice(0, MAX_VISIBLE);
  const overflow = sorted.slice(MAX_VISIBLE);

  const visHTML  = visible.map(i => itemHTML(i)).join('');
  const ovHTML   = overflow.map(i => itemHTML(i, true)).join('');
  const showMore = overflow.length
    ? `<button class="show-more-btn">Mostrar ${overflow.length} más…</button>`
    : '';

  return `<div class="card-summary">${escHtml(data.summary)}</div>
    <div class="items-list">${visHTML}${ovHTML}${showMore}</div>`;
}

function itemHTML(item, hidden = false) {
  const icon = statusIcon(item.status);
  const detail = item.detail
    ? `<div class="item-detail">${escHtml(item.detail)}</div>`
    : '';
  return `
    <div class="item ${item.status}${hidden ? ' hidden-item' : ''}" style="${hidden ? 'display:none' : ''}">
      <div class="item-icon ${item.status}">${icon}</div>
      <div class="item-body">
        <div class="item-name">${escHtml(item.name)}</div>
        <div class="item-msg">${escHtml(item.message)}</div>
        ${detail}
      </div>
      <span class="item-value ${item.status}">${escHtml(item.value || '')}</span>
    </div>`;
}

/* ── Resumen global ──────────────────────────────────────────────────────── */
function renderSummary() {
  const bar   = document.getElementById('summary-bar');
  const pill  = document.getElementById('overall-pill');
  const title = document.getElementById('summary-title');
  const desc  = document.getElementById('summary-desc');
  const chips = document.getElementById('summary-chips');
  const icon  = document.getElementById('summary-icon-wrap');

  const results   = Object.values(scanResults);
  const dangers   = results.filter(r => r.status === 'danger').length;
  const warnings  = results.filter(r => r.status === 'warning').length;
  const totalIssues = results.reduce((acc, r) => acc + (r.issue_count || 0), 0);

  let overall, emoji, titleText, descText;

  if (dangers > 0) {
    overall   = 'danger';
    emoji     = '🚨';
    titleText = `Se encontraron problemas críticos`;
    descText  = `Hay ${dangers} categoría(s) en estado peligroso y ${warnings} con advertencias. Revisa los detalles de cada sección.`;
  } else if (warnings > 0) {
    overall   = 'warning';
    emoji     = '⚠️';
    titleText = `Tu PC puede mejorar su rendimiento`;
    descText  = `${warnings} categoría(s) con puntos de mejora. No son urgentes, pero solucionarlos notará la diferencia.`;
  } else {
    overall   = 'ok';
    emoji     = '✅';
    titleText = `¡Tu PC está en excelente estado!`;
    descText  = `No se detectaron problemas en ninguna categoría. Puedes escanear de nuevo en cualquier momento.`;
  }

  bar.className = `summary-bar ${overall}`;
  icon.textContent = emoji;
  title.textContent = titleText;
  desc.textContent  = descText;

  chips.innerHTML = [
    dangers  > 0 ? `<span class="chip danger">🔴 ${dangers} Crítico(s)</span>` : '',
    warnings > 0 ? `<span class="chip warning">🟡 ${warnings} Aviso(s)</span>` : '',
    totalIssues === 0 ? `<span class="chip ok">🟢 Sin problemas</span>` : '',
  ].join('');

  // Pill en header
  pill.className = `overall-pill ${overall}`;
  pill.querySelector('.overall-dot').style.cssText = '';
  pill.querySelector('.overall-label').textContent =
    overall === 'ok' ? 'Óptimo' : overall === 'warning' ? 'Avisos' : 'Peligro';

  bar.classList.remove('hidden');
  pill.classList.remove('hidden');
}

function hideSummary() {
  document.getElementById('summary-bar').classList.add('hidden');
}

/* ── Progreso ────────────────────────────────────────────────────────────── */
function showProgress(show) {
  document.getElementById('progress-section').classList.toggle('hidden', !show);
  if (show) resetSteps();
}

function setProgress(label, pct) {
  if (label) document.getElementById('progress-label').textContent = label;
  document.getElementById('progress-fill').style.width = pct + '%';
  document.getElementById('progress-pct').textContent  = pct + ' %';
}

function setStepState(stepId, state) {
  const el = document.getElementById(stepId);
  if (!el) return;
  el.className = `pstep ${state}`;
}

function setStepDone(stepId, modId, elapsed) {
  setStepState(stepId, 'done');
  const t = document.getElementById(`ptime-${modId}`);
  if (t) t.textContent = `${elapsed}s`;
}

function resetSteps() {
  MODULES.forEach(m => {
    const el = document.getElementById(m.step);
    if (el) el.className = 'pstep';
    const t = document.getElementById(`ptime-${m.id}`);
    if (t) t.textContent = '';
  });
}

/* ── Terminal ────────────────────────────────────────────────────────────── */
function toggleTerminal() {
  const panel = document.getElementById('terminal-panel');
  const btn   = document.getElementById('btn-terminal');
  const hidden = panel.classList.toggle('hidden');
  btn.textContent = hidden ? 'Ver detalles ▾' : 'Ocultar ▴';
}

function termLog(type, msg) {
  const body = document.getElementById('terminal-body');
  if (!body) return;
  const now = new Date().toLocaleTimeString('es-ES');
  const span = document.createElement('div');
  span.className = `tlog-${type}`;
  span.textContent = `[${now}] ${msg}`;
  body.appendChild(span);
  body.scrollTop = body.scrollHeight;
}

function clearTerminal() {
  const body = document.getElementById('terminal-body');
  if (body) body.innerHTML = '';
}

/* ── UI de escaneo ───────────────────────────────────────────────────────── */
function setScanningUI(isScanning) {
  const btn     = document.getElementById('scan-btn');
  const scanIco = btn.querySelector('.scan-icon');
  const spinIco = btn.querySelector('.spin-icon');
  const label   = btn.querySelector('.btn-label');

  btn.disabled = isScanning;
  scanIco.classList.toggle('hidden', isScanning);
  spinIco.classList.toggle('hidden', !isScanning);
  label.textContent = isScanning ? 'Analizando…' : 'Escanear Sistema';
}

/* ── Última ejecución ────────────────────────────────────────────────────── */
function updateLastScan() {
  const el = document.getElementById('last-scan-text');
  const now = new Date();
  el.textContent = `Último análisis: ${now.toLocaleTimeString('es-ES')}`;
  // Actualizar también el footer del sidebar
  if (typeof _updateSidebarTime === 'function') _updateSidebarTime();
}

/* ── Actualizaciones (módulo independiente) ──────────────────────────────── */
async function scanUpdates() {
  const btn  = document.getElementById('btn-updates');
  const body = document.getElementById('body-updates');
  const badge = document.getElementById('badge-updates');

  btn.disabled = true;
  btn.textContent = 'Analizando…';
  body.innerHTML = `
    <div class="empty-state">
      <span class="empty-emoji">🔍</span>
      <p>Consultando winget. Esto puede tardar un momento…</p>
    </div>`;

  try {
    const data = await fetchModule('updates', { fresh: true });
    renderUpdates(data, body, badge);
  } catch (e) {
    body.innerHTML = `<div class="empty-state"><span class="empty-emoji">⚠️</span><p>No se pudo conectar con el servidor.</p></div>`;
    badge.innerHTML = badgeHTML('warning', 0);
  }

  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
    <polyline points="23 4 23 10 17 10"/>
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
  </svg> Actualizar lista`;
}

/* ── Renderer de Controladores ───────────────────────────────────────────── */
function renderDrivers(data) {
  if (!data.items || data.items.length === 0) {
    return `
      <div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px">
        <span class="empty-emoji">✅</span>
        <p>Todos los controladores están firmados y con versión registrada.</p>
      </div>`;
  }

  const rows = data.items.map((item, idx) => {
    const hasDevice = !!item.device_id;
    const statusColor = item.status === 'danger' ? '#e74c3c' : item.status === 'warning' ? '#f39c12' : '#2ecc71';

    const categoryBadge = item.devmgr_category
      ? `<span class="drv-category-badge" title="Ubicación en Administrador de dispositivos">${escHtml(item.devmgr_category)}</span>`
      : '';
    const classBadge = item.class_label
      ? `<span class="drv-class-label">${escHtml(item.class_label)}</span>`
      : '';

    const actionBtns = hasDevice ? `
      <button class="btn-drv btn-drv-update" id="drvupd-${idx}"
              onclick="doDriverUpdate('${escHtml(item.device_id)}', ${idx})">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
          <path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>
          <path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>
        </svg>
        Actualizar
      </button>
      <button class="btn-drv btn-drv-uninstall" id="drvunin-${idx}"
              onclick="doDriverUninstall('${escHtml(item.device_id)}', '${escHtml(item.name)}', ${idx})">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
          <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
        </svg>
        Desinstalar
      </button>` : '';

    return `
      <div class="drv-row" id="drv-row-${idx}">
        <div class="drv-header">
          <span class="drv-dot" style="background:${statusColor}"></span>
          <span class="drv-name">${escHtml(item.name)}</span>
          <span class="drv-value ${item.status}">${escHtml(item.value)}</span>
        </div>
        <div class="drv-meta">
          ${classBadge}
          ${categoryBadge}
        </div>
        <div class="drv-msg">${escHtml(item.message)}</div>
        ${item.detail ? `<div class="drv-detail">${escHtml(item.detail)}</div>` : ''}
        ${actionBtns ? `<div class="drv-actions">${actionBtns}</div>` : ''}
      </div>`;
  }).join('');

  return `
    <div class="card-summary">${escHtml(data.summary)}</div>
    <div class="drv-list">${rows}</div>`;
}

async function doDriverUpdate(deviceId, idx) {
  const btn = document.getElementById(`drvupd-${idx}`);
  if (!btn) return;
  btn.disabled = true;
  btn.className = 'btn-drv btn-drv-update updating';
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="12" height="12" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Buscando…`;

  try {
    const res = await fetch('/api/driver/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId }),
    });
    const data = await res.json();
    if (data.success) {
      btn.className = 'btn-drv btn-drv-update done';
      btn.textContent = '✓ Buscado';
      btn.title = data.message;
    } else {
      btn.className = 'btn-drv btn-drv-update error';
      btn.textContent = '✗ Error';
      btn.disabled = false;
      alert('No se pudo actualizar el controlador:\n\n' + (data.message || 'Error desconocido'));
    }
  } catch (e) {
    btn.className = 'btn-drv btn-drv-update error';
    btn.textContent = '✗ Error';
    btn.disabled = false;
  }
}

async function doDriverUninstall(deviceId, deviceName, idx) {
  if (!confirm(`¿Desinstalar el dispositivo "${deviceName}"?\n\nEl controlador se eliminará del árbol de dispositivos. Si Windows lo redetecta al reiniciar, puede volver a instalarse automáticamente.\n\nEsta acción requiere permisos de administrador.`)) return;

  const btn = document.getElementById(`drvunin-${idx}`);
  if (!btn) return;
  btn.disabled = true;
  btn.className = 'btn-drv btn-drv-uninstall updating';
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="12" height="12" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Desinstalando…`;

  try {
    const res = await fetch('/api/driver/uninstall', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId }),
    });
    const data = await res.json();
    if (data.success) {
      btn.className = 'btn-drv btn-drv-uninstall done';
      btn.textContent = '✓ Desinstalado';
      const row = document.getElementById(`drv-row-${idx}`);
      if (row) row.style.opacity = '0.4';
      alert(data.message);
    } else {
      btn.className = 'btn-drv btn-drv-uninstall error';
      btn.textContent = '✗ Error';
      btn.disabled = false;
      alert('No se pudo desinstalar:\n\n' + (data.message || 'Error desconocido'));
    }
  } catch (e) {
    btn.className = 'btn-drv btn-drv-uninstall error';
    btn.textContent = '✗ Error';
    btn.disabled = false;
  }
}

function renderUpdates(data, body, badge) {
  const card = document.getElementById('card-updates');
  card.className = `card card-wide ${data.status}-card`;
  badge.innerHTML = badgeHTML(data.status, data.issue_count);

  if (!data.winget_available) {
    body.innerHTML = `
      <div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px">
        <span class="empty-emoji">ℹ️</span>
        <p>winget no está disponible. Actualiza Windows o instala el <strong>Instalador de aplicaciones</strong> desde la Microsoft Store.</p>
      </div>`;
    return;
  }

  if (data.items.length === 0) {
    body.innerHTML = `
      <div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px">
        <span class="empty-emoji">✅</span><p>Todo actualizado. ¡Bien hecho!</p>
      </div>`;
    return;
  }

  const rows = data.items.map((item, idx) => `
    <div class="item-update-row" id="update-row-${idx}">
      <div class="item warning" style="border-left:3px solid rgba(255,165,2,0.5); flex:1">
        <div class="item-icon warning">↑</div>
        <div class="item-body">
          <div class="item-name">${escHtml(item.name)}</div>
          <div class="item-msg">${escHtml(item.message)}</div>
          <div class="item-detail">${escHtml(item.detail)}</div>
        </div>
        <span class="item-value warning">${escHtml(item.value)}</span>
      </div>
      <button class="btn-update" id="updbtn-${idx}"
              onclick="doUpdate('${escHtml(item.package_id)}', ${idx})">
        Actualizar
      </button>
    </div>
    <div class="update-error-msg" id="update-err-${idx}" style="display:none"></div>
  `).join('');

  // Guardar la lista de package_ids para "Actualizar todo"
  window._updateAllIds = data.items.map(i => i.package_id);

  body.innerHTML = `
    <div class="card-summary">${escHtml(data.summary)}</div>
    <div class="updates-toolbar">
      <button class="btn-update-all" id="btn-update-all" onclick="doUpdateAll()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>
          <path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>
        </svg>
        Actualizar todo (${data.items.length})
      </button>
    </div>
    <div class="updates-grid">${rows}</div>`;
}

async function doUpdate(packageId, idx) {
  const btn    = document.getElementById(`updbtn-${idx}`);
  const errDiv = document.getElementById(`update-err-${idx}`);
  if (!btn) return;

  btn.disabled = true;
  btn.className = 'btn-update updating';
  btn.textContent = 'Actualizando…';
  if (errDiv) errDiv.style.display = 'none';

  try {
    const res  = await fetch(`/api/update/${encodeURIComponent(packageId)}`, { method: 'POST' });
    const data = await res.json();

    if (data.success) {
      btn.className = 'btn-update done';
      btn.textContent = '✓ Actualizado';
      const row = document.getElementById(`update-row-${idx}`);
      if (row) row.style.opacity = '0.5';
      return true;
    } else {
      btn.className = 'btn-update error';
      btn.textContent = '✗ Error';
      btn.disabled = false;
      if (errDiv) {
        errDiv.textContent = data.message || 'Error desconocido';
        errDiv.style.display = 'block';
      }
      return false;
    }
  } catch (e) {
    btn.className = 'btn-update error';
    btn.textContent = '✗ Sin conexión';
    btn.disabled = false;
    if (errDiv) {
      errDiv.textContent = 'No se pudo conectar con el servidor.';
      errDiv.style.display = 'block';
    }
    return false;
  }
}

async function doUpdateAll() {
  const btn = document.getElementById('btn-update-all');
  const ids = window._updateAllIds || [];
  if (!ids.length || !btn) return;

  btn.disabled = true;
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Actualizando…`;

  let ok = 0, fail = 0;
  for (let idx = 0; idx < ids.length; idx++) {
    const rowBtn = document.getElementById(`updbtn-${idx}`);
    // Saltar los que ya están actualizados o en error previo
    if (rowBtn && rowBtn.classList.contains('done')) { ok++; continue; }
    const success = await doUpdate(ids[idx], idx);
    if (success) ok++; else fail++;
  }

  btn.disabled = false;
  if (fail === 0) {
    btn.innerHTML = `✓ Todo actualizado (${ok})`;
    btn.className = 'btn-update-all done';
  } else {
    btn.innerHTML = `✓ ${ok} actualizados · ✗ ${fail} con error`;
    btn.className = 'btn-update-all partial';
  }
}

/* ── Conectividad — test de velocidad ────────────────────────────────────── */
async function runSpeedtest() {
  const btn  = document.getElementById('btn-speedtest');
  const body = document.getElementById('body-connectivity');

  btn.disabled = true;
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Midiendo…`;

  // Añadir fila de estado al cuerpo existente
  let stRow = document.getElementById('speedtest-row');
  if (!stRow) {
    stRow = document.createElement('div');
    stRow.id = 'speedtest-row';
    stRow.className = 'item warning';
    stRow.innerHTML = `
      <div class="item-icon warning">↓</div>
      <div class="item-body">
        <span class="item-name">Test de velocidad</span>
        <span class="item-msg" id="speedtest-msg">Descargando ~10 MB desde servidor de prueba…</span>
      </div>
      <span class="item-value warning" id="speedtest-val">…</span>`;
    body.appendChild(stRow);
  }

  try {
    const res  = await fetch('/api/connectivity/speedtest');
    const data = await res.json();

    if (!data.success) {
      stRow.className = 'item danger';
      stRow.querySelector('.item-icon').className = 'item-icon danger';
      stRow.querySelector('#speedtest-val').textContent = '—';
      stRow.querySelector('#speedtest-val').className   = 'item-value danger';
      const detail = data.error_detail ? `\n\nDetalle: ${data.error_detail}` : '';
      stRow.querySelector('#speedtest-msg').textContent = `${data.error}${detail}`;
      stRow.querySelector('#speedtest-msg').style.whiteSpace = 'pre-wrap';
    } else {
      const s = data.speed_status;
      stRow.className = `item ${s}`;
      stRow.querySelector('.item-icon').className = `item-icon ${s}`;
      const lat = data.latency_ms != null ? ` · Latencia ${data.latency_ms} ms` : '';
      const srv = data.server ? ` (vía ${data.server})` : '';
      stRow.querySelector('#speedtest-msg').textContent =
        `${data.speed_label} — ${data.download_mbps} Mbps de bajada${lat}${srv}`;
      stRow.querySelector('#speedtest-val').textContent = `${data.download_mbps} Mbps`;
      stRow.querySelector('#speedtest-val').className   = `item-value ${s}`;
    }
  } catch (e) {
    stRow.querySelector('#speedtest-msg').textContent = 'No se pudo conectar con el servidor de prueba.';
  }

  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> Test velocidad`;
}

/* ── Privacidad y Limpieza ───────────────────────────────────────────────── */
function renderPrivacy(data) {
  const summary = `<div class="card-summary">${escHtml(data.summary)}</div>`;

  const rows = data.items.map(item => {
    const detail = item.detail ? `<span class="item-detail">${escHtml(item.detail)}</span>` : '';
    const isTemp = item.name === 'Archivos temporales';
    const cleanBtn = isTemp && item.status !== 'ok' ? `
      <button class="btn-clean-temp" id="btn-clean-temp" onclick="doCleanTemp(this)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13" stroke-linecap="round">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
          <path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
        </svg>
        Limpiar ahora
      </button>` : '';

    return `
      <div class="item ${escHtml(item.status)}">
        <div class="item-icon ${escHtml(item.status)}">${privacyIcon(item)}</div>
        <div class="item-body">
          <span class="item-name">${escHtml(item.name)}</span>
          <span class="item-msg">${escHtml(item.message)}</span>
          ${detail}
        </div>
        <div class="item-right">
          <span class="item-value ${escHtml(item.status)}">${escHtml(item.value)}</span>
          ${cleanBtn}
        </div>
      </div>`;
  }).join('');

  return summary + rows;
}

function privacyIcon(item) {
  const icons = {
    'Telemetría de Windows':        '📡',
    'Micrófono':                    '🎤',
    'Cámara':                       '📷',
    'Ubicación':                    '📍',
    'Archivos temporales':          '🗑️',
    'Pantallazos azules (BSOD)':    '💀',
    'Errores críticos del sistema': '⚠️',
  };
  if (icons[item.name]) return icons[item.name];
  // Eventos del Visor (nombre = proveedor dinámico)
  if (item.value === 'Critical' || item.value === 'Crítico') return '🔴';
  if (item.status === 'warning') return '🟡';
  return item.status === 'ok' ? '✓' : '!';
}

async function doCleanTemp(btn) {
  btn.disabled = true;
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="13" height="13" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Limpiando…`;
  try {
    const res  = await fetch('/api/privacy/clean-temp', { method: 'POST' });
    const data = await res.json();
    btn.closest('.item').querySelector('.item-msg').textContent = data.message || 'Limpieza completada.';
    btn.closest('.item').querySelector('.item-value').textContent = '0 MB';
    btn.remove();
  } catch(e) {
    btn.disabled = false;
    btn.textContent = 'Error — reintentar';
  }
}

/* ── Energía y Temperatura ───────────────────────────────────────────────── */
function renderEnergy(data) {
  const summary = `<div class="card-summary">${escHtml(data.summary)}</div>`;

  const rows = data.items.map(item => {
    const isThermal = item.value && item.value.includes('°C');
    const isPercent = item.value && item.value.endsWith('%') && item.name !== 'Batería';
    const pct = isThermal
      ? Math.min(100, parseFloat(item.value) * 100 / 110)   // escala 0–110 °C
      : isPercent
        ? parseFloat(item.value)
        : null;

    const gauge = pct !== null ? `
      <div class="energy-gauge-track">
        <div class="energy-gauge-fill ${escHtml(item.status)}" style="width:${pct.toFixed(1)}%"></div>
      </div>` : '';

    const detail = item.detail ? `<span class="item-detail">${escHtml(item.detail)}</span>` : '';

    return `
      <div class="item ${escHtml(item.status)}">
        <div class="item-icon ${escHtml(item.status)}">${itemIcon(item)}</div>
        <div class="item-body">
          <span class="item-name">${escHtml(item.name)}</span>
          <span class="item-msg">${escHtml(item.message)}</span>
          ${detail}
          ${gauge}
        </div>
        <span class="item-value ${escHtml(item.status)}">${escHtml(item.value)}</span>
      </div>`;
  }).join('');

  return summary + rows;
}

function itemIcon(item) {
  if (item.name === 'Plan de energía')    return '⚡';
  if (item.name === 'Batería')             return '🔋';
  if (item.name === 'Salud de la batería') return '❤️';
  if (item.value && item.value.includes('°C')) {
    const v = parseFloat(item.value);
    return v >= 90 ? '🔴' : v >= 75 ? '🟡' : '🌡️';
  }
  return item.status === 'ok' ? '✓' : item.status === 'danger' ? '!' : '~';
}

/* ── Monitor de Rendimiento ──────────────────────────────────────────────── */
const PERF_HISTORY = { cpu: [], ram: [], disk: [] };
const PERF_MAX_POINTS = 40;
let perfInterval = null;
let perfRunning   = false;
let prevIO = null;

function togglePerf() {
  if (perfRunning) {
    stopPerf();
  } else {
    startPerf();
  }
}

function startPerf() {
  perfRunning = true;
  const btn = document.getElementById('btn-perf-toggle');
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> Detener`;

  document.getElementById('body-perf').innerHTML = `
    <div class="perf-grid">
      ${perfTileHTML('cpu',  'CPU',  '#4f8ef7')}
      ${perfTileHTML('ram',  'RAM',  '#a29bfe')}
      ${perfTileHTML('disk', 'Disco','#00b894')}
      <div class="perf-tile" id="perf-tile-gpu" style="display:none">
        ${perfTileInnerHTML('gpu', 'GPU', '#fd79a8')}
      </div>
    </div>`;

  fetchPerf();
  perfInterval = setInterval(fetchPerf, 2000);
}

function stopPerf() {
  perfRunning = false;
  clearInterval(perfInterval);
  perfInterval = null;
  prevIO = null;
  PERF_HISTORY.cpu = [];
  PERF_HISTORY.ram = [];
  PERF_HISTORY.disk = [];
  const btn = document.getElementById('btn-perf-toggle');
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> Iniciar monitor`;
  document.getElementById('body-perf').innerHTML =
    `<div class="empty-state"><span class="empty-emoji">📊</span><p>Monitor detenido. Pulsa "Iniciar monitor" para volver a activarlo.</p></div>`;
}

function perfTileHTML(id, label, color) {
  return `<div class="perf-tile" id="perf-tile-${id}">${perfTileInnerHTML(id, label, color)}</div>`;
}

function perfTileInnerHTML(id, label, color) {
  return `
    <div class="perf-tile-header">
      <div class="perf-tile-label-wrap">
        <div class="perf-dot" style="background:${color}"></div>
        <span class="perf-tile-label">${label}</span>
      </div>
      <span class="perf-tile-value" id="pval-${id}">—</span>
    </div>
    <div class="perf-bar-track">
      <div class="perf-bar-fill" id="pbar-${id}" style="width:0%;background:${color}"></div>
    </div>
    <span class="perf-tile-sub" id="psub-${id}"></span>
    <canvas class="perf-sparkline" id="pspark-${id}"></canvas>`;
}

async function fetchPerf() {
  try {
    const res  = await fetch('/api/perf/snapshot');
    const data = await res.json();
    updateTile('cpu',  data.cpu.percent,  `${data.cpu.percent}%`,  '', '#4f8ef7');
    updateTile('ram',  data.ram.percent,  `${data.ram.percent}%`,
      `${data.ram.used_gb} GB / ${data.ram.total_gb} GB`, '#a29bfe');
    updateTile('disk', data.disk.percent, `${data.disk.percent}%`,
      `${data.disk.used_gb} GB / ${data.disk.total_gb} GB`, '#00b894');

    // GPU (opcional)
    if (data.gpu) {
      const gpuTile = document.getElementById('perf-tile-gpu');
      if (gpuTile) gpuTile.style.display = '';
      updateTile('gpu', data.gpu.percent, `${data.gpu.percent}%`, '', '#fd79a8');
    }
  } catch (_) { /* silenciar errores de red transitorios */ }
}

function updateTile(id, pct, valText, subText, color) {
  const hist = PERF_HISTORY[id];
  if (hist) {
    hist.push(pct);
    if (hist.length > PERF_MAX_POINTS) hist.shift();
  }

  const valEl  = document.getElementById(`pval-${id}`);
  const barEl  = document.getElementById(`pbar-${id}`);
  const subEl  = document.getElementById(`psub-${id}`);
  const canvas = document.getElementById(`pspark-${id}`);

  if (valEl) valEl.textContent = valText;
  if (barEl) { barEl.style.width = `${pct}%`; barEl.style.background = perfColor(pct, color); }
  if (subEl) subEl.textContent = subText;
  if (canvas && hist) drawSparkline(canvas, hist, perfColor(pct, color));
}

function perfColor(pct, baseColor) {
  if (pct >= 90) return '#ff4757';
  if (pct >= 70) return '#ffa502';
  return baseColor;
}

function drawSparkline(canvas, data, color) {
  const dpr = window.devicePixelRatio || 1;
  const w   = canvas.offsetWidth  || 200;
  const h   = canvas.offsetHeight || 40;
  canvas.width  = w * dpr;
  canvas.height = h * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  if (data.length < 2) return;

  const step  = w / (PERF_MAX_POINTS - 1);
  const max   = 100;

  // Área rellena
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0,   hexToRgba(color, 0.25));
  grad.addColorStop(1,   hexToRgba(color, 0.02));

  ctx.beginPath();
  data.forEach((v, i) => {
    const x = (PERF_MAX_POINTS - data.length + i) * step;
    const y = h - (v / max) * h;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  // Cerrar área
  const lastX = (PERF_MAX_POINTS - 1) * step;
  const firstX = (PERF_MAX_POINTS - data.length) * step;
  ctx.lineTo(lastX, h);
  ctx.lineTo(firstX, h);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Línea
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = (PERF_MAX_POINTS - data.length + i) * step;
    const y = h - (v / max) * h;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth   = 1.5;
  ctx.lineJoin    = 'round';
  ctx.stroke();
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function badgeHTML(status, count) {
  const labels = { ok: 'Óptimo', warning: 'Aviso', danger: 'Peligro' };
  const label  = labels[status] || status;
  const countTxt = count > 0 ? ` · ${count}` : '';
  return `<div class="badge ${status}"><div class="bdot"></div>${label}${countTxt}</div>`;
}

function statusIcon(status) {
  return status === 'ok' ? '✓' : status === 'danger' ? '!' : '~';
}

function escHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ── Puntuación global del PC (A) ─────────────────────────────────────────── */
function calculateScore() {
  const SECURITY_MODULES = new Set(['security', 'protection']);
  const STATUS_PTS = { ok: 100, warning: 60, danger: 10 };

  const entries = Object.entries(scanResults).filter(([, v]) => v && v.status);
  if (entries.length < 3) {
    // Ocultar widget si hay pocos datos
    const w = document.getElementById('score-widget');
    if (w) w.style.display = 'none';
    return;
  }

  let totalWeight = 0;
  let weightedSum = 0;
  for (const [id, result] of entries) {
    const pts    = STATUS_PTS[result.status] ?? 60;
    const weight = SECURITY_MODULES.has(id) ? 1.5 : 1;
    weightedSum += pts * weight;
    totalWeight += weight;
  }

  const score = Math.round(weightedSum / totalWeight);
  _lastScore = score;   // lo consume saveScanToHistory()

  // Color según score
  let color, label;
  if (score >= 80)      { color = '#00b894'; label = 'Bueno'; }
  else if (score >= 60) { color = '#fdcb6e'; label = 'Aceptable'; }
  else                  { color = '#d63031'; label = 'Crítico'; }

  const barPct = score + '%';
  const moduleCount = entries.length;

  // Si el overview está activo, refrescar para mostrar el widget
  if (activeView === 'overview') {
    renderOverview();
    // El widget se inserta mediante _injectScoreWidget después del render
  }
  _injectScoreWidget(score, color, label, barPct, moduleCount);
}

function _injectScoreWidget(score, color, label, barPct, moduleCount) {
  const area = document.getElementById('content-area');
  if (!area) return;

  // Crear o actualizar el widget
  let widget = document.getElementById('score-widget');
  if (!widget) {
    widget = document.createElement('div');
    widget.id = 'score-widget';
    widget.className = 'score-widget';
    // Insertar antes del overview-grid si existe, si no al inicio
    const grid = area.querySelector('.overview-grid');
    if (grid) {
      area.insertBefore(widget, grid);
    } else {
      area.prepend(widget);
    }
  }

  widget.style.display = '';
  widget.innerHTML = `
    <div class="score-widget-inner">
      <div class="score-ring" style="--score-color:${color}">
        <span class="score-number" style="color:${color}">${score}</span>
        <span class="score-label-sm">/ 100</span>
      </div>
      <div class="score-details">
        <div class="score-title">Puntuación del sistema</div>
        <div class="score-bar-track">
          <div class="score-bar-fill" style="width:${barPct};background:${color}"></div>
        </div>
        <div class="score-meta">
          <span class="score-verdict" style="color:${color}">${label}</span>
          <span class="score-modules">Basado en ${moduleCount} módulo${moduleCount !== 1 ? 's' : ''} analizados</span>
        </div>
      </div>
    </div>`;
}

/* ── Certificados del sistema ────────────────────────────────────────────── */
function renderCerts(data) {
  const total = data.total ? ` (${data.total} analizados)` : '';
  if (!data.items || data.items.length === 0) {
    return `<div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px">
        <span class="empty-emoji">✅</span><p>Todos los certificados están vigentes${total}.</p>
      </div>`;
  }
  const rows = data.items.map((item, idx) => {
    const expColor = item.status === 'danger' ? 'var(--danger)' : 'var(--warning)';
    const deleteBtn = item.can_delete
      ? `<button class="btn-cert-delete" id="certdel-${idx}"
           data-store-path="${escHtml(item.store_path)}"
           data-thumbprint="${escHtml(item.thumbprint)}"
           onclick="doDeleteCert(this.dataset.storePath,this.dataset.thumbprint,${idx})"
           title="Eliminar certificado caducado">
           <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
             <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
             <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
           </svg> Eliminar
         </button>` : '';
    return `<div class="cert-row ${item.status}" id="cert-row-${idx}">
      <div class="cert-row-left">
        <span class="cert-status-dot" style="background:${expColor}"></span>
        <div class="cert-info">
          <div class="cert-name">${escHtml(item.name)}</div>
          <div class="cert-detail">${escHtml(item.detail)}</div>
          <div class="cert-store-path"><code>${escHtml(item.store_path || item.store || '')}</code></div>
        </div>
      </div>
      <div class="cert-row-right">
        <span class="cert-expires" style="color:${expColor}">${escHtml(item.message)}</span>
        <span class="cert-date">${escHtml(item.expires || '')}</span>
        ${deleteBtn}
      </div>
    </div>`;
  }).join('');
  return `<div class="card-summary">${escHtml(data.summary)}</div>
    <div class="cert-list">${rows}</div>`;
}

async function doDeleteCert(storePath, thumbprint, idx) {
  if (!confirm('¿Eliminar este certificado caducado?\n\nEsta acción es irreversible y requiere permisos de administrador.')) return;
  const btn = document.getElementById(`certdel-${idx}`);
  if (btn) { btn.disabled = true; btn.textContent = 'Eliminando…'; }
  try {
    const res  = await fetch('/api/cert/delete', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({store_path: storePath, thumbprint}) });
    const data = await res.json();
    if (data.success) {
      const row = document.getElementById(`cert-row-${idx}`);
      if (row) row.style.opacity = '0.35';
      if (btn) { btn.textContent = '✓ Eliminado'; btn.style.color = 'var(--success)'; }
    } else {
      if (btn) { btn.disabled = false; btn.textContent = '✗ Error'; btn.title = data.message; }
      alert('No se pudo eliminar:\n\n' + data.message);
    }
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '✗ Error'; }
  }
}

async function scanCerts() {
  const btn  = document.getElementById('btn-certs');
  const body = document.getElementById('body-certs');
  if (btn) { btn.disabled = true; btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Analizando…`; }
  if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji spin-anim" style="display:inline-block">🏅</span><p>Revisando certificados…</p></div>`;
  try {
    const data = await fetchModule('certs', { fresh: true });
    renderCard('certs', data);
    scanResults['certs'] = data;
    updateNavDot('certs', data.status);
  } catch(e) {
    if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji">⚠️</span><p>Error: ${escHtml(e.message)}</p></div>`;
  }
  if (btn) { btn.disabled = false; btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></svg> Analizar`; }
}

/* ── Exportar informe HTML ────────────────────────────────────────────────── */
function exportReport() {
  const results = (typeof scanResults !== 'undefined' ? scanResults : {});
  if (!Object.keys(results).length) {
    alert('Primero ejecuta "Escanear Sistema" para tener datos que exportar.'); return;
  }

  const STATUS_LABEL = { ok: '✅ OK', warning: '⚠️ Aviso', danger: '🔴 Crítico' };
  const date = new Date().toLocaleString('es-ES');

  const sections = Object.entries(results).map(([id, data]) => {
    if (!data || !data.title) return '';
    // Los datos vienen del sistema (nombres de proceso, rutas, claves de registro):
    // pueden contener '<' o comillas, asi que se escapan igual que en la UI.
    const itemRows = (data.items || []).map(item => `
      <tr class="s-${escHtml(item.status)}">
        <td>${escHtml(item.name)}</td>
        <td>${escHtml(STATUS_LABEL[item.status] || item.status)}</td>
        <td>${escHtml(item.message)}</td>
        <td>${escHtml(item.value)}</td>
        <td>${escHtml(item.detail)}</td>
      </tr>`).join('');
    const table = itemRows ? `<table><thead><tr><th>Elemento</th><th>Estado</th><th>Mensaje</th><th>Valor</th><th>Detalle</th></tr></thead><tbody>${itemRows}</tbody></table>` : '';
    return `<section>
      <h2><span class="badge-${escHtml(data.status)}">${STATUS_LABEL[data.status] || ''}</span> ${escHtml(data.title)}</h2>
      <p class="summary">${escHtml(data.summary)}</p>
      ${table}
    </section>`;
  }).join('');

  const html = `<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>PC Guardian — Informe ${date}</title>
<style>
  body{font-family:Segoe UI,sans-serif;background:#0f1117;color:#e0e0e0;margin:0;padding:24px}
  h1{color:#4f8ef7;margin-bottom:4px}
  .meta{color:#888;font-size:13px;margin-bottom:32px}
  section{background:#1a1d27;border:1px solid #2a2d3a;border-radius:10px;padding:20px;margin-bottom:16px}
  h2{margin:0 0 8px;font-size:16px;display:flex;align-items:center;gap:10px}
  .summary{color:#aaa;font-size:13px;margin:0 0 14px}
  table{width:100%;border-collapse:collapse;font-size:12px}
  th{text-align:left;padding:6px 10px;background:#0f1117;color:#888;border-bottom:1px solid #2a2d3a}
  td{padding:6px 10px;border-bottom:1px solid #1e2130}
  tr.s-danger td{color:#ff6b7a} tr.s-warning td{color:#ffa94d} tr.s-ok td{color:#69db7c}
  .badge-ok{color:#69db7c} .badge-warning{color:#ffa94d} .badge-danger{color:#ff6b7a}
  footer{text-align:center;color:#555;font-size:12px;margin-top:32px}
</style></head><body>
<h1>PC Guardian — Informe de diagnóstico</h1>
<p class="meta">Generado el ${date} · © 2026 David Castillo</p>
${sections}
<footer>PC Guardian · Informe generado automáticamente</footer>
</body></html>`;

  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url;
  a.download = `PCGuardian_${new Date().toISOString().slice(0,10)}.html`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ── Analizador WiFi ─────────────────────────────────────────────────────── */
function _signalBars(pct) {
  const bars = 4;
  const filled = Math.round((pct / 100) * bars);
  const color  = pct >= 70 ? 'var(--success)' : pct >= 40 ? 'var(--warning)' : 'var(--danger)';
  let svg = `<svg viewBox="0 0 20 14" width="20" height="14" style="vertical-align:middle">`;
  for (let i = 0; i < bars; i++) {
    const h = 3 + i * 3;
    const y = 14 - h;
    const c = i < filled ? color : 'rgba(255,255,255,0.15)';
    svg += `<rect x="${i * 5}" y="${y}" width="4" height="${h}" rx="1" fill="${c}"/>`;
  }
  return svg + '</svg>';
}

function renderWifi(data) {
  if (!data.networks || data.networks.length === 0) {
    return `
      <div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px">
        <span class="empty-emoji">📶</span>
        <p>${escHtml(data.summary)}</p>
      </div>`;
  }

  // — Red conectada —
  const conn = data.connected || {};
  let connBlock = '';
  if (conn.ssid) {
    const sig = conn.signal || 0;
    const sigColor = sig >= 70 ? 'var(--success)' : sig >= 40 ? 'var(--warning)' : 'var(--danger)';
    connBlock = `
      <div class="wifi-connected-card">
        <div class="wifi-conn-header">
          <span class="wifi-conn-dot" style="background:${sigColor}"></span>
          <span class="wifi-conn-ssid">${escHtml(conn.ssid)}</span>
          <span class="wifi-conn-signal" style="color:${sigColor}">${_signalBars(sig)} ${sig}%</span>
        </div>
        <div class="wifi-conn-meta">
          ${conn.channel  ? `<span class="wifi-meta-pill">Canal ${escHtml(String(conn.channel))}</span>` : ''}
          ${conn.radio_type ? `<span class="wifi-meta-pill">${escHtml(conn.radio_type)}</span>` : ''}
          ${conn.auth     ? `<span class="wifi-meta-pill">${escHtml(conn.auth)}</span>` : ''}
          ${conn.rx_mbps  ? `<span class="wifi-meta-pill">↓ ${escHtml(conn.rx_mbps)} Mbps</span>` : ''}
          ${conn.tx_mbps  ? `<span class="wifi-meta-pill">↑ ${escHtml(conn.tx_mbps)} Mbps</span>` : ''}
          ${conn.adapter  ? `<span class="wifi-meta-pill wifi-adapter">${escHtml(conn.adapter)}</span>` : ''}
        </div>
      </div>`;
  }

  // — Diagnóstico —
  const diagBlock = (data.items && data.items.length)
    ? `<div class="wifi-diag">${data.items.map(i => itemHTML(i)).join('')}</div>`
    : '';

  // — Tabla de redes —
  const chCount = data.channel_count || {};
  const myBssid = (conn.bssid || '').toLowerCase();
  const rows = data.networks.map(net => {
    const isMe = net.bssid.toLowerCase() === myBssid;
    const sig  = net.signal;
    const sigColor = sig >= 70 ? 'var(--success)' : sig >= 40 ? 'var(--warning)' : 'var(--danger)';
    const chCnt = chCount[net.channel] || 1;
    const chClass = chCnt > 3 ? 'wifi-ch-busy' : chCnt > 1 ? 'wifi-ch-moderate' : 'wifi-ch-free';
    const openNet = ['open','abierta','abierto',''].includes((net.auth || '').toLowerCase());
    const lockIcon = openNet
      ? `<svg viewBox="0 0 24 24" fill="none" stroke="var(--warning)" stroke-width="2" width="12" height="12" title="Red abierta"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>`
      : `<svg viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2" width="12" height="12"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;
    return `
      <tr class="${isMe ? 'wifi-row-me' : ''}">
        <td class="wifi-td-ssid">${isMe ? '▶ ' : ''}${escHtml(net.ssid || '(oculta)')}</td>
        <td class="wifi-td-sig" style="color:${sigColor}">${_signalBars(sig)} ${sig}%</td>
        <td class="wifi-td-ch"><span class="wifi-ch-badge ${chClass}">CH ${net.channel || '?'}</span></td>
        <td class="wifi-td-band">${escHtml(net.band || '—')}</td>
        <td class="wifi-td-radio">${escHtml(net.radio || '—')}</td>
        <td class="wifi-td-lock" title="${openNet ? 'Red abierta' : escHtml(net.auth)}">${lockIcon}</td>
      </tr>`;
  }).join('');

  const table = `
    <div class="wifi-table-wrap">
      <table class="wifi-table">
        <thead>
          <tr>
            <th>Red (SSID)</th><th>Señal</th><th>Canal</th>
            <th>Banda</th><th>Protocolo</th><th>Seguridad</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  return `
    <div class="card-summary">${escHtml(data.summary)}</div>
    ${connBlock}
    ${diagBlock}
    <h4 class="wifi-section-title">Redes detectadas (${data.networks.length})</h4>
    ${table}`;
}

async function scanWifi() {
  const btn  = document.getElementById('btn-wifi');
  const body = document.getElementById('body-wifi');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Escaneando…`;
  }
  if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji spin-anim" style="display:inline-block">📶</span><p>Escaneando redes WiFi cercanas…</p></div>`;

  try {
    const data = await fetchModule('wifi', { fresh: true });
    renderCard('wifi', data);
    scanResults['wifi'] = data;
    updateNavDot('wifi', data.status);
  } catch (e) {
    if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji">⚠️</span><p>Error al escanear WiFi: ${escHtml(e.message)}</p></div>`;
  }

  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
      <path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>
      <path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>
    </svg> Analizar`;
  }
}

/* ── Renderer de Actualizaciones Windows ─────────────────────────────────── */
function renderWupdates(data) {
  const SEVERITY_LABEL = { danger: 'Crítica / Importante', warning: 'Moderada', ok: 'Baja' };
  const SEVERITY_COLOR = { danger: '#e74c3c', warning: '#f39c12', ok: '#2ecc71' };

  if (!data.items || data.items.length === 0) {
    return `
      <div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px">
        <span class="empty-emoji">✅</span>
        <p>Windows está completamente actualizado.</p>
      </div>`;
  }

  const rows = data.items.map((item, idx) => {
    const color = SEVERITY_COLOR[item.status] || SEVERITY_COLOR.ok;
    const sevLabel = SEVERITY_LABEL[item.status] || 'Baja';

    const kbLinks = (item.kb_numbers || []).map(kb =>
      `<a href="https://support.microsoft.com/kb/${escHtml(kb)}" target="_blank" rel="noopener"
          class="kb-link" title="Ver detalles en soporte de Microsoft">KB${escHtml(kb)}</a>`
    ).join(' ');

    const descBlock = item.detail
      ? `<div class="wupdate-desc">${escHtml(item.detail)}</div>`
      : '';

    const updateId = escHtml(item.update_id || '');
    const hasId = !!item.update_id;
    const btnHtml = hasId
      ? `<button class="btn-wupdate" id="wupdbtn-${idx}"
              onclick="doWindowsUpdate('${updateId}', ${idx})">
           Aplicar actualización
         </button>`
      : `<button class="btn-wupdate" disabled title="Sin ID de actualización disponible">
           Aplicar actualización
         </button>`;

    return `
      <div class="wupdate-row" id="wupdate-row-${idx}">
        <div class="wupdate-header">
          <span class="wupdate-severity-dot" style="background:${color}" title="${sevLabel}"></span>
          <span class="wupdate-title">${escHtml(item.name)}</span>
          <span class="wupdate-size">${escHtml(item.value)}</span>
        </div>
        <div class="wupdate-meta">
          <span class="wupdate-severity-badge" style="color:${color}">${sevLabel}</span>
          ${kbLinks ? `<span class="wupdate-kb">${kbLinks}</span>` : ''}
        </div>
        ${descBlock}
        <div class="wupdate-actions">${btnHtml}</div>
      </div>`;
  }).join('');

  return `
    <div class="card-summary">${escHtml(data.summary)}</div>
    <div class="wupdates-list">${rows}</div>`;
}

async function doWindowsUpdate(updateId, idx) {
  const btn = document.getElementById(`wupdbtn-${idx}`);
  if (!btn) return;

  if (!confirm('¿Instalar esta actualización de Windows ahora?\n\nEl proceso puede tardar varios minutos. Es posible que se requiera reiniciar el equipo al finalizar.')) return;

  btn.disabled = true;
  btn.className = 'btn-wupdate updating';
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="13" height="13" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Instalando…`;

  try {
    const res = await fetch(`/api/wupdate/apply/${encodeURIComponent(updateId)}`, { method: 'POST' });
    const data = await res.json();

    if (data.success) {
      btn.className = 'btn-wupdate done';
      btn.textContent = '✓ Instalada';
      const row = document.getElementById(`wupdate-row-${idx}`);
      if (row) row.style.opacity = '0.5';
      if (data.reboot_required) {
        const row2 = document.getElementById(`wupdate-row-${idx}`);
        if (row2) {
          const notice = document.createElement('div');
          notice.className = 'wupdate-reboot-notice';
          notice.textContent = '⚠️ Reinicia el equipo para completar la instalación.';
          row2.appendChild(notice);
        }
      }
    } else {
      btn.className = 'btn-wupdate error';
      btn.textContent = '✗ Error';
      btn.disabled = false;
      btn.title = data.message || 'Error desconocido';
      alert('No se pudo instalar la actualización:\n\n' + (data.message || 'Error desconocido'));
    }
  } catch (e) {
    btn.className = 'btn-wupdate error';
    btn.textContent = '✗ Sin conexión';
    btn.disabled = false;
  }
}

/* ── Actualizaciones Windows bajo demanda (C) ─────────────────────────────── */
async function checkWindowsUpdates() {
  const btn = document.getElementById('btn-wupdates');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Consultando Windows Update…`;
  }

  const body  = document.getElementById('body-wupdates');
  if (body) {
    body.innerHTML = `
      <div class="empty-state">
        <span class="empty-emoji spin-anim" style="display:inline-block">🔄</span>
        <p>Consultando Windows Update… Esto puede tardar hasta 60 segundos.</p>
      </div>`;
  }

  try {
    const data = await fetchModule('wupdates', { fresh: true });
    renderCard('wupdates', data);
    scanResults['wupdates'] = data;
    updateNavDot('wupdates', data.status);
  } catch (e) {
    console.warn('checkWindowsUpdates error:', e);
    if (body) {
      body.innerHTML = `
        <div class="empty-state">
          <span class="empty-emoji">⚠️</span>
          <p>No se pudo consultar Windows Update: ${escHtml(e.message)}</p>
        </div>`;
    }
  }

  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
      <polyline points="23 4 23 10 17 10"/>
      <polyline points="1 20 1 14 7 14"/>
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    </svg> Comprobar`;
  }
}

/* ── Renderer de inventario de hardware (B) ──────────────────────────────── */
function renderInventory(data) {
  if (!data || !data.sections) {
    return `<div class="card-summary">${escHtml(data && data.summary ? data.summary : '')}</div>
      <div class="empty-state"><span class="empty-emoji">🖥️</span><p>Sin datos de inventario.</p></div>`;
  }

  const SECTION_LABELS = {
    system:      { label: 'Equipo', emoji: '🏢' },
    cpu:         { label: 'Procesador (CPU)', emoji: '🔲' },
    gpu:         { label: 'Tarjeta gráfica (GPU)', emoji: '🎮' },
    ram:         { label: 'Memoria RAM', emoji: '💾' },
    motherboard: { label: 'Placa base', emoji: '🔧' },
    bios:        { label: 'BIOS / UEFI', emoji: '⚡' },
  };

  const ORDER = ['system', 'cpu', 'gpu', 'ram', 'motherboard', 'bios'];

  function renderKV(obj) {
    if (!obj || typeof obj !== 'object') return '';
    return `<table class="inv-table">
      ${Object.entries(obj).map(([k, v]) =>
        `<tr><td class="inv-key">${escHtml(k)}</td><td class="inv-val">${escHtml(String(v))}</td></tr>`
      ).join('')}
    </table>`;
  }

  function renderSection(key) {
    const meta = SECTION_LABELS[key] || { label: key, emoji: '•' };
    const val  = data.sections[key];
    if (!val || (Array.isArray(val) && val.length === 0)) return '';

    let inner = '';
    if (Array.isArray(val)) {
      inner = val.map((item, idx) =>
        `<div class="inv-subitem">
          <div class="inv-subitem-label">${escHtml(meta.label)} #${idx + 1}</div>
          ${renderKV(item)}
        </div>`
      ).join('');
    } else {
      inner = renderKV(val);
    }

    return `
      <div class="inventory-section">
        <button class="inv-section-title" onclick="this.closest('.inventory-section').classList.toggle('collapsed')">
          <span>${meta.emoji} ${escHtml(meta.label)}</span>
          <svg class="inv-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
        <div class="inv-section-body">${inner}</div>
      </div>`;
  }

  const sections = ORDER.map(renderSection).filter(Boolean).join('');

  return `<div class="card-summary">${escHtml(data.summary || '')}</div>${sections}`;
}

/* ── Privilegios de administrador ──────────────────────────────── */
// Sin elevacion, media docena de modulos devuelven datos parciales y el usuario
// lo descubria modulo a modulo. Se avisa una sola vez, arriba del todo.
let isAdmin = null;

async function checkAdmin() {
  try {
    const res = await fetch('/api/status/admin');
    const data = await res.json();
    isAdmin = !!data.admin;
  } catch (e) {
    isAdmin = true;   // ante la duda no molestamos con el aviso
  }
  const banner = _id('admin-banner');
  if (!banner) return;
  const dismissed = localStorage.getItem('pcg-admin-banner-dismissed') === '1';
  banner.classList.toggle('hidden', isAdmin || dismissed);
}

function dismissAdminBanner() {
  localStorage.setItem('pcg-admin-banner-dismissed', '1');
  const banner = _id('admin-banner');
  if (banner) banner.classList.add('hidden');
}

async function elevateApp() {
  if (!confirm('Se cerrara PC Guardian y se volvera a abrir pidiendo permisos de administrador.\n\n¿Continuar?')) return;
  try {
    const res = await fetch('/api/admin/elevate', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      document.body.innerHTML =
        '<div style="display:flex;height:100vh;align-items:center;justify-content:center;' +
        'font-family:Segoe UI,sans-serif;color:#9aa0ab;text-align:center;padding:24px">' +
        'Reiniciando con permisos de administrador\u2026<br><small>Acepta el aviso de Windows. ' +
        'Puedes cerrar esta pesta\u00f1a.</small></div>';
    } else {
      alert(data.message || 'No se pudo reiniciar con permisos de administrador.');
    }
  } catch (e) {
    alert('No se pudo contactar con la aplicacion: ' + e.message);
  }
}

document.addEventListener('DOMContentLoaded', checkAdmin);


/* ── Historial de escaneos ────────────────────────────────────────────────── */
// Un escaneo suelto solo dice como esta el equipo ahora. Guardarlos permite
// responder la pregunta util: que ha cambiado desde la ultima vez.

const STATUS_ES = { ok: 'Correcto', warning: 'Aviso', danger: 'Critico' };
let _lastScore = null;

async function saveScanToHistory() {
  try {
    const res = await fetch('/api/history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ results: scanResults, score: _lastScore }),
    });
    const data = await res.json();
    if (!data.success) console.warn('historial:', data.message);
  } catch (e) {
    console.warn('No se pudo guardar en el historial:', e.message);
  }
}

function _fmtFecha(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString('es-ES', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function _scoreClass(score) {
  if (score == null) return 'muted';
  return score >= 80 ? 'ok' : score >= 55 ? 'warning' : 'danger';
}

async function renderHistoryView() {
  const area = _id('content-area');
  if (!area) return;
  _returnCardsToPool();
  area.innerHTML = '<div class="history-loading">Cargando historial\u2026</div>';

  let scans = [];
  try {
    const res = await fetch('/api/history');
    scans = (await res.json()).scans || [];
  } catch (e) {
    area.innerHTML = `<div class="history-empty"><p>No se pudo leer el historial: ${escHtml(e.message)}</p></div>`;
    return;
  }

  if (!scans.length) {
    area.innerHTML = `
      <div class="history-empty">
        <span class="empty-emoji">\u{1F553}</span>
        <p>Todavia no hay escaneos guardados.</p>
        <p class="history-empty-sub">Cada vez que pulses "Escanear Sistema" se guardara
           una instantanea aqui, y podras comparar dos cualesquiera.</p>
      </div>`;
    return;
  }

  const maxIssues = Math.max(1, ...scans.map(s => s.issue_count || 0));

  const rows = scans.map((s, i) => {
    const prev = scans[i + 1];   // el listado viene del mas nuevo al mas viejo
    let delta = '';
    if (prev && s.score != null && prev.score != null) {
      const d = s.score - prev.score;
      if (d !== 0) {
        delta = `<span class="history-delta ${d > 0 ? 'up' : 'down'}">${d > 0 ? '\u25B2' : '\u25BC'} ${Math.abs(d)}</span>`;
      }
    }
    const barPct = Math.round(((s.issue_count || 0) / maxIssues) * 100);
    return `
      <tr>
        <td><input type="checkbox" class="history-pick" value="${s.id}" onchange="_syncCompareBtn()"></td>
        <td class="history-date">${escHtml(_fmtFecha(s.created_at))}</td>
        <td class="history-score s-${_scoreClass(s.score)}">${s.score == null ? '\u2014' : s.score} ${delta}</td>
        <td>
          <div class="history-bar"><span style="width:${barPct}%"></span></div>
          <span class="history-issues">${s.issue_count || 0} incidencia${s.issue_count === 1 ? '' : 's'}</span>
        </td>
        <td class="history-mods">${s.module_count} modulos</td>
        <td><button class="history-del" onclick="deleteHistoryEntry(${s.id})" title="Eliminar">\u2715</button></td>
      </tr>`;
  }).join('');

  area.innerHTML = `
    <div class="history-view">
      <div class="history-header">
        <div>
          <h2>Historial de escaneos</h2>
          <p class="history-sub">${scans.length} escaneo${scans.length === 1 ? '' : 's'} guardado${scans.length === 1 ? '' : 's'}.
             Marca dos para ver exactamente que cambio entre ellos.</p>
        </div>
        <div class="history-actions">
          <button id="history-compare-btn" class="history-btn primary" disabled onclick="compareSelectedScans()">
            Comparar seleccionados
          </button>
          <button class="history-btn" onclick="clearHistory()">Vaciar historial</button>
        </div>
      </div>

      <table class="history-table">
        <thead>
          <tr><th></th><th>Fecha</th><th>Puntuacion</th><th>Incidencias</th><th></th><th></th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>

      <div id="history-diff"></div>
    </div>`;
}

function _syncCompareBtn() {
  const picked = document.querySelectorAll('.history-pick:checked');
  const btn = _id('history-compare-btn');
  if (btn) btn.disabled = picked.length !== 2;
}

async function deleteHistoryEntry(id) {
  if (!confirm('\u00bfEliminar este escaneo del historial?')) return;
  await fetch(`/api/history/${id}`, { method: 'DELETE' });
  renderHistoryView();
}

async function clearHistory() {
  if (!confirm('Se borraran todos los escaneos guardados. \u00bfContinuar?')) return;
  await fetch('/api/history/clear', { method: 'POST' });
  renderHistoryView();
}

async function compareSelectedScans() {
  const picked = [...document.querySelectorAll('.history-pick:checked')].map(c => +c.value);
  if (picked.length !== 2) return;
  // El id mas bajo es el escaneo mas antiguo: ese es la referencia.
  const [a, b] = picked.sort((x, y) => x - y);

  const box = _id('history-diff');
  box.innerHTML = '<div class="history-loading">Comparando\u2026</div>';

  let d;
  try {
    d = await (await fetch(`/api/history/diff?a=${a}&b=${b}`)).json();
  } catch (e) {
    box.innerHTML = `<div class="history-empty"><p>${escHtml(e.message)}</p></div>`;
    return;
  }
  if (!d.success) {
    box.innerHTML = `<div class="history-empty"><p>${escHtml(d.message)}</p></div>`;
    return;
  }

  const itemList = (items, cls) => items.length
    ? `<ul class="diff-items">${items.map(i => `
        <li class="${cls}">
          <span class="diff-mod">${escHtml((MODULE_META[i.module] || {}).label || i.module)}</span>
          <strong>${escHtml(i.name)}</strong>
          <span class="diff-msg">${escHtml(i.message)}</span>
          ${i.before ? `<span class="diff-arrow">${escHtml(STATUS_ES[i.before] || i.before)} \u2192 ${escHtml(STATUS_ES[i.status] || i.status)}</span>` : ''}
        </li>`).join('')}</ul>`
    : '<p class="diff-none">Nada en esta categoria.</p>';

  const modRows = d.modules.filter(m => m.trend !== 'same').map(m => `
    <li class="trend-${m.trend}">
      <strong>${escHtml(m.title)}</strong>
      <span>${escHtml(STATUS_ES[m.before] || m.before)} \u2192 ${escHtml(STATUS_ES[m.after] || m.after)}</span>
      <span class="diff-msg">${m.issues_before} \u2192 ${m.issues_after} incidencias</span>
    </li>`).join('');

  const scoreLine = d.score_delta == null
    ? ''
    : `<div class="diff-score ${d.score_delta >= 0 ? 'up' : 'down'}">
         Puntuacion ${d.a.score} \u2192 ${d.b.score}
         <span>(${d.score_delta > 0 ? '+' : ''}${d.score_delta})</span>
       </div>`;

  box.innerHTML = `
    <div class="diff-panel">
      <div class="diff-header">
        <h3>Cambios entre los dos escaneos</h3>
        <p class="history-sub">${escHtml(_fmtFecha(d.a.created_at))} \u2192 ${escHtml(_fmtFecha(d.b.created_at))}</p>
        ${scoreLine}
        <p class="history-sub">${d.issue_delta === 0 ? 'Mismo numero de incidencias.'
          : d.issue_delta > 0 ? `${d.issue_delta} incidencia(s) mas que antes.`
          : `${Math.abs(d.issue_delta)} incidencia(s) menos que antes.`}</p>
      </div>

      ${modRows ? `<section class="diff-section">
        <h4>Modulos que cambiaron de estado</h4>
        <ul class="diff-modules">${modRows}</ul>
      </section>` : ''}

      <section class="diff-section">
        <h4>Nuevos problemas <span class="diff-count danger">${d.new_issues.length}</span></h4>
        ${itemList(d.new_issues, 'is-new')}
      </section>

      <section class="diff-section">
        <h4>Resueltos <span class="diff-count ok">${d.fixed.length}</span></h4>
        ${itemList(d.fixed, 'is-fixed')}
      </section>

      ${d.changed.length ? `<section class="diff-section">
        <h4>Empeoraron <span class="diff-count warning">${d.changed.length}</span></h4>
        ${itemList(d.changed, 'is-changed')}
      </section>` : ''}
    </div>`;

  box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}


/* ── Procesos activos ─────────────────────────────────────────────────────── */
// Lo que se abre cuando el equipo va lento: quien se esta comiendo la maquina
// y un boton para cerrarlo sin salir a buscar el Administrador de tareas.

function _barra(pct, clase) {
  const w = Math.max(2, Math.min(100, pct));
  return `<div class="proc-bar ${clase}"><span style="width:${w}%"></span></div>`;
}

function renderProcesses(data) {
  if (!data.items || !data.items.length) {
    return `<div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state"><span class="empty-emoji">\u{1F4CA}</span><p>${escHtml(data.summary)}</p></div>`;
  }

  const filas = data.items.map(p => `
    <div class="proc-row s-${escHtml(p.status)}">
      <div class="proc-main">
        <span class="proc-name">${escHtml(p.name)}</span>
        <span class="proc-pid">PID ${p.pid}</span>
      </div>
      <div class="proc-metric">
        ${_barra(p.cpu, 'cpu')}
        <span class="proc-num">${p.cpu.toFixed(1)}% CPU</span>
      </div>
      <div class="proc-metric">
        ${_barra(p.ram_pct, 'ram')}
        <span class="proc-num">${p.ram_mb.toFixed(0)} MB</span>
      </div>
      <div class="proc-action">
        ${p.protected
          ? '<span class="proc-locked" title="Proceso critico de Windows">Protegido</span>'
          : `<button class="proc-kill" onclick="killProcess(${p.pid}, '${escHtml(p.name).replace(/'/g, "\\'")}')">Terminar</button>`}
      </div>
      <div class="proc-path" title="${escHtml(p.detail)}">${escHtml(p.detail)}</div>
    </div>`).join('');

  return `<div class="card-summary">${escHtml(data.summary)}</div>
    <div class="proc-list">${filas}</div>`;
}

async function killProcess(pid, name) {
  if (!confirm(`Se cerrara "${name}" (PID ${pid}) de forma inmediata.\n\n` +
               `El programa perdera lo que no haya guardado. \u00bfContinuar?`)) return;
  try {
    const res = await fetch('/api/process/kill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pid }),
    });
    const data = await res.json();
    alert(data.message);
    if (data.success) _triggerModuleScan('processes');
  } catch (e) {
    alert('No se pudo terminar el proceso: ' + e.message);
  }
}

/* ── Conexiones salientes ─────────────────────────────────────────────────── */

function renderConnections(data) {
  if (!data.items || !data.items.length) {
    return `<div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state"><span class="empty-emoji">\u{1F310}</span><p>${escHtml(data.summary)}</p></div>`;
  }

  const MAX_VISIBLE = 8;
  const fila = (c, oculta) => `
    <div class="conn-row s-${escHtml(c.status)}${oculta ? ' hidden-item' : ''}">
      <span class="conn-dot dot-${escHtml(c.status)}"></span>
      <div class="conn-body">
        <div class="conn-head">
          <strong>${escHtml(c.name)}</strong>
          <span class="conn-endpoint">${escHtml(c.value)}</span>
        </div>
        <div class="conn-msg">${escHtml(c.message)}</div>
        <div class="conn-path">${escHtml(c.detail)}</div>
      </div>
    </div>`;

  const visibles = data.items.slice(0, MAX_VISIBLE).map(c => fila(c, false)).join('');
  const resto    = data.items.slice(MAX_VISIBLE);
  const ocultas  = resto.map(c => fila(c, true)).join('');
  const boton    = resto.length
    ? `<button class="show-more-btn">Mostrar ${resto.length} m\u00e1s\u2026</button>` : '';

  return `<div class="card-summary">${escHtml(data.summary)}</div>
    <div class="conn-list">${visibles}${ocultas}${boton}</div>`;
}
