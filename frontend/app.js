// Mapa base
const map = L.map('map', { zoomControl: false }).setView([40.0, -3.7], 6);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
  attribution: '© OpenStreetMap © CARTO', maxZoom: 18
}).addTo(map);

L.control.zoom({ position: 'topright' }).addTo(map);

const visibleBboxEl = document.getElementById('visible-bbox');
const pointerCoordEl = document.getElementById('pointer-coord');

function formatCoord(value, digits = 4) {
  return Number(value).toFixed(digits);
}

function updateVisibleBbox() {
  if (!visibleBboxEl) return;
  const bounds = map.getBounds();
  const southWest = bounds.getSouthWest();
  const northEast = bounds.getNorthEast();
  visibleBboxEl.textContent =
    `${formatCoord(southWest.lng)}, ${formatCoord(southWest.lat)} · ${formatCoord(northEast.lng)}, ${formatCoord(northEast.lat)}`;
}

function updatePointerCoord(latlng) {
  if (!pointerCoordEl) return;
  if (!latlng) {
    pointerCoordEl.textContent = '--';
    return;
  }
  pointerCoordEl.textContent = `${formatCoord(latlng.lat, 5)}, ${formatCoord(latlng.lng, 5)}`;
}

map.on('moveend zoomend', updateVisibleBbox);
map.on('mousemove', e => updatePointerCoord(e.latlng));
map.on('mouseout', () => updatePointerCoord(null));
updateVisibleBbox();

const resetBtn = L.control({ position: 'topright' });
resetBtn.onAdd = () => {
  const btn = L.DomUtil.create('button', 'leaflet-bar leaflet-control');
  btn.title = 'Ver España completa';
  btn.innerHTML = '&#8962;';
  btn.style.cssText = 'width:30px;height:30px;font-size:20px;cursor:pointer;background:#1a1d27;color:#aaa;border:1px solid #2a2d3a;display:flex;align-items:center;justify-content:center;margin-top:4px;';
  btn.onclick = () => {
    // Resetear vista
    map.setView([40.0, -3.7], 6);
    // Desactivar capas WMS
    Object.keys(wmsActive).forEach(key => {
      map.removeLayer(wmsActive[key]);
      delete wmsActive[key];
      const chk = document.getElementById('chk-' + key);
      if (chk) chk.checked = false;
    });
    // Desactivar CORINE
    if (corineLayer) { map.removeLayer(corineLayer); }
    corineVisible = false;
    const chkC = document.getElementById('chk-corine');
    if (chkC) chkC.checked = false;
    // Mantener las capas esenciales activas en la vista inicial.
    showAlerts = true;
    showFires = true;
    activeList = 'alerts';
    const chkAlerts = document.getElementById('chk-alerts');
    const chkFires = document.getElementById('chk-fires');
    if (chkAlerts) chkAlerts.checked = true;
    if (chkFires) chkFires.checked = true;
    if (tlMin) resetTimeline();
    renderAlerts();
    renderFires();
    renderList();
    updateLegend();
  };
  L.DomEvent.disableClickPropagation(btn);
  return btn;
};
resetBtn.addTo(map);

// ── WMS ────────────────────────────────────────────────────────────────────
const EFFIS_URL = 'https://maps.effis.emergency.copernicus.eu/effis';
const EFFIS_FIRES_URL = '/api/effis/wmts';
const SPAIN_BOUNDARY_URL = '/api/boundaries/spain';
const TODAY     = new Date().toISOString().split('T')[0];

const WMS_DEFS = {
  effis_fires: {
    url:     EFFIS_FIRES_URL,
    type:    'geojson',
    layer:   'effis_viirs_hs_today_wfs', // focos calientes EFFIS/Copernicus vectorizados
    time:    null,
    opacity: 0.85,
  },
  effis_fwi: {
    url:     EFFIS_URL,
    layer:   'mf010.fwi',        // Fire Weather Index: peligro meteorológico de incendio - diario
    time:    TODAY,
    opacity: 0.65,
    clipToSpain: true,
  },
  effis_dc: {
    url:     EFFIS_URL,
    layer:   'mf010.dc',         // Drought Code: sequía profunda diaria
    time:    TODAY,
    opacity: 0.65,
    clipToSpain: true,
  },
  flood: {
    url:     'https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones',
    layer:   'NZ.Flood.FluvialT100',  // inundación fluvial T=100 - MITECO/SNCZI - capa estatica
    time:    null,
    opacity: 0.6,
    version: '1.3.0',
  },
  // WMS CORINE completo (44 clases)
  corine_wms: {
    url:     'https://servicios.idee.es/wms-inspire/ocupacion-suelo',
    layer:   'LC.LandCoverSurfaces',  // CORINE Land Cover 2018 - IGN
    time:    null,                    // capa estática, cada 6 años
    opacity: 0.55,
    version: '1.3.0',
    minZoom: 8,                       // visible a partir de zoom 8
  },
};

const wmsActive = {};
const SPAIN_BOUNDS = L.latLngBounds([27.5, -18.5], [43.9, 4.5]);
const WMS_LAYER_PANE = 'wmsLayerPane';
let spainBoundaryData = null;
let spainBoundaryPromise = null;

map.createPane(WMS_LAYER_PANE);
map.getPane(WMS_LAYER_PANE).style.zIndex = 250;

function loadSpainBoundary() {
  if (spainBoundaryData) return Promise.resolve(spainBoundaryData);
  if (!spainBoundaryPromise) {
    spainBoundaryPromise = fetch(SPAIN_BOUNDARY_URL, { cache: 'force-cache' })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        spainBoundaryData = data;
        return data;
      })
      .catch(e => {
        spainBoundaryPromise = null;
        throw e;
      });
  }
  return spainBoundaryPromise;
}

function forEachSpainBoundaryGeometry(boundaryData, callback) {
  const features = boundaryData.type === 'FeatureCollection'
    ? boundaryData.features
    : [boundaryData];

  features.forEach(feature => {
    const geometry = feature.type === 'Feature' ? feature.geometry : feature;
    if (geometry) callback(geometry);
  });
}

function addGeometryToCanvasPath(ctx, geometry, coords, tileSize) {
  const tileOrigin = coords.scaleBy(tileSize);

  function addRing(ring) {
    let started = false;
    ring.forEach(([lon, lat]) => {
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
      const p = map.project([lat, lon], coords.z).subtract(tileOrigin);
      if (!started) {
        ctx.moveTo(p.x, p.y);
        started = true;
      } else {
        ctx.lineTo(p.x, p.y);
      }
    });
    if (started) ctx.closePath();
  }

  if (geometry.type === 'Polygon') {
    geometry.coordinates.forEach(addRing);
  } else if (geometry.type === 'MultiPolygon') {
    geometry.coordinates.forEach(polygon => {
      polygon.forEach(addRing);
    });
  }
}

function clipCanvasToSpain(ctx, coords, tileSize, boundaryData) {
  ctx.save();
  ctx.globalCompositeOperation = 'destination-in';
  ctx.beginPath();
  forEachSpainBoundaryGeometry(boundaryData, geometry => {
    addGeometryToCanvasPath(ctx, geometry, coords, tileSize);
  });
  ctx.fill('evenodd');
  ctx.restore();
}

const SpainClippedWMSLayer = L.TileLayer.WMS.extend({
  createTile(coords, done) {
    const tile = L.DomUtil.create('canvas', 'leaflet-tile');
    const size = this.getTileSize();
    tile.width = size.x;
    tile.height = size.y;

    const ctx = tile.getContext('2d');
    const img = new Image();
    img.alt = '';
    img.onload = () => {
      loadSpainBoundary()
        .then(boundaryData => {
          ctx.drawImage(img, 0, 0, size.x, size.y);
          clipCanvasToSpain(ctx, coords, size, boundaryData);
          done(null, tile);
        })
        .catch(e => {
          console.error('Error recortando la tesela WMS al límite de España:', e);
          ctx.drawImage(img, 0, 0, size.x, size.y);
          done(null, tile);
        });
    };
    img.onerror = () => done(new Error('No se pudo cargar la tesela WMS'), tile);
    img.src = this.getTileUrl(coords);

    return tile;
  },
});

function buildEffisFiresGeoJSON(d) {
  const layer = L.geoJSON(null, {
    pointToLayer: (feature, latlng) => {
      const p = feature.properties || {};
      const color = p.avg_color || '#ff0000';
      const radius = Math.max(4, Math.min(10, Math.sqrt(Number(p.pixel_count) || 16) / 2));
      return L.circleMarker(latlng, {
        radius,
        color: '#7f0000',
        fillColor: color,
        fillOpacity: d.opacity,
        weight: 1,
      });
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties || {};
      const coords = feature.geometry?.coordinates || [];
      const lon = Number(coords[0]);
      const lat = Number(coords[1]);
      const location = Number.isFinite(lat) && Number.isFinite(lon)
        ? `${lat.toFixed(4)}, ${lon.toFixed(4)}`
        : 'Coordenadas no disponibles';
      layer.bindTooltip(
        `<b>Foco EFFIS/Copernicus</b><br>${location}<br>` +
        `Píxeles detectados: ${p.pixel_count ?? 'n/d'}<br>` +
        `Color medio: ${p.avg_color || 'n/d'}`,
        { sticky: true }
      );
    },
  });

  fetch(d.url)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => layer.addData(data))
    .catch(e => console.error('Error cargando EFFIS GeoJSON:', e));

  return layer;
}

function buildWMS(key) {
  const d = WMS_DEFS[key];
  if (d.type === 'geojson') {
    return buildEffisFiresGeoJSON(d);
  }
  if (d.type === 'wmts') {
    const url =
      `${d.url}/${d.layer}/{z}/{y}/{x}.png`;

    return L.tileLayer(url, {
      opacity: d.opacity,
      bounds: SPAIN_BOUNDS,
      pane: WMS_LAYER_PANE,
      minZoom: d.minZoom,
      maxZoom: d.maxZoom || 18,
    });
  }

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
    pane:        WMS_LAYER_PANE,
  };
  if (d.time) opts.TIME = d.time;
  if (d.minZoom) opts.minZoom = d.minZoom;
  return d.clipToSpain
    ? new SpainClippedWMSLayer(d.url, opts)
    : L.tileLayer.wms(d.url, opts);
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

const EFFIS_FIRE_DANGER_FWI_CLASSES = [
  { color: '#9CFFC0', nameEs: 'Bajo',         nameEn: 'Low',          min: null, max: 11.2 },
  { color: '#CDE24E', nameEs: 'Moderado',     nameEn: 'Moderate',     min: 11.2, max: 21.3 },
  { color: '#E6AC00', nameEs: 'Alto',         nameEn: 'High',         min: 21.3, max: 38.0 },
  { color: '#D97010', nameEs: 'Muy alto',     nameEn: 'Very High',    min: 38.0, max: 50.0 },
  { color: '#AD060E', nameEs: 'Extremo',      nameEn: 'Extreme',      min: 50.0, max: 70.0 },
  { color: '#3A0015', nameEs: 'Muy extremo',  nameEn: 'Very Extreme', min: 70.0, max: null },
];

const EFFIS_FIRE_DANGER_DC_CLASSES = [
  { color: '#9CFFC0', nameEs: 'Bajo',         nameEn: 'Low',          min: null, max: 256.1 },
  { color: '#CDE24E', nameEs: 'Moderado',     nameEn: 'Moderate',     min: 256.1, max: 334.1 },
  { color: '#E6AC00', nameEs: 'Alto',         nameEn: 'High',         min: 334.1, max: 450.6 },
  { color: '#D97010', nameEs: 'Muy alto',     nameEn: 'Very High',    min: 450.6, max: 600.0 },
  { color: '#AD060E', nameEs: 'Extremo',      nameEn: 'Extreme',      min: 600.0, max: 749.4 },
  { color: '#3A0015', nameEs: 'Muy extremo',  nameEn: 'Very Extreme', min: 749.4, max: null },
];

function formatEffisIndexValue(value) {
  return value.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function formatEffisIndexRange(effisClass, indexName) {
  if (effisClass.min === null) return `${indexName} < ${formatEffisIndexValue(effisClass.max)}`;
  if (effisClass.max === null) return `${indexName} > ${formatEffisIndexValue(effisClass.min)}`;
  return `${indexName} ${formatEffisIndexValue(effisClass.min)} - ${formatEffisIndexValue(effisClass.max)}`;
}

// Leyenda WMS
const WMS_LEGENDS = {
  effis_fires: {
    title: 'Focos activos VIIRS (EFFIS)',
    items: [
      { color: '#ff66cc', label: 'Menos de 6 h' },
      { color: '#ff9999', label: '6 a 12 h' },
      { color: '#ff0000', label: '12 a 24 h' },
    ],
    note: 'Copernicus EFFIS - últimos 1 día'
  },
  effis_fwi: {
    title: 'Peligro de incendio FWI (EFFIS)',
    items: EFFIS_FIRE_DANGER_FWI_CLASSES.map(c => ({
      color: c.color,
      label: `${c.nameEs} (${formatEffisIndexRange(c, 'FWI')})`,
    })),
    note: 'Capa WMS mf010.fwi - MeteoFrance ~10 km - clases oficiales EFFIS'
  },
  effis_dc: {
    title: 'Código de sequía DC (EFFIS)',
    items: EFFIS_FIRE_DANGER_DC_CLASSES.map(c => ({
      color: c.color,
      label: `${c.nameEs} (${formatEffisIndexRange(c, 'DC')})`,
    })),
    note: 'Capa WMS mf010.dc - subcomponente FWI - clases oficiales EFFIS'
  },
  flood: {
    title: 'Zonas inundables fluviales T=100',
    items: [
      { color: '#4da6ff', label: 'Peligrosidad media (T=100 años)' },
    ],
    note: 'MITECO/SNCZI - capa estática oficial España'
  },
  corine_wms: {
    title: 'Usos del suelo CORINE 2018 (IGN)',
    items: [
      { color: '#e6004d', label: 'Tejido urbano' }, //11
      { color: '#cc4df2', label: 'Industrial y comercial' }, //12
      { color: '#cccccc', label: 'Extracción minera' }, //13
      { color: '#a6e6cc', label: 'Zonas verdes artificiales' }, //14
      { color: '#ffffa8', label: 'Tierras de labor' }, //21
      { color: '#ffff00', label: 'Cultivos permanentes' }, //22
      { color: '#e6e64d', label: 'Praderas' }, //23
      { color: '#e6cc4d', label: 'Zonas agrícolas heterogéneas' }, //24
      { color: '#267300', label: 'Bosques' }, //31
      { color: '#70a800', label: 'Vegetación arbustiva y herbácea' }, //32
      { color: '#ccaa4d', label: 'Espacios abiertos sin vegetación' }, //33
      { color: '#a6a6ff', label: 'Zonas húmedas continentales' }, //41
      { color: '#4d4dff', label: 'Zonas húmedas costeras' }, //42
      { color: '#80d4ff', label: 'Aguas continentales' }, //51
      { color: '#00ccf2', label: 'Aguas marinas' }, //52
    ],
    note: 'CORINE Land Cover 2018 - IGN/CNIG - nivel 2'
  },
};

function updateLegend() {
  const el = document.getElementById('wms-legend');
  if (!el) return;
 
  const wmsKeys = Object.keys(wmsActive);
  const showCorine = corineVisible && corineLayer;
  if (!wmsKeys.length && !showCorine) { el.style.display = 'none'; return; }
 
  el.style.display = 'block';
 
  const wmsHtml = wmsKeys.map(key => {
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
 
  const corineHtml = showCorine ? (() => {
    const items = CORINE_LEGEND.items.map(i =>
      `<div class="leg-item">
        <span class="leg-dot" style="background:${i.color}"></span>
        <span class="leg-label">${i.label}</span>
      </div>`
    ).join('');
    return `<div class="leg-block">
      <div class="leg-title">${CORINE_LEGEND.title}</div>
      ${items}
      <div class="leg-note">${CORINE_LEGEND.note}</div>
    </div>`;
  })() : '';
 
  el.innerHTML = wmsHtml + corineHtml;
}
 
// CORINE (vector tiles MVT desde backend)
let corineLayer   = null;   // L.vectorGrid instance
let corineVisible = false;
let corineTooltip = null;
const CORINE_VECTOR_TILE_URL = '/api/landcover/tiles/{z}/{x}/{y}.mvt';

const CORINE_CLASSES = [
  { code: '1001', color: '#e6004d', label: 'Tejido urbano' },
  { code: '121', color: '#cc4df2', label: 'Zonas industriales o comerciales' },
  { code: '211', color: '#ffffa8', label: 'Tierras de labor secano' },
  { code: '242', color: '#e6e600', label: 'Mosaico de cultivos' },
  { code: '311', color: '#4ce600', label: 'Bosque de frondosas' },
  { code: '312', color: '#267300', label: 'Bosque de coníferas' },
  { code: '313', color: '#70a800', label: 'Bosque mixto' },
  { code: '321', color: '#d4e6a5', label: 'Pastizales naturales' },
  { code: '322', color: '#a8a800', label: 'Brezales y matorrales' },
  { code: '323', color: '#d4a46a', label: 'Vegetación esclerófila' },
  { code: '324', color: '#c8c800', label: 'Matorral en transición' },
];

const CORINE_CLASS_INDEX = Object.fromEntries(CORINE_CLASSES.map(item => [item.code, item]));
 
const CORINE_LEGEND = {
  title: 'Usos del suelo (filtrado)',
  items: CORINE_CLASSES.map(item => ({ color: item.color, label: item.label })),
  note: 'CORINE Land Cover 2018 - IGN/CNIG - selección filtrada de usos del suelo'
};
 
function getCorineFeatureStyle(properties) {
  const classInfo = CORINE_CLASS_INDEX[properties.class_code] || null;
  const color = classInfo?.color || properties.class_color || properties.color || '#888888';
  return {
    fill:        true,
    fillColor:   color,
    fillOpacity: 0.55,
    color,
    opacity:     0.5,
    weight:      0.2,
  };
}

function clearCorineTooltip() {
  if (corineTooltip) {
    map.removeLayer(corineTooltip);
    corineTooltip = null;
  }
}

function ensureCorineTooltip(latlng, content) {
  if (!corineTooltip) {
    corineTooltip = L.tooltip({
      permanent: false,
      sticky: true,
      direction: 'top',
      opacity: 0.95,
    });
  }
  corineTooltip.setLatLng(latlng).setContent(content);
  if (!map.hasLayer(corineTooltip)) corineTooltip.addTo(map);
}

function buildCorineLayer() {
  const layerStyles = {
    landcover: properties => getCorineFeatureStyle(properties),
    landcover_mvt_source: properties => getCorineFeatureStyle(properties),
    'pub.landcover_mvt_source': properties => getCorineFeatureStyle(properties),
  };
  const layer = L.vectorGrid.protobuf(CORINE_VECTOR_TILE_URL, {
    rendererFactory: L.canvas.tile,
    interactive: true,
    // El backend sirve MVT de detalle por feature también a zoom alto;
    // limitarlo a z14 difumina o hace demasiado sutiles manchas pequeñas.
    maxNativeZoom: 18,
    vectorTileLayerStyles: layerStyles,
    getFeatureId: feature => feature.properties.core_feature_id,
  });
  layer.on('mouseover', e => {
    const props = e.layer.properties || {};
    const label = props.class_label || props.label || 'Uso del suelo';
    ensureCorineTooltip(e.latlng, label);
  });
  layer.on('mousemove', e => {
    if (corineTooltip) corineTooltip.setLatLng(e.latlng);
  });
  layer.on('mouseout', () => {
    clearCorineTooltip();
  });
  layer.on('click', e => {
    const props = e.layer.properties || {};
    const label = props.class_label || props.label || 'Uso del suelo';
    L.popup()
      .setLatLng(e.latlng)
      .setContent(`<b>${label}</b><br>Código canónico: ${props.class_code || 'n/d'}`)
      .openOn(map);
  });
  return layer;
}

function toggleCorine(enabled) {
  corineVisible = enabled;
  if (enabled) {
    if (!corineLayer) corineLayer = buildCorineLayer();
    if (corineLayer) corineLayer.addTo(map);
  } else {
    clearCorineTooltip();
    if (corineLayer) map.removeLayer(corineLayer);
  }
  updateLegend();
}
 
function autoActivateCorine() {
  const chk = document.getElementById('chk-corine');
  if (chk && !chk.checked) {
    chk.checked = true;
    toggleCorine(true);
  }
}

// Estado 
let alertsData   = [];
let firesData    = [];
let alertLayers  = {};
let fireLayers   = [];
let showAlerts   = true;
let showFires    = true;
let activeList   = 'alerts';
let activeLevels = new Set(['Rojo','Naranja','Amarillo','Verde']);
let activeEvent  = 'all';
let firesError   = null;
let firesLoading = false;

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

// Carga 
async function fetchJson(url) {
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) {
    let message = `HTTP ${r.status}`;
    try {
      const data = await r.json();
      if (data.detail) message = data.detail;
    } catch (_) {}
    throw new Error(message);
  }
  return r.json();
}

function fetchSpainHotspots() {
  return fetchJson('/api/fires');
}

function buildClientStats(alerts, fires) {
  const levelCount = {};
  const fireLevelCount = {};
  alerts.forEach(a => {
    levelCount[a.level] = (levelCount[a.level] || 0) + 1;
  });
  fires.forEach(f => {
    fireLevelCount[f.level] = (fireLevelCount[f.level] || 0) + 1;
  });
  return {
    alerts: { total: alerts.length, por_nivel: levelCount },
    fires: {
      total: fires.length,
      por_nivel: fireLevelCount,
      frp_max: Math.max(0, ...fires.map(f => Number(f.frp) || 0)),
    },
  };
}

function updateStatsBar(stats) {
  const fireLoadingNote = firesLoading
    ? ' &nbsp;-&nbsp; <span style="color:#9db7ff">FIRMS: cargando...</span>'
    : '';
  const fireNote = firesError
    ? ` &nbsp;-&nbsp; <span style="color:#ff7676">FIRMS: ${firesError}</span>`
    : '';
  document.getElementById('stats-bar').innerHTML =
    `<b>${stats.alerts.total}</b> avisos AEMET &nbsp;-&nbsp; `+
    `<b>${stats.fires.total}</b> focos FIRMS &nbsp;-&nbsp; `+
    `FRP máx: <b>${stats.fires.frp_max.toFixed(1)} MW</b>`+
    fireLoadingNote +
    fireNote;
}

async function loadFiresInBackground() {
  firesLoading = true;
  updateStatsBar(buildClientStats(alertsData, firesData));
  if (activeList === 'fires') renderList();

  try {
    firesData = await fetchSpainHotspots();
    firesError = null;
  } catch (error) {
    firesData = [];
    firesError = error.message;
  } finally {
    firesLoading = false;
    updateStatsBar(buildClientStats(alertsData, firesData));
    renderFires();
    renderList();
  }
}

async function init() {
  document.getElementById('stats-bar').textContent = 'Cargando datos...';
  document.getElementById('main-list').innerHTML = '<div class="empty">Cargando...</div>';
  const [alertsResult] = await Promise.allSettled([
    fetchJson('/api/alerts'),
  ]);

  alertsData = alertsResult.status === 'fulfilled' ? alertsResult.value : [];
  firesData = [];
  firesError = null;
  firesLoading = true;
  const stats = buildClientStats(alertsData, firesData);
  updateStatsBar(stats);

  populateEventFilter();
  initTimeline();
  const chkF = document.getElementById('chk-fires');
  if (chkF) chkF.checked = true;
  renderAlerts();
  renderFires();
  renderList();
  void loadFiresInBackground();
}

// Filtrado
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

// Renderizar
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

    // Activacion de capas en click a poligonos
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

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatFireTime(f) {
  if (!f.acq_time) return '';
  const time = String(f.acq_time).padStart(4, '0');
  return time.replace(/(\d{2})(\d{2})/, '$1:$2');
}

function renderFires() {
  fireLayers.forEach(l => map.removeLayer(l));
  fireLayers = [];
  if (!showFires) return;
  if (firesError) {
    if (activeList === 'fires') updateListHeader([]);
    return;
  }

  firesData.forEach(f => {
    const lat = Number(f.latitude);
    const lon = Number(f.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    const radius = f.level === 'Rojo' ? 10 : f.level === 'Naranja' ? 7 : 5;
    const circle = L.circleMarker([lat, lon], {
      radius, color: f.level_color, fillColor: f.level_color,
      fillOpacity: 0.85, weight: 1.5,
    }).addTo(map);
    circle.fireId = f.id;

    const hora = formatFireTime(f);
    circle.bindTooltip(
      `<b>Foco de incendio</b><br>FRP: ${f.frp} MW · `+
      `<span style="color:${f.level_color}">${f.level}</span><br>${f.acq_date} ${hora} UTC`,
      { sticky: true }
    );
    
    // Activacion de capas en click a puntos
    circle.on('click', () => {
      map.setView([lat, lon], 16);
      highlightCard(f.id);
      autoActivateWMS('effis_fwi');  // peligro meteorológico de incendio FWI
      autoActivateCorine();    // tipo de vegetación
    });

    fireLayers.push(circle);
  });

  if (activeList === 'fires') updateListHeader(firesData);
}

// Sidebar 
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
    if (firesLoading) {
      el.innerHTML = '<div class="empty">Cargando focos FIRMS...</div>';
      return;
    }
    if (firesError) {
      el.innerHTML = `<div class="empty">No se pudieron cargar los focos FIRMS: ${escapeHtml(firesError)}</div>`;
      return;
    }
    if (!firesData.length) { el.innerHTML = '<div class="empty">Sin focos activos en España</div>'; return; }

    const sorted = firesData
      .filter(f => Number.isFinite(Number(f.latitude)) && Number.isFinite(Number(f.longitude)))
      .sort((a,b) => b.frp - a.frp);
    if (!sorted.length) { el.innerHTML = '<div class="empty">Sin focos activos en España</div>'; return; }
    el.innerHTML = sorted.map(f => {
      const hora = formatFireTime(f);
      const lat = Number(f.latitude);
      const lon = Number(f.longitude);
      return `<div class="card" data-id="${f.id}"
        style="border-left-color:${f.level_color}" onclick="zoomToFire(${lat},${lon},'${f.id}')">
        <div class="name">${lat.toFixed(3)}, ${lon.toFixed(3)}</div>
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

// Zoom 
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
  map.setView([lat, lon], 14);
  highlightCard(id);
  autoActivateWMS('effis_fwi');
  autoActivateCorine();
}

// Toggles capas
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

// Utilidades
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

// Listeners WMS y capas de datos 
const chkCorine = document.getElementById('chk-corine');
if (chkCorine) chkCorine.addEventListener('change', e => toggleCorine(e.target.checked));
 
['effis_fires','flood','effis_fwi','effis_dc','corine_wms'].forEach(key => {
  const el = document.getElementById('chk-' + key);
  if (el) el.addEventListener('change', e => toggleWMS(key, e.target.checked));
});
 
const chkAlerts = document.getElementById('chk-alerts');
const chkFires  = document.getElementById('chk-fires');
if (chkAlerts) chkAlerts.addEventListener('change', e => toggleLayer('alerts', e.target.checked));
if (chkFires)  chkFires.addEventListener('change',  e => toggleLayer('fires',  e.target.checked));
 
init().then(() => {
  const urlParams = new URLSearchParams(window.location.search);
  if (['1', 'true', 'yes'].includes((urlParams.get('corine') || '').toLowerCase())) {
    autoActivateCorine();
  }
});
