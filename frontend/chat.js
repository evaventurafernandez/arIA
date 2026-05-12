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

  startAssistantMessage() {
    const div = this.appendMessage('assistant', '');
    div.innerHTML =
      '<div class="chat-block chat-block-streaming">' +
        '<div class="chat-block-title">Procesando consulta...</div>' +
        '<div class="chat-block-body" data-streaming-body></div>' +
      '</div>' +
      '<details class="chat-trace" data-streaming-trace hidden>' +
        '<summary>Acciones realizadas (<span data-trace-count>0</span>)</summary>' +
        '<div data-trace-entries></div>' +
      '</details>' +
      '<div data-final-blocks></div>' +
      '<div data-client-actions hidden></div>';
    return {
      root: div,
      streamingBody: div.querySelector('[data-streaming-body]'),
      streamingBlock: div.querySelector('.chat-block-streaming'),
      trace: div.querySelector('[data-streaming-trace]'),
      traceEntries: div.querySelector('[data-trace-entries]'),
      traceCount: div.querySelector('[data-trace-count]'),
      finalBlocks: div.querySelector('[data-final-blocks]'),
      clientActions: div.querySelector('[data-client-actions]'),
      streamBuffer: '',
      blocksRendered: {},
      traceItems: 0,
    };
  }

  appendToken(uiState, text) {
    if (!uiState.streamingBlock) return;
    uiState.streamBuffer += text;
    uiState.streamingBody.textContent = uiState.streamBuffer;
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  addTraceEntry(uiState, tool, args, status, summary) {
    if (!uiState.trace) return;
    uiState.trace.hidden = false;
    uiState.traceItems += 1;
    uiState.traceCount.textContent = String(uiState.traceItems);
    const cls = status === 'ok' ? '' : (status === 'pending' ? '' : ' failed');
    const div = document.createElement('div');
    div.className = 'chat-trace-entry' + cls;
    div.innerHTML =
      '<div><strong>' + chatEscapeHtml(tool) + '</strong>(' +
        chatEscapeHtml(JSON.stringify(args || {})) + ')</div>' +
      '<div>' + chatEscapeHtml(summary || '') + '</div>';
    uiState.traceEntries.appendChild(div);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    return div;
  }

  renderFinalBlock(uiState, key, content) {
    const labels = {
      interpretacion: 'Consulta interpretada',
      operaciones: 'Operaciones',
      resultados: 'Resultados',
      interpretacion_emergencia: 'Interpretacion para emergencias',
    };
    if (uiState.blocksRendered[key]) return;
    uiState.blocksRendered[key] = true;
    const div = document.createElement('div');
    div.className = 'chat-block';
    div.innerHTML =
      '<div class="chat-block-title">' + chatEscapeHtml(labels[key] || key) + '</div>' +
      '<div class="chat-block-body">' + chatFormatText(content) + '</div>';
    uiState.finalBlocks.appendChild(div);
    // Limpiar el bloque "Generando..." la primera vez que llega un bloque final.
    if (uiState.streamingBlock && !uiState.streamingBlock._cleared) {
      uiState.streamingBlock._cleared = true;
      uiState.streamingBlock.style.display = 'none';
    }
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  renderClientActionsSummary(uiState, actions) {
    if (!actions.length) return;
    uiState.clientActions.hidden = false;
    const summary = actions.map(function (ca) {
      return chatEscapeHtml(ca.action + '(' + JSON.stringify(ca.arguments) + ')');
    }).join('<br>');
    uiState.clientActions.className = 'chat-trace-entry';
    uiState.clientActions.innerHTML = 'Aplicado al mapa:<br>' + summary;
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

    const uiState = this.startAssistantMessage();
    const pendingClientActions = [];
    const traceById = {};

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ messages: this.history }),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error('HTTP ' + resp.status + ': ' + detail.slice(0, 200));
      }
      if (!resp.body) {
        throw new Error('Respuesta sin body de stream.');
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      // Procesa una pieza SSE: bloques separados por linea en blanco doble.
      const processChunk = (chunk) => {
        const events = chunk.split(/\n\n/);
        for (const ev of events) {
          if (!ev.trim()) continue;
          let evType = 'message';
          let data = '';
          for (const line of ev.split(/\n/)) {
            if (line.startsWith('event:')) evType = line.slice(6).trim();
            else if (line.startsWith('data:')) data += line.slice(5).trim();
          }
          if (!data) continue;
          let payload;
          try { payload = JSON.parse(data); } catch (_) { continue; }
          this.handleStreamEvent(evType, payload, uiState, pendingClientActions, traceById);
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // Cada vez que tengamos al menos un evento completo (doble salto), procesar.
        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const piece = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          processChunk(piece);
        }
      }
      // flush final
      if (buffer.trim()) processChunk(buffer);

      this.setStatus('');
      // Ejecutar las acciones de cliente al final.
      this.executeClientActions(pendingClientActions);
      this.renderClientActionsSummary(uiState, pendingClientActions);
      // Anadir al historial el texto final acumulado.
      if (uiState.streamBuffer) {
        this.history.push({ role: 'assistant', content: uiState.streamBuffer });
      }
    } catch (err) {
      this.appendMessage('error', chatEscapeHtml('Error: ' + (err.message || err)));
      this.setStatus('Error en la peticion');
    } finally {
      this.setSending(false);
      this.inputEl.focus();
    }
  }

  handleStreamEvent(evType, payload, uiState, pendingClientActions, traceById) {
    if (evType === 'token') {
      this.appendToken(uiState, payload.text || '');
    } else if (evType === 'tool_call_start') {
      const div = this.addTraceEntry(
        uiState, payload.tool, payload.arguments, 'pending', '...'
      );
      if (payload.id) traceById[payload.id] = div;
    } else if (evType === 'tool_call_done') {
      const div = traceById[payload.id];
      const status = payload.ok ? 'ok' : 'failed';
      const summary = payload.ok ? (payload.result_summary || 'OK') : (payload.error || 'error');
      if (div) {
        div.classList.remove('failed');
        if (!payload.ok) div.classList.add('failed');
        const bodies = div.querySelectorAll('div');
        if (bodies.length >= 2) bodies[1].textContent = summary;
      } else {
        this.addTraceEntry(uiState, payload.tool, {}, status, summary);
      }
    } else if (evType === 'client_action') {
      pendingClientActions.push({
        id: payload.id,
        action: payload.action,
        arguments: payload.arguments || {},
      });
    } else if (evType === 'final_block') {
      this.renderFinalBlock(uiState, payload.key, payload.content);
    } else if (evType === 'done') {
      if (payload.truncated) {
        this.appendMessage('system', 'Se alcanzo el tope de iteraciones del orquestador.');
      }
      // El bloque "Generando..." se oculta solo cuando llega un final_block.
      // Si solo hay tokens sin bloques (caso de rechazo), lo dejamos visible
      // pero con el texto streaming acumulado.
    } else if (evType === 'error') {
      this.appendMessage('error', chatEscapeHtml('Error del backend: ' + (payload.message || '')));
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
