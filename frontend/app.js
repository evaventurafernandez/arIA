// Mapa base
const IGN_ATTRIBUTION = '© Instituto Geográfico Nacional / CNIG';

const map = L.map('map', {
  zoomControl: false,
  maxZoom: 20,
}).setView([40.0, -3.7], 6);

const baseIGNSimplificado = L.tileLayer(
  'https://tms-ign-base.idee.es/1.0.0/IGNBaseSimplificado/{z}/{x}/{-y}.png',
  {
    attribution: IGN_ATTRIBUTION,
    maxZoom: 20,
  }
);

const baseIGNTodo = L.tileLayer(
  'https://tms-ign-base.idee.es/1.0.0/IGNBaseTodo/{z}/{x}/{-y}.jpeg',
  {
    attribution: IGN_ATTRIBUTION,
    maxZoom: 20,
  }
);

const basePNOA = L.tileLayer(
  'https://tms-pnoa-ma.idee.es/1.0.0/pnoa-ma/{z}/{x}/{-y}.jpeg',
  {
    attribution: IGN_ATTRIBUTION,
    maxNativeZoom: 19,
    maxZoom: 20,
  }
);

baseIGNTodo.addTo(map);

const baseLayers = {
  'IGN Base completo': baseIGNTodo,
  'IGN Base simplificado': baseIGNSimplificado,
  'Ortofoto PNOA': basePNOA,
};

const thematicLayers = {
  // Futuras capas temáticas Leaflet:
  // 'Municipios': municipiosLayer,
  // 'Avisos meteorológicos': avisosLayer,
};

L.control.layers(baseLayers, thematicLayers, {
  collapsed: true,
  position: 'topleft',
}).addTo(map);

L.control.zoom({ position: 'topright' }).addTo(map);

const mapZoomEl = document.getElementById('map-zoom');
const visibleBboxEl = document.getElementById('visible-bbox');
const pointerCoordEl = document.getElementById('pointer-coord');

function formatCoord(value, digits = 4) {
  return Number(value).toFixed(digits);
}

function formatZoom(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return '--';
  return Number.isInteger(numericValue)
    ? String(numericValue)
    : numericValue.toFixed(2).replace(/\.?0+$/, '');
}

function updateMapZoom() {
  if (!mapZoomEl) return;
  mapZoomEl.textContent = formatZoom(map.getZoom());
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
map.on('zoomend', updateMapZoom);
map.on('mousemove', e => updatePointerCoord(e.latlng));
map.on('mouseout', () => updatePointerCoord(null));
updateMapZoom();
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
      const chk = document.getElementById('chk-' + key);
      if (chk) chk.checked = false;
      toggleWMS(key, false);
    });
    // Desactivar CORINE
    if (corineLayer) { map.removeLayer(corineLayer); }
    corineVisible = false;
    const chkNucleos = document.getElementById('chk-nucleos_poblacion');
    if (chkNucleos) chkNucleos.checked = false;
    toggleNucleos(false);
    // Desactivar burnt area diaria
    const chkBurntArea = document.getElementById('chk-burnt_area_daily');
    if (chkBurntArea) chkBurntArea.checked = false;
    toggleBurntAreaLayer(false);
    // Desactivar histórico FIRMS
    const chkFirmsHistory = document.getElementById('chk-firms_history');
    if (chkFirmsHistory) chkFirmsHistory.checked = false;
    toggleHistoricalFiresLayer(false);
    const chkAemetMaxTempHistory = document.getElementById('chk-aemet_max_temp_history');
    if (chkAemetMaxTempHistory) chkAemetMaxTempHistory.checked = false;
    toggleAemetMaxTempLayer(false);
    // Mantener las capas esenciales activas en la vista inicial.
    showAlerts = true;
    showFires = true;
    activeList = 'alerts';
    const chkAlerts = document.getElementById('chk-alerts');
    const chkFires = document.getElementById('chk-fires');
    if (chkAlerts) chkAlerts.checked = true;
    if (chkFires) chkFires.checked = true;
    syncTimelinePanelsVisibility();
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
const SPAIN_BOUNDARY_URL = '/api/boundaries/spain';
const LANDCOVER_WMS_CRS = L.CRS.EPSG4326;

function localIsoDate(date = new Date()) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().split('T')[0];
}

const TODAY = localIsoDate();
const BURNT_AREA_LAYER_METADATA_URL = '/api/layers/burnt-area';
const BURNT_AREA_DEFAULT_VERSION = 'v4';
const BURNT_AREA_DEFAULT_FORMAT = 'cog';
const BURNT_AREA_DEFAULT_DATE_FROM = '2025-05-01';
const BURNT_AREA_DEFAULT_DATE_TO = '2025-08-31';
const BURNT_AREA_MAX_NATIVE_ZOOM = 10;
const BURNT_AREA_LOCATOR_SOURCE_ZOOM = 10;
const BURNT_AREA_DISPLAY_MODE_DAILY = 'daily';
const BURNT_AREA_DISPLAY_MODE_CUMULATIVE = 'cumulative';
const BURNT_AREA_DISPLAY_MODES = new Set([
  BURNT_AREA_DISPLAY_MODE_DAILY,
  BURNT_AREA_DISPLAY_MODE_CUMULATIVE,
]);
const FIRMS_HISTORY_TIMELINE_URL = '/api/firms/history/timeline';
const FIRMS_HISTORY_FEATURES_URL = '/api/firms/history/features';
const FIRMS_HISTORY_DEFAULT_DATE_FROM = '2025-05-01';
const FIRMS_HISTORY_DEFAULT_DATE_TO = '2025-08-31';
const FIRMS_HISTORY_FETCH_LIMIT = 20000;
const AEMET_MAX_TEMP_LAYER_METADATA_URL = '/api/layers/aemet-max-temperature';
const AEMET_MAX_TEMP_TIMELINE_URL = '/api/aemet/max-temperature/timeline';
const AEMET_MAX_TEMP_DEFAULT_DATE_FROM = '2025-05-01';
const AEMET_MAX_TEMP_DEFAULT_DATE_TO = '2025-08-31';
const AEMET_MAX_TEMP_MVT_LAYER_NAME = 'aemet_max_temp';
const NUCLEOS_VECTOR_TILE_URL = '/api/nucleos/tiles/{z}/{x}/{y}.mvt';
const NUCLEOS_MVT_LAYER_NAME = 'nucleos_poblacion';
const NUCLEOS_MIN_ZOOM = 8;
const HISTORICAL_DATA_FETCH_OPTIONS = { cache: 'force-cache' };

const WMS_DEFS = {
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
    layer:   'NZ.Flood.FluvialT10',   // inundación fluvial T=10 - MITECO/SNCZI - capa estática
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
    crs:     LANDCOVER_WMS_CRS,
    minZoom: 8,                       // visible a partir de zoom 8
  },
};

const wmsActive = {};
const SPAIN_BOUNDS = L.latLngBounds([27.5, -18.5], [43.9, 4.5]);
const WMS_LAYER_PANE = 'wmsLayerPane';
const BURNT_AREA_LOCATOR_PANE = 'burntAreaLocatorPane';
const AEMET_MAX_TEMP_PANE = 'aemetMaxTempPane';
const NUCLEOS_PANE = 'nucleosPoblacionPane';
const CORINE_SELECTION_PANE = 'corineSelectionPane';
let spainBoundaryData = null;
let spainBoundaryPromise = null;
let burntAreaLayer = null;
let burntAreaLocatorLayer = null;
let burntAreaLocatorCache = new Map();
let burntAreaLocatorCachePromise = null;
let burntAreaLocatorKey = null;
let burntAreaVisible = false;
let burntAreaDisplayMode = BURNT_AREA_DISPLAY_MODE_DAILY;
let burntAreaMetadata = null;
let burntAreaTimeline = [];
let burntAreaTimelineByDate = new Map();
let burntAreaLoadingPromise = null;
let burntAreaError = null;
let historicalFiresVisible = false;
let historicalFiresMetadata = null;
let historicalFiresTimeline = [];
let historicalFiresTimelineByDate = new Map();
let historicalTimeline = [];
let historicalTimelineIndex = 0;
let historicalTimelinePlayInterval = null;
let historicalFiresData = [];
let historicalFireLayers = [];
let historicalFiresLoadingPromise = null;
let historicalFiresError = null;
let historicalFiresFrameLoading = false;
let historicalFiresRequestToken = 0;
const historicalFiresDataCache = new Map();
const historicalFiresRenderer = L.canvas({ padding: 0.5 });
let aemetMaxTempVisible = false;
let aemetMaxTempMetadata = null;
let aemetMaxTempTimeline = [];
let aemetMaxTempTimelineByDate = new Map();
let aemetMaxTempLoadingPromise = null;
let aemetMaxTempError = null;
let aemetMaxTempLayer = null;
let nucleosLayer = null;
let nucleosVisible = false;
let nucleosTooltip = null;
let nucleosMapPopup = null;

map.createPane(WMS_LAYER_PANE);
map.getPane(WMS_LAYER_PANE).style.zIndex = 250;
map.createPane(BURNT_AREA_LOCATOR_PANE);
map.getPane(BURNT_AREA_LOCATOR_PANE).style.zIndex = 285;
map.getPane(BURNT_AREA_LOCATOR_PANE).style.pointerEvents = 'none';
map.createPane(AEMET_MAX_TEMP_PANE);
map.getPane(AEMET_MAX_TEMP_PANE).style.zIndex = 330;
map.createPane(NUCLEOS_PANE);
map.getPane(NUCLEOS_PANE).style.zIndex = 345;
map.createPane(CORINE_SELECTION_PANE);
map.getPane(CORINE_SELECTION_PANE).style.zIndex = 460;
map.getPane(CORINE_SELECTION_PANE).style.pointerEvents = 'none';

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
    pane:        WMS_LAYER_PANE,
  };
  if (d.time) opts.TIME = d.time;
  if (d.minZoom) opts.minZoom = d.minZoom;
  if (d.crs) opts.crs = d.crs;
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
    if (key === 'corine_wms') clearCorinePointSelection();
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
    title: 'Zonas inundables fluviales T=10',
    items: [
      { color: '#4da6ff', label: 'Peligrosidad alta (T=10 años)' },
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

const FIRMS_FRP_CLASSES = [
  { color: '#FFD166', label: '<10 MW: bajo' },
  { color: '#F8961E', label: '10-50 MW: medio' },
  { color: '#E94F37', label: '50-200 MW: alto' },
  { color: '#8E1B1B', label: '>200 MW: muy alto' },
];

const FIRMS_CONFIDENCE_STYLES = {
  n: { label: 'nominal', weight: 1 },
  h: { label: 'alta', weight: 3 },
};

function formatFireFrp(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '0,0';
  return num.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function getFireIntensityLabel(f) {
  return f.intensity_label || f.frp_category || f.level || 'Sin clasificar';
}

function getFireIntensityColor(f) {
  return f.intensity_color || f.level_color || '#F8961E';
}

function getFireConfidenceCode(f) {
  const raw = String(f.confidence_code || f.confidence || '').trim().toLowerCase();
  const aliases = { low: 'l', l: 'l', nominal: 'n', n: 'n', high: 'h', h: 'h' };
  return aliases[raw] || raw;
}

function getFireConfidenceLabel(f) {
  const code = getFireConfidenceCode(f);
  return f.confidence_label || FIRMS_CONFIDENCE_STYLES[code]?.label || code || 'no indicada';
}

function getFireBorderWeight(f) {
  return FIRMS_CONFIDENCE_STYLES[getFireConfidenceCode(f)]?.weight || 1;
}

function getFireRadius(f) {
  const frp = Number(f.frp) || 0;
  if (frp > 200) return 11;
  if (frp >= 50) return 9;
  if (frp >= 10) return 7;
  return 5;
}

function getFireDayNightLabel(f) {
  const raw = String(f.daynight || '').trim().toUpperCase();
  if (raw === 'D') return 'Día';
  if (raw === 'N') return 'Noche';
  return raw || 'no indicado';
}

function getFireDateTimeLabel(f) {
  const hora = formatFireTime(f);
  const date = f.acq_date || 'fecha no indicada';
  return `${date}${hora ? ` ${hora}` : ''} UTC`;
}

function updateLegend() {
  const el = document.getElementById('wms-legend');
  if (!el) return;
 
  const wmsKeys = Object.keys(wmsActive);
  const showCorine = corineVisible && corineLayer;
  const showNucleos = nucleosVisible && nucleosLayer;
  const showFirms = (showFires && !firesError) || (historicalFiresVisible && !historicalFiresError);
  const showAemetMaxTemp = aemetMaxTempVisible && !aemetMaxTempError;
  if (!wmsKeys.length && !showCorine && !showNucleos && !showFirms && !showAemetMaxTemp) { el.style.display = 'none'; return; }
 
  el.style.display = 'block';

  const firmsHtml = showFirms ? (() => {
    const frpItems = FIRMS_FRP_CLASSES.map(i =>
      `<div class="leg-item">
        <span class="leg-dot" style="background:${i.color}"></span>
        <span class="leg-label">${i.label}</span>
      </div>`
    ).join('');
    return `<div class="leg-block">
      <div class="leg-title">Potencia radiativa del foco (FRP, MW)</div>
      ${frpItems}
      <div class="leg-subtitle">Confianza de detección</div>
      <div class="leg-item">
        <span class="leg-ring" style="border-width:1px"></span>
        <span class="leg-label">nominal</span>
      </div>
      <div class="leg-item">
        <span class="leg-ring" style="border-width:3px"></span>
        <span class="leg-label">alta</span>
      </div>
      <div class="leg-note">Categorías visuales de intensidad; no son umbrales oficiales NASA.</div>
    </div>`;
  })() : '';
 
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

  const nucleosHtml = showNucleos ? (() => {
    const items = NUCLEOS_LEGEND.items.map(i =>
      `<div class="leg-item">
        <span class="leg-dot" style="background:${i.color}"></span>
        <span class="leg-label">${i.label}</span>
      </div>`
    ).join('');
    return `<div class="leg-block">
      <div class="leg-title">${NUCLEOS_LEGEND.title}</div>
      ${items}
      <div class="leg-note">${NUCLEOS_LEGEND.note}</div>
    </div>`;
  })() : '';

  const aemetMaxTempHtml = showAemetMaxTemp ? `<div class="leg-block">
      <div class="leg-title">Avisos AEMET temperaturas máximas</div>
      <div class="leg-item">
        <span class="leg-dot" style="background:#FFD700"></span>
        <span class="leg-label">Amarillo</span>
      </div>
      <div class="leg-item">
        <span class="leg-dot" style="background:#FFA500"></span>
        <span class="leg-label">Naranja</span>
      </div>
      <div class="leg-item">
        <span class="leg-dot" style="background:#CC0000"></span>
        <span class="leg-label">Rojo</span>
      </div>
      <div class="leg-note">Capa histórica diaria filtrada a AT;Temperaturas máximas.</div>
    </div>` : '';
 
  el.innerHTML = firmsHtml + aemetMaxTempHtml + wmsHtml + corineHtml + nucleosHtml;
}
 
// CORINE (vector tiles MVT desde backend)
let corineLayer   = null;   // L.vectorGrid instance
let corineVisible = false;
let corineTooltip = null;
let corineMapPopup = null;
let corinePointSelectionLayer = null;
let corinePointQueryController = null;
let corinePointQueryToken = 0;
let fireLandcoverBatchToken = 0;
const CORINE_VECTOR_TILE_URL = '/api/landcover/tiles/{z}/{x}/{y}.mvt';
const LANDCOVER_POINT_QUERY_SIZE = 101;
const LANDCOVER_FIRE_QUERY_ZOOM = 16;
const FIRE_LANDCOVER_WORKERS = 4;
const fireLandcoverInfoCache = new Map();

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

const NUCLEOS_POPULATION_CLASSES = [
  { code: 'menor_100', color: '#7fc97f', label: '< 100' },
  { code: '100_499', color: '#4db6ac', label: '100-499' },
  { code: '500_4999', color: '#3f88c5', label: '500-4.999' },
  { code: '5000_49999', color: '#f2c14e', label: '5.000-49.999' },
  { code: '50000_mas', color: '#e76f51', label: '>= 50.000' },
];

const NUCLEOS_POPULATION_INDEX = Object.fromEntries(
  NUCLEOS_POPULATION_CLASSES.map(item => [item.code, item])
);
const NUCLEOS_POPULATION_FALLBACK = { color: '#7fc97f', label: 'Población registrada' };

const NUCLEOS_LEGEND = {
  title: 'Núcleos de población',
  items: NUCLEOS_POPULATION_CLASSES.map(item => ({ color: item.color, label: item.label })),
  note: `BTN IGN - habitantes > 0 - polígonos visibles desde zoom ${NUCLEOS_MIN_ZOOM}`
};

function getNucleosPopulationInfo(properties) {
  return NUCLEOS_POPULATION_INDEX[properties.population_class] || NUCLEOS_POPULATION_FALLBACK;
}

function formatNucleosHabitantes(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return 'sin dato';
  return Math.round(numericValue).toLocaleString('es-ES');
}

function getNucleosFeatureStyle(properties) {
  const classInfo = getNucleosPopulationInfo(properties);
  const rank = Number(properties.population_rank) || 0;
  const isCapital = Boolean(properties.is_capital);
  return {
    fill: true,
    fillColor: classInfo.color,
    fillOpacity: Math.min(0.2 + rank * 0.045, 0.48),
    color: isCapital ? '#ffffff' : '#17202c',
    opacity: isCapital ? 0.92 : 0.72,
    weight: isCapital ? 1.1 : 0.45,
  };
}

function clearNucleosTooltip() {
  if (nucleosTooltip) {
    map.removeLayer(nucleosTooltip);
    nucleosTooltip = null;
  }
}

function closeNucleosMapPopup() {
  const popup = nucleosMapPopup;
  nucleosMapPopup = null;
  if (!popup) return;
  if (map.closePopup) map.closePopup(popup);
}

function openNucleosMapPopup(latlng, content) {
  closeNucleosMapPopup();
  nucleosMapPopup = L.popup({ className: 'nucleos-poblacion-popup' })
    .setLatLng(latlng)
    .setContent(content);
  nucleosMapPopup.openOn(map);
  return nucleosMapPopup;
}

function buildNucleosPopupContent(properties) {
  const classInfo = getNucleosPopulationInfo(properties);
  const nombre = properties.nombre || properties.label || 'Núcleo de población';
  const habitantes = formatNucleosHabitantes(properties.habitantes);
  const capital = properties.is_capital ? '<br>Capitalidad: sí' : '';
  const tipo = properties.tipo_label ? `<br>${escapeHtml(properties.tipo_label)}` : '';
  const codigo = properties.codigo_ep ? `<br>Código EP: ${escapeHtml(properties.codigo_ep)}` : '';
  return `<b>${escapeHtml(nombre)}</b><br>`+
    `Habitantes: ${escapeHtml(habitantes)}<br>`+
    `Clase: ${escapeHtml(classInfo.label)}`+
    `${tipo}${capital}${codigo}`;
}

function ensureNucleosTooltip(latlng, content) {
  if (!nucleosTooltip) {
    nucleosTooltip = L.tooltip({
      permanent: false,
      sticky: true,
      direction: 'top',
      opacity: 0.95,
    });
  }
  nucleosTooltip.setLatLng(latlng).setContent(content);
  if (!map.hasLayer(nucleosTooltip)) nucleosTooltip.addTo(map);
}

function buildNucleosLayer() {
  const layerStyles = {
    [NUCLEOS_MVT_LAYER_NAME]: properties => getNucleosFeatureStyle(properties),
    nucleos_poblacion_mvt_source: properties => getNucleosFeatureStyle(properties),
    'pub.nucleos_poblacion_mvt_source': properties => getNucleosFeatureStyle(properties),
  };
  const layer = L.vectorGrid.protobuf(NUCLEOS_VECTOR_TILE_URL, {
    rendererFactory: L.canvas.tile,
    pane: NUCLEOS_PANE,
    interactive: true,
    minZoom: NUCLEOS_MIN_ZOOM,
    maxNativeZoom: 18,
    vectorTileLayerStyles: layerStyles,
    getFeatureId: feature => feature.properties.core_feature_id,
  });
  layer.on('mouseover', e => {
    const props = e.layer.properties || {};
    const habitantes = formatNucleosHabitantes(props.habitantes);
    ensureNucleosTooltip(e.latlng, `${escapeHtml(props.nombre || 'Núcleo de población')} · ${escapeHtml(habitantes)} hab.`);
  });
  layer.on('mousemove', e => {
    if (nucleosTooltip) nucleosTooltip.setLatLng(e.latlng);
  });
  layer.on('mouseout', () => {
    clearNucleosTooltip();
  });
  layer.on('click', e => {
    const props = e.layer.properties || {};
    openNucleosMapPopup(e.latlng, buildNucleosPopupContent(props));
  });
  return layer;
}

function toggleNucleos(enabled) {
  nucleosVisible = enabled;
  if (enabled) {
    if (!nucleosLayer) nucleosLayer = buildNucleosLayer();
    if (nucleosLayer) nucleosLayer.addTo(map);
  } else {
    clearNucleosTooltip();
    closeNucleosMapPopup();
    if (nucleosLayer) map.removeLayer(nucleosLayer);
  }
  updateLegend();
}
 
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

function closeCorineMapPopup(abortQuery = true) {
  if (abortQuery) abortCorinePointQuery();
  const popup = corineMapPopup;
  corineMapPopup = null;
  if (!popup) return;
  if (map.closePopup) map.closePopup(popup);
}

function openCorineMapPopup(latlng, content) {
  closeCorineMapPopup(false);
  corineMapPopup = L.popup({ className: 'corine-landcover-popup' })
    .setLatLng(latlng)
    .setContent(content);
  corineMapPopup.openOn(map);
  return corineMapPopup;
}

function mercatorToWgs84(x, y) {
  const lng = (x / 20037508.34) * 180;
  let lat = (y / 20037508.34) * 180;
  lat = (180 / Math.PI) * (2 * Math.atan(Math.exp(lat * Math.PI / 180)) - Math.PI / 2);
  return [lng, lat];
}

function getFirstCoordinatePair(coords) {
  if (!Array.isArray(coords) || !coords.length) return null;
  if (typeof coords[0] === 'number') return coords;
  return getFirstCoordinatePair(coords[0]);
}

function shouldReprojectLandcoverGeometry(feature) {
  const geometryCrs = feature?.properties?.geometry_crs;
  if (geometryCrs === 'EPSG:4326' || geometryCrs === 'CRS:84') return false;
  if (geometryCrs === 'EPSG:3857') return true;

  const firstCoord = getFirstCoordinatePair(feature?.geometry?.coordinates);
  if (!firstCoord || firstCoord.length < 2) return false;

  const [x, y] = firstCoord;
  return Math.abs(Number(x)) > 180 || Math.abs(Number(y)) > 90;
}

function reprojectLandcoverCoordinates(coords) {
  if (!Array.isArray(coords) || !coords.length) return coords;
  if (typeof coords[0] === 'number') {
    const [lng, lat] = mercatorToWgs84(Number(coords[0]), Number(coords[1]));
    if (coords.length > 2) return [lng, lat, ...coords.slice(2)];
    return [lng, lat];
  }
  return coords.map(reprojectLandcoverCoordinates);
}

function reprojectLandcoverGeometry(geometry) {
  if (!geometry) return geometry;
  if (geometry.type === 'GeometryCollection') {
    return {
      ...geometry,
      geometries: Array.isArray(geometry.geometries)
        ? geometry.geometries.map(reprojectLandcoverGeometry)
        : [],
    };
  }
  return {
    ...geometry,
    coordinates: reprojectLandcoverCoordinates(geometry.coordinates),
  };
}

function normalizeLandcoverPointFeature(feature) {
  if (!feature?.geometry || !shouldReprojectLandcoverGeometry(feature)) return feature;
  return {
    ...feature,
    geometry: reprojectLandcoverGeometry(feature.geometry),
    properties: {
      ...(feature.properties || {}),
      geometry_crs: 'EPSG:4326',
    },
  };
}

function abortCorinePointQuery() {
  if (corinePointQueryController) {
    corinePointQueryController.abort();
    corinePointQueryController = null;
  }
}

function clearCorinePointSelection() {
  closeCorineMapPopup();
  if (corinePointSelectionLayer) {
    map.removeLayer(corinePointSelectionLayer);
    corinePointSelectionLayer = null;
  }
}

function setCorinePointSelection(feature) {
  const normalizedFeature = normalizeLandcoverPointFeature(feature);
  clearCorinePointSelection();
  corinePointSelectionLayer = L.geoJSON(normalizedFeature, {
    pane: CORINE_SELECTION_PANE,
    interactive: false,
    style: () => ({
      color: '#00f0f0',
      weight: 2,
      opacity: 1,
      fill: true,
      fillColor: '#00f0f0',
      fillOpacity: 0.05,
      dashArray: '8 5',
      lineJoin: 'round',
    }),
  }).addTo(map);
  if (corinePointSelectionLayer.bringToFront) corinePointSelectionLayer.bringToFront();
}

function isCorineWmsActive() {
  return Boolean(wmsActive.corine_wms);
}

function getLandcoverWmsCrs() {
  return WMS_DEFS.corine_wms.crs || map.options.crs;
}

function buildWmsBbox(bounds, crs, version = '1.3.0') {
  const southWestProjected = crs.project(bounds.getSouthWest());
  const northEastProjected = crs.project(bounds.getNorthEast());
  const isWms13Geographic = version === '1.3.0' && crs.code === 'EPSG:4326';

  if (isWms13Geographic) {
    return [
      southWestProjected.y,
      southWestProjected.x,
      northEastProjected.y,
      northEastProjected.x,
    ].join(',');
  }

  return [
    southWestProjected.x,
    southWestProjected.y,
    northEastProjected.x,
    northEastProjected.y,
  ].join(',');
}

function buildLandcoverPointQuery(latlng, options = {}) {
  const wmsCrs = getLandcoverWmsCrs();
  const wmsVersion = WMS_DEFS.corine_wms.version || '1.3.0';
  const queryZoom = Number.isFinite(Number(options.queryZoom))
    ? Number(options.queryZoom)
    : null;
  const width = Number.isFinite(Number(options.width))
    ? Math.max(3, Math.round(Number(options.width)))
    : map.getSize().x;
  const height = Number.isFinite(Number(options.height))
    ? Math.max(3, Math.round(Number(options.height)))
    : map.getSize().y;
  let queryBounds;
  let i;
  let j;

  if (queryZoom !== null) {
    const centerPoint = map.project(latlng, queryZoom);
    const halfWidth = (width - 1) / 2;
    const halfHeight = (height - 1) / 2;
    const southWest = map.unproject(
      L.point(centerPoint.x - halfWidth, centerPoint.y + halfHeight),
      queryZoom
    );
    const northEast = map.unproject(
      L.point(centerPoint.x + halfWidth, centerPoint.y - halfHeight),
      queryZoom
    );
    queryBounds = L.latLngBounds(southWest, northEast);
    i = Math.floor(width / 2);
    j = Math.floor(height / 2);
  } else {
    queryBounds = map.getBounds();
    const size = map.getSize();
    const clickPoint = map.latLngToContainerPoint(latlng);
    i = Math.max(0, Math.min(size.x - 1, Math.round(clickPoint.x)));
    j = Math.max(0, Math.min(size.y - 1, Math.round(clickPoint.y)));
  }

  return {
    lon: latlng.lng,
    lat: latlng.lat,
    bbox: buildWmsBbox(queryBounds, wmsCrs, wmsVersion),
    width,
    height,
    i,
    j,
    crs: wmsCrs.code,
  };
}

async function fetchLandcoverPoint(latlng, signal, options = {}) {
  const query = buildLandcoverPointQuery(latlng, options);
  const params = new URLSearchParams({
    lon: String(query.lon),
    lat: String(query.lat),
    bbox: query.bbox,
    width: String(query.width),
    height: String(query.height),
    i: String(query.i),
    j: String(query.j),
    crs: query.crs,
  });
  const response = await fetch(`/api/landcover/point?${params.toString()}`, {
    cache: 'no-store',
    signal,
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data.detail) message = data.detail;
    } catch (_) {}
    throw new Error(message);
  }
  return response.json();
}

function buildFireLandcoverCacheKey(lat, lon) {
  return `${lat.toFixed(5)},${lon.toFixed(5)}@z${LANDCOVER_FIRE_QUERY_ZOOM}`;
}

function applyFireLandcoverInfo(fire, info) {
  fire.landcoverStatus = info.status;
  fire.landcoverLabel = info.label || '';
  fire.landcoverSourceDataset = info.sourceDataset || '';
}

function initializeFireLandcoverInfo(fire) {
  const lat = Number(fire.latitude);
  const lon = Number(fire.longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    applyFireLandcoverInfo(fire, { status: 'error' });
    return;
  }
  const cached = fireLandcoverInfoCache.get(buildFireLandcoverCacheKey(lat, lon));
  if (cached) {
    applyFireLandcoverInfo(fire, cached);
    return;
  }
  applyFireLandcoverInfo(fire, { status: 'loading' });
}

function buildCorinePointPopupContent(feature) {
  const props = feature?.properties || {};
  const label = props.label || 'Uso del suelo';
  const code = props.code || 'n/d';
  const sourceDataset = props.source_dataset
    ? `<br>Fuente: ${escapeHtml(props.source_dataset)}`
    : '';
  const secondary = props.secondary_label
    ? `<br>${escapeHtml(props.secondary_label)}`
    : '';
  const area = Number.isFinite(Number(props.surface_ha))
    ? `<br>Superficie: ${Number(props.surface_ha).toFixed(2)} ha`
    : '';
  return `<b>${escapeHtml(label)}</b><br>Código: ${escapeHtml(code)}${sourceDataset}${secondary}${area}`;
}

async function handleCorineWmsClick(latlng) {
  if (!isCorineWmsActive()) return;
  if (map.getZoom() < 11) {
    clearCorinePointSelection();
    openCorineMapPopup(latlng, '<b>Zoom insuficiente.</b><br>Acércate más e inténtalo de nuevo.');
    return;
  }

  const token = ++corinePointQueryToken;
  abortCorinePointQuery();
  const controller = new AbortController();
  corinePointQueryController = controller;

  openCorineMapPopup(latlng, 'Consultando uso del suelo...');

  try {
    const data = await fetchLandcoverPoint(latlng, controller.signal);
    if (controller.signal.aborted || token !== corinePointQueryToken) return;

    corinePointQueryController = null;
    const feature = Array.isArray(data.features) ? data.features[0] : null;

    if (!feature) {
      clearCorinePointSelection();
      openCorineMapPopup(latlng, 'Información no disponible para este punto.');
      return;
    }

    setCorinePointSelection(feature);
    openCorineMapPopup(latlng, buildCorinePointPopupContent(feature));
  } catch (error) {
    if (error.name === 'AbortError') return;
    corinePointQueryController = null;
    clearCorinePointSelection();
    openCorineMapPopup(latlng, `No se pudo consultar el uso del suelo: ${escapeHtml(error.message)}`);
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
    openCorineMapPopup(e.latlng, `<b>${label}</b><br>Código canónico: ${props.class_code || 'n/d'}`);
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
 
map.on('click', e => {
  if (!isCorineWmsActive()) return;
  void handleCorineWmsClick(e.latlng);
});

// Estado 
let alertsData   = [];
let firesData    = [];
let alertLayers  = {};
let fireLayers   = [];
let showAlerts   = true;
let showFires    = true;
let activeList   = 'alerts';
let alertsListView = 'all';
let activeLevels = new Set(['Rojo','Naranja','Amarillo','Verde']);
let activeEvent  = 'all';
let firesError   = null;
let firesLoading = false;

// ── Timeline ──────────────────────────────────────────────────────────────
let tlMin = null, tlMax = null, tlCurrent = null, playInterval = null;
let timelineBarSplitLayout = null;
const STEP_MS = 60 * 60 * 1000;
const TICK_MS = 700;

function isTimelineBarSplitLayout() {
  return document.getElementById('timelines-bar')?.classList.contains('is-split');
}

function syncTimelineBarVisibility() {
  const bar = document.getElementById('timelines-bar');
  const alertsTimelineEl = document.getElementById('timeline');
  const historicalTimelineEl = document.getElementById('historical-timeline');
  if (!bar || !alertsTimelineEl || !historicalTimelineEl) return;

  const showAlertsTimeline = Boolean(showAlerts);
  const showHistoricalTimeline = hasVisibleHistoricalLayers();
  const visibleCount = Number(showAlertsTimeline) + Number(showHistoricalTimeline);
  const splitLayout = visibleCount > 1;

  alertsTimelineEl.hidden = !showAlertsTimeline;
  historicalTimelineEl.hidden = !showHistoricalTimeline;
  bar.hidden = visibleCount === 0;
  bar.classList.toggle('is-split', splitLayout);

  if (timelineBarSplitLayout !== splitLayout) {
    timelineBarSplitLayout = splitLayout;
    if (tlMin && tlMax) buildTicks();
  }
}

function syncTimelinePanelsVisibility() {
  syncTimelineBarVisibility();
}

function initTimeline() {
  tlMin = tlCurrent = new Date();
  tlMax = alertsData.reduce((mx, a) => {
    const d = new Date(a.expires); return d > mx ? d : mx;
  }, new Date());
  const slider = document.getElementById('tl-slider');
  slider.min = 0;
  slider.max = Math.max(1, Math.floor((tlMax - tlMin) / STEP_MS));
  slider.value = 0;
  syncTimelineBarVisibility();
  updateTimelineUI();
  buildTicks();
}

function buildTicks() {
  const c = document.getElementById('tl-ticks');
  if (!c || !tlMin || !tlMax) return;
  c.innerHTML = '';
  const splitLayout = isTimelineBarSplitLayout();
  const hrs = (tlMax - tlMin) / 3600000;
  const every = hrs <= 48 ? (splitLayout ? 12 : 6) : 24;
  let t = new Date(tlMin);
  while (t <= tlMax) {
    const s = document.createElement('span');
    const dateLabel = t.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
    if (splitLayout) {
      const timeLabel = every < 24
        ? t.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
        : '';
      s.textContent = timeLabel ? `${dateLabel} ${timeLabel}` : dateLabel;
    } else {
      s.textContent = dateLabel
        + ' ' + t.toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'});
    }
    c.appendChild(s);
    t = new Date(t.getTime() + every * 3600000);
  }
}

function updateTimelinePlayButton() {
  const btn = document.getElementById('tl-play');
  if (!btn) return;
  btn.innerHTML = playInterval ? '&#9646;&#9646; Pausa' : '&#9654; Play';
  btn.classList.toggle('playing', Boolean(playInterval));
}

function updateTimelineUI() {
  syncTimelinePanelsVisibility();
  const isNow = (tlCurrent - tlMin) < 60000;
  const badge = document.getElementById('tl-badge');
  badge.textContent = isNow ? 'AHORA' : 'FUTURO';
  badge.className = isNow ? '' : 'future';
  document.getElementById('tl-datetime').textContent =
    tlCurrent.toLocaleDateString('es-ES',{weekday:'short',day:'2-digit',month:'short'})
    + ' · ' + tlCurrent.toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'});
  updateTimelinePlayButton();
}

function onSliderInput(val) {
  tlCurrent = new Date(tlMin.getTime() + val * STEP_MS);
  updateTimelineUI();
  renderAll();
}

function stopTimelinePlayback() {
  if (!playInterval) return;
  clearInterval(playInterval);
  playInterval = null;
  updateTimelinePlayButton();
}

function togglePlay() {
  if (playInterval) {
    stopTimelinePlayback();
  } else {
    playInterval = setInterval(() => {
      const s = document.getElementById('tl-slider');
      const next = parseInt(s.value) + 1;
      if (next > parseInt(s.max)) { stopTimelinePlayback(); return; }
      s.value = next; onSliderInput(next);
    }, TICK_MS);
    updateTimelinePlayButton();
  }
}

function resetTimeline() {
  stopTimelinePlayback();
  document.getElementById('tl-slider').value = 0;
  onSliderInput(0);
}

function isActive(a) { return new Date(a.onset) <= tlCurrent; }

// Carga 
async function fetchJson(url, options = {}) {
  const { cache = 'no-store', ...fetchOptions } = options;
  const r = await fetch(url, { cache, ...fetchOptions });
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

function buildBurntAreaTimelineUrl() {
  const params = new URLSearchParams({
    version: BURNT_AREA_DEFAULT_VERSION,
    format: BURNT_AREA_DEFAULT_FORMAT,
    date_from: BURNT_AREA_DEFAULT_DATE_FROM,
    date_to: BURNT_AREA_DEFAULT_DATE_TO,
  });
  return `/api/burnt-area/timeline?${params.toString()}`;
}

function buildBurntAreaTileUrl(dateString) {
  const params = new URLSearchParams({ mode: burntAreaDisplayMode });
  return `/api/burnt-area/tiles/${BURNT_AREA_DEFAULT_VERSION}/${dateString}/{z}/{x}/{y}.png?${params.toString()}`;
}

function buildBurntAreaLocatorUrl(dateString, sourceZoom) {
  const params = new URLSearchParams({
    source_zoom: String(sourceZoom),
    mode: burntAreaDisplayMode,
  });
  return `/api/burnt-area/locator/${BURNT_AREA_DEFAULT_VERSION}/${dateString}?${params.toString()}`;
}

function formatBurntAreaDate(dateString) {
  const dateValue = new Date(`${dateString}T00:00:00`);
  if (Number.isNaN(dateValue.getTime())) return dateString;
  return dateValue.toLocaleDateString('es-ES', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function formatBurntAreaSurface(areaHa) {
  const value = Number(areaHa);
  if (!Number.isFinite(value)) return null;
  const maxDigits = value >= 1000 ? 0 : value >= 100 ? 1 : 2;
  return `${new Intl.NumberFormat('es-ES', { maximumFractionDigits: maxDigits }).format(value)} ha`;
}

function isBurntAreaCumulativeMode() {
  return burntAreaDisplayMode === BURNT_AREA_DISPLAY_MODE_CUMULATIVE;
}

function getBurntAreaTimelineItemsThroughDate(dateString) {
  if (!dateString) return [];
  return burntAreaTimeline.filter(item => item?.date && item.date <= dateString);
}

function getBurntAreaCumulativeStats(dateString) {
  const items = getBurntAreaTimelineItemsThroughDate(dateString);
  if (!items.length) {
    return { hasStats: false, hasTiles: false, areaHa: null, pixelCount: null, tileDateCount: 0 };
  }

  const lastItem = items[items.length - 1];
  const backendArea = Number(lastItem.cumulative_burned_area_ha);
  const backendPixels = Number(lastItem.cumulative_burned_pixel_count);
  if (Number.isFinite(backendArea)) {
    return {
      hasStats: true,
      hasTiles: items.some(item => item.has_local_tiles || item.has_cumulative_tiles),
      areaHa: backendArea,
      pixelCount: Number.isFinite(backendPixels) ? backendPixels : null,
      tileDateCount: Number(lastItem.cumulative_tile_date_count) || items.filter(item => item.has_local_tiles).length,
    };
  }

  let areaHa = 0;
  let pixelCount = 0;
  let hasStats = false;
  let hasPixels = false;
  let tileDateCount = 0;
  items.forEach(item => {
    const dailyArea = Number(item.burned_area_ha);
    const dailyPixels = Number(item.burned_pixel_count);
    if (Number.isFinite(dailyArea)) {
      areaHa += dailyArea;
      hasStats = true;
    }
    if (Number.isFinite(dailyPixels)) {
      pixelCount += dailyPixels;
      hasPixels = true;
    }
    if (item.has_local_tiles) tileDateCount += 1;
  });

  return {
    hasStats,
    hasTiles: tileDateCount > 0,
    areaHa: hasStats ? areaHa : null,
    pixelCount: hasPixels ? pixelCount : null,
    tileDateCount,
  };
}

function updateBurntAreaModeControl() {
  document.querySelectorAll('[data-burnt-area-mode]').forEach(button => {
    const selected = button.dataset.burntAreaMode === burntAreaDisplayMode;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-pressed', selected ? 'true' : 'false');
  });

  const control = document.getElementById('burnt-area-mode-control');
  if (!control) return;
  control.title = isBurntAreaCumulativeMode()
    ? 'Mostrando áreas quemadas acumuladas hasta la fecha seleccionada'
    : 'Mostrando áreas quemadas del día seleccionado';
}

function setBurntAreaDisplayMode(mode) {
  if (!BURNT_AREA_DISPLAY_MODES.has(mode) || mode === burntAreaDisplayMode) {
    updateBurntAreaModeControl();
    return;
  }

  burntAreaDisplayMode = mode;
  burntAreaLocatorKey = null;
  updateBurntAreaModeControl();
  updateHistoricalTimelineUI();
  if (burntAreaVisible) {
    renderBurntAreaForDate(getHistoricalTimelineCurrentDate(), true);
  }
}

function resolveBurntAreaLocatorSourceZoom() {
  return BURNT_AREA_LOCATOR_SOURCE_ZOOM;
}

function shouldDisplayBurntAreaLocator() {
  return true;
}

function resolveBurntAreaRasterOpacity() {
  return 0;
}

function updateBurntAreaSurfaceUI(item) {
  const areaEl = document.getElementById('ba-area');
  if (!areaEl) return;
  if (!item) {
    areaEl.dataset.state = 'nodata';
    areaEl.textContent = '--';
    return;
  }

  const formattedSurface = formatBurntAreaSurface(item.burned_area_ha);
  if (formattedSurface === null) {
    areaEl.dataset.state = 'nodata';
    areaEl.textContent = 's/d';
    return;
  }

  if (Number(item.burned_area_ha) <= 0) {
    areaEl.dataset.state = 'zero';
    areaEl.textContent = '0 ha';
    return;
  }

  areaEl.dataset.state = 'active';
  areaEl.textContent = formattedSurface;
}

function setBurntAreaInlineNote(message = '') {
  const inlineNote = document.getElementById('ba-inline-note');
  if (!inlineNote) return;
  if (!message) {
    inlineNote.hidden = true;
    inlineNote.textContent = '';
    return;
  }
  inlineNote.hidden = false;
  inlineNote.textContent = message;
}

function getBurntAreaLocatorStyle() {
  return {
    pane: BURNT_AREA_LOCATOR_PANE,
    color: '#6e2300',
    weight: 2,
    opacity: 0.92,
    fillColor: '#c24a00',
    fillOpacity: 0.24,
    lineJoin: 'round',
    className: 'burnt-area-locator-shape',
    interactive: false,
  };
}

function getBurntAreaInitialTimelineIndex() {
  const firstPublishedIndex = burntAreaTimeline.findIndex(item => item.has_local_tiles);
  return firstPublishedIndex >= 0 ? firstPublishedIndex : 0;
}

function setBurntAreaTimelineNote(message, tone = 'info') {
  const note = document.getElementById('ba-note');
  if (!note) return;
  if (!message) {
    note.hidden = true;
    note.textContent = '';
    note.dataset.state = '';
    return;
  }
  note.hidden = false;
  note.dataset.state = tone;
  note.textContent = message;
  note.style.color = tone === 'error'
    ? '#ff9786'
    : (tone === 'warning' ? '#f0bc8d' : '#cbb6ad');
}

function refreshBurntAreaTimelineNote() {
  setBurntAreaInlineNote('');

  if (burntAreaError) {
    setBurntAreaTimelineNote(`No se pudo cargar la capa temporal: ${burntAreaError}`, 'error');
    return;
  }

  if (!burntAreaTimeline.length) {
    setBurntAreaTimelineNote('No hay fechas disponibles para la ventana temporal configurada.', 'error');
    return;
  }

  const publishedCount = burntAreaTimeline.filter(item => item.has_local_tiles).length;
  if (!publishedCount) {
    setBurntAreaTimelineNote(
      `Catalogo listo: ${burntAreaTimeline.length} dias. Aun no hay teselas locales generadas para mostrar el raster.`,
      'warning'
    );
    return;
  }

  const currentItem = burntAreaTimeline[burntAreaTimelineIndex] || burntAreaTimeline[0];
  if (currentItem && !currentItem.has_local_tiles) {
    setBurntAreaInlineNote('Sin teselas locales');
    setBurntAreaTimelineNote('');
    return;
  }

  setBurntAreaTimelineNote('');
}

function syncTimelinePanelLayout() {
  document.body.classList.toggle('dual-timeline', burntAreaVisible && historicalFiresVisible);
}

function updateBurntAreaTimelineUI() {
  const slider = document.getElementById('ba-slider');
  const dateEl = document.getElementById('ba-datetime');
  const rangeStartEl = document.getElementById('ba-range-start');
  const rangeEndEl = document.getElementById('ba-range-end');
  const playBtn = document.getElementById('ba-play');
  syncTimelineBarVisibility();
  if (!slider || !dateEl || !rangeStartEl || !rangeEndEl || !playBtn) return;

  playBtn.classList.toggle('playing', Boolean(burntAreaPlayInterval));
  playBtn.innerHTML = burntAreaPlayInterval ? '&#9646;&#9646; Pausa' : '&#9654; Play';
  refreshBurntAreaTimelineNote();

  if (!burntAreaTimeline.length) {
    slider.min = 0;
    slider.max = 0;
    slider.value = 0;
    dateEl.textContent = '--';
    updateBurntAreaSurfaceUI(null);
    rangeStartEl.textContent = BURNT_AREA_DEFAULT_DATE_FROM;
    rangeEndEl.textContent = BURNT_AREA_DEFAULT_DATE_TO;
    return;
  }

  const currentItem = burntAreaTimeline[burntAreaTimelineIndex] || burntAreaTimeline[0];
  slider.min = 0;
  slider.max = Math.max(0, burntAreaTimeline.length - 1);
  slider.value = String(burntAreaTimelineIndex);
  dateEl.textContent = formatBurntAreaDate(currentItem.date);
  updateBurntAreaSurfaceUI(currentItem);
  rangeStartEl.textContent = burntAreaTimeline[0].date;
  rangeEndEl.textContent = burntAreaTimeline[burntAreaTimeline.length - 1].date;
}

function ensureBurntAreaLocatorLayer() {
  if (burntAreaLocatorLayer) return burntAreaLocatorLayer;
  burntAreaLocatorLayer = L.geoJSON(null, {
    pane: BURNT_AREA_LOCATOR_PANE,
    style: () => getBurntAreaLocatorStyle(),
    interactive: false,
  });
  return burntAreaLocatorLayer;
}

function refreshBurntAreaLocatorStyle() {
  if (!burntAreaLocatorLayer) return;
  burntAreaLocatorLayer.setStyle(getBurntAreaLocatorStyle());
}

function refreshBurntAreaRasterPresentation() {
  if (!burntAreaLayer) return;
  const opacity = resolveBurntAreaRasterOpacity();
  burntAreaLayer.setOpacity(opacity);
  if (!burntAreaVisible || opacity <= 0) {
    if (map.hasLayer(burntAreaLayer)) map.removeLayer(burntAreaLayer);
    return;
  }
  if (!map.hasLayer(burntAreaLayer)) {
    burntAreaLayer.addTo(map);
  }
}

function clearBurntAreaLocatorLayer() {
  burntAreaLocatorKey = null;
  if (burntAreaLocatorLayer) {
    burntAreaLocatorLayer.clearLayers();
    if (map.hasLayer(burntAreaLocatorLayer)) map.removeLayer(burntAreaLocatorLayer);
  }
}

async function syncBurntAreaLocatorForCurrentView(forceReload = false) {
  if (!burntAreaVisible || !burntAreaTimeline.length) {
    clearBurntAreaLocatorLayer();
    return;
  }

  if (!shouldDisplayBurntAreaLocator()) {
    clearBurntAreaLocatorLayer();
    return;
  }

  const currentItem = burntAreaTimeline[burntAreaTimelineIndex];
  if (!currentItem || !currentItem.has_local_tiles) {
    clearBurntAreaLocatorLayer();
    return;
  }

  const sourceZoom = resolveBurntAreaLocatorSourceZoom();
  const cacheKey = `${currentItem.date}:${sourceZoom}`;
  const layer = ensureBurntAreaLocatorLayer();
  refreshBurntAreaLocatorStyle();

  if (!forceReload && burntAreaLocatorKey === cacheKey && map.hasLayer(layer)) {
    return;
  }

  if (burntAreaLocatorCache.has(cacheKey)) {
    burntAreaLocatorKey = cacheKey;
    layer.clearLayers();
    layer.addData(burntAreaLocatorCache.get(cacheKey));
    if (!map.hasLayer(layer)) layer.addTo(map);
    return;
  }

  const requestKey = cacheKey;
  burntAreaLocatorCachePromise = fetchJson(buildBurntAreaLocatorUrl(currentItem.date, sourceZoom))
    .then(data => {
      burntAreaLocatorCache.set(requestKey, data);
      if (!burntAreaVisible || burntAreaTimeline[burntAreaTimelineIndex]?.date !== currentItem.date) return;
      if (resolveBurntAreaLocatorSourceZoom() !== sourceZoom) return;
      burntAreaLocatorKey = requestKey;
      layer.clearLayers();
      layer.addData(data);
      if (!map.hasLayer(layer)) layer.addTo(map);
      refreshBurntAreaLocatorStyle();
    })
    .catch(error => {
      console.error('No se pudo cargar el localizador de burnt area:', error);
      if (burntAreaLocatorKey === requestKey) clearBurntAreaLocatorLayer();
    })
    .finally(() => {
      if (burntAreaLocatorCachePromise && burntAreaLocatorKey === requestKey) {
        burntAreaLocatorCachePromise = null;
      } else if (!burntAreaLocatorKey) {
        burntAreaLocatorCachePromise = null;
      }
    });
  return burntAreaLocatorCachePromise;
}

function ensureBurntAreaLayer(dateString) {
  const url = buildBurntAreaTileUrl(dateString);
  if (!burntAreaLayer) {
    burntAreaLayer = L.tileLayer(url, {
      pane: WMS_LAYER_PANE,
      opacity: resolveBurntAreaRasterOpacity(),
      bounds: SPAIN_BOUNDS,
      minZoom: 4,
      maxNativeZoom: Number(burntAreaMetadata?.tile_max_zoom) || BURNT_AREA_MAX_NATIVE_ZOOM,
      maxZoom: 18,
      className: 'burnt-area-tile',
      attribution: 'Copernicus CLMS Burnt Area',
    });
  } else {
    burntAreaLayer.setUrl(url, false);
  }
  refreshBurntAreaRasterPresentation();
}

function stopBurntAreaPlayback() {
  if (!burntAreaPlayInterval) return;
  clearInterval(burntAreaPlayInterval);
  burntAreaPlayInterval = null;
  updateBurntAreaTimelineUI();
}

function setBurntAreaFrame(index) {
  if (!burntAreaTimeline.length) return;
  burntAreaTimelineIndex = Math.max(0, Math.min(index, burntAreaTimeline.length - 1));
  const currentItem = burntAreaTimeline[burntAreaTimelineIndex];
  ensureBurntAreaLayer(currentItem.date);
  void syncBurntAreaLocatorForCurrentView(true);
  updateBurntAreaTimelineUI();
}

function resetBurntAreaTimeline() {
  stopBurntAreaPlayback();
  setBurntAreaFrame(0);
}

function toggleBurntAreaPlayback() {
  if (!burntAreaTimeline.length) return;
  if (burntAreaPlayInterval) {
    stopBurntAreaPlayback();
    return;
  }
  burntAreaPlayInterval = setInterval(() => {
    const nextIndex = burntAreaTimelineIndex + 1;
    if (nextIndex >= burntAreaTimeline.length) {
      stopBurntAreaPlayback();
      return;
    }
    setBurntAreaFrame(nextIndex);
  }, 650);
  updateBurntAreaTimelineUI();
}

async function ensureBurntAreaTimelineLoaded() {
  if (burntAreaMetadata && burntAreaTimeline.length) {
    return {
      layer_id: burntAreaMetadata.layer_id,
      dataset_version: BURNT_AREA_DEFAULT_VERSION,
      delivery_format: BURNT_AREA_DEFAULT_FORMAT,
      date_from: BURNT_AREA_DEFAULT_DATE_FROM,
      date_to: BURNT_AREA_DEFAULT_DATE_TO,
      date_count: burntAreaTimeline.length,
      dates: burntAreaTimeline,
    };
  }
  if (burntAreaLoadingPromise) return burntAreaLoadingPromise;
  burntAreaLoadingPromise = (async () => {
    burntAreaMetadata = await fetchJson(BURNT_AREA_LAYER_METADATA_URL);
    const timelinePayload = await fetchJson(buildBurntAreaTimelineUrl());
    burntAreaTimeline = Array.isArray(timelinePayload.dates) ? timelinePayload.dates : [];
    burntAreaTimelineIndex = getBurntAreaInitialTimelineIndex();
    updateBurntAreaTimelineUI();
    return timelinePayload;
  })()
    .catch(error => {
      burntAreaError = error.message;
      burntAreaTimeline = [];
      setBurntAreaTimelineNote(`No se pudo cargar la capa temporal: ${error.message}`, 'error');
      updateBurntAreaTimelineUI();
      throw error;
    })
    .finally(() => {
      burntAreaLoadingPromise = null;
    });
  return burntAreaLoadingPromise;
}

async function toggleBurntAreaLayer(enabled) {
  burntAreaVisible = enabled;
  updateBurntAreaTimelineUI();
  if (!enabled) {
    stopBurntAreaPlayback();
    if (burntAreaLayer && map.hasLayer(burntAreaLayer)) map.removeLayer(burntAreaLayer);
    clearBurntAreaLocatorLayer();
    updateBurntAreaTimelineUI();
    return;
  }

  try {
    await ensureBurntAreaTimelineLoaded();
    burntAreaError = null;
    if (!burntAreaTimeline.length) {
      updateBurntAreaTimelineUI();
      return;
    }
    setBurntAreaFrame(burntAreaTimelineIndex);
  } catch (_) {
    updateBurntAreaTimelineUI();
  }
}

function getFirmsHistoricalDateRange() {
  return {
    dateFrom: historicalFiresMetadata?.default_date_from || FIRMS_HISTORY_DEFAULT_DATE_FROM,
    dateTo: historicalFiresMetadata?.default_date_to || FIRMS_HISTORY_DEFAULT_DATE_TO,
  };
}

function buildFirmsHistoricalTimelineUrl() {
  const { dateFrom, dateTo } = getFirmsHistoricalDateRange();
  const params = new URLSearchParams({
    date_from: dateFrom,
    date_to: dateTo,
  });
  return `${FIRMS_HISTORY_TIMELINE_URL}?${params.toString()}`;
}

function buildFirmsHistoricalFeaturesUrl(dateString) {
  const params = new URLSearchParams({
    date: dateString,
    limit: String(FIRMS_HISTORY_FETCH_LIMIT),
  });
  return `${FIRMS_HISTORY_FEATURES_URL}?${params.toString()}`;
}

function getAemetMaxTempDateRange() {
  return {
    dateFrom: aemetMaxTempMetadata?.default_date_from || AEMET_MAX_TEMP_DEFAULT_DATE_FROM,
    dateTo: aemetMaxTempMetadata?.default_date_to || AEMET_MAX_TEMP_DEFAULT_DATE_TO,
  };
}

function buildAemetMaxTempTimelineUrl() {
  const { dateFrom, dateTo } = getAemetMaxTempDateRange();
  const params = new URLSearchParams({
    date_from: dateFrom,
    date_to: dateTo,
  });
  return `${AEMET_MAX_TEMP_TIMELINE_URL}?${params.toString()}`;
}

function buildAemetMaxTempTileUrl(dateString) {
  const params = new URLSearchParams({ warnings_only: 'true' });
  return `/api/aemet/max-temperature/tiles/${dateString}/{z}/{x}/{y}.mvt?${params.toString()}`;
}

function formatFirmsHistoricalDate(dateString) {
  const dateValue = new Date(`${dateString}T00:00:00`);
  if (Number.isNaN(dateValue.getTime())) return dateString;
  return dateValue.toLocaleDateString('es-ES', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function formatFirmsHistoricalCount(count) {
  const value = Number(count) || 0;
  const formatted = new Intl.NumberFormat('es-ES').format(value);
  return `${formatted} ${value === 1 ? 'foco' : 'focos'}`;
}

function formatAemetMaxTempCount(count) {
  const value = Number(count) || 0;
  const formatted = new Intl.NumberFormat('es-ES').format(value);
  return `${formatted} ${value === 1 ? 'zona' : 'zonas'}`;
}

function formatAemetTemperature(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return null;
  return `${numericValue.toLocaleString('es-ES', { maximumFractionDigits: 1 })} °C`;
}

function updateHistoricalFiresSummaryUI(item) {
  const summaryEl = document.getElementById('fh-summary');
  if (!summaryEl) return;
  if (!item) {
    summaryEl.dataset.state = 'nodata';
    summaryEl.textContent = '--';
    return;
  }

  const hotspotCount = Number(item.hotspot_count) || 0;
  const frpMax = Number(item.frp_max_mw);
  const frpLabel = Number.isFinite(frpMax) ? ` · FRP máx ${formatFireFrp(frpMax)} MW` : '';
  summaryEl.dataset.state = hotspotCount > 0 ? 'active' : 'zero';
  summaryEl.textContent = `${formatFirmsHistoricalCount(hotspotCount)}${frpLabel}`;
}

function getHistoricalFiresCurrentTimelineItem() {
  return historicalFiresTimeline[historicalFiresTimelineIndex] || historicalFiresTimeline[0] || null;
}

function setHistoricalFiresTimelineNote(message, isError = false) {
  const note = document.getElementById('fh-note');
  if (!note) return;
  note.textContent = message;
  note.style.color = isError ? '#ff9786' : '#cbb6ad';
}

function refreshHistoricalFiresTimelineNote() {
  if (historicalFiresError) {
    setHistoricalFiresTimelineNote(`No se pudo cargar la capa histórica: ${historicalFiresError}`, true);
    return;
  }

  if (!historicalFiresTimeline.length) {
    setHistoricalFiresTimelineNote('No hay fechas históricas disponibles para la ventana temporal configurada.', true);
    return;
  }

  const currentItem = getHistoricalFiresCurrentTimelineItem();
  if (!currentItem) {
    setHistoricalFiresTimelineNote('No se pudo resolver la fecha histórica seleccionada.', true);
    return;
  }

  if (historicalFiresFrameLoading) {
    setHistoricalFiresTimelineNote(`Cargando focos históricos del ${currentItem.date}...`);
    return;
  }

  const coverageLabel = `Cobertura ${currentItem.coverage_unit_count}/${currentItem.coverage_expected_unit_count}`;
  setHistoricalFiresTimelineNote(
    `Serie lista: ${historicalFiresTimeline.length} días. ${coverageLabel}.`
  );
}

function updateHistoricalFiresTimelineUI() {
  const panel = document.getElementById('firms-history-timeline');
  const slider = document.getElementById('fh-slider');
  const dateEl = document.getElementById('fh-datetime');
  const rangeStartEl = document.getElementById('fh-range-start');
  const rangeEndEl = document.getElementById('fh-range-end');
  const playBtn = document.getElementById('fh-play');
  const resetBtn = document.getElementById('fh-reset');
  if (!panel || !slider || !dateEl || !rangeStartEl || !rangeEndEl || !playBtn || !resetBtn) return;

  panel.hidden = !historicalFiresVisible;
  syncTimelinePanelLayout();
  playBtn.classList.toggle('playing', Boolean(historicalFiresPlayInterval));
  playBtn.innerHTML = historicalFiresPlayInterval ? '&#9646;&#9646; Pausa' : '&#9654; Play';
  refreshHistoricalFiresTimelineNote();

  if (!historicalFiresTimeline.length) {
    const { dateFrom, dateTo } = getFirmsHistoricalDateRange();
    slider.min = 0;
    slider.max = 0;
    slider.value = 0;
    slider.disabled = true;
    playBtn.disabled = true;
    resetBtn.disabled = true;
    dateEl.textContent = '--';
    updateHistoricalFiresSummaryUI(null);
    rangeStartEl.textContent = dateFrom;
    rangeEndEl.textContent = dateTo;
    return;
  }

  const currentItem = getHistoricalFiresCurrentTimelineItem();
  slider.min = 0;
  slider.max = Math.max(0, historicalFiresTimeline.length - 1);
  slider.value = String(historicalFiresTimelineIndex);
  slider.disabled = historicalFiresFrameLoading;
  playBtn.disabled = false;
  resetBtn.disabled = false;
  dateEl.textContent = formatFirmsHistoricalDate(currentItem.date);
  updateHistoricalFiresSummaryUI(currentItem);
  rangeStartEl.textContent = historicalFiresTimeline[0].date;
  rangeEndEl.textContent = historicalFiresTimeline[historicalFiresTimeline.length - 1].date;
}

function stopHistoricalFiresPlayback() {
  if (!historicalFiresPlayInterval) return;
  clearInterval(historicalFiresPlayInterval);
  historicalFiresPlayInterval = null;
  updateHistoricalFiresTimelineUI();
}

function getHistoricalRenderableFires(fires = historicalFiresData) {
  return Array.isArray(fires) ? fires : [];
}

function trimHistoricalFiresCache(maxEntries = 6) {
  while (historicalFiresDataCache.size > maxEntries) {
    const oldestKey = historicalFiresDataCache.keys().next().value;
    historicalFiresDataCache.delete(oldestKey);
  }
}

function normalizeHistoricalFireFeature(feature) {
  const properties = feature?.properties || {};
  const coordinates = Array.isArray(feature?.geometry?.coordinates) ? feature.geometry.coordinates : [];
  const longitude = Number(properties.longitude ?? coordinates[0]);
  const latitude = Number(properties.latitude ?? coordinates[1]);
  return {
    ...properties,
    id: feature?.id || properties.id || `${properties.firms_source || 'firms'}_${latitude}_${longitude}`,
    longitude,
    latitude,
  };
}

function compareHistoricalFires(a, b) {
  const frpDiff = (Number(b.frp) || 0) - (Number(a.frp) || 0);
  if (frpDiff !== 0) return frpDiff;
  return String(b.acq_datetime_utc || '').localeCompare(String(a.acq_datetime_utc || ''));
}

function normalizeHistoricalFiresPayload(payload) {
  return (Array.isArray(payload?.features) ? payload.features : [])
    .map(normalizeHistoricalFireFeature)
    .filter(f => Number.isFinite(Number(f.latitude)) && Number.isFinite(Number(f.longitude)))
    .sort(compareHistoricalFires);
}

function buildFireTooltipHtml(fire, title = 'Foco FIRMS') {
  const intensityLabel = getFireIntensityLabel(fire);
  const intensityColor = getFireIntensityColor(fire);
  const confidenceLabel = getFireConfidenceLabel(fire);
  return `<b>${title}</b><br>`+
    `FRP: ${formatFireFrp(fire.frp)} MW · <span style="color:${intensityColor}">${escapeHtml(intensityLabel)}</span><br>`+
    `Confianza: ${escapeHtml(confidenceLabel)}<br>`+
    `Fecha/hora: ${escapeHtml(getFireDateTimeLabel(fire))}<br>`+
    `Satélite: ${escapeHtml(fire.satellite || fire.firms_source || 'no indicado')}<br>`+
    `Día/noche: ${escapeHtml(getFireDayNightLabel(fire))}`;
}

function renderHistoricalFires() {
  historicalFireLayers.forEach(layer => map.removeLayer(layer));
  historicalFireLayers = [];
  if (!historicalFiresVisible) return;
  if (historicalFiresError) return;

  historicalFiresData.forEach(fire => {
    const lat = Number(fire.latitude);
    const lon = Number(fire.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

    const intensityColor = getFireIntensityColor(fire);
    const radius = Math.max(4, getFireRadius(fire) - 1);
    const circle = L.circleMarker([lat, lon], {
      renderer: historicalFiresRenderer,
      radius,
      color: '#1f2430',
      fillColor: intensityColor,
      fillOpacity: 0.72,
      weight: getFireBorderWeight(fire),
      opacity: 0.88,
    }).addTo(map);
    circle.fireId = fire.id;
    circle.bindTooltip(buildFireTooltipHtml(fire, 'Foco FIRMS histórico'), { sticky: true });
    circle.on('click', () => {
      focusFireLocation(lat, lon, fire.id);
      L.popup({ offset: [0, -8] })
        .setLatLng([lat, lon])
        .setContent(buildFireTooltipHtml(fire, 'Foco FIRMS histórico'))
        .openOn(map);
    });
    historicalFireLayers.push(circle);
  });

}

function getAemetMaxTempLevelColor(properties = {}) {
  return properties.level_color || {
    Rojo: '#CC0000',
    Naranja: '#FFA500',
    Amarillo: '#FFD700',
    Verde: '#4CAF50',
  }[properties.level_label] || '#FFD700';
}

function clearAemetMaxTempLayer() {
  if (aemetMaxTempLayer && map.hasLayer(aemetMaxTempLayer)) {
    map.removeLayer(aemetMaxTempLayer);
  }
  aemetMaxTempLayer = null;
}

function buildAemetMaxTempPopupHtml(properties = {}) {
  const color = getAemetMaxTempLevelColor(properties);
  const temperature = formatAemetTemperature(properties.temperature_max_c);
  const probability = properties.probability ? ` · Prob. ${escapeHtml(properties.probability)}` : '';
  const valueLine = temperature
    ? `Umbral: <b>${escapeHtml(temperature)}</b>${probability}<br>`
    : '';
  return `<b>Aviso AEMET temperaturas máximas</b><br>`+
    `${escapeHtml(properties.area_name || 'Zona AEMET')}<br>`+
    `<span style="color:${color}">${escapeHtml(properties.level_label || 'Aviso')}</span><br>`+
    valueLine+
    `Válido: ${escapeHtml(properties.onset_at || 'n/d')} - ${escapeHtml(properties.expires_at || 'n/d')}`;
}

function renderAemetMaxTempForDate(dateString) {
  clearAemetMaxTempLayer();
  if (!aemetMaxTempVisible || !dateString || aemetMaxTempError) return;

  const currentItem = aemetMaxTempTimelineByDate.get(dateString);
  if (!currentItem || Number(currentItem.warning_count) <= 0) return;

  const styleByLayer = {};
  styleByLayer[AEMET_MAX_TEMP_MVT_LAYER_NAME] = properties => {
    const color = getAemetMaxTempLevelColor(properties);
    const rank = Number(properties.level_rank) || 1;
    return {
      color,
      weight: Math.max(1.2, rank + 0.4),
      opacity: 0.9,
      fill: true,
      fillColor: color,
      fillOpacity: 0.24,
    };
  };

  aemetMaxTempLayer = L.vectorGrid.protobuf(buildAemetMaxTempTileUrl(dateString), {
    rendererFactory: L.canvas.tile,
    pane: AEMET_MAX_TEMP_PANE,
    interactive: true,
    maxNativeZoom: 12,
    vectorTileLayerStyles: styleByLayer,
    getFeatureId: feature => feature.properties.feature_id,
  });

  aemetMaxTempLayer.on('mouseover', event => {
    const properties = event.layer?.properties || {};
    event.layer.bindTooltip(
      `<b>${escapeHtml(properties.area_name || 'Zona AEMET')}</b><br>`+
      `${escapeHtml(properties.level_label || 'Aviso')} · ${escapeHtml(formatAemetTemperature(properties.temperature_max_c) || 's/d')}`,
      { sticky: true }
    ).openTooltip();
  });
  aemetMaxTempLayer.on('click', event => {
    const properties = event.layer?.properties || {};
    L.popup({ offset: [0, -4] })
      .setLatLng(event.latlng)
      .setContent(buildAemetMaxTempPopupHtml(properties))
      .openOn(map);
  });
  aemetMaxTempLayer.addTo(map);
}

async function loadHistoricalFiresForDate(dateString, forceReload = false) {
  const requestToken = ++historicalFiresRequestToken;
  historicalFiresFrameLoading = true;
  updateHistoricalFiresTimelineUI();

  try {
    let fires = null;
    if (!forceReload && historicalFiresDataCache.has(dateString)) {
      fires = historicalFiresDataCache.get(dateString);
    } else {
      const payload = await fetchJson(buildFirmsHistoricalFeaturesUrl(dateString), HISTORICAL_DATA_FETCH_OPTIONS);
      fires = normalizeHistoricalFiresPayload(payload);
      historicalFiresDataCache.set(dateString, fires);
      trimHistoricalFiresCache();
    }

    if (requestToken !== historicalFiresRequestToken) return;
    historicalFiresData = fires;
    historicalFiresError = null;
    renderHistoricalFires();
    updateLegend();
  } catch (error) {
    if (requestToken !== historicalFiresRequestToken) return;
    historicalFiresData = [];
    historicalFiresError = error.message;
    renderHistoricalFires();
    updateLegend();
  } finally {
    if (requestToken === historicalFiresRequestToken) {
      historicalFiresFrameLoading = false;
      updateHistoricalFiresTimelineUI();
    }
  }
}

async function setHistoricalFiresFrame(index, forceReload = false) {
  if (!historicalFiresTimeline.length) return;
  historicalFiresTimelineIndex = Math.max(0, Math.min(index, historicalFiresTimeline.length - 1));
  updateHistoricalFiresTimelineUI();
  const currentItem = getHistoricalFiresCurrentTimelineItem();
  if (!currentItem) return;
  await loadHistoricalFiresForDate(currentItem.date, forceReload);
}

function resetHistoricalFiresTimeline() {
  stopHistoricalFiresPlayback();
  void setHistoricalFiresFrame(0);
}

function toggleHistoricalFiresPlayback() {
  if (!historicalFiresTimeline.length) return;
  if (historicalFiresPlayInterval) {
    stopHistoricalFiresPlayback();
    return;
  }
  historicalFiresPlayInterval = setInterval(() => {
    if (historicalFiresFrameLoading) return;
    const nextIndex = historicalFiresTimelineIndex + 1;
    if (nextIndex >= historicalFiresTimeline.length) {
      stopHistoricalFiresPlayback();
      return;
    }
    void setHistoricalFiresFrame(nextIndex);
  }, 700);
  updateHistoricalFiresTimelineUI();
}

async function ensureHistoricalFiresTimelineLoaded() {
  if (historicalFiresMetadata && historicalFiresTimeline.length) {
    return {
      layer_id: historicalFiresMetadata.layer_id,
      dataset_type: historicalFiresMetadata.dataset_type,
      date_from: historicalFiresMetadata.default_date_from,
      date_to: historicalFiresMetadata.default_date_to,
      date_count: historicalFiresTimeline.length,
      dates: historicalFiresTimeline,
    };
  }
  if (historicalFiresLoadingPromise) return historicalFiresLoadingPromise;
  historicalFiresLoadingPromise = (async () => {
    const timelinePayload = await fetchJson(buildFirmsHistoricalTimelineUrl(), HISTORICAL_DATA_FETCH_OPTIONS);
    historicalFiresMetadata = {
      layer_id: timelinePayload.layer_id || 'firms_hotspot_historical',
      dataset_type: timelinePayload.dataset_type || 'SP',
      default_date_from: timelinePayload.date_from || FIRMS_HISTORY_DEFAULT_DATE_FROM,
      default_date_to: timelinePayload.date_to || FIRMS_HISTORY_DEFAULT_DATE_TO,
    };
    historicalFiresTimeline = Array.isArray(timelinePayload.dates) ? timelinePayload.dates : [];
    historicalFiresTimelineIndex = 0;
    updateHistoricalFiresTimelineUI();
    return timelinePayload;
  })()
    .catch(error => {
      historicalFiresError = error.message;
      historicalFiresTimeline = [];
      historicalFiresData = [];
      setHistoricalFiresTimelineNote(`No se pudo cargar la capa histórica: ${error.message}`, true);
      updateHistoricalFiresTimelineUI();
      throw error;
    })
    .finally(() => {
      historicalFiresLoadingPromise = null;
    });
  return historicalFiresLoadingPromise;
}

async function ensureAemetMaxTempTimelineLoaded() {
  if (aemetMaxTempMetadata && aemetMaxTempTimeline.length) {
    return {
      layer_id: aemetMaxTempMetadata.layer_id,
      date_from: aemetMaxTempMetadata.default_date_from,
      date_to: aemetMaxTempMetadata.default_date_to,
      date_count: aemetMaxTempTimeline.length,
      dates: aemetMaxTempTimeline,
    };
  }
  if (aemetMaxTempLoadingPromise) return aemetMaxTempLoadingPromise;
  aemetMaxTempLoadingPromise = (async () => {
    aemetMaxTempMetadata = await fetchJson(AEMET_MAX_TEMP_LAYER_METADATA_URL, HISTORICAL_DATA_FETCH_OPTIONS);
    const timelinePayload = await fetchJson(buildAemetMaxTempTimelineUrl(), HISTORICAL_DATA_FETCH_OPTIONS);
    aemetMaxTempMetadata = {
      ...aemetMaxTempMetadata,
      layer_id: timelinePayload.layer_id || 'aemet_max_temperature_warnings',
      default_date_from: timelinePayload.date_from || AEMET_MAX_TEMP_DEFAULT_DATE_FROM,
      default_date_to: timelinePayload.date_to || AEMET_MAX_TEMP_DEFAULT_DATE_TO,
    };
    aemetMaxTempTimeline = Array.isArray(timelinePayload.dates) ? timelinePayload.dates : [];
    aemetMaxTempTimelineByDate = buildDateItemMap(aemetMaxTempTimeline);
    rebuildHistoricalTimeline();
    updateHistoricalTimelineUI();
    return timelinePayload;
  })()
    .catch(error => {
      aemetMaxTempError = error.message;
      aemetMaxTempTimeline = [];
      aemetMaxTempTimelineByDate = new Map();
      clearAemetMaxTempLayer();
      rebuildHistoricalTimeline();
      updateHistoricalTimelineUI();
      throw error;
    })
    .finally(() => {
      aemetMaxTempLoadingPromise = null;
    });
  return aemetMaxTempLoadingPromise;
}

async function toggleHistoricalFiresLayer(enabled) {
  historicalFiresVisible = enabled;

  if (!enabled) {
    stopHistoricalFiresPlayback();
    historicalFiresData = [];
    historicalFiresError = null;
    historicalFiresFrameLoading = false;
    historicalFiresRequestToken += 1;
    renderHistoricalFires();
    renderList();
    updateLegend();
    updateHistoricalFiresTimelineUI();
    return;
  }

  renderList();
  updateLegend();
  updateHistoricalFiresTimelineUI();

  try {
    await ensureHistoricalFiresTimelineLoaded();
    historicalFiresError = null;
    if (!historicalFiresTimeline.length) {
      updateHistoricalFiresTimelineUI();
      return;
    }
    await setHistoricalFiresFrame(historicalFiresTimelineIndex);
  } catch (_) {
    updateHistoricalFiresTimelineUI();
  }
}

async function toggleAemetMaxTempLayer(enabled) {
  const hadVisibleHistoricalLayers = hasVisibleHistoricalLayers();
  aemetMaxTempVisible = enabled;

  if (!enabled) {
    clearAemetMaxTempLayer();
    aemetMaxTempError = null;
    if (!burntAreaVisible && !historicalFiresVisible) stopHistoricalTimelinePlayback();
    rebuildHistoricalTimeline(getHistoricalTimelineCurrentDate());
    updateHistoricalTimelineUI();
    updateLegend();
    return;
  }

  updateLegend();
  updateHistoricalTimelineUI();

  try {
    await ensureAemetMaxTempTimelineLoaded();
    aemetMaxTempError = null;
    rebuildHistoricalTimeline(getHistoricalTimelineCurrentDate());
    if (!historicalTimeline.length) {
      updateHistoricalTimelineUI();
      return;
    }
    if (!hadVisibleHistoricalLayers) {
      historicalTimelineIndex = resolveHistoricalTimelineDefaultIndex();
    }
    await setHistoricalTimelineFrame(historicalTimelineIndex);
  } catch (_) {
    updateHistoricalTimelineUI();
  }
}

function buildDateItemMap(items) {
  return new Map(
    (Array.isArray(items) ? items : [])
      .filter(item => item && item.date)
      .map(item => [item.date, item])
  );
}

function hasVisibleHistoricalLayers() {
  return burntAreaVisible || historicalFiresVisible || aemetMaxTempVisible;
}

function getHistoricalTimelineCurrentDate() {
  return historicalTimeline[historicalTimelineIndex] || historicalTimeline[0] || null;
}

function getHistoricalTimelineDefaultDate() {
  if (aemetMaxTempVisible) {
    return aemetMaxTempTimeline.find(item => Number(item.warning_count) > 0)?.date
      || historicalFiresTimeline[0]?.date
      || burntAreaTimeline.find(item => item.has_local_tiles)?.date
      || aemetMaxTempTimeline[0]?.date
      || burntAreaTimeline[0]?.date
      || null;
  }
  if (historicalFiresVisible) {
    return historicalFiresTimeline[0]?.date
      || burntAreaTimeline.find(item => item.has_local_tiles)?.date
      || aemetMaxTempTimeline.find(item => Number(item.warning_count) > 0)?.date
      || burntAreaTimeline[0]?.date
      || aemetMaxTempTimeline[0]?.date
      || null;
  }
  return burntAreaTimeline.find(item => item.has_local_tiles)?.date
    || burntAreaTimeline[0]?.date
    || historicalFiresTimeline[0]?.date
    || aemetMaxTempTimeline.find(item => Number(item.warning_count) > 0)?.date
    || aemetMaxTempTimeline[0]?.date
    || null;
}

function resolveHistoricalTimelineDefaultIndex() {
  if (!historicalTimeline.length) return 0;
  const defaultDate = getHistoricalTimelineDefaultDate();
  const nextIndex = defaultDate ? historicalTimeline.indexOf(defaultDate) : -1;
  return nextIndex >= 0 ? nextIndex : 0;
}

function rebuildHistoricalTimeline(preferredDate = null) {
  const currentDate = preferredDate || getHistoricalTimelineCurrentDate();
  historicalTimeline = Array.from(
    new Set([
      ...burntAreaTimeline.map(item => item?.date),
      ...historicalFiresTimeline.map(item => item?.date),
      ...aemetMaxTempTimeline.map(item => item?.date),
    ].filter(Boolean))
  ).sort((a, b) => a.localeCompare(b));

  if (!historicalTimeline.length) {
    historicalTimelineIndex = 0;
    return;
  }

  const targetDate = currentDate || getHistoricalTimelineDefaultDate();
  const nextIndex = targetDate ? historicalTimeline.indexOf(targetDate) : -1;
  historicalTimelineIndex = nextIndex >= 0 ? nextIndex : resolveHistoricalTimelineDefaultIndex();
}

function getHistoricalTimelineBoundaryRange() {
  const startCandidates = [
    historicalTimeline[0],
    burntAreaTimeline[0]?.date,
    historicalFiresTimeline[0]?.date,
    aemetMaxTempTimeline[0]?.date,
    burntAreaMetadata?.default_date_from,
    historicalFiresMetadata?.default_date_from,
    aemetMaxTempMetadata?.default_date_from,
    BURNT_AREA_DEFAULT_DATE_FROM,
    FIRMS_HISTORY_DEFAULT_DATE_FROM,
    AEMET_MAX_TEMP_DEFAULT_DATE_FROM,
  ].filter(Boolean).sort((a, b) => a.localeCompare(b));
  const endCandidates = [
    historicalTimeline[historicalTimeline.length - 1],
    burntAreaTimeline[burntAreaTimeline.length - 1]?.date,
    historicalFiresTimeline[historicalFiresTimeline.length - 1]?.date,
    aemetMaxTempTimeline[aemetMaxTempTimeline.length - 1]?.date,
    burntAreaMetadata?.default_date_to,
    historicalFiresMetadata?.default_date_to,
    aemetMaxTempMetadata?.default_date_to,
    BURNT_AREA_DEFAULT_DATE_TO,
    FIRMS_HISTORY_DEFAULT_DATE_TO,
    AEMET_MAX_TEMP_DEFAULT_DATE_TO,
  ].filter(Boolean).sort((a, b) => a.localeCompare(b));

  return {
    start: startCandidates[0] || '--',
    end: endCandidates[endCandidates.length - 1] || '--',
  };
}

function getBurntAreaCurrentTimelineItem() {
  const currentDate = getHistoricalTimelineCurrentDate();
  return currentDate ? (burntAreaTimelineByDate.get(currentDate) || null) : null;
}

function getHistoricalFiresCurrentTimelineItem() {
  const currentDate = getHistoricalTimelineCurrentDate();
  return currentDate ? (historicalFiresTimelineByDate.get(currentDate) || null) : null;
}

function getAemetMaxTempCurrentTimelineItem() {
  const currentDate = getHistoricalTimelineCurrentDate();
  return currentDate ? (aemetMaxTempTimelineByDate.get(currentDate) || null) : null;
}

function setHistoricalTimelineNote(message, isError = false) {
  const note = document.getElementById('ht-note');
  if (!note) return;
  if (!message) {
    note.hidden = true;
    note.textContent = '';
    return;
  }
  note.hidden = false;
  note.textContent = message;
  note.style.color = isError ? '#ff9786' : '#cbb6ad';
}

function setHistoricalSummaryState(elementId, { hidden = false, state = 'nodata', text = '--' } = {}) {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.hidden = hidden;
  if (hidden) return;
  el.dataset.state = state;
  el.textContent = text;
}

function updateHistoricalBurntAreaSummaryUI(dateString) {
  if (!burntAreaVisible) {
    setHistoricalSummaryState('ht-ba-summary', { hidden: true });
    return;
  }
  if (burntAreaError) {
    setHistoricalSummaryState('ht-ba-summary', { state: 'error', text: 'BA error' });
    return;
  }

  if (isBurntAreaCumulativeMode()) {
    const cumulative = getBurntAreaCumulativeStats(dateString);
    if (!cumulative.hasStats) {
      setHistoricalSummaryState('ht-ba-summary', { state: 'nodata', text: 'BA acum. s/d' });
      return;
    }
    const formattedSurface = formatBurntAreaSurface(cumulative.areaHa);
    if (formattedSurface === null) {
      setHistoricalSummaryState('ht-ba-summary', { state: 'nodata', text: 'BA acum. s/d' });
      return;
    }
    if (Number(cumulative.areaHa) <= 0) {
      setHistoricalSummaryState('ht-ba-summary', { state: 'zero', text: 'BA acum. 0 ha' });
      return;
    }
    setHistoricalSummaryState('ht-ba-summary', { state: 'active', text: `BA acum. ${formattedSurface}` });
    return;
  }

  const item = dateString ? (burntAreaTimelineByDate.get(dateString) || null) : null;
  if (!item) {
    setHistoricalSummaryState('ht-ba-summary', { state: 'nodata', text: 'BA s/d' });
    return;
  }
  if (!item.has_local_tiles) {
    setHistoricalSummaryState('ht-ba-summary', { state: 'nodata', text: 'BA sin teselas' });
    return;
  }

  const formattedSurface = formatBurntAreaSurface(item.burned_area_ha);
  if (formattedSurface === null) {
    setHistoricalSummaryState('ht-ba-summary', { state: 'nodata', text: 'BA s/d' });
    return;
  }
  if (Number(item.burned_area_ha) <= 0) {
    setHistoricalSummaryState('ht-ba-summary', { state: 'zero', text: 'BA 0 ha' });
    return;
  }
  setHistoricalSummaryState('ht-ba-summary', { state: 'active', text: `BA ${formattedSurface}` });
}

function updateHistoricalFiresSummaryUI(item) {
  if (!historicalFiresVisible) {
    setHistoricalSummaryState('ht-fh-summary', { hidden: true });
    return;
  }
  if (historicalFiresError) {
    setHistoricalSummaryState('ht-fh-summary', { state: 'error', text: 'FIRMS error' });
    return;
  }
  if (historicalFiresFrameLoading) {
    setHistoricalSummaryState('ht-fh-summary', { state: 'loading', text: 'FIRMS cargando' });
    return;
  }
  if (!item) {
    setHistoricalSummaryState('ht-fh-summary', { state: 'nodata', text: 'FIRMS s/d' });
    return;
  }

  const hotspotCount = Number(item.hotspot_count) || 0;
  if (hotspotCount <= 0) {
    setHistoricalSummaryState('ht-fh-summary', { state: 'zero', text: 'FIRMS 0 focos' });
    return;
  }
  setHistoricalSummaryState('ht-fh-summary', {
    state: 'active',
    text: `FIRMS ${formatFirmsHistoricalCount(hotspotCount)}`,
  });
}

function updateHistoricalAemetMaxTempSummaryUI(item) {
  if (!aemetMaxTempVisible) {
    setHistoricalSummaryState('ht-aemet-summary', { hidden: true });
    return;
  }
  if (aemetMaxTempError) {
    setHistoricalSummaryState('ht-aemet-summary', { state: 'error', text: 'AEMET error' });
    return;
  }
  if (!item) {
    setHistoricalSummaryState('ht-aemet-summary', { state: 'nodata', text: 'AEMET s/d' });
    return;
  }

  const warningCount = Number(item.warning_count) || 0;
  if (warningCount <= 0) {
    setHistoricalSummaryState('ht-aemet-summary', { state: 'zero', text: 'AEMET 0 zonas' });
    return;
  }
  const temperature = formatAemetTemperature(item.max_temperature_c);
  setHistoricalSummaryState('ht-aemet-summary', {
    state: 'active',
    text: `AEMET ${formatAemetMaxTempCount(warningCount)}${temperature ? ` · ${temperature}` : ''}`,
  });
}

function refreshHistoricalTimelineNote() {
  if (!hasVisibleHistoricalLayers()) {
    setHistoricalTimelineNote('');
    return;
  }
  if (!historicalTimeline.length) {
    const errorMessages = [];
    if (burntAreaVisible && burntAreaError) errorMessages.push(`BA: ${burntAreaError}`);
    if (historicalFiresVisible && historicalFiresError) errorMessages.push(`FIRMS: ${historicalFiresError}`);
    if (aemetMaxTempVisible && aemetMaxTempError) errorMessages.push(`AEMET: ${aemetMaxTempError}`);
    setHistoricalTimelineNote(
      errorMessages.length
        ? errorMessages.join(' · ')
        : 'No hay fechas historicas disponibles para las capas seleccionadas.',
      errorMessages.length > 0
    );
    return;
  }

  const currentDate = getHistoricalTimelineCurrentDate();
  if (!currentDate) {
    setHistoricalTimelineNote('No se pudo resolver la fecha historica seleccionada.', true);
    return;
  }

  setHistoricalTimelineNote('');
  return;

  const messages = [];
  let visibleLayerCount = 0;
  let errorLayerCount = 0;

  if (burntAreaVisible) {
    visibleLayerCount += 1;
    const item = getBurntAreaCurrentTimelineItem();
    if (burntAreaError) {
      messages.push(`BA: ${burntAreaError}`);
      errorLayerCount += 1;
    } else if (!item) {
      messages.push(`BA: sin dato para ${currentDate}`);
    } else if (!item.has_local_tiles) {
      messages.push(`BA: sin teselas para ${currentDate}`);
    } else {
      messages.push(`BA: ${formatBurntAreaSurface(item.burned_area_ha) || 's/d'}`);
    }
  }

  if (historicalFiresVisible) {
    visibleLayerCount += 1;
    const item = getHistoricalFiresCurrentTimelineItem();
    if (historicalFiresError) {
      messages.push(`FIRMS: ${historicalFiresError}`);
      errorLayerCount += 1;
    } else if (historicalFiresFrameLoading) {
      messages.push(`FIRMS: cargando ${currentDate}...`);
    } else if (!item) {
      messages.push(`FIRMS: sin dato para ${currentDate}`);
    } else {
      const coverageActual = Number(item.coverage_unit_count);
      const coverageExpected = Number(item.coverage_expected_unit_count);
      const coverageLabel = Number.isFinite(coverageActual) && Number.isFinite(coverageExpected)
        ? ` cobertura ${coverageActual}/${coverageExpected}`
        : '';
      messages.push(`FIRMS: ${formatFirmsHistoricalCount(item.hotspot_count)}${coverageLabel}`);
    }
  }

  setHistoricalTimelineNote(messages.join(' · '), visibleLayerCount > 0 && errorLayerCount === visibleLayerCount);
}

function updateHistoricalTimelineUI() {
  const panel = document.getElementById('historical-timeline');
  const slider = document.getElementById('ht-slider');
  const dateEl = document.getElementById('ht-datetime');
  const rangeStartEl = document.getElementById('ht-range-start');
  const rangeEndEl = document.getElementById('ht-range-end');
  const playBtn = document.getElementById('ht-play');
  const resetBtn = document.getElementById('ht-reset');
  if (!panel || !slider || !dateEl || !rangeStartEl || !rangeEndEl || !playBtn || !resetBtn) return;

  syncTimelinePanelsVisibility();
  updateBurntAreaModeControl();
  playBtn.classList.toggle('playing', Boolean(historicalTimelinePlayInterval));
  playBtn.innerHTML = historicalTimelinePlayInterval ? '&#9646;&#9646; Pausa' : '&#9654; Play';

  updateHistoricalBurntAreaSummaryUI(getHistoricalTimelineCurrentDate());
  updateHistoricalFiresSummaryUI(getHistoricalFiresCurrentTimelineItem());
  updateHistoricalAemetMaxTempSummaryUI(getAemetMaxTempCurrentTimelineItem());
  refreshHistoricalTimelineNote();

  const boundaryRange = getHistoricalTimelineBoundaryRange();
  if (!historicalTimeline.length) {
    slider.min = 0;
    slider.max = 0;
    slider.value = 0;
    slider.disabled = true;
    playBtn.disabled = true;
    resetBtn.disabled = true;
    dateEl.textContent = '--';
    rangeStartEl.textContent = boundaryRange.start;
    rangeEndEl.textContent = boundaryRange.end;
    return;
  }

  const currentDate = getHistoricalTimelineCurrentDate();
  slider.min = 0;
  slider.max = Math.max(0, historicalTimeline.length - 1);
  slider.value = String(historicalTimelineIndex);
  slider.disabled = historicalFiresVisible && historicalFiresFrameLoading;
  playBtn.disabled = slider.disabled;
  resetBtn.disabled = false;
  dateEl.textContent = formatFirmsHistoricalDate(currentDate);
  rangeStartEl.textContent = historicalTimeline[0];
  rangeEndEl.textContent = historicalTimeline[historicalTimeline.length - 1];
}

function updateBurntAreaTimelineUI() {
  updateHistoricalTimelineUI();
}

function updateHistoricalFiresTimelineUI() {
  updateHistoricalTimelineUI();
}

function clearBurntAreaRasterLayer() {
  if (burntAreaLayer && map.hasLayer(burntAreaLayer)) {
    map.removeLayer(burntAreaLayer);
  }
}

async function syncBurntAreaLocatorForDate(dateString, forceReload = false) {
  if (!burntAreaVisible || !dateString || !shouldDisplayBurntAreaLocator()) {
    clearBurntAreaLocatorLayer();
    return;
  }

  const currentItem = burntAreaTimelineByDate.get(dateString);
  const cumulative = isBurntAreaCumulativeMode();
  if (!cumulative && (!currentItem || !currentItem.has_local_tiles)) {
    clearBurntAreaLocatorLayer();
    return;
  }
  if (cumulative && !getBurntAreaCumulativeStats(dateString).hasTiles) {
    clearBurntAreaLocatorLayer();
    return;
  }

  const sourceZoom = resolveBurntAreaLocatorSourceZoom();
  const requestDate = cumulative ? dateString : currentItem.date;
  const requestMode = burntAreaDisplayMode;
  const cacheKey = `${requestMode}:${requestDate}:${sourceZoom}`;
  const layer = ensureBurntAreaLocatorLayer();
  refreshBurntAreaLocatorStyle();

  if (!forceReload && burntAreaLocatorKey === cacheKey && map.hasLayer(layer)) return;

  if (burntAreaLocatorCache.has(cacheKey)) {
    burntAreaLocatorKey = cacheKey;
    layer.clearLayers();
    layer.addData(burntAreaLocatorCache.get(cacheKey));
    if (!map.hasLayer(layer)) layer.addTo(map);
    return;
  }

  const requestKey = cacheKey;
  const locatorPromise = fetchJson(buildBurntAreaLocatorUrl(requestDate, sourceZoom))
    .then(data => {
      burntAreaLocatorCache.set(requestKey, data);
      if (!burntAreaVisible || getHistoricalTimelineCurrentDate() !== requestDate) return;
      if (burntAreaDisplayMode !== requestMode) return;
      if (resolveBurntAreaLocatorSourceZoom() !== sourceZoom) return;
      burntAreaLocatorKey = requestKey;
      layer.clearLayers();
      layer.addData(data);
      if (!map.hasLayer(layer)) layer.addTo(map);
      refreshBurntAreaLocatorStyle();
    })
    .catch(error => {
      console.error('No se pudo cargar el localizador de burnt area:', error);
      if (burntAreaLocatorKey === requestKey) clearBurntAreaLocatorLayer();
    })
    .finally(() => {
      if (burntAreaLocatorCachePromise === locatorPromise) {
        burntAreaLocatorCachePromise = null;
      }
    });
  burntAreaLocatorCachePromise = locatorPromise;
  return locatorPromise;
}

async function syncBurntAreaLocatorForCurrentView(forceReload = false) {
  return syncBurntAreaLocatorForDate(getHistoricalTimelineCurrentDate(), forceReload);
}

function renderBurntAreaForDate(dateString, forceReload = false) {
  if (!burntAreaVisible || !dateString) {
    clearBurntAreaRasterLayer();
    clearBurntAreaLocatorLayer();
    return;
  }

  if (isBurntAreaCumulativeMode()) {
    const hasKnownDate = burntAreaTimeline.some(item => item?.date && item.date <= dateString);
    if (!hasKnownDate) {
      clearBurntAreaRasterLayer();
      clearBurntAreaLocatorLayer();
      return;
    }
    clearBurntAreaRasterLayer();
    void syncBurntAreaLocatorForDate(dateString, forceReload);
    return;
  }

  const currentItem = burntAreaTimelineByDate.get(dateString);
  if (!currentItem || !currentItem.has_local_tiles) {
    clearBurntAreaRasterLayer();
    clearBurntAreaLocatorLayer();
    return;
  }

  ensureBurntAreaLayer(currentItem.date);
  void syncBurntAreaLocatorForDate(currentItem.date, forceReload);
}

function clearHistoricalFiresFrameState({ resetError = true, cancelPending = false } = {}) {
  if (cancelPending) historicalFiresRequestToken += 1;
  historicalFiresData = [];
  if (resetError) historicalFiresError = null;
  historicalFiresFrameLoading = false;
  renderHistoricalFires();
  renderList();
  updateLegend();
  updateHistoricalTimelineUI();
}

async function applyHistoricalFiresForDate(dateString, forceReload = false) {
  if (!historicalFiresVisible || !dateString) {
    clearHistoricalFiresFrameState({ cancelPending: true });
    return;
  }

  const currentItem = historicalFiresTimelineByDate.get(dateString);
  if (!currentItem) {
    clearHistoricalFiresFrameState({ cancelPending: true });
    return;
  }

  await loadHistoricalFiresForDate(currentItem.date, forceReload);
}

function stopHistoricalTimelinePlayback() {
  if (!historicalTimelinePlayInterval) return;
  clearInterval(historicalTimelinePlayInterval);
  historicalTimelinePlayInterval = null;
  updateHistoricalTimelineUI();
}

function stopBurntAreaPlayback() {
  stopHistoricalTimelinePlayback();
}

function stopHistoricalFiresPlayback() {
  stopHistoricalTimelinePlayback();
}

async function setHistoricalTimelineFrame(index, forceReload = false) {
  if (!historicalTimeline.length) {
    updateHistoricalTimelineUI();
    return;
  }

  historicalTimelineIndex = Math.max(0, Math.min(index, historicalTimeline.length - 1));
  const currentDate = getHistoricalTimelineCurrentDate();
  renderBurntAreaForDate(currentDate, forceReload);
  renderAemetMaxTempForDate(currentDate);
  updateHistoricalTimelineUI();
  if (historicalFiresVisible) {
    await applyHistoricalFiresForDate(currentDate, forceReload);
  }
  updateHistoricalTimelineUI();
}

function setBurntAreaFrame(index) {
  void setHistoricalTimelineFrame(index, true);
}

function setHistoricalFiresFrame(index, forceReload = false) {
  return setHistoricalTimelineFrame(index, forceReload);
}

// Activa la capa historica indicada (si no lo estaba) y posiciona el slider
// del timeline unificado en la fecha solicitada. Hace todo el trabajo en una
// sola pasada para evitar carreras entre el frame por defecto que aplica el
// toggle y un reposicionamiento posterior. Llamado por el chat (setLayerDate)
// y reutilizable desde cualquier otra integracion externa.
const HISTORICAL_LAYER_DESCRIPTORS = {
  burnt_area: {
    checkboxId: 'chk-burnt_area_daily',
    toggleFn: () => toggleBurntAreaLayer,
    timeline: () => burntAreaTimeline,
  },
  firms_history: {
    checkboxId: 'chk-firms_history',
    toggleFn: () => toggleHistoricalFiresLayer,
    timeline: () => historicalFiresTimeline,
  },
  aemet_max_temp_history: {
    checkboxId: 'chk-aemet_max_temp_history',
    toggleFn: () => toggleAemetMaxTempLayer,
    timeline: () => aemetMaxTempTimeline,
  },
};

async function showHistoricalLayerAtDate(layer, dateString) {
  const descriptor = HISTORICAL_LAYER_DESCRIPTORS[layer];
  if (!descriptor || !dateString) return false;
  const toggleFn = descriptor.toggleFn();
  if (typeof toggleFn !== 'function') return false;

  const cb = document.getElementById(descriptor.checkboxId);
  if (cb) cb.checked = true;
  // Llamamos al toggle directamente y esperamos a que termine: asi cuando
  // continuemos, el timeline esta cargado y el frame por defecto ya se ha
  // aplicado. Cualquier frame posterior que nosotros mismos pongamos sera
  // el ultimo escritor sobre historicalTimelineIndex y, por tanto, el que
  // gane.
  await toggleFn(true);

  if (historicalTimeline.indexOf(dateString) < 0 && typeof rebuildHistoricalTimeline === 'function') {
    rebuildHistoricalTimeline(dateString);
  }
  const idx = historicalTimeline.indexOf(dateString);
  if (idx < 0) return false;
  await setHistoricalTimelineFrame(idx, true);
  return true;
}

function resetHistoricalTimeline() {
  stopHistoricalTimelinePlayback();
  void setHistoricalTimelineFrame(0);
}

function resetBurntAreaTimeline() {
  resetHistoricalTimeline();
}

function resetHistoricalFiresTimeline() {
  resetHistoricalTimeline();
}

function toggleHistoricalTimelinePlayback() {
  if (!historicalTimeline.length) return;
  if (historicalTimelinePlayInterval) {
    stopHistoricalTimelinePlayback();
    return;
  }

  historicalTimelinePlayInterval = setInterval(() => {
    if (historicalFiresVisible && historicalFiresFrameLoading) return;
    const nextIndex = historicalTimelineIndex + 1;
    if (nextIndex >= historicalTimeline.length) {
      stopHistoricalTimelinePlayback();
      return;
    }
    void setHistoricalTimelineFrame(nextIndex);
  }, 700);
  updateHistoricalTimelineUI();
}

function toggleBurntAreaPlayback() {
  toggleHistoricalTimelinePlayback();
}

function toggleHistoricalFiresPlayback() {
  toggleHistoricalTimelinePlayback();
}

async function ensureBurntAreaTimelineLoaded() {
  if (burntAreaMetadata && burntAreaTimeline.length) {
    return {
      layer_id: burntAreaMetadata.layer_id,
      dataset_version: BURNT_AREA_DEFAULT_VERSION,
      delivery_format: BURNT_AREA_DEFAULT_FORMAT,
      date_from: BURNT_AREA_DEFAULT_DATE_FROM,
      date_to: BURNT_AREA_DEFAULT_DATE_TO,
      date_count: burntAreaTimeline.length,
      dates: burntAreaTimeline,
    };
  }
  if (burntAreaLoadingPromise) return burntAreaLoadingPromise;
  burntAreaLoadingPromise = (async () => {
    burntAreaMetadata = await fetchJson(BURNT_AREA_LAYER_METADATA_URL);
    const timelinePayload = await fetchJson(buildBurntAreaTimelineUrl());
    burntAreaTimeline = Array.isArray(timelinePayload.dates) ? timelinePayload.dates : [];
    burntAreaTimelineByDate = buildDateItemMap(burntAreaTimeline);
    rebuildHistoricalTimeline();
    updateHistoricalTimelineUI();
    return timelinePayload;
  })()
    .catch(error => {
      burntAreaError = error.message;
      burntAreaTimeline = [];
      burntAreaTimelineByDate = new Map();
      rebuildHistoricalTimeline();
      updateHistoricalTimelineUI();
      throw error;
    })
    .finally(() => {
      burntAreaLoadingPromise = null;
    });
  return burntAreaLoadingPromise;
}

async function ensureHistoricalFiresTimelineLoaded() {
  if (historicalFiresMetadata && historicalFiresTimeline.length) {
    return {
      layer_id: historicalFiresMetadata.layer_id,
      dataset_type: historicalFiresMetadata.dataset_type,
      date_from: historicalFiresMetadata.default_date_from,
      date_to: historicalFiresMetadata.default_date_to,
      date_count: historicalFiresTimeline.length,
      dates: historicalFiresTimeline,
    };
  }
  if (historicalFiresLoadingPromise) return historicalFiresLoadingPromise;
  historicalFiresLoadingPromise = (async () => {
    const timelinePayload = await fetchJson(buildFirmsHistoricalTimelineUrl(), HISTORICAL_DATA_FETCH_OPTIONS);
    historicalFiresMetadata = {
      layer_id: timelinePayload.layer_id || 'firms_hotspot_historical',
      dataset_type: timelinePayload.dataset_type || 'SP',
      default_date_from: timelinePayload.date_from || FIRMS_HISTORY_DEFAULT_DATE_FROM,
      default_date_to: timelinePayload.date_to || FIRMS_HISTORY_DEFAULT_DATE_TO,
    };
    historicalFiresTimeline = Array.isArray(timelinePayload.dates) ? timelinePayload.dates : [];
    historicalFiresTimelineByDate = buildDateItemMap(historicalFiresTimeline);
    rebuildHistoricalTimeline();
    updateHistoricalTimelineUI();
    return timelinePayload;
  })()
    .catch(error => {
      historicalFiresError = error.message;
      historicalFiresTimeline = [];
      historicalFiresTimelineByDate = new Map();
      historicalFiresData = [];
      rebuildHistoricalTimeline();
      updateHistoricalTimelineUI();
      throw error;
    })
    .finally(() => {
      historicalFiresLoadingPromise = null;
    });
  return historicalFiresLoadingPromise;
}

async function toggleBurntAreaLayer(enabled) {
  const hadVisibleHistoricalLayers = hasVisibleHistoricalLayers();
  burntAreaVisible = enabled;

  if (!enabled) {
    clearBurntAreaRasterLayer();
    clearBurntAreaLocatorLayer();
    if (!historicalFiresVisible && !aemetMaxTempVisible) stopHistoricalTimelinePlayback();
    rebuildHistoricalTimeline(getHistoricalTimelineCurrentDate());
    updateHistoricalTimelineUI();
    return;
  }

  updateHistoricalTimelineUI();

  try {
    await ensureBurntAreaTimelineLoaded();
    burntAreaError = null;
    rebuildHistoricalTimeline(getHistoricalTimelineCurrentDate());
    if (!historicalTimeline.length) {
      updateHistoricalTimelineUI();
      return;
    }
    if (!hadVisibleHistoricalLayers) {
      historicalTimelineIndex = resolveHistoricalTimelineDefaultIndex();
    }
    await setHistoricalTimelineFrame(historicalTimelineIndex, true);
  } catch (_) {
    updateHistoricalTimelineUI();
  }
}

async function toggleHistoricalFiresLayer(enabled) {
  const hadVisibleHistoricalLayers = hasVisibleHistoricalLayers();
  historicalFiresVisible = enabled;

  if (!enabled) {
    clearHistoricalFiresFrameState({ cancelPending: true });
    if (!burntAreaVisible && !aemetMaxTempVisible) stopHistoricalTimelinePlayback();
    rebuildHistoricalTimeline(getHistoricalTimelineCurrentDate());
    updateHistoricalTimelineUI();
    return;
  }

  renderList();
  updateLegend();
  updateHistoricalTimelineUI();

  try {
    await ensureHistoricalFiresTimelineLoaded();
    historicalFiresError = null;
    rebuildHistoricalTimeline(getHistoricalTimelineCurrentDate());
    if (!historicalTimeline.length) {
      updateHistoricalTimelineUI();
      return;
    }
    if (!hadVisibleHistoricalLayers) {
      historicalTimelineIndex = resolveHistoricalTimelineDefaultIndex();
    }
    await setHistoricalTimelineFrame(historicalTimelineIndex);
  } catch (_) {
    updateHistoricalTimelineUI();
  }
}

function fetchSpainHotspots() {
  return fetchJson('/api/fires');
}

function getAlertCountsByTime(alerts, referenceTime = (tlCurrent || new Date())) {
  let active = 0;
  let upcoming = 0;
  let expired = 0;

  alerts.forEach(a => {
    const onset = new Date(a.onset);
    const expires = new Date(a.expires);
    if (expires < referenceTime) {
      expired += 1;
    } else if (onset <= referenceTime) {
      active += 1;
    } else {
      upcoming += 1;
    }
  });

  return {
    active,
    upcoming,
    expired,
    total: active + upcoming,
  };
}

function buildClientStats(alerts, fires) {
  const referenceTime = tlCurrent || new Date();
  const alertCounts = getAlertCountsByTime(alerts, referenceTime);
  const levelCount = {};
  const fireLevelCount = {};
  alerts
    .filter(a => new Date(a.expires) >= referenceTime)
    .forEach(a => {
      levelCount[a.level] = (levelCount[a.level] || 0) + 1;
    });
  fires.forEach(f => {
    const intensity = getFireIntensityLabel(f);
    fireLevelCount[intensity] = (fireLevelCount[intensity] || 0) + 1;
  });
  return {
    alerts: {
      total: alertCounts.total,
      active: alertCounts.active,
      upcoming: alertCounts.upcoming,
      expired: alertCounts.expired,
      por_nivel: levelCount,
    },
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
    firesData.forEach(initializeFireLandcoverInfo);
  } catch (error) {
    firesData = [];
    firesError = error.message;
  } finally {
    firesLoading = false;
    updateStatsBar(buildClientStats(alertsData, firesData));
    renderFires();
    renderList();
    updateLegend();
    if (!firesError) void enrichFireLandcoverInfo();
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

  populateEventFilter();
  initTimeline();
  const stats = buildClientStats(alertsData, firesData);
  updateStatsBar(stats);
  const chkF = document.getElementById('chk-fires');
  if (chkF) chkF.checked = true;
  renderAlerts();
  renderFires();
  renderList();
  updateLegend();
  void loadFiresInBackground();
  void ensureBurntAreaTimelineLoaded().catch(() => {});
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

function getVisibleAlerts(alerts) {
  return alertsListView === 'active'
    ? alerts.filter(isActive)
    : alerts;
}

function syncAlertsListViewControls(nActive, nUpcoming) {
  const toggle = document.getElementById('alerts-view-toggle');
  const count = document.getElementById('list-count');
  const summaryText = alertsListView === 'active'
    ? `${nActive} act.`
    : (nUpcoming > 0 ? `${nActive} act. · ${nUpcoming} próx.` : `${nActive} act.`);
  const summaryTitle = alertsListView === 'active'
    ? `${nActive} avisos activos para este filtro`
    : (nUpcoming > 0 ? `${nActive} avisos activos y ${nUpcoming} próximos para este filtro` : `${nActive} avisos activos para este filtro`);

  if (count) {
    count.textContent = summaryText;
    count.title = summaryTitle;
  }

  if (toggle) {
    toggle.title = alertsListView === 'active'
      ? 'Mostrando solo los avisos activos en la lista y en el mapa'
      : 'Mostrando avisos activos y próximos en la lista y en el mapa';
    toggle.classList.toggle('is-active', alertsListView === 'active');
    toggle.setAttribute('aria-pressed', alertsListView === 'active' ? 'true' : 'false');
  }
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
function renderAll() {
  updateStatsBar(buildClientStats(alertsData, firesData));
  renderAlerts();
  renderList();
}

function renderAlerts() {
  Object.values(alertLayers).forEach(l => map.removeLayer(l));
  alertLayers = {};
  if (!showAlerts) return;

  const filtered = getFilteredAlerts();
  const visible = getVisibleAlerts(filtered);
  visible.forEach(a => {
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

  if (getListMode() === 'alerts') updateListHeader(filtered);
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

function getRenderableFires(fires = firesData) {
  return (Array.isArray(fires) ? fires : [])
    .filter(f => Number.isFinite(Number(f.latitude)) && Number.isFinite(Number(f.longitude)))
    .sort((a, b) => (Number(b.frp) || 0) - (Number(a.frp) || 0));
}

function getListMode() {
  if (activeList === 'alerts' && showAlerts) return 'alerts';
  if (activeList === 'fires' && showFires) return 'fires';
  if (showFires && !showAlerts) return 'fires';
  if (showAlerts && !showFires) return 'alerts';
  if (showAlerts) return 'alerts';
  if (showFires) return 'fires';
  return 'none';
}

function formatFireCount(count) {
  return `${count} ${count === 1 ? 'foco' : 'focos'}`;
}

function buildFireLandcoverMarkup(fire) {
  if (fire.landcoverStatus === 'ready' && fire.landcoverLabel) {
    const source = fire.landcoverSourceDataset
      ? ` · ${escapeHtml(fire.landcoverSourceDataset)}`
      : '';
    return `Cae en: <b>${escapeHtml(fire.landcoverLabel)}</b>${source}`;
  }
  if (fire.landcoverStatus === 'empty') {
    return 'Cae en: sin coincidencia en la capa IGN';
  }
  if (fire.landcoverStatus === 'error') {
    return 'Cae en: uso del suelo no disponible';
  }
  return 'Cae en: consultando uso del suelo...';
}

function updateFireLandcoverCard(fire) {
  const target = document.querySelector(`.card[data-id="${fire.id}"] [data-role="fire-landcover"]`);
  if (target) target.innerHTML = buildFireLandcoverMarkup(fire);
}

async function fetchFireLandcoverInfo(fire, batchToken) {
  const lat = Number(fire.latitude);
  const lon = Number(fire.longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

  const cacheKey = buildFireLandcoverCacheKey(lat, lon);
  const cached = fireLandcoverInfoCache.get(cacheKey);
  if (cached) {
    applyFireLandcoverInfo(fire, cached);
    updateFireLandcoverCard(fire);
    return;
  }

  try {
    const data = await fetchLandcoverPoint(
      L.latLng(lat, lon),
      undefined,
      {
        queryZoom: LANDCOVER_FIRE_QUERY_ZOOM,
        width: LANDCOVER_POINT_QUERY_SIZE,
        height: LANDCOVER_POINT_QUERY_SIZE,
      }
    );
    const feature = Array.isArray(data.features) ? data.features[0] : null;
    const info = feature
      ? {
          status: 'ready',
          label: feature.properties?.label || 'Uso del suelo',
          sourceDataset: feature.properties?.source_dataset || '',
        }
      : { status: 'empty' };
    fireLandcoverInfoCache.set(cacheKey, info);
    if (batchToken !== fireLandcoverBatchToken) return;
    applyFireLandcoverInfo(fire, info);
    updateFireLandcoverCard(fire);
  } catch (_) {
    const info = { status: 'error' };
    if (batchToken !== fireLandcoverBatchToken) return;
    applyFireLandcoverInfo(fire, info);
    updateFireLandcoverCard(fire);
  }
}

async function enrichFireLandcoverInfo() {
  const batchToken = ++fireLandcoverBatchToken;
  const candidates = firesData.filter(f => Number.isFinite(Number(f.latitude)) && Number.isFinite(Number(f.longitude)));
  if (!candidates.length) return;

  let index = 0;
  const workerCount = Math.min(FIRE_LANDCOVER_WORKERS, candidates.length);
  const workers = Array.from({ length: workerCount }, async () => {
    while (index < candidates.length && batchToken === fireLandcoverBatchToken) {
      const fire = candidates[index];
      index += 1;
      if (fire.landcoverStatus === 'ready') {
        updateFireLandcoverCard(fire);
        continue;
      }
      await fetchFireLandcoverInfo(fire, batchToken);
    }
  });

  await Promise.all(workers);
}

function focusFireLocation(lat, lon, id) {
  const latlng = L.latLng(lat, lon);
  map.setView(latlng, 16, { animate: false });
  highlightCard(id);
  autoActivateWMS('effis_fwi');
  autoActivateWMS('corine_wms');
  void handleCorineWmsClick(latlng);
}

function renderFires() {
  fireLayers.forEach(l => map.removeLayer(l));
  fireLayers = [];
  if (!showFires) return;
  if (firesError) {
    if (getListMode() === 'fires') updateListHeader([]);
    return;
  }

  firesData.forEach(f => {
    const lat = Number(f.latitude);
    const lon = Number(f.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    const intensityLabel = getFireIntensityLabel(f);
    const intensityColor = getFireIntensityColor(f);
    const confidenceLabel = getFireConfidenceLabel(f);
    const radius = getFireRadius(f);
    const circle = L.circleMarker([lat, lon], {
      radius,
      color: '#111827',
      fillColor: intensityColor,
      fillOpacity: 0.85,
      weight: getFireBorderWeight(f),
      opacity: 0.95,
    }).addTo(map);
    circle.fireId = f.id;

    circle.bindTooltip(
      `<b>Foco FIRMS</b><br>`+
      `FRP: ${formatFireFrp(f.frp)} MW · <span style="color:${intensityColor}">${escapeHtml(intensityLabel)}</span><br>`+
      `Confianza: ${escapeHtml(confidenceLabel)}<br>`+
      `Fecha/hora: ${escapeHtml(getFireDateTimeLabel(f))}<br>`+
      `Satélite: ${escapeHtml(f.satellite || f.firms_source || 'no indicado')}<br>`+
      `Día/noche: ${escapeHtml(getFireDayNightLabel(f))}`,
      { sticky: true }
    );
    
    // Activacion de capas en click a puntos
    circle.on('click', () => {
      focusFireLocation(lat, lon, f.id);
    });

    fireLayers.push(circle);
  });

  if (getListMode() === 'fires') updateListHeader(getRenderableFires(firesData));
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
  const listMode = getListMode();

  if (listMode === 'none') {
    title.textContent = 'Resultados';
    updateListHeader([]);
    el.innerHTML = historicalFiresVisible || burntAreaVisible || aemetMaxTempVisible
      ? '<div class="empty">Las capas históricas activas se muestran directamente en el mapa.</div>'
      : '<div class="empty">Activa Avisos AEMET o Focos NASA FIRMS para ver resultados</div>';
    return;
  }

  if (listMode === 'alerts') {
    title.textContent = 'Avisos';
    const filtered = getFilteredAlerts();
    const visible = getVisibleAlerts(filtered);
    updateListHeader(filtered);
    if (!visible.length) {
      el.innerHTML = `<div class="empty">${alertsListView === 'active' ? 'Sin avisos activos para este filtro' : 'Sin avisos para este filtro'}</div>`;
      return;
    }

    const order = { Rojo:0, Naranja:1, Amarillo:2, Verde:3 };
    const sorted = [...visible].sort((a,b) => {
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

  } else if (listMode === 'fires') {
    title.textContent = 'Focos de incendio';
    const visibleFires = getRenderableFires(firesData);
    updateListHeader(visibleFires);
    if (firesLoading) {
      el.innerHTML = '<div class="empty">Cargando focos FIRMS...</div>';
      return;
    }
    if (firesError) {
      el.innerHTML = `<div class="empty">No se pudieron cargar los focos FIRMS: ${escapeHtml(firesError)}</div>`;
      return;
    }
    if (!visibleFires.length) { el.innerHTML = '<div class="empty">Sin focos activos en España</div>'; return; }
    el.innerHTML = visibleFires.map(f => {
      const lat = Number(f.latitude);
      const lon = Number(f.longitude);
      const intensityLabel = getFireIntensityLabel(f);
      const intensityColor = getFireIntensityColor(f);
      const confidenceLabel = getFireConfidenceLabel(f);
      return `<div class="card fire-card" data-id="${f.id}"
        style="border-left-color:${intensityColor}" onclick="zoomToFire(${lat},${lon},'${f.id}')">
        <div class="name">${lat.toFixed(3)}, ${lon.toFixed(3)}</div>
        <div class="area">${escapeHtml(getFireDateTimeLabel(f))} · ${escapeHtml(f.satellite || f.firms_source || '')}</div>
        <div class="meta">
          <span class="badge" style="background:${intensityColor}22;color:${intensityColor}">${escapeHtml(intensityLabel)}</span>
          <span class="confidence-badge">Confianza: ${escapeHtml(confidenceLabel)}</span>
          <span class="time">FRP: ${formatFireFrp(f.frp)} MW</span>
        </div>
        <div class="desc" data-role="fire-landcover">${buildFireLandcoverMarkup(f)}</div>
      </div>`;
    }).join('');
  }
}

function updateListHeader(data) {
  const alertsControl = document.getElementById('alerts-view-control');
  const firesCount = document.getElementById('fires-list-count');
  const listMode = getListMode();

  if (listMode === 'alerts' && Array.isArray(data)) {
    const nA = data.filter(isActive).length;
    const nF = data.filter(a => !isActive(a)).length;
    if (alertsControl) alertsControl.hidden = false;
    if (firesCount) firesCount.hidden = true;
    syncAlertsListViewControls(nA, nF);
  } else if (listMode === 'fires') {
    if (alertsControl) alertsControl.hidden = true;
    if (firesCount) {
      firesCount.hidden = false;
      const total = Array.isArray(data) ? data.length : getRenderableFires().length;
      firesCount.textContent = formatFireCount(total);
      firesCount.title = `${formatFireCount(total)} en la lista`;
    }
  } else {
    if (alertsControl) alertsControl.hidden = true;
    if (firesCount) firesCount.hidden = true;
  }
}

// Zoom 
function zoomToAlert(id) {
  const a = alertsData.find(x => x.id === id);
  if (!a || !a.polygon) return;
  const coords = parsePolygon(a.polygon);
  if (coords.length) map.fitBounds(L.polygon(coords).getBounds(), { padding:[40,40] });
  highlightCard(id);
  autoActivateWMS('corine_wms');
  if (isFloodRelated(a.event)) {
    autoActivateWMS('flood');
  } else {
    const chk = document.getElementById('chk-flood');
    if (chk && chk.checked) { chk.checked = false; toggleWMS('flood', false); }
  }
}

function zoomToFire(lat, lon, id) {
  focusFireLocation(lat, lon, id);
}

// Toggles capas
function toggleLayer(type, enabled) {
  if (type === 'alerts') {
    showAlerts = enabled;
    if (!enabled) stopTimelinePlayback();
    renderAlerts();
    if (enabled) activeList = 'alerts';
    else if (showFires) activeList = 'fires';
  }
  if (type === 'fires') {
    showFires = enabled; renderFires();
    if (enabled) activeList = 'fires';
    else if (showAlerts) activeList = 'alerts';
  }
  renderList();
  updateLegend();
  syncTimelinePanelsVisibility();
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

const alertsViewToggle = document.getElementById('alerts-view-toggle');
if (alertsViewToggle) {
  alertsViewToggle.addEventListener('click', () => {
    alertsListView = alertsListView === 'active' ? 'all' : 'active';
    renderAll();
  });
}

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
['flood','effis_fwi','effis_dc','corine_wms'].forEach(key => {
  const el = document.getElementById('chk-' + key);
  if (el) el.addEventListener('change', e => toggleWMS(key, e.target.checked));
});

map.on('zoomend', () => {
  if (!burntAreaVisible) return;
  refreshBurntAreaRasterPresentation();
  refreshBurntAreaLocatorStyle();
  void syncBurntAreaLocatorForCurrentView();
});

const chkBurntArea = document.getElementById('chk-burnt_area_daily');
if (chkBurntArea) {
  chkBurntArea.addEventListener('change', e => {
    void toggleBurntAreaLayer(e.target.checked);
  });
}

document.querySelectorAll('[data-burnt-area-mode]').forEach(button => {
  button.addEventListener('click', event => {
    event.preventDefault();
    setBurntAreaDisplayMode(event.currentTarget.dataset.burntAreaMode);
  });
});
updateBurntAreaModeControl();

const chkNucleos = document.getElementById('chk-nucleos_poblacion');
if (chkNucleos) {
  chkNucleos.addEventListener('change', e => toggleNucleos(e.target.checked));
}

const chkFirmsHistory = document.getElementById('chk-firms_history');
if (chkFirmsHistory) {
  chkFirmsHistory.addEventListener('change', e => {
    void toggleHistoricalFiresLayer(e.target.checked);
  });
}

const chkAemetMaxTempHistory = document.getElementById('chk-aemet_max_temp_history');
if (chkAemetMaxTempHistory) {
  chkAemetMaxTempHistory.addEventListener('change', e => {
    void toggleAemetMaxTempLayer(e.target.checked);
  });
}

const historicalTimelineSlider = document.getElementById('ht-slider');
if (historicalTimelineSlider) {
  historicalTimelineSlider.addEventListener('input', e => {
    const nextIndex = Number(e.target.value);
    stopHistoricalTimelinePlayback();
    void setHistoricalTimelineFrame(nextIndex);
  });
}

const historicalTimelinePlayBtn = document.getElementById('ht-play');
if (historicalTimelinePlayBtn) {
  historicalTimelinePlayBtn.addEventListener('click', () => toggleHistoricalTimelinePlayback());
}

const historicalTimelineResetBtn = document.getElementById('ht-reset');
if (historicalTimelineResetBtn) {
  historicalTimelineResetBtn.addEventListener('click', () => resetHistoricalTimeline());
}
 
const chkAlerts = document.getElementById('chk-alerts');
const chkFires  = document.getElementById('chk-fires');
if (chkAlerts) chkAlerts.addEventListener('change', e => toggleLayer('alerts', e.target.checked));
if (chkFires)  chkFires.addEventListener('change',  e => toggleLayer('fires',  e.target.checked));

// === ROADS LAYER (IDEE WFS primario + IGR-RT fallback) ===
const ROADS_FEATURES_URL = '/api/roads/features';
const ROADS_HEALTH_URL = '/api/roads/health';
const ROADS_TILE_URL = '/api/roads/tiles/{z}/{x}/{y}.mvt';
const ROADS_MVT_LAYER_NAME = 'carreteras';
const ROADS_PRIMARY_MIN_ZOOM = 10;  // por debajo de z=10 usamos siempre MVT (rápido, escalonado por clase)
const ROADS_TILE_MIN_ZOOM = 7;      // autopistas visibles desde z=7
const ROADS_FEATURE_LIMIT = 1500;
const ROADS_MOVE_DEBOUNCE_MS = 350;
const ROADS_HEALTH_REPROBE_MS = 60000;  // re-probe periódico al WFS si se está usando fallback
const ROADS_STYLE_BY_CLASE = {
  'Autopista de peaje':        { color: '#B71C1C', weight: 3.0 },
  'Autopista libre / autovía': { color: '#D32F2F', weight: 3.0 },
  'Carretera multicarril':     { color: '#E65100', weight: 2.5 },
  'Carretera convencional':    { color: '#FBC02D', weight: 2.0 },
  'Urbano':                    { color: '#90A4AE', weight: 1.6 },
  'Urbano diseminado':         { color: '#B0BEC5', weight: 1.3 },
  'Camino':                    { color: '#8D6E63', weight: 1.0, dashArray: '3,3' },
  'Senda':                     { color: '#A1887F', weight: 0.8, dashArray: '2,3' },
  'Carril bici':               { color: '#388E3C', weight: 1.5, dashArray: '5,4' },
};
const ROADS_DEFAULT_STYLE = { color: '#9E9E9E', weight: 1.2 };

let roadsVisible = false;
let roadsPrimaryLayer = null;
let roadsFallbackLayer = null;
let roadsRefreshHandle = null;
let roadsRequestToken = 0;
let roadsHealthCache = null;
let roadsHealthCacheUntil = 0;
let roadsHealthReprobeHandle = null;
let roadsSourceLabel = null;
const ROADS_PANE = 'roadsLayerPane';

function ensureRoadsPane() {
  if (!map.getPane(ROADS_PANE)) {
    map.createPane(ROADS_PANE);
    // Carreteras como capa de contexto: visualmente entre los overlays WMS (250-285)
    // y las capas tematicas (AEMET=330, NUCLEOS=345, overlayPane=400 con focos FIRMS
    // y avisos CAP). Asi los elementos tematicos reciben los clicks por encima.
    map.getPane(ROADS_PANE).style.zIndex = 290;
  }
}

function getRoadStyle(props) {
  const base = ROADS_STYLE_BY_CLASE[props && props.clase] || ROADS_DEFAULT_STYLE;
  return Object.assign({}, base, { opacity: 0.9, fill: false });
}

function escapeRoadValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  return escapeHtml(String(value));
}

function buildRoadsPopupContent(props) {
  const rows = [
    ['Identificador', props.inspire_id || props.id_tramo],
    ['Clase', props.clase],
    ['Tipo', props.tipo],
    ['Nombre', props.nombre],
    ['Código', props.codigo],
    ['Titular', props.titular],
    ['Sentido', props.sentido],
    ['Acceso', props.acceso],
    ['Estado físico', props.estado_fisico],
    ['Firme', props.firme],
    ['Nº carriles', props.n_carriles],
    ['Orden', props.orden],
    ['Vehículos', props.tipovehic],
    ['Territorio', props.territory_code],
  ];
  const body = rows
    .map(([label, value]) => `<tr><th>${escapeHtml(label)}</th><td>${escapeRoadValue(value)}</td></tr>`)
    .join('');
  const fuente = escapeHtml(props.fuente || '—');
  return `<div class="roads-popup"><table>${body}</table><div class="roads-popup-source">Fuente: ${fuente}</div></div>`;
}

// Estados del badge:
//   wfsStatus: 'ok' | 'down' | 'probing' | null
//   mode: 'primary' (WFS+local enriquecido) | 'mvt-by-zoom' (WFS ok pero estamos en zoom bajo)
//         | 'mvt-by-fallback' (WFS no responde, render desde local) | null
function setRoadsLabel({ wfsStatus = null, wfsLatency = null, wfsCheckedAt = null, mode = null } = {}) {
  if (!roadsSourceLabel) roadsSourceLabel = document.getElementById('roads-source-label');
  if (!roadsSourceLabel) return;
  roadsSourceLabel.classList.remove('is-ok', 'is-secondary', 'is-fallback', 'is-down', 'is-probing');
  if (!wfsStatus && !mode) {
    roadsSourceLabel.textContent = '';
    roadsSourceLabel.removeAttribute('title');
    return;
  }
  let badgeText, cls;
  if (wfsStatus === 'probing') {
    badgeText = 'probando…';
    cls = 'is-probing';
  } else if (mode === 'primary') {
    badgeText = 'WFS+local';
    cls = 'is-ok';
  } else if (mode === 'mvt-by-zoom') {
    badgeText = 'MVT local · zoom bajo';
    cls = 'is-secondary';
  } else if (mode === 'mvt-by-fallback') {
    badgeText = 'MVT local · WFS no responde';
    cls = 'is-fallback';
  } else if (wfsStatus === 'down') {
    badgeText = 'WFS no responde';
    cls = 'is-down';
  } else {
    badgeText = wfsStatus || '';
    cls = 'is-secondary';
  }
  roadsSourceLabel.classList.add(cls);
  roadsSourceLabel.textContent = badgeText;
  const wfsLine = 'WFS de transportes de IDEE: '
    + (wfsStatus === 'ok' ? 'responde' : wfsStatus === 'down' ? 'no responde' : wfsStatus || '—')
    + (wfsStatus === 'ok' && wfsLatency != null ? ` (${wfsLatency} ms)` : '');
  const tooltip = [
    wfsLine,
    wfsCheckedAt ? 'última prueba: ' + new Date(wfsCheckedAt).toLocaleTimeString() : null,
    mode === 'primary' ? 'Geometría del WFS, atributos de IGR-RT local (enriquecimiento por id_tramo).' : null,
    mode === 'mvt-by-zoom' ? 'Aunque el WFS responde, a este zoom el bbox es demasiado grande para el WFS; el visor sirve la teselación MVT derivada de IGR-RT local. Al acercar el zoom (z≥12), se vuelve a la ruta WFS+local.' : null,
    mode === 'mvt-by-fallback' ? 'El WFS no respondió o devolvió error; el visor está usando exclusivamente la copia local IGR-RT por resiliencia. Reintenta automáticamente cada minuto.' : null,
  ].filter(Boolean).join('\n');
  roadsSourceLabel.setAttribute('title', tooltip);
}

async function probeRoadsHealth(force = false) {
  const now = Date.now();
  if (!force && roadsHealthCache && now < roadsHealthCacheUntil) return roadsHealthCache;
  try {
    const r = await fetch(ROADS_HEALTH_URL, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    roadsHealthCache = await r.json();
  } catch (err) {
    roadsHealthCache = { status: 'down', error: String(err) };
  }
  roadsHealthCacheUntil = now + 20000;
  return roadsHealthCache;
}

function clearRoadsLayers() {
  if (roadsPrimaryLayer) {
    map.removeLayer(roadsPrimaryLayer);
    roadsPrimaryLayer = null;
  }
  if (roadsFallbackLayer) {
    map.removeLayer(roadsFallbackLayer);
    roadsFallbackLayer = null;
  }
}

function buildRoadsFallbackLayer() {
  ensureRoadsPane();
  const layerStyles = {
    [ROADS_MVT_LAYER_NAME]: properties => getRoadStyle(properties),
  };
  const layer = L.vectorGrid.protobuf(ROADS_TILE_URL, {
    rendererFactory: L.canvas.tile,
    pane: ROADS_PANE,
    interactive: true,
    minZoom: ROADS_TILE_MIN_ZOOM,
    maxNativeZoom: 18,
    vectorTileLayerStyles: layerStyles,
    getFeatureId: feature => feature.properties.core_feature_id,
  });
  layer.on('click', e => {
    const props = Object.assign({}, e.layer.properties || {});
    if (!props.fuente) props.fuente = 'IGR-RT local (fallback)';
    L.popup({ pane: ROADS_PANE })
      .setLatLng(e.latlng)
      .setContent(buildRoadsPopupContent(props))
      .openOn(map);
  });
  return layer;
}

async function loadRoadsPrimary() {
  if (!roadsVisible) return;
  if (map.getZoom() < ROADS_PRIMARY_MIN_ZOOM) {
    // Zoom bajo: la ruta primaria no es eficiente; usamos siempre la teselación MVT
    // (con filtro de clase escalonado server-side). Esto NO es un fallo del WFS,
    // es una decisión de diseño por el tamaño del bbox.
    activateRoadsFallback('mvt-by-zoom');
    return;
  }
  const bounds = map.getBounds();
  const bbox = [
    bounds.getWest().toFixed(5),
    bounds.getSouth().toFixed(5),
    bounds.getEast().toFixed(5),
    bounds.getNorth().toFixed(5),
  ].join(',');
  const zoom = map.getZoom();
  const token = ++roadsRequestToken;
  let payload;
  try {
    const url = `${ROADS_FEATURES_URL}?bbox=${encodeURIComponent(bbox)}&limit=${ROADS_FEATURE_LIMIT}&zoom=${zoom}`;
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    payload = await r.json();
  } catch (err) {
    if (token !== roadsRequestToken) return;
    console.warn('Roads primary failed, switching to fallback:', err);
    roadsHealthCache = { status: 'down', error: String(err), checked_at: new Date().toISOString() };
    roadsHealthCacheUntil = Date.now() + 20000;
    activateRoadsFallback('mvt-by-fallback');
    return;
  }
  if (token !== roadsRequestToken || !roadsVisible) return;
  const source = (payload.metadata && payload.metadata.source) || '';
  const latency = payload.metadata && payload.metadata.wfs_latency_ms;
  if (source.startsWith('IGR-RT local')) {
    // El backend ya cayó al modo local internamente: el WFS no respondió.
    roadsHealthCache = { status: 'down', checked_at: new Date().toISOString() };
    roadsHealthCacheUntil = Date.now() + 20000;
    activateRoadsFallback('mvt-by-fallback');
    return;
  }
  ensureRoadsPane();
  const newLayer = L.geoJSON(payload, {
    pane: ROADS_PANE,
    style: feature => getRoadStyle(feature.properties),
    onEachFeature: (feature, lyr) => {
      lyr.bindPopup(buildRoadsPopupContent(feature.properties), { pane: ROADS_PANE });
    },
  });
  if (roadsPrimaryLayer) map.removeLayer(roadsPrimaryLayer);
  if (roadsFallbackLayer) { map.removeLayer(roadsFallbackLayer); roadsFallbackLayer = null; }
  roadsPrimaryLayer = newLayer.addTo(map);
  if (typeof latency === 'number') {
    roadsHealthCache = { status: 'ok', latency_ms: latency, checked_at: new Date().toISOString() };
    roadsHealthCacheUntil = Date.now() + 20000;
  }
  setRoadsLabel({
    wfsStatus: 'ok',
    wfsLatency: typeof latency === 'number' ? latency : (roadsHealthCache && roadsHealthCache.latency_ms),
    wfsCheckedAt: roadsHealthCache && roadsHealthCache.checked_at,
    mode: 'primary',
  });
}

function activateRoadsFallback(reason = 'mvt-by-fallback') {
  if (!roadsVisible) return;
  if (roadsPrimaryLayer) { map.removeLayer(roadsPrimaryLayer); roadsPrimaryLayer = null; }
  if (!roadsFallbackLayer) {
    roadsFallbackLayer = buildRoadsFallbackLayer();
    roadsFallbackLayer.addTo(map);
  }
  const h = roadsHealthCache || {};
  setRoadsLabel({
    wfsStatus: h.status || null,
    wfsLatency: h.latency_ms,
    wfsCheckedAt: h.checked_at,
    mode: reason,
  });
}

function scheduleRoadsRefresh() {
  if (!roadsVisible) return;
  if (roadsRefreshHandle) clearTimeout(roadsRefreshHandle);
  roadsRefreshHandle = setTimeout(() => {
    roadsRefreshHandle = null;
    if (roadsFallbackLayer) return;
    void loadRoadsPrimary();
  }, ROADS_MOVE_DEBOUNCE_MS);
}

async function refreshRoadsHealthAndRecover() {
  if (!roadsVisible) return;
  const prev = roadsHealthCache && roadsHealthCache.status;
  const h = await probeRoadsHealth(true);
  if (!roadsVisible) return;
  const currentMode = roadsPrimaryLayer
    ? 'primary'
    : (map.getZoom() < ROADS_PRIMARY_MIN_ZOOM
        ? (h.status === 'ok' ? 'mvt-by-zoom' : 'mvt-by-fallback')
        : (h.status === 'ok' ? 'mvt-by-fallback' : 'mvt-by-fallback'));
  setRoadsLabel({
    wfsStatus: h.status,
    wfsLatency: h.latency_ms,
    wfsCheckedAt: h.checked_at,
    mode: currentMode,
  });
  // Si el WFS ha vuelto y estamos en fallback a zoom alto, recuperamos la ruta primaria.
  if (prev !== 'ok' && h.status === 'ok'
      && !roadsPrimaryLayer
      && map.getZoom() >= ROADS_PRIMARY_MIN_ZOOM) {
    void loadRoadsPrimary();
  }
}

async function toggleRoads(enabled) {
  roadsVisible = enabled;
  if (!enabled) {
    if (roadsRefreshHandle) { clearTimeout(roadsRefreshHandle); roadsRefreshHandle = null; }
    if (roadsHealthReprobeHandle) { clearInterval(roadsHealthReprobeHandle); roadsHealthReprobeHandle = null; }
    clearRoadsLayers();
    setRoadsLabel({});
    return;
  }
  // Probamos SIEMPRE primero el WFS para que el usuario vea que la fuente primaria
  // se ha contactado, independientemente del modo de render que se acabe usando.
  setRoadsLabel({ wfsStatus: 'probing' });
  const health = await probeRoadsHealth(true);
  if (!roadsVisible) return;
  if (roadsHealthReprobeHandle) clearInterval(roadsHealthReprobeHandle);
  roadsHealthReprobeHandle = setInterval(() => { void refreshRoadsHealthAndRecover(); }, ROADS_HEALTH_REPROBE_MS);
  if (map.getZoom() < ROADS_PRIMARY_MIN_ZOOM) {
    activateRoadsFallback(health.status === 'ok' ? 'mvt-by-zoom' : 'mvt-by-fallback');
    return;
  }
  if (health.status === 'ok') {
    await loadRoadsPrimary();
  } else {
    activateRoadsFallback('mvt-by-fallback');
  }
}

map.on('moveend', () => {
  if (!roadsVisible) return;
  // Si cruzamos el umbral hacia zoom alto y estamos en fallback MVT, intentamos pasar a primaria.
  if (map.getZoom() >= ROADS_PRIMARY_MIN_ZOOM && roadsFallbackLayer && !roadsPrimaryLayer) {
    scheduleRoadsRefresh();
    return;
  }
  // Si cruzamos hacia zoom bajo y estamos en primaria, conmutamos a MVT (fallback).
  if (map.getZoom() < ROADS_PRIMARY_MIN_ZOOM && roadsPrimaryLayer) {
    activateRoadsFallback();
    return;
  }
  // En primaria, recargamos por bbox con debounce.
  if (roadsFallbackLayer) return;
  scheduleRoadsRefresh();
});

const chkRoads = document.getElementById('chk-roads');
if (chkRoads) {
  chkRoads.addEventListener('change', e => { void toggleRoads(e.target.checked); });
}

init();
