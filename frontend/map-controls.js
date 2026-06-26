/* Botones flotantes sobre el mapa (Nucleos / Carreteras).
   Conmutan exactamente las mismas capas que sus checkboxes del sidebar y
   reflejan su estado activo. No tocan la logica de app.js: se limitan a
   disparar el evento 'change' del checkbox correspondiente, que es donde
   app.js engancha toggleNucleos / toggleRoads. Asi ambos controles
   (sidebar y mapa) quedan siempre sincronizados. */
(function () {
  function wire(btnId, checkboxId) {
    var btn = document.getElementById(btnId);
    var chk = document.getElementById(checkboxId);
    if (!btn || !chk) return;
    function sync() {
      var on = chk.checked;
      btn.classList.toggle('is-active', on);
      btn.setAttribute('aria-pressed', String(on));
    }
    btn.addEventListener('click', function () { chk.click(); });
    chk.addEventListener('change', sync);
    sync();
  }
  wire('mapctrl-nucleos', 'chk-nucleos_poblacion');
  wire('mapctrl-roads', 'chk-roads');

  // Panel flotante de fichas de detalle: colapsar / expandir
  var panel = document.getElementById('detail-panel');
  var toggle = document.getElementById('detail-panel-toggle');
  if (panel && toggle) {
    toggle.addEventListener('click', function () {
      var collapsed = panel.classList.toggle('is-collapsed');
      toggle.setAttribute('aria-expanded', String(!collapsed));
    });
  }

  // Leyenda: plegado general del panel
  var legendPanel = document.getElementById('legend-panel');
  var legendToggle = document.getElementById('legend-toggle');
  if (legendPanel && legendToggle) {
    legendToggle.addEventListener('click', function () {
      var collapsed = legendPanel.classList.toggle('is-collapsed');
      legendToggle.setAttribute('aria-expanded', String(!collapsed));
    });
  }

  // Leyenda: cada capa (bloque) plegable. app.js reescribe #wms-legend en cada
  // actualizacion, asi que reconectamos los titulos con un MutationObserver.
  var legendBody = document.getElementById('wms-legend');
  if (legendBody) {
    var wireLegendBlocks = function () {
      var titles = legendBody.querySelectorAll('.leg-block > .leg-title');
      for (var i = 0; i < titles.length; i++) {
        if (titles[i].dataset.collapsibleWired) continue;
        titles[i].dataset.collapsibleWired = '1';
        titles[i].addEventListener('click', function () {
          this.parentNode.classList.toggle('is-collapsed');
        });
      }
    };
    new MutationObserver(wireLegendBlocks).observe(legendBody, { childList: true });
    wireLegendBlocks();
  }
})();
