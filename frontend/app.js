// ── Mapa ──────────────────────────────────────────────────────────────────
const map = L.map('map', { zoomControl: false }).setView([40.4, -3.7], 6);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '© OpenStreetMap © CARTO', maxZoom: 18
}).addTo(map);

L.control.zoom({ position: 'topright' }).addTo(map);

const resetBtn = L.control({ position: 'topright' });
resetBtn.onAdd = () => {
  const btn = L.DomUtil.create('button', 'leaflet-bar leaflet-control');
  btn.title = 'Ver España completa';
  btn.innerHTML = '&#9635;';
  btn.style.cssText = 'width:30px;height:30px;font-size:15px;cursor:pointer;background:#1a1d27;color:#aaa;border:1px solid #2a2d3a;display:flex;align-items:center;justify-content:center;margin-top:4px;';
  btn.onclick = () => {
    // Resetear vista
    map.setView([40.4, -3.7], 6);
    // Desactivar todas las capas WMS
    Object.keys(wmsActive).forEach(key => {
      map.removeLayer(wmsActive[key]);
      delete wmsActive[key];
      const chk = document.getElementById('chk-' + key);
      if (chk) chk.checked = false;
    });
    updateLegend();
  };
  L.DomEvent.disableClickPropagation(btn);
  return btn;
};
resetBtn.addTo(map);

// ── WMS ────────────────────────────────────────────────────────────────────
const EFFIS_URL = 'https://maps.effis.emergency.copernicus.eu/effis';
const TODAY     = new Date().toISOString().split('T')[0];
const YESTERDAY = new Date(Date.now() - 86400000).toISOString().split('T')[0];

const WMS_DEFS = {
  effis_fires: {
    url:     EFFIS_URL,
    layer:   'viirs.hs',
    time:    YESTERDAY,
    opacity: 0.85,
  },
  effis_fwi: {
    url:     EFFIS_URL,
    layer:   'mf010.fwi',        // Fire Weather Index — actualización diaria
    time:    TODAY,
    opacity: 0.65,
  },
  effis_dc: {
    url:     EFFIS_URL,
    layer:   'mf010.dc',         // Drought Code — actualización diaria
    time:    TODAY,
    opacity: 0.65,
  },
  flood: {
    url:     'https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones',
    layer:   'NZ.Flood.FluvialT100',  // inundación fluvial T=100 — MITECO/SNCZI
    time:    null,
    opacity: 0.6,
    version: '1.3.0',
  },
  corine: {
    url:     'https://servicios.idee.es/wms-inspire/ocupacion-suelo',
    layer:   'LC.LandCoverSurfaces',  // CORINE Land Cover 2018 + SIOSE — IGN
    time:    null,                    // capa estática, actualización cada 6 años
    opacity: 0.55,
    version: '1.3.0',
    minZoom: 8,                       // visible a partir de zoom provincial
  },
};

const wmsActive = {};
const SPAIN_BOUNDS = L.latLngBounds([27.5, -18.5], [43.9, 4.5]);

function buildWMS(key) {
  const d = WMS_DEFS[key];
  const ver = d.version || '1.1.1';
  const opts = {
    layers:      d.layer,
    styles:      '',
    format:      'image/png',
    transparent: true,
    version:     ver,
    opacity:     d.opacity,
    uppercase:   true,
    bounds:      SPAIN_BOUNDS,
  };
  if (d.time) opts.TIME = d.time;
  if (d.minZoom) opts.minZoom = d.minZoom;
  return L.tileLayer.wms(d.url, opts);
}

function toggleWMS(key, enabled) {
  if (enabled) {
    if (wmsActive[key]) return;
    wmsActive[key] = buildWMS(key).addTo(map);
  } else {
    if (wmsActive[key]) { map.removeLayer(wmsActive[key]); delete wmsActive[key]; }
  }
  updateLegend();
}

function autoActivateWMS(key) {
  const chk = document.getElementById('chk-' + key);
  if (chk && !chk.checked) {
    chk.checked = true;
    toggleWMS(key, true);
  }
}

// ── Leyenda WMS ────────────────────────────────────────────────────────────
const WMS_LEGENDS = {
  effis_fwi: {
    title: 'Peligro de incendio FWI (EFFIS)',
    items: [
      { color: '#3f003f', label: 'Muy extremo  (> 70)' },
      { color: '#7f0000', label: 'Extremo  (50 – 70)' },
      { color: '#c00000', label: 'Muy alto  (38.0 – 50.0)' },
      { color: '#ff0000', label: 'Alto  (21.3 – 38.0)' },
      { color: '#ffc000', label: 'Moderado  (11.2 – 21.3)' },
      { color: '#ffff00', label: 'Bajo  (5.2 – 11.2)' },
      { color: '#00c800', label: 'Muy bajo  (< 5.2)' },
    ],
    note: 'Modelo ECMWF - previsión diaria hasta 9 días'
  },
  effis_dc: {
    title: 'Índice de sequía (DC)',
    items: [
      { color: '#800026', label: 'Extremo (>600)' },
      { color: '#fd8d3c', label: 'Alto (300 – 600)' },
      { color: '#fed976', label: 'Moderado (100 – 300)' },
      { color: '#ffffcc', label: 'Bajo (<100)' },
    ],
    note: 'Humedad profunda del suelo - actualización diaria'
  },
  flood: {
    title: 'Zonas inundables fluviales T=100',
    items: [
      { color: '#4da6ff', label: 'Peligrosidad media (T=100 años)' },
    ],
    note: 'MITECO/SNCZI - capa estática oficial España'
  },
  corine: {
    title: 'Usos del suelo',
    items: [
      { color: '#267300', label: 'Bosque de coníferas' },
      { color: '#4ce600', label: 'Bosque de frondosas' },
      { color: '#70a800', label: 'Bosque mixto' },
      { color: '#a8a800', label: 'Matorral y brezal' },
      { color: '#d4a46a', label: 'Vegetación esclerófila mediterránea' },
      { color: '#ffffa8', label: 'Cultivos en secano' },
      { color: '#e6e600', label: 'Mosaico de cultivos' },
    ],
    note: 'CORINE Land Cover 2018 - IGN'
  },
};

function updateLegend() {
  const el = document.getElementById('wms-legend');
  if (!el) return;
  const activeKeys = Object.keys(wmsActive);
  if (!activeKeys.length) { el.style.display = 'none'; return; }
  el.style.display = 'block';
  el.innerHTML = activeKeys.map(key => {
    const leg = WMS_LEGENDS[key];
    if (!leg) return '';
    const items = leg.items.map(i =>
      `<div class="leg-item">
        <span class="leg-dot" style="background:${i.color}"></span>
        <span class="leg-label">${i.label}</span>
      </div>`
    ).join('');
    return `<div class="leg-block">
      <div class="leg-title">${leg.title}</div>
      ${items}
      <div class="leg-note">${leg.note}</div>
    </div>`;
  }).join('');
}

// ── Estado ────────────────────────────────────────────────────────────────
let alertsData   = [];
let firesData    = [];
let alertLayers  = {};
let fireLayers   = [];
let showAlerts   = true;
let showFires    = true;
let activeList   = 'alerts';
let activeLevels = new Set(['Rojo','Naranja','Amarillo','Verde']);
let activeEvent  = 'all';

// ── Timeline ──────────────────────────────────────────────────────────────
let tlMin = null, tlMax = null, tlCurrent = null, playInterval = null;
const STEP_MS = 60 * 60 * 1000;
const TICK_MS = 700;

function initTimeline() {
  tlMin = tlCurrent = new Date();
  tlMax = alertsData.reduce((mx, a) => {
    const d = new Date(a.expires); return d > mx ? d : mx;
  }, new Date());
  const slider = document.getElementById('tl-slider');
  slider.min = 0;
  slider.max = Math.max(1, Math.floor((tlMax - tlMin) / STEP_MS));
  slider.value = 0;
  updateTimelineUI();
  buildTicks();
}

function buildTicks() {
  const c = document.getElementById('tl-ticks');
  c.innerHTML = '';
  const hrs = (tlMax - tlMin) / 3600000;
  const every = hrs <= 48 ? 6 : 24;
  let t = new Date(tlMin);
  while (t <= tlMax) {
    const s = document.createElement('span');
    s.textContent = t.toLocaleDateString('es-ES',{day:'2-digit',month:'short'})
      + ' ' + t.toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'});
    c.appendChild(s);
    t = new Date(t.getTime() + every * 3600000);
  }
}

function updateTimelineUI() {
  const isNow = (tlCurrent - tlMin) < 60000;
  const badge = document.getElementById('tl-badge');
  badge.textContent = isNow ? 'AHORA' : 'FUTURO';
  badge.className = isNow ? '' : 'future';
  document.getElementById('tl-datetime').textContent =
    tlCurrent.toLocaleDateString('es-ES',{weekday:'short',day:'2-digit',month:'short'})
    + ' · ' + tlCurrent.toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'});
}

function onSliderInput(val) {
  tlCurrent = new Date(tlMin.getTime() + val * STEP_MS);
  updateTimelineUI();
  renderAll();
}

function togglePlay() {
  const btn = document.getElementById('tl-play');
  if (playInterval) {
    clearInterval(playInterval); playInterval = null;
    btn.innerHTML = '&#9654; Play'; btn.classList.remove('playing');
  } else {
    btn.innerHTML = '&#9646;&#9646; Pausa'; btn.classList.add('playing');
    playInterval = setInterval(() => {
      const s = document.getElementById('tl-slider');
      const next = parseInt(s.value) + 1;
      if (next > parseInt(s.max)) { togglePlay(); return; }
      s.value = next; onSliderInput(next);
    }, TICK_MS);
  }
}

function resetTimeline() {
  if (playInterval) togglePlay();
  document.getElementById('tl-slider').value = 0;
  onSliderInput(0);
}

function isActive(a) { return new Date(a.onset) <= tlCurrent; }

// ── Carga ─────────────────────────────────────────────────────────────────
async function init() {
  const [alerts, fires, stats] = await Promise.all([
    fetch('/api/alerts').then(r => r.json()),
    fetch('/api/fires').then(r => r.json()),
    fetch('/api/stats').then(r => r.json()),
  ]);
  alertsData = alerts;
  firesData  = fires;

  document.getElementById('stats-bar').innerHTML =
    `<b>${stats.alerts.total}</b> avisos AEMET &nbsp;·&nbsp; `+
    `<b>${stats.fires.total}</b> focos FIRMS &nbsp;·&nbsp; `+
    `FRP máx: <b>${stats.fires.frp_max.toFixed(1)} MW</b>`;

  populateEventFilter();
  initTimeline();
  const chkF = document.getElementById('chk-fires');
  if (chkF) chkF.checked = true;
  renderAlerts();
  renderFires();
  renderList();
}

// ── Filtrado ──────────────────────────────────────────────────────────────
function getFilteredAlerts() {
  return alertsData.filter(a => {
    const inTime  = new Date(a.expires) >= tlCurrent;
    const levelOk = activeLevels.has(a.level);
    const eventOk = activeEvent === 'all' || normalizeEvent(a.event) === activeEvent;
    return inTime && levelOk && eventOk;
  });
}

const FLOOD_KEYWORDS = ['lluvia','precipitación','tormenta','costero','nieve derretida','deshielo','vaguada','dana'];

function isFloodRelated(event) {
  if (!event) return false;
  const lower = event.toLowerCase();
  return FLOOD_KEYWORDS.some(kw => lower.includes(kw));
}

function normalizeEvent(ev) {
  if (!ev) return 'Desconocido';
  return ev.replace(/\s*(amarillo|naranja|rojo|verde|nivel\s*\d)/gi,'')
           .replace(/\s+/g,' ').trim();
}

function populateEventFilter() {
  const sel = document.getElementById('event-select');
  const tipos = [...new Set(alertsData.map(a => normalizeEvent(a.event)))].sort();
  sel.innerHTML = '<option value="all">Todos los tipos</option>';
  tipos.forEach(t => {
    const o = document.createElement('option');
    o.value = t; o.textContent = t; sel.appendChild(o);
  });
}

// ── Render ────────────────────────────────────────────────────────────────
function renderAll() { renderAlerts(); renderList(); }

function renderAlerts() {
  Object.values(alertLayers).forEach(l => map.removeLayer(l));
  alertLayers = {};
  if (!showAlerts) return;

  const filtered = getFilteredAlerts();
  filtered.forEach(a => {
    if (!a.polygon) return;
    const coords = parsePolygon(a.polygon);
    if (!coords.length) return;
    const color  = a.level_color;
    const future = !isActive(a);
    const poly = L.polygon(coords, {
      color, weight: future ? 1 : 1.5, opacity: future ? 0.5 : 0.9,
      fillColor: color, fillOpacity: future ? 0.07 : 0.2,
      dashArray: future ? '5 4' : null,
    }).addTo(map);

    poly.bindTooltip(
      `<b>${normalizeEvent(a.event)}</b><br>${a.area_name}<br>`+
      `<span style="color:${color}">${a.level}</span>`+
      (future ? `<br><i style="color:#a06af8;font-size:11px">Aviso futuro</i>` : ''),
      { sticky: true }
    );

    poly.on('click', () => {
      map.fitBounds(poly.getBounds(), { padding: [40,40] });
      highlightCard(a.id);
      if (isFloodRelated(a.event)) {
        autoActivateWMS('flood');
      } else {
        const chk = document.getElementById('chk-flood');
        if (chk && chk.checked) { chk.checked = false; toggleWMS('flood', false); }
      }
    });
    alertLayers[a.id] = poly;
  });

  if (activeList === 'alerts') updateListHeader(filtered);
}

function renderFires() {
  fireLayers.forEach(l => map.removeLayer(l));
  fireLayers = [];
  if (!showFires) return;

  firesData.forEach(f => {
    const radius = f.level === 'Rojo' ? 10 : f.level === 'Naranja' ? 7 : 5;
    const circle = L.circleMarker([f.latitude, f.longitude], {
      radius, color: f.level_color, fillColor: f.level_color,
      fillOpacity: 0.85, weight: 1.5,
    }).addTo(map);

    const hora = f.acq_time.padStart(4,'0').replace(/(\d{2})(\d{2})/, '$1:$2');
    circle.bindTooltip(
      `<b>Foco de incendio</b><br>FRP: ${f.frp} MW · `+
      `<span style="color:${f.level_color}">${f.level}</span><br>${f.acq_date} ${hora} UTC`,
      { sticky: true }
    );

    circle.on('click', () => {
      map.setView([f.latitude, f.longitude], 16);
      highlightCard(f.id);
      autoActivateWMS('effis_fwi');  // peligrosidad meteorológica
      autoActivateWMS('corine');     // tipo de vegetación
    });

    fireLayers.push(circle);
  });

  if (activeList === 'fires') updateListHeader(firesData);
}

// ── Sidebar ───────────────────────────────────────────────────────────────
function highlightCard(id) {
  document.querySelectorAll('.card').forEach(c => c.classList.remove('highlighted'));
  const card = document.querySelector(`.card[data-id="${id}"]`);
  if (card) { card.classList.add('highlighted'); card.scrollIntoView({ behavior:'smooth', block:'nearest' }); }
}

function renderList() {
  const el    = document.getElementById('main-list');
  const title = document.getElementById('list-title');

  if (activeList === 'alerts') {
    title.textContent = 'Avisos';
    const filtered = getFilteredAlerts();
    updateListHeader(filtered);
    if (!filtered.length) { el.innerHTML = '<div class="empty">Sin avisos para este filtro</div>'; return; }

    const order = { Rojo:0, Naranja:1, Amarillo:2, Verde:3 };
    const sorted = [...filtered].sort((a,b) => {
      const da = isActive(a)?0:1, db = isActive(b)?0:1;
      return da !== db ? da-db : (order[a.level]||9)-(order[b.level]||9);
    });

    el.innerHTML = sorted.map(a => {
      const future = !isActive(a);
      const desc = a.description ? `<div class="desc">${a.description}</div>` : '';
      const floodIcon = isFloodRelated(a.event)
        ? `<span class="flood-icon" title="Zona con posible riesgo de inundación">&#x26A0</span>`
        : '';
      return `<div class="card ${future?'future':''}" data-id="${a.id}"
        style="border-left-color:${a.level_color}" onclick="zoomToAlert('${a.id}')">
        <div class="name">${normalizeEvent(a.event)} ${floodIcon}</div>
        <div class="area">${a.area_name}</div>
        <div class="meta">
          <span class="badge" style="background:${a.level_color}22;color:${a.level_color}">${a.level}</span>
          ${future ? `<span class="future-tag">Inicia ${fmtDate(a.onset)}</span>` : ''}
          <span class="time">${fmtDate(a.onset)}</span>
        </div>
        ${desc}
      </div>`;
    }).join('');

  } else {
    title.textContent = 'Focos de incendio';
    updateListHeader(firesData);
    if (!firesData.length) { el.innerHTML = '<div class="empty">Sin focos activos en España</div>'; return; }

    const sorted = [...firesData].sort((a,b) => b.frp - a.frp);
    el.innerHTML = sorted.map(f => {
      const hora = f.acq_time.padStart(4,'0').replace(/(\d{2})(\d{2})/, '$1:$2');
      return `<div class="card" data-id="${f.id}"
        style="border-left-color:${f.level_color}" onclick="zoomToFire(${f.latitude},${f.longitude},'${f.id}')">
        <div class="name">${f.latitude.toFixed(3)}, ${f.longitude.toFixed(3)}</div>
        <div class="area">${f.acq_date} ${hora} UTC · ${f.satellite}</div>
        <div class="meta">
          <span class="badge" style="background:${f.level_color}22;color:${f.level_color}">${f.level}</span>
          <span class="time">FRP: ${f.frp} MW</span>
        </div>
      </div>`;
    }).join('');
  }
}

function updateListHeader(data) {
  const count = document.getElementById('list-count');
  if (activeList === 'alerts' && Array.isArray(data)) {
    const nA = data.filter(isActive).length;
    const nF = data.filter(a => !isActive(a)).length;
    count.textContent = `${nA} activos · ${nF} próximos`;
  } else {
    count.textContent = `(${Array.isArray(data) ? data.length : 0})`;
  }
}

// ── Zoom ──────────────────────────────────────────────────────────────────
function zoomToAlert(id) {
  const a = alertsData.find(x => x.id === id);
  if (!a || !a.polygon) return;
  const coords = parsePolygon(a.polygon);
  if (coords.length) map.fitBounds(L.polygon(coords).getBounds(), { padding:[40,40] });
  highlightCard(id);
  if (isFloodRelated(a.event)) {
    autoActivateWMS('flood');
  } else {
    const chk = document.getElementById('chk-flood');
    if (chk && chk.checked) { chk.checked = false; toggleWMS('flood', false); }
  }
}

function zoomToFire(lat, lon, id) {
  map.setView([lat, lon], 16);
  highlightCard(id);
  autoActivateWMS('effis_fwi');
  autoActivateWMS('corine');
}

// ── Toggles capas ─────────────────────────────────────────────────────────
function toggleLayer(type, enabled) {
  if (type === 'alerts') {
    showAlerts = enabled; renderAlerts();
    if (enabled) activeList = 'alerts';
    else if (showFires) activeList = 'fires';
  }
  if (type === 'fires') {
    showFires = enabled; renderFires();
    if (enabled) activeList = 'fires';
    else if (showAlerts) activeList = 'alerts';
  }
  renderList();
}

// Filtros de nivel
document.querySelectorAll('#level-filters .fbtn').forEach(btn => {
  btn.addEventListener('click', () => {
    const level = btn.dataset.level;
    const all   = document.querySelector('.fbtn.all');
    const none  = document.querySelector('.fbtn.none');
    const colors = [...document.querySelectorAll('#level-filters .fbtn')]
      .filter(b => b.dataset.level !== 'all' && b.dataset.level !== 'none');

    if (level === 'all') {
      activeLevels = new Set(['Rojo','Naranja','Amarillo','Verde']);
      colors.forEach(b => b.classList.add('active'));
      all.classList.add('active'); none.classList.remove('active');
    } else if (level === 'none') {
      activeLevels = new Set();
      colors.forEach(b => b.classList.remove('active'));
      all.classList.remove('active'); none.classList.add('active');
    } else {
      none.classList.remove('active');
      if (activeLevels.has(level)) { activeLevels.delete(level); btn.classList.remove('active'); }
      else { activeLevels.add(level); btn.classList.add('active'); }
      if (activeLevels.size === 0) { none.classList.add('active'); all.classList.remove('active'); }
      else if (activeLevels.size === 4) { all.classList.add('active'); none.classList.remove('active'); }
      else { all.classList.remove('active'); }
    }
    renderAll();
  });
});

document.getElementById('event-select').addEventListener('change', e => {
  activeEvent = e.target.value; renderAll();
});

// ── Utilidades ────────────────────────────────────────────────────────────
function parsePolygon(str) {
  return str.trim().split(' ').map(p => {
    const [la,lo] = p.split(',').map(Number);
    return [la,lo];
  }).filter(([la,lo]) => !isNaN(la) && !isNaN(lo));
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('es-ES',{day:'2-digit',month:'short'}) + ' ' +
         d.toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'});
}

// ── Listeners WMS y capas de datos ────────────────────────────────────────
['flood','effis_fwi','effis_dc','corine'].forEach(key => {
  const el = document.getElementById('chk-' + key);
  if (el) el.addEventListener('change', e => toggleWMS(key, e.target.checked));
});

const chkAlerts = document.getElementById('chk-alerts');
const chkFires  = document.getElementById('chk-fires');
if (chkAlerts) chkAlerts.addEventListener('change', e => toggleLayer('alerts', e.target.checked));
if (chkFires)  chkFires.addEventListener('change',  e => toggleLayer('fires',  e.target.checked));

init();