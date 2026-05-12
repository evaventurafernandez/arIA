// ============================================================================
// Chat LLM (Fase 2): panel flotante + window.chatTools + clase ChatClient.
// El panel envia mensajes a POST /api/chat, renderiza los 4 bloques y ejecuta
// las client_actions devueltas (flyTo / toggleLayer / setFilter / getFeatureDetail).
//
// Depende de app.js (acceso a `map`, `zoomToAlert`, los checkboxes del sidebar
// y los botones de filtro de nivel).
// ============================================================================

// Mapeo de nombres logicos de capa -> id de checkbox del sidebar.
// Disparar `change` sobre el checkbox preserva la coherencia con los handlers
// existentes (toggleWMS, toggleNucleos, toggleBurntAreaLayer, etc.).
const CHAT_LAYER_CHECKBOX = {
  alerts: 'chk-alerts',
  fires: 'chk-fires',
  firms_history: 'chk-firms_history',
  aemet_max_temp_history: 'chk-aemet_max_temp_history',
  burnt_area: 'chk-burnt_area_daily',
  nucleos: 'chk-nucleos_poblacion',
  flood: 'chk-flood',
  corine_wms: 'chk-corine_wms',
};

function chatToolFlyTo(args) {
  args = args || {};
  if (Array.isArray(args.bbox) && args.bbox.length === 4) {
    const minLon = Number(args.bbox[0]);
    const minLat = Number(args.bbox[1]);
    const maxLon = Number(args.bbox[2]);
    const maxLat = Number(args.bbox[3]);
    if ([minLon, minLat, maxLon, maxLat].every(Number.isFinite)) {
      map.fitBounds(
        L.latLngBounds([[minLat, minLon], [maxLat, maxLon]]),
        { padding: [40, 40] }
      );
      return true;
    }
  }
  if (args.coords && Number.isFinite(args.coords.lat) && Number.isFinite(args.coords.lon)) {
    const zoom = Number.isFinite(args.coords.zoom) ? args.coords.zoom : 9;
    map.setView([args.coords.lat, args.coords.lon], zoom);
    return true;
  }
  return false;
}

function chatToolToggleLayer(args) {
  args = args || {};
  const checkboxId = CHAT_LAYER_CHECKBOX[args.name];
  if (!checkboxId) return false;
  const cb = document.getElementById(checkboxId);
  if (!cb) return false;
  const target = Boolean(args.on);
  if (cb.checked === target) return true;
  cb.checked = target;
  cb.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
}

function chatToolSetFilter(args) {
  args = args || {};
  if (args.field === 'level' && Array.isArray(args.value)) {
    const noneBtn = document.querySelector('#level-filters .fbtn.none');
    if (noneBtn) noneBtn.click();
    args.value.forEach(function (level) {
      const btn = document.querySelector('#level-filters .fbtn[data-level="' + level + '"]');
      if (btn) btn.click();
    });
    return true;
  }
  if (args.field === 'event_type') {
    const select = document.getElementById('event-select');
    if (!select) return false;
    select.value = String(args.value);
    select.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }
  return false;
}

function chatToolGetFeatureDetail(args) {
  args = args || {};
  if (args.layer === 'alerts' && args.id) {
    if (typeof zoomToAlert === 'function') zoomToAlert(args.id);
    return true;
  }
  return false;
}

window.chatTools = {
  flyTo: chatToolFlyTo,
  toggleLayer: chatToolToggleLayer,
  setFilter: chatToolSetFilter,
  getFeatureDetail: chatToolGetFeatureDetail,
};

// ----- Render minimal de texto a HTML (escape + negrita + saltos) -----

function chatEscapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function chatFormatText(s) {
  if (!s) return '';
  return chatEscapeHtml(s).replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
}

class ChatClient {
  constructor(opts) {
    this.messagesEl = opts.messagesEl;
    this.formEl = opts.formEl;
    this.inputEl = opts.inputEl;
    this.sendBtn = opts.sendBtn;
    this.statusEl = opts.statusEl;
    this.history = [];
    this.sending = false;

    const self = this;
    this.formEl.addEventListener('submit', function (ev) {
      ev.preventDefault();
      self.send();
    });
    this.inputEl.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' && !ev.shiftKey) {
        ev.preventDefault();
        self.send();
      }
    });
  }

  appendMessage(role, html, extraClass) {
    const div = document.createElement('div');
    div.className = 'chat-msg chat-msg-' + role + (extraClass ? ' ' + extraClass : '');
    div.innerHTML = html;
    this.messagesEl.appendChild(div);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    return div;
  }

  setStatus(text) {
    this.statusEl.textContent = text || '';
  }

  setSending(flag) {
    this.sending = flag;
    this.sendBtn.disabled = flag;
    this.inputEl.disabled = flag;
  }

  renderAssistant(reply) {
    const blocks = (reply && reply.blocks) || {};
    const trace = (reply && reply.trace) || [];
    const clientActions = (reply && reply.client_actions) || [];

    const blockTitles = [
      ['interpretacion', 'Consulta interpretada'],
      ['operaciones', 'Operaciones'],
      ['resultados', 'Resultados'],
      ['interpretacion_emergencia', 'Interpretacion para emergencias'],
    ];
    const parts = [];
    blockTitles.forEach(function (entry) {
      const key = entry[0];
      const label = entry[1];
      const val = blocks[key];
      if (!val) return;
      parts.push(
        '<div class="chat-block">' +
          '<div class="chat-block-title">' + chatEscapeHtml(label) + '</div>' +
          '<div class="chat-block-body">' + chatFormatText(val) + '</div>' +
        '</div>'
      );
    });

    if (trace.length) {
      const entries = trace.map(function (t) {
        const cls = t.ok ? '' : ' failed';
        const args = JSON.stringify(t.arguments == null ? {} : t.arguments);
        const summary = t.ok
          ? chatEscapeHtml(t.result_summary || '')
          : chatEscapeHtml(t.error || 'error');
        return '<div class="chat-trace-entry' + cls + '">' +
                 '<div><strong>' + chatEscapeHtml(t.tool) + '</strong>(' + chatEscapeHtml(args) + ')</div>' +
                 '<div>' + summary + '</div>' +
               '</div>';
      }).join('');
      parts.push(
        '<details class="chat-trace">' +
          '<summary>Acciones realizadas (' + trace.length + ')</summary>' +
          entries +
        '</details>'
      );
    }

    if (parts.length === 0) {
      parts.push('<div class="chat-block-body">' + chatFormatText((reply && reply.text) || '(respuesta vacia)') + '</div>');
    }

    if (clientActions.length) {
      const summary = clientActions.map(function (ca) {
        return chatEscapeHtml(ca.action + '(' + JSON.stringify(ca.arguments) + ')');
      }).join('<br>');
      parts.push('<div class="chat-trace-entry">Aplicado al mapa:<br>' + summary + '</div>');
    }

    this.appendMessage('assistant', parts.join(''));
  }

  executeClientActions(actions) {
    if (!Array.isArray(actions) || actions.length === 0) return;
    actions.forEach(function (ca) {
      const handler = window.chatTools[ca.action];
      if (typeof handler === 'function') {
        try { handler(ca.arguments || {}); }
        catch (err) { console.error('chatTool failed', ca, err); }
      } else {
        console.warn('chatTool desconocida', ca);
      }
    });
  }

  async send() {
    if (this.sending) return;
    const text = (this.inputEl.value || '').trim();
    if (!text) return;

    this.appendMessage('user', chatFormatText(text));
    this.history.push({ role: 'user', content: text });
    this.inputEl.value = '';
    this.setSending(true);
    this.setStatus('Enviando...');

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ messages: this.history }),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error('HTTP ' + resp.status + ': ' + detail.slice(0, 200));
      }
      const body = await resp.json();
      const reply = body.reply || {};
      this.renderAssistant(reply);
      this.executeClientActions(reply.client_actions || []);
      if (reply.text) {
        this.history.push({ role: 'assistant', content: reply.text });
      }
      this.setStatus('');
    } catch (err) {
      this.appendMessage('error', chatEscapeHtml('Error: ' + (err.message || err)));
      this.setStatus('Error en la peticion');
    } finally {
      this.setSending(false);
      this.inputEl.focus();
    }
  }
}

(function initChat() {
  const fab = document.getElementById('chat-fab');
  const panel = document.getElementById('chat-panel');
  const closeBtn = document.getElementById('chat-panel-close');
  if (!fab || !panel) return;

  const client = new ChatClient({
    messagesEl: document.getElementById('chat-messages'),
    formEl: document.getElementById('chat-form'),
    inputEl: document.getElementById('chat-input'),
    sendBtn: document.getElementById('chat-send'),
    statusEl: document.getElementById('chat-status'),
  });

  client.appendMessage(
    'system',
    'Pregunta por avisos AEMET, focos FIRMS o areas quemadas, o pide acciones sobre el mapa (centrar, activar capas, filtrar).'
  );

  fab.addEventListener('click', function () {
    panel.hidden = false;
    fab.hidden = true;
    client.inputEl.focus();
  });
  closeBtn.addEventListener('click', function () {
    panel.hidden = true;
    fab.hidden = false;
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && !panel.hidden) {
      panel.hidden = true;
      fab.hidden = false;
    }
  });

  window.chatClient = client;
})();
