'use strict';

/* ── Tema claro / oscuro ─────────────────────────────────────────────────── */
function toggleTheme() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  if (isLight) {
    document.documentElement.removeAttribute('data-theme');
    localStorage.setItem('pc-guardian-theme', 'dark');
  } else {
    document.documentElement.setAttribute('data-theme', 'light');
    localStorage.setItem('pc-guardian-theme', 'light');
  }
}

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
  connections:  { label: 'Conexiones TCP', group: 'Red',           emoji: '🔌', color: '#e17055' },
  processes:    { label: 'Procesos',       group: 'Rendimiento',   emoji: '⚡', color: '#6c5ce7' },
  software:         { label: 'Programas',    group: 'Sistema',    emoji: '📦', color: '#00b894' },
  dns:              { label: 'DNS activo',   group: 'Red',        emoji: '🌐', color: '#0984e3' },
  'firewall-rules': { label: 'Firewall',     group: 'Seguridad',  emoji: '🛡️', color: '#d63031' },
};

// IDs del escaneo general (excluye perf que es on-demand)
const SCAN_MODULE_IDS = ['hardware','startup','security','drivers','protection','network','maintenance','updates','connectivity','energy','privacy','services'];

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
        ? 'Historial'
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
    _hideHistorySection();
    renderOverview();
  } else if (id === 'history') {
    _returnCardsToPool();
    _hideContentArea();
    showHistoryView();
  } else if (id === 'perf-history') {
    _returnCardsToPool();
    _hideContentArea();
    showPerfHistoryView();
  } else {
    _hideHistorySection();
    showModuleView(id);
  }

  // En móvil cerrar sidebar al navegar
  if (window.innerWidth <= 900) closeSidebar();
}

function _hideHistorySection() {
  const hs = _id('history-section');
  if (hs) hs.classList.add('hidden');
  const ph = _id('perf-history-section');
  if (ph) ph.classList.add('hidden');
  const ca = _id('content-area');
  if (ca) ca.style.display = '';
}
function _hideContentArea() {
  const ca = _id('content-area');
  if (ca) ca.style.display = 'none';
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
        <div class="overview-tile-sub">${subText}</div>
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
  if (id === 'wupdates')    { if (typeof checkWindowsUpdates === 'function') checkWindowsUpdates(); return; }
  if (id === 'wifi')        { if (typeof scanWifi  === 'function') scanWifi();  return; }
  if (id === 'certs')       { if (typeof scanCerts === 'function') scanCerts(); return; }
  if (id === 'connections') { if (typeof scanConnections === 'function') scanConnections(); return; }
  if (id === 'processes')  { if (typeof scanProcesses  === 'function') scanProcesses();  return; }
  if (id === 'software')       { if (typeof scanSoftware      === 'function') scanSoftware();      return; }
  if (id === 'firewall-rules') { if (typeof scanFirewallRules === 'function') scanFirewallRules(); return; }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Analizando…`;
  }
  try {
    const data = await fetchModule(id);
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
  const ids = Object.keys(MODULE_META).concat(['perf', 'inventory', 'wupdates', 'services', 'connections', 'processes', 'software', 'dns', 'firewall-rules']);
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
  { id: 'processes',   label: 'Analizando procesos activos…',               step: 'pstep-processes'    },
  { id: 'dns',         label: 'Comprobando configuración DNS…',             step: 'pstep-dns'          },
];

let scanResults = {};
let scanning    = false;

// Comandos que muestra el terminal por módulo
const MODULE_CMDS = {
  hardware:    ['psutil.cpu_percent(interval=1)', 'psutil.virtual_memory()', 'psutil.disk_usage("C:\\\\")'],
  startup:     ['winreg HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run', 'winreg HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run'],
  security:    ['psutil.process_iter(["pid","name","exe"])', 'entropy_check(process_names)', 'critical_process_count()'],
  drivers:     ['powershell Get-WmiObject Win32_PnPSignedDriver', 'winreg HKLM:\\Software\\...\\Uninstall\\*'],
  protection:  ['powershell Get-CimInstance AntiVirusProduct', 'powershell Get-NetFirewallProfile'],
  network:     ['psutil.net_connections(kind="inet")', 'open("C:\\\\Windows\\\\System32\\\\drivers\\\\etc\\\\hosts")'],
  maintenance: ['powershell Get-PhysicalDisk', 'psutil.boot_time()', 'schtasks /query /fo CSV /nh'],
  updates:     ['winget list --upgrade-available --source winget'],
  connectivity: ['ping -n 4 8.8.8.8', 'socket.gethostbyname("www.google.com")', 'route print 0.0.0.0'],
  energy:       ['powercfg /getactivescheme', 'psutil.sensors_battery()', 'wmi.WMI(namespace="root\\\\OpenHardwareMonitor").Sensor()'],
  privacy:      ['winreg HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection', 'winreg HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore', 'Get-WinEvent -FilterHashtable @{LogName="System";Level=1,2}'],
  connections:  ['psutil.net_connections(kind="tcp")', 'socket.gethostbyaddr(remote_ip)', 'psutil.Process(pid).name()'],
  processes:        ['psutil.process_iter(["pid","name","cpu_percent","memory_percent"])', 'proc.memory_info().rss', 'proc.terminate()'],
  dns:              ['Get-DnsClientServerAddress -AddressFamily IPv4', 'winreg HKLM\\SYSTEM\\...\\Dnscache\\EnableAutoDoh'],
  'firewall-rules': ['Get-NetFirewallRule -Enabled True | Where-Object {...} | ConvertTo-Json'],
};

/* ── Punto de entrada ────────────────────────────────────────────────────── */
async function startScan() {
  if (scanning) return;
  scanning = true;
  scanResults = {};

  setScanningUI(true);
  showProgress(true);
  hideSummary();
  clearTerminal();

  termLog('info', '=== PC Guardian — análisis iniciado ===');

  for (let i = 0; i < MODULES.length; i++) {
    const mod = MODULES[i];
    setProgress(mod.label, Math.round((i / MODULES.length) * 100));
    setStepState(mod.step, 'active');

    const t0 = performance.now();
    const cmds = MODULE_CMDS[mod.id] || [];
    cmds.forEach(c => termLog('cmd', `> ${c}`));

    try {
      const data = await fetchModule(mod.id);
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

    setProgress(null, Math.round(((i + 1) / MODULES.length) * 100));
  }

  termLog('info', '=== Análisis completado ===');
  setScanningUI(false);
  showProgress(false);
  renderSummary();
  updateLastScan();
  calculateScore();
  scanning = false;
  _autoSaveHistory();
}

async function _autoSaveHistory() {
  try {
    const scoreEl = document.querySelector('.score-number');
    const score   = scoreEl ? parseInt(scoreEl.textContent, 10) || 0 : 0;
    await fetch('/api/history/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ score, results: scanResults }),
    });
  } catch (_) { /* silencioso */ }
}

/* ── Fetch ───────────────────────────────────────────────────────────────── */
async function fetchModule(id) {
  const res = await fetch(`/api/scan/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
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
  } else if (id === 'certs') {
    body.innerHTML = renderCerts(data);
    const btnC = document.getElementById('btn-certs');
    if (btnC) btnC.style.display = '';
  } else if (id === 'connections') {
    body.innerHTML = renderConnections(data);
    const btnConn = document.getElementById('btn-connections');
    if (btnConn) btnConn.style.display = '';
  } else if (id === 'processes') {
    body.innerHTML = renderProcesses(data);
    const btnProc = document.getElementById('btn-processes');
    if (btnProc) btnProc.style.display = '';
  } else if (id === 'software') {
    body.innerHTML = renderSoftware(data);
    const btnSoft = document.getElementById('btn-software');
    if (btnSoft) btnSoft.style.display = '';
  } else if (id === 'dns') {
    body.innerHTML = renderDns(data);
  } else if (id === 'firewall-rules') {
    body.innerHTML = renderFirewallRules(data);
    const btnFw = document.getElementById('btn-firewall-rules');
    if (btnFw) btnFw.style.display = '';
  } else if (id === 'startup') {
    body.innerHTML = renderStartup(data);
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
    const data = await fetchModule('updates');
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
    const isTelemetry = item.name === 'Telemetría de Windows';
    const telemetryBtn = isTelemetry && item.status !== 'ok' ? `
      <button class="btn-quickfix" onclick="doFixTelemetry(this)">🔕 Desactivar telemetría</button>` : '';

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
          ${telemetryBtn}
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
    const fixBtn = (item.name === 'Plan de energía' && item.status !== 'ok')
      ? `<button class="btn-quickfix" onclick="doFixEnergyHigh(this)">⚡ Aplicar Alto Rendimiento</button>`
      : '';

    return `
      <div class="item ${escHtml(item.status)}">
        <div class="item-icon ${escHtml(item.status)}">${itemIcon(item)}</div>
        <div class="item-body">
          <span class="item-name">${escHtml(item.name)}</span>
          <span class="item-msg">${escHtml(item.message)}</span>
          ${detail}
          ${gauge}
          ${fixBtn}
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
    const data = await fetchModule('certs');
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
    const itemRows = (data.items || []).map(item => `
      <tr class="s-${item.status}">
        <td>${item.name || ''}</td>
        <td>${STATUS_LABEL[item.status] || item.status}</td>
        <td>${item.message || ''}</td>
        <td>${item.value || ''}</td>
        <td>${item.detail || ''}</td>
      </tr>`).join('');
    const table = itemRows ? `<table><thead><tr><th>Elemento</th><th>Estado</th><th>Mensaje</th><th>Valor</th><th>Detalle</th></tr></thead><tbody>${itemRows}</tbody></table>` : '';
    return `<section>
      <h2><span class="badge-${data.status}">${STATUS_LABEL[data.status] || ''}</span> ${data.title}</h2>
      <p class="summary">${data.summary || ''}</p>
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
    const data = await fetchModule('wifi');
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

/* ── Conexiones TCP salientes ────────────────────────────────────────────── */
async function scanConnections() {
  const btn  = document.getElementById('btn-connections');
  const body = document.getElementById('body-connections');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Analizando…`;
  }
  if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji spin-anim" style="display:inline-block">🔌</span><p>Resolviendo conexiones activas…</p></div>`;

  try {
    const data = await fetchModule('connections');
    renderCard('connections', data);
    scanResults['connections'] = data;
    updateNavDot('connections', data.status);
  } catch (e) {
    if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji">⚠️</span><p>Error: ${escHtml(e.message)}</p></div>`;
  }

  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Analizar`;
  }
}

function renderConnections(data) {
  if (!data.items || data.items.length === 0) {
    return `<div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px">
        <span class="empty-emoji">✅</span>
        <p>Sin conexiones TCP externas activas en este momento.</p>
      </div>`;
  }

  const rows = data.items.map(item => {
    const icon  = statusIcon(item.status);
    const badge = `<span class="conn-port-badge ${item.status}">${escHtml(item.value)}</span>`;
    return `
      <tr class="conn-row conn-${item.status}">
        <td class="conn-icon">${icon}</td>
        <td class="conn-proc">${escHtml(item.name)}</td>
        <td class="conn-dest">${escHtml(item.message)}</td>
        <td class="conn-port">${badge}</td>
      </tr>
      ${item.detail ? `<tr class="conn-detail-row"><td colspan="4"><span class="conn-detail">${escHtml(item.detail)}</span></td></tr>` : ''}`;
  }).join('');

  return `
    <div class="card-summary">${escHtml(data.summary)}</div>
    <div class="conn-table-wrap">
      <table class="conn-table">
        <thead>
          <tr>
            <th></th>
            <th>Proceso</th>
            <th>Destino</th>
            <th>Puerto</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
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
    const data = await fetchModule('wupdates');
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

/* ── Procesos activos ─────────────────────────────────────────────────────── */
async function scanProcesses() {
  const btn  = document.getElementById('btn-processes');
  const body = document.getElementById('body-processes');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Analizando…`;
  }
  if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji spin-anim" style="display:inline-block">⚡</span><p>Obteniendo procesos activos…</p></div>`;

  try {
    const data = await fetchModule('processes');
    renderCard('processes', data);
    scanResults['processes'] = data;
    updateNavDot('processes', data.status);
  } catch (e) {
    if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji">⚠️</span><p>Error: ${escHtml(e.message)}</p></div>`;
  }

  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Analizar`;
  }
}

function renderProcesses(data) {
  if (!data.items || data.items.length === 0) {
    return `<div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px"><span class="empty-emoji">✅</span><p>Sin procesos con consumo elevado.</p></div>`;
  }

  const rows = data.items.map(item => {
    const icon     = statusIcon(item.status);
    const killBtn  = item.killable
      ? `<button class="btn-kill" onclick="killProcess(${item.pid}, ${JSON.stringify(item.name)})">Terminar</button>`
      : '';
    return `
      <tr class="proc-row">
        <td class="proc-icon">${icon}</td>
        <td class="proc-name">${escHtml(item.name)}</td>
        <td class="proc-stats">${escHtml(item.message)}</td>
        <td class="proc-pid">${escHtml(item.value)}</td>
        <td class="proc-user">${escHtml(item.detail || '')}</td>
        <td>${killBtn}</td>
      </tr>`;
  }).join('');

  return `
    <div class="card-summary">${escHtml(data.summary)}</div>
    <div class="proc-table-wrap">
      <table class="proc-table">
        <thead><tr><th></th><th>Proceso</th><th>CPU / RAM</th><th>PID</th><th>Usuario</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

async function killProcess(pid, name) {
  if (!confirm(`¿Terminar el proceso "${name}" (PID ${pid})?\nEsto cerrará la aplicación de forma forzada.`)) return;
  try {
    const res  = await fetch(`/api/processes/${pid}/kill`, { method: 'POST' });
    const data = await res.json();
    alert(data.msg || (data.ok ? 'Proceso terminado.' : 'No se pudo terminar el proceso.'));
    if (data.ok) scanProcesses();
  } catch (e) {
    alert('Error de comunicación: ' + e.message);
  }
}

/* ── Historial de escaneos ────────────────────────────────────────────────── */
async function showHistoryView() {
  const hs   = _id('history-section');
  const body = _id('history-body');
  if (!hs) return;

  hs.classList.remove('hidden');
  if (body) body.innerHTML = `<div class="empty-state" style="padding:40px 0"><span class="empty-emoji spin-anim" style="display:inline-block">⏳</span><p>Cargando…</p></div>`;

  try {
    const res   = await fetch('/api/history');
    const scans = await res.json();
    if (body) body.innerHTML = renderHistoryView(scans);
  } catch (e) {
    if (body) body.innerHTML = `<div class="history-empty">Error al cargar historial: ${escHtml(e.message)}</div>`;
  }
}

function renderHistoryView(scans) {
  if (!scans || scans.length === 0) {
    return `<div class="history-empty">Sin escaneos guardados aún.<br>Ejecuta "Escanear Sistema" para registrar el primer análisis.</div>`;
  }

  const MODULE_ORDER = ['hardware','security','protection','startup','drivers','network',
    'connectivity','maintenance','updates','energy','privacy','services','processes'];

  const rows = scans.map(s => {
    const ts      = s.ts ? s.ts.replace('T', ' ') : '—';
    const score   = s.score ?? '—';
    const scoreColor = s.score >= 80 ? '#2ed573' : s.score >= 60 ? '#ffa502' : '#ff4757';
    const mods    = s.modules || {};
    const dots    = MODULE_ORDER.map(id => {
      const m  = mods[id];
      const st = m ? m.status : 'unknown';
      const lbl = m ? `${id}: ${m.summary || st}` : id;
      return `<span class="hist-dot ${st}" title="${escHtml(lbl)}"></span>`;
    }).join('');

    return `
      <tr class="hist-row">
        <td class="hist-ts">${escHtml(ts)}</td>
        <td class="hist-score" style="color:${scoreColor}">${score}</td>
        <td><div class="hist-dots">${dots}</div></td>
        <td style="display:flex;gap:6px;align-items:center">
          <button class="btn-hist-compare" onclick="showCompare(${JSON.stringify(s).replace(/</g,'\\u003c')})">Comparar</button>
          <button class="btn-hist-del" onclick="deleteHistoryScan(${s.id}, this)">Borrar</button>
        </td>
      </tr>`;
  }).join('');

  return `
    <div class="hist-table-wrap">
      <table class="hist-table">
        <thead><tr><th>Fecha</th><th>Score</th><th>Módulos</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

async function deleteHistoryScan(id, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '…'; }
  try {
    await fetch(`/api/history/${id}`, { method: 'DELETE' });
    showHistoryView();
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = 'Borrar'; }
    alert('Error: ' + e.message);
  }
}

/* ── Comparar escaneos ────────────────────────────────────────────────────── */
function showCompare(historicScan) {
  const hasCurrent = Object.keys(scanResults).length > 0;
  if (!hasCurrent) {
    alert('Ejecuta primero "Escanear Sistema" para tener datos actuales con los que comparar.');
    return;
  }
  const body = _id('history-body');
  if (body) body.innerHTML = renderCompare(historicScan);
}

function renderCompare(hist) {
  const _STATUS_SCORE = { ok: 0, warning: 1, danger: 2 };
  const _STATUS_LABEL = { ok: '✓ ok', warning: '~ warning', danger: '✗ danger' };
  const _STATUS_COLOR = { ok: '#2ed573', warning: '#ffa502', danger: '#ff4757' };

  const moduleIds = Array.from(new Set([
    ...Object.keys(hist.modules || {}),
    ...Object.keys(scanResults).filter(id => scanResults[id] && scanResults[id].status),
  ]));

  const rows = moduleIds.map(id => {
    const hMod  = (hist.modules || {})[id];
    const cMod  = scanResults[id];
    if (!hMod && !cMod) return '';

    const hSt   = hMod ? hMod.status : null;
    const cSt   = cMod ? cMod.status : null;
    const hScore = hSt ? (_STATUS_SCORE[hSt] ?? 3) : 3;
    const cScore = cSt ? (_STATUS_SCORE[cSt] ?? 3) : 3;

    let change = '→', changeColor = 'var(--text-muted)';
    if (hSt && cSt) {
      if (cScore < hScore)      { change = '↑ Mejoró';    changeColor = '#2ed573'; }
      else if (cScore > hScore) { change = '↓ Empeoró';   changeColor = '#ff4757'; }
      else                      { change = '→ Sin cambio'; }
    } else if (!hSt && cSt) {
      change = '★ Nuevo'; changeColor = '#74b9ff';
    }

    const meta  = MODULE_META[id] || { label: id, emoji: '•' };
    const hCell = hSt ? `<span style="color:${_STATUS_COLOR[hSt]}">${_STATUS_LABEL[hSt]}</span>` : '<span style="color:var(--text-muted)">—</span>';
    const cCell = cSt ? `<span style="color:${_STATUS_COLOR[cSt]}">${_STATUS_LABEL[cSt]}</span>` : '<span style="color:var(--text-muted)">—</span>';

    return `
      <tr class="hist-row">
        <td style="white-space:nowrap">${meta.emoji} ${escHtml(meta.label)}</td>
        <td>${hCell}</td>
        <td>${cCell}</td>
        <td style="color:${changeColor};font-weight:600;white-space:nowrap">${change}</td>
      </tr>`;
  }).filter(Boolean).join('');

  const ts = hist.ts ? hist.ts.replace('T', ' ') : '—';
  const scoreColor = hist.score >= 80 ? '#2ed573' : hist.score >= 60 ? '#ffa502' : '#ff4757';

  return `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <button class="module-back-btn" onclick="showHistoryView()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <path d="M19 12H5"/><polyline points="12 19 5 12 12 5"/>
        </svg> Volver al historial
      </button>
      <span style="font-size:0.82rem;color:var(--text-soft)">
        Escaneo histórico del <strong>${escHtml(ts)}</strong>
        — score <strong style="color:${scoreColor}">${hist.score ?? '—'}</strong>
      </span>
    </div>
    <div class="hist-table-wrap">
      <table class="hist-table">
        <thead><tr><th>Módulo</th><th>Histórico</th><th>Actual</th><th>Cambio</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

/* ── Programas instalados ─────────────────────────────────────────────────── */
async function scanSoftware() {
  const btn  = document.getElementById('btn-software');
  const body = document.getElementById('body-software');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Cargando…`;
  }
  if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji spin-anim" style="display:inline-block">📦</span><p>Leyendo registro de Windows…</p></div>`;
  try {
    const data = await fetchModule('software');
    renderCard('software', data);
    scanResults['software'] = data;
  } catch (e) {
    if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji">⚠️</span><p>Error: ${escHtml(e.message)}</p></div>`;
  }
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Analizar`;
  }
}

function renderSoftware(data) {
  if (!data.items || data.items.length === 0) {
    return `<div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px"><span class="empty-emoji">📭</span><p>No se encontraron programas.</p></div>`;
  }

  let filterHtml = `
    <div class="soft-filter-bar">
      <input type="text" class="soft-search" id="soft-search-input"
        placeholder="Filtrar programas…" oninput="filterSoftware(this.value)">
      <span class="soft-count" id="soft-count">${data.items.length} programas</span>
    </div>`;

  const rows = data.items.map((item, idx) => `
    <tr class="soft-row" data-name="${escHtml(item.name.toLowerCase())}">
      <td class="soft-name">${escHtml(item.name)}</td>
      <td class="soft-version">${escHtml(item.version)}</td>
      <td class="soft-pub">${escHtml(item.publisher)}</td>
      <td class="soft-date">${escHtml(item.date)}</td>
      <td class="soft-size">${item.size_mb > 0 ? item.size_mb + ' MB' : '—'}</td>
      <td><button class="btn-uninstall" onclick="uninstallSoftware(${JSON.stringify(item.name).replace(/</g,'\\u003c')}, this)">Desinstalar</button></td>
    </tr>`).join('');

  return `
    <div class="card-summary">${escHtml(data.summary)}</div>
    ${filterHtml}
    <div class="soft-table-wrap">
      <table class="soft-table" id="soft-table">
        <thead><tr><th>Nombre</th><th>Versión</th><th>Fabricante</th><th>Instalado</th><th>Tamaño</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function filterSoftware(q) {
  const rows  = document.querySelectorAll('#soft-table .soft-row');
  const lower = q.toLowerCase();
  let visible = 0;
  rows.forEach(r => {
    const match = r.dataset.name.includes(lower);
    r.style.display = match ? '' : 'none';
    if (match) visible++;
  });
  const cnt = document.getElementById('soft-count');
  if (cnt) cnt.textContent = `${visible} programas`;
}

async function uninstallSoftware(name, btn) {
  if (!confirm(`¿Desinstalar "${name}"?\nEsto ejecutará winget uninstall de forma silenciosa.`)) return;
  if (btn) { btn.disabled = true; btn.textContent = 'Desinstalando…'; }
  try {
    const res  = await fetch('/api/software/uninstall', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    const data = await res.json();
    alert(data.msg || (data.ok ? 'Desinstalado.' : 'No se pudo desinstalar.'));
    if (data.ok) scanSoftware();
    else if (btn) { btn.disabled = false; btn.textContent = 'Desinstalar'; }
  } catch (e) {
    alert('Error: ' + e.message);
    if (btn) { btn.disabled = false; btn.textContent = 'Desinstalar'; }
  }
}

/* ── Arranque — renderer con acciones ────────────────────────────────────── */
function renderStartup(data) {
  if (!data.items || data.items.length === 0) {
    return `<div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px"><span class="empty-emoji">✅</span><p>Sin entradas de arranque detectadas.</p></div>`;
  }

  const rows = data.items.map(item => {
    const icon   = statusIcon(item.status);
    const detail = item.detail ? `<span class="item-detail">${escHtml(item.detail)}</span>` : '';
    const canDisable = item.fix_name && item.value !== 'Sistema';
    const disableBtn = canDisable
      ? `<button class="btn-quickfix" onclick="doDisableStartup(${JSON.stringify(item.fix_hive)},${JSON.stringify(item.fix_key)},${JSON.stringify(item.fix_name)},this)">✕ Deshabilitar</button>`
      : '';
    return `
      <div class="item ${escHtml(item.status)}">
        <div class="item-icon ${escHtml(item.status)}">${icon}</div>
        <div class="item-body">
          <span class="item-name">${escHtml(item.name)}</span>
          <span class="item-msg">${escHtml(item.message)}</span>
          ${detail}
          ${disableBtn}
        </div>
        <span class="item-value ${escHtml(item.status)}">${escHtml(item.value)}</span>
      </div>`;
  }).join('');

  return `<div class="card-summary">${escHtml(data.summary)}</div>${rows}`;
}

/* ── Quickfix handlers ───────────────────────────────────────────────────── */
async function doFixEnergyHigh(btn) {
  if (!confirm('¿Cambiar el plan de energía a Alto Rendimiento?')) return;
  if (btn) { btn.disabled = true; btn.textContent = 'Aplicando…'; }
  try {
    const res  = await fetch('/api/quickfix/energy-high', { method: 'POST' });
    const data = await res.json();
    alert(data.msg);
    if (data.ok) _triggerModuleScan('energy');
    else if (btn) { btn.disabled = false; btn.textContent = '⚡ Aplicar Alto Rendimiento'; }
  } catch (e) {
    alert('Error: ' + e.message);
    if (btn) { btn.disabled = false; btn.textContent = '⚡ Aplicar Alto Rendimiento'; }
  }
}

async function doFixTelemetry(btn) {
  if (!confirm('¿Desactivar la telemetría de Windows?\nSe requiere reinicio para que el cambio tenga efecto.')) return;
  if (btn) { btn.disabled = true; btn.textContent = 'Aplicando…'; }
  try {
    const res  = await fetch('/api/quickfix/telemetry-off', { method: 'POST' });
    const data = await res.json();
    alert(data.msg);
    if (data.ok) _triggerModuleScan('privacy');
    else if (btn) { btn.disabled = false; btn.textContent = '🔕 Desactivar telemetría'; }
  } catch (e) {
    alert('Error: ' + e.message);
    if (btn) { btn.disabled = false; btn.textContent = '🔕 Desactivar telemetría'; }
  }
}

/* ── DNS activo ──────────────────────────────────────────────────────────── */
function renderDns(data) {
  if (!data.items || data.items.length === 0) {
    return `<div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px"><span class="empty-emoji">🌐</span><p>Sin información DNS disponible.</p></div>`;
  }

  const rows = data.items.map(item => {
    const icon   = statusIcon(item.status);
    const detail = item.detail ? `<span class="item-detail">${escHtml(item.detail)}</span>` : '';
    let fixBtns  = '';
    if (item.fix_available && item.servers && item.servers.length > 0) {
      const iface = item.interface;
      fixBtns = `
        <div class="dns-fix-bar">
          <button class="btn-quickfix" onclick="doSetDns(${JSON.stringify(iface)},'1.1.1.1','1.0.0.1',this)">
            🔒 Cloudflare (1.1.1.1)
          </button>
          <button class="btn-quickfix" onclick="doSetDns(${JSON.stringify(iface)},'8.8.8.8','8.8.4.4',this)">
            🔍 Google (8.8.8.8)
          </button>
        </div>`;
    }
    return `
      <div class="item ${escHtml(item.status)}">
        <div class="item-icon ${escHtml(item.status)}">${icon}</div>
        <div class="item-body">
          <span class="item-name">${escHtml(item.name)}</span>
          <span class="item-msg">${escHtml(item.message)}</span>
          ${detail}
          ${fixBtns}
        </div>
        <span class="item-value ${escHtml(item.status)}">${escHtml(item.value)}</span>
      </div>`;
  }).join('');

  return `<div class="card-summary">${escHtml(data.summary)}</div>${rows}`;
}

async function doSetDns(iface, dns1, dns2, btn) {
  if (!confirm(`¿Cambiar el DNS de "${iface}" a ${dns1}?`)) return;
  if (btn) { btn.disabled = true; btn.textContent = 'Aplicando…'; }
  try {
    const res  = await fetch('/api/dns/set', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interface: iface, dns1, dns2 }),
    });
    const data = await res.json();
    alert(data.msg);
    if (data.ok) _triggerModuleScan('dns');
    else if (btn) { btn.disabled = false; btn.textContent = btn.textContent.replace('…', ''); }
  } catch (e) {
    alert('Error: ' + e.message);
    if (btn) { btn.disabled = false; }
  }
}

/* ── Reglas de firewall ──────────────────────────────────────────────────── */
async function scanFirewallRules() {
  const btn  = document.getElementById('btn-firewall-rules');
  const body = document.getElementById('body-firewall-rules');
  if (btn) { btn.disabled = true; btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Analizando…`; }
  if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji spin-anim" style="display:inline-block">🛡️</span><p>Obteniendo reglas del firewall…</p></div>`;
  try {
    const data = await fetchModule('firewall-rules');
    renderCard('firewall-rules', data);
    scanResults['firewall-rules'] = data;
    updateNavDot('firewall-rules', data.status);
  } catch (e) {
    if (body) body.innerHTML = `<div class="empty-state"><span class="empty-emoji">⚠️</span><p>Error: ${escHtml(e.message)}</p></div>`;
  }
  if (btn) { btn.disabled = false; btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Analizar`; }
}

function renderFirewallRules(data) {
  if (!data.items || data.items.length === 0) {
    return `<div class="card-summary">${escHtml(data.summary)}</div>
      <div class="empty-state" style="padding-top:20px"><span class="empty-emoji">✅</span><p>Sin reglas no estándar habilitadas.</p></div>`;
  }

  const rows = data.items.map(item => {
    const icon = statusIcon(item.status);
    const delBtn = `<button class="btn-kill" onclick="deleteFirewallRule(${JSON.stringify(item.rule_name).replace(/</g,'\\u003c')},this)">Eliminar</button>`;
    return `
      <tr class="proc-row">
        <td class="proc-icon">${icon}</td>
        <td class="proc-name" style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(item.name)}</td>
        <td class="proc-stats">${escHtml(item.message)}</td>
        <td>${delBtn}</td>
      </tr>`;
  }).join('');

  return `
    <div class="card-summary">${escHtml(data.summary)}</div>
    <div class="proc-table-wrap">
      <table class="proc-table">
        <thead><tr><th></th><th>Regla</th><th>Detalles</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

async function deleteFirewallRule(name, btn) {
  if (!confirm(`¿Eliminar la regla de firewall "${name}"?`)) return;
  if (btn) { btn.disabled = true; btn.textContent = 'Eliminando…'; }
  try {
    const res  = await fetch('/api/firewall-rules/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    const data = await res.json();
    alert(data.msg);
    if (data.ok) scanFirewallRules();
    else if (btn) { btn.disabled = false; btn.textContent = 'Eliminar'; }
  } catch (e) {
    alert('Error: ' + e.message);
    if (btn) { btn.disabled = false; btn.textContent = 'Eliminar'; }
  }
}

/* ── Tendencias de rendimiento ───────────────────────────────────────────── */
async function showPerfHistoryView() {
  const sec  = _id('perf-history-section');
  const body = _id('perf-history-body');
  if (!sec) return;
  sec.classList.remove('hidden');
  if (body) body.innerHTML = `<div class="empty-state" style="padding:40px 0"><span class="empty-emoji spin-anim" style="display:inline-block">⏳</span><p>Cargando…</p></div>`;
  try {
    const res  = await fetch('/api/perf/history');
    const data = await res.json();
    if (body) body.innerHTML = renderPerfHistoryView(data);
  } catch (e) {
    if (body) body.innerHTML = `<div class="history-empty">Error: ${escHtml(e.message)}</div>`;
  }
}

function _svgSparkline(values, color, h = 70) {
  if (!values || values.length < 2) return `<div class="perf-hist-empty">Sin datos</div>`;
  const w    = 600;
  const max  = Math.max(...values, 1);
  const pts  = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - (v / max) * (h - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const areaClose = `${w},${h} 0,${h}`;
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none" class="perf-spark-svg">
    <polygon points="${pts} ${areaClose}" fill="${color}" fill-opacity="0.12" stroke="none"/>
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`;
}

function renderPerfHistoryView(snaps) {
  if (!snaps || snaps.length === 0) {
    return `<div class="history-empty">Sin snapshots registrados aún.<br>PC Guardian guarda uno cada 5 minutos mientras está en ejecución.</div>`;
  }

  const cpu  = snaps.map(s => s.cpu  ?? 0);
  const ram  = snaps.map(s => s.ram  ?? 0);
  const disk = snaps.map(s => s.disk ?? 0);
  const gpu  = snaps.map(s => s.gpu  ?? null).filter(v => v !== null);

  const tsFirst = snaps[0]?.ts?.replace('T',' ') || '';
  const tsLast  = snaps[snaps.length - 1]?.ts?.replace('T',' ') || '';

  const avgOf = arr => arr.length ? (arr.reduce((a,b) => a+b, 0) / arr.length).toFixed(1) : '—';
  const maxOf = arr => arr.length ? Math.max(...arr).toFixed(1) : '—';

  const charts = [
    { label: 'CPU',    values: cpu,  color: '#4f8ef7' },
    { label: 'RAM',    values: ram,  color: '#a29bfe' },
    { label: 'Disco',  values: disk, color: '#fdcb6e' },
  ];
  if (gpu.length > 1) charts.push({ label: 'GPU', values: gpu, color: '#00cec9' });

  const chartHtml = charts.map(c => `
    <div class="perf-chart-block">
      <div class="perf-chart-header">
        <span class="perf-chart-label">${c.label}</span>
        <span class="perf-chart-stats">
          Promedio <strong>${avgOf(c.values)}%</strong> · Máx <strong>${maxOf(c.values)}%</strong>
        </span>
      </div>
      <div class="perf-chart-body">${_svgSparkline(c.values, c.color)}</div>
      <div class="perf-chart-axis">
        <span>${escHtml(tsFirst)}</span>
        <span>${snaps.length} puntos</span>
        <span>${escHtml(tsLast)}</span>
      </div>
    </div>`).join('');

  return `
    <p class="perf-hist-meta">Últimas 24 h · ${snaps.length} snapshots</p>
    <div class="perf-charts-grid">${chartHtml}</div>`;
}

async function doDisableStartup(hive, key, name, btn) {
  if (!confirm(`¿Deshabilitar "${name}" del arranque automático?\nPuedes volver a habilitarlo desde el Administrador de tareas.`)) return;
  if (btn) { btn.disabled = true; btn.textContent = 'Deshabilitando…'; }
  try {
    const res  = await fetch('/api/quickfix/disable-startup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hive, key, name }),
    });
    const data = await res.json();
    alert(data.msg);
    if (data.ok) _triggerModuleScan('startup');
    else if (btn) { btn.disabled = false; btn.textContent = '✕ Deshabilitar'; }
  } catch (e) {
    alert('Error: ' + e.message);
    if (btn) { btn.disabled = false; btn.textContent = '✕ Deshabilitar'; }
  }
}
