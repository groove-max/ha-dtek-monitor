import { outageText } from "./outage-card-text.js?v=2.0.0-rc4";
import { validateGrid, gridIntervals, slotLabel, endLabel, callGridWS } from "./schedule-grid-data.js?v=2.0.0-rc4";
import "./outage-card-editor.js?v=2.0.0-rc4";
/* DTEK compact outage card. Uses verified schedule_grid data from DTEK Monitor. */

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const stamp = (value, language) => {
    const d = new Date(value);
    return Number.isFinite(d.getTime()) ? new Intl.DateTimeFormat(language === 'uk' || language === 'ru' ? 'uk-UA' : 'en-GB', { timeZone: 'Europe/Kyiv', hour: '2-digit', minute: '2-digit' }).format(d) : '—';
  };
  const style = `
    :host{display:block;min-width:0;container-type:inline-size}*{box-sizing:border-box}
    ha-card{display:block;color:var(--primary-text-color,#e9f0f7);background:var(--ha-card-background,var(--card-background-color,#18212b));border:1px solid var(--divider-color,#303b48);border-radius:22px;padding:20px;font:14px/1.4 system-ui;overflow:hidden;--green:#58d8ae;--amber:#ffb95b;--muted:var(--secondary-text-color,#98a6b6)}
    .head,.status,.tools,.foot{display:flex;align-items:center;justify-content:space-between;gap:12px}.brand{font-size:10px;letter-spacing:1.8px;color:var(--muted)}h2{font-size:19px;margin:3px 0 0;font-weight:650}button,select{font:inherit;color:inherit;background:transparent;border:1px solid var(--divider-color,#303b48);border-radius:10px;min-height:38px;padding:7px 11px;cursor:pointer;max-width:100%}button:focus-visible,select:focus-visible{outline:2px solid #7abaff;outline-offset:2px}button:disabled{opacity:.5;cursor:wait}.refresh{font-size:20px;line-height:1;width:40px;flex-shrink:0}.status{justify-content:flex-start;border-radius:13px;padding:12px;margin:16px 0;background:color-mix(in srgb,var(--tone) 9%,transparent)}.dot{width:9px;height:9px;border-radius:50%;background:var(--tone);flex-shrink:0}.status strong{font-size:15px;color:var(--tone);overflow-wrap:anywhere}.sub{color:var(--muted);font-size:11px;margin-top:3px}.tools{margin:0 0 14px;flex-wrap:wrap}.tabs{display:flex;gap:4px}.tabs button{font-size:12px;padding:7px 12px}.tabs button.active{background:#7abaff1c;border-color:#7abaff77;color:#91c9ff}select{font-size:12px;min-width:100px;flex:1;max-width:180px}.feedback{font-size:12px;color:var(--amber);line-height:1.5;margin:10px 0}.feedback:empty{display:none}.hours{display:flex;justify-content:space-between;font-size:10px;color:var(--muted);margin:8px 0 5px;font-variant-numeric:tabular-nums}.track{display:flex;gap:2px;height:25px}.cell{flex:1;min-width:0;border-radius:3px;background:#364553}.cell.outage,.key.outage{background:var(--amber)}.cell.possible,.key.possible{background:repeating-linear-gradient(135deg,#efcc91 0 4px,#907755 4px 6px)}.cell.clear,.key.clear{background:#58d8ae40}.cell.forecast,.key.forecast{background:repeating-linear-gradient(135deg,#a798ee 0 4px,#625a8a 4px 6px)}.cell.forecast_clear{background:#a798ee33}.cell.unknown,.key.unknown{background:repeating-linear-gradient(135deg,#44505e 0 4px,#28323e 4px 6px)}.legend{display:flex;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:10px;margin:12px 0 16px}.legend span{display:flex;align-items:center;gap:5px}.key{display:inline-block;width:8px;height:8px;border-radius:2px}.intervals{max-height:155px;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin}.interval{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid var(--divider-color,#303b48);padding:9px 0;font-size:12px}.interval b{font-variant-numeric:tabular-nums;overflow-wrap:anywhere;text-align:right;font-weight:600}.interval span{color:var(--muted)}.foot{font-size:10px;align-items:flex-start;color:var(--muted);margin-top:13px;border-top:1px solid var(--divider-color,#303b48);padding-top:12px}.foot span:last-child{white-space:nowrap}.empty{font-size:12px;color:var(--muted);padding:10px 0}.restoration{font-size:11px;color:var(--amber);margin:-7px 0 14px}
    .head>div{min-width:0}h2{overflow-wrap:anywhere}button,select{min-height:44px}select{max-width:230px}.key.forecast_clear{background:#a798ee66}[hidden]{display:none!important}
    @container(max-width:420px){.tools select{flex-basis:100%;max-width:none}}
    @container(max-width:350px){ha-card{padding:15px}.status strong{font-size:13px}h2{font-size:17px}.tools{gap:8px}.foot{flex-wrap:wrap}}
  `;
  class DtekOutageCard extends HTMLElement {
    constructor() { super(); this.attachShadow({ mode: 'open' }); this._seq = 0; this._day = 0; this._group = ''; }
    static getConfigElement() { return document.createElement('dtek-outage-card-editor'); }
    static getStubConfig() { return {}; }
    get t() { return outageText(this._hass?.language); }
    setConfig(config) {
      for (const key of ['entity', 'status_entity', 'updated_entity', 'title', 'group']) if (config[key] !== undefined && typeof config[key] !== 'string') throw new Error(`${key} must be a string`);
      if (config.entity !== this._config?.entity || config.status_entity !== this._config?.status_entity) { this._group = ''; this._day = 0; }
      this._config = { ...config }; this._data = null; this._key = null; this._seq++; this._busy = false; this._render();
      if (this.isConnected && this._hass) this._load();
    }
    set hass(value) {
      const key = JSON.stringify([value.states[this._config?.status_entity], value.user?.id]);
      const contextChanged = value.user?.id !== this._hass?.user?.id || value.connection !== this._hass?.connection;
      const changed = key !== this._key || contextChanged;
      if (contextChanged || (changed && this._busy)) { this._seq++; this._busy = false; this._data = null; this._error = ''; }
      if (contextChanged) this._group = '';
      this._hass = value; this._key = key; this._render();
      if (changed && this.isConnected && this._config) this._load();
    }
    connectedCallback() { this._render(); if (this._hass && this._config) this._load(); this._timer = setInterval(() => this._load(), 60000); }
    disconnectedCallback() { clearInterval(this._timer); this._seq++; this._busy = false; }
    getCardSize() { return 6; }
    getGridOptions() { return { columns: 12, min_columns: 6 }; }
    async _load(refresh = false) {
      if (!this._config?.status_entity || !this._hass || !this.isConnected || this._busy) return;
      const seq = ++this._seq;
      const hass = this._hass, entity = this._config.status_entity, user = hass.user?.id, connection = hass.connection;
      const current = () => seq === this._seq && this.isConnected && entity === this._config?.status_entity && user === this._hass?.user?.id && connection === this._hass?.connection;
      this._busy = true; this._error = ''; this._render();
      try {
        if (refresh) {
          await callGridWS(hass,{ type: 'dtek_monitor/schedule_refresh', entity_id: entity });
          if (!current()) return;
        }
        const data = await callGridWS(hass,{ type: 'dtek_monitor/schedule_grid', entity_id: entity });
        if (!current()) return;
        validateGrid(data);
        this._data = data;
      } catch (error) {
        if (!current()) return;
        this._data = null;
        this._error = error?.code === 'schedule_refresh_cooldown' ? 'cooldown' : error?.code === 'unauthorized' ? 'denied' : 'error';
      } finally { if (current()) { this._busy = false; this._render(); } }
    }
    _patch(markup) {
      if (!this.shadowRoot.querySelector('ha-card')) { this.shadowRoot.innerHTML = markup; return; }
      const template = document.createElement('template');
      template.innerHTML = markup;
      const next = template.content;
      this.shadowRoot.querySelector('ha-card').setAttribute('style', next.querySelector('ha-card').getAttribute('style'));
      for (const selector of ['.brand', '.sub', 'h2', '.status strong', '.restoration', '.feedback', '.timeline', '.legend', '.intervals', '.foot']) {
        const target = this.shadowRoot.querySelector(selector), source = next.querySelector(selector);
        if (target.innerHTML !== source.innerHTML) target.innerHTML = source.innerHTML;
        target.hidden = source.hidden;
        if (source.hasAttribute('aria-label')) target.setAttribute('aria-label', source.getAttribute('aria-label'));
      }
      this.shadowRoot.querySelector('.refresh').disabled = this._busy || !this._config.status_entity;
      this.shadowRoot.querySelector('.refresh').setAttribute('aria-label',this.t.refresh);
      for (const button of this.shadowRoot.querySelectorAll('[data-day]')) {
        button.textContent = Number(button.dataset.day) === 0 ? this.t.today : this.t.tomorrow;
        const active = Number(button.dataset.day) === this._day;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
      }
      const select = this.shadowRoot.querySelector('select'), options = next.querySelector('select');
      select.setAttribute('aria-label',this.t.group);
      const selectedValue = options.value;
      // Keep both the select and its option nodes when the available groups are unchanged.
      const key = JSON.stringify([...options.options].map((option) => [option.value, option.text, option.disabled]));
      if (key !== this._optionsKey) {
        const oldKey = JSON.stringify([...select.options].map((option) => [option.value, option.text, option.disabled]));
        if (key !== oldKey) select.replaceChildren(...options.children);
        this._optionsKey = key;
      }
      if (select.value !== selectedValue) select.value = selectedValue;
    }
    _render() {
      if (!this._config || !this._hass) return;
      const t = this.t, names = t.types;
      const c = this._config, power = this._hass.states[c.entity];
      const known = ['on', 'off'].includes(power?.state), on = power?.state === 'on';
      const tone = !known ? '#98a6b6' : on ? '#58d8ae' : '#ffb95b';
      const label = !known ? t.unavailable : on ? t.clearNow : t[power.attributes?.outage_type] || t.outageReported;
      const day = this._data?.days[this._day];
      const rows = day?.rows || [];
      const home = rows.filter((r) => r.home || r.selected);
      // Never guess a home's group from an unrelated operator row.
      const row = rows.find((r) => r.id === this._group) || rows.find((r) => r.id === c.group) || home.find((r) => r.selected) || home[0];
      const notice = !c.status_entity ? t.setup : this._error ? t[this._error] : this._busy ? t.checking : this._data?.status !== 'ready' ? (t[this._data?.status] || t.missing) : !row ? t.noGroup : row.cells.includes('unknown') ? t.unknownHours : row.cells.some(kind => kind.startsWith('forecast')) ? t.forecastHours : '';
      let timeline = '', intervals = '';
      if (row && this._data?.status === 'ready') {
        const split = day.slots.findIndex((slot) => slot.label === '12:00');
        const cut = split > 0 ? split : Math.ceil(day.slots.length / 2);
        timeline = [[0, cut], [cut, day.slots.length]].map(([a, b]) => `<div class="hours"><span>${esc(day.slots[a]?.label)}</span><span>${a === 0 ? '06:00' : '18:00'}</span><span>${b === day.slots.length ? '24:00' : '12:00'}</span></div><div class="track">${row.cells.slice(a, b).map((kind, n) => { const slot = day.slots[a + n]; return `<div class="cell ${kind}" title="${esc(slot.label)} UTC${esc(slot.offset)} · ${esc(names[kind])}" role="img" aria-label="${esc(slot.label)} UTC${esc(slot.offset)}: ${esc(names[kind])}"></div>`; }).join('')}</div>`).join('');
        const merged = gridIntervals(day,row,true);
        const dst = new Set(day.slots.map((slot) => slot.offset)).size > 1;
        intervals = merged.filter((part) => part.kind !== 'clear').map((part) => {
          const startLabel = slotLabel(day,part.start,dst), finishLabel = endLabel(day,part.end,dst);
          return `<div class="interval"><span>${esc(names[part.kind])}</span><b>${esc(startLabel)}–${esc(finishLabel)}</b></div>`;
        }).join('') || `<div class="empty">${esc(t.empty)}</div>`;
      }
      const updated = this._data?.source_updated_at || this._hass.states[c.updated_entity]?.state;
      const markup = `<style>${style}</style><ha-card style="--tone:${tone}"><div class="head"><div><div class="brand">${esc(t.brand)}</div><h2>${esc(c.title || this._data?.address || t.title)}</h2></div><button class="refresh" aria-label="${esc(t.refresh)}" ${this._busy || !c.status_entity ? 'disabled' : ''}>↻</button></div><div class="status"><i class="dot"></i><div><strong>${esc(label)}</strong><div class="sub">${esc(t.operator)}</div></div></div><div class="restoration" ${known && !on && power.attributes?.outage_end ? '' : 'hidden'}>${known && !on && power.attributes?.outage_end ? esc(t.restoration) + ': ' + esc(stamp(power.attributes.outage_end,this._hass.language)) : ''}</div><div class="tools"><div class="tabs"><button data-day="0" class="${this._day === 0 ? 'active' : ''}" aria-pressed="${this._day === 0}">${esc(t.today)}</button><button data-day="1" class="${this._day === 1 ? 'active' : ''}" aria-pressed="${this._day === 1}">${esc(t.tomorrow)}</button></div><select aria-label="${esc(t.group)}"><option value="" disabled ${!row ? 'selected' : ''}>${esc(t.choose)}</option>${rows.map((r) => `<option value="${esc(r.id)}" ${r.id === row?.id ? 'selected' : ''}>${esc(r.label)}${r.home ? ' · ' + esc(t.home) : ''}</option>`).join('')}</select></div><div class="feedback" role="status">${esc(notice)}</div><div class="timeline" aria-label="${esc(day?.date || '')} · ${esc(t.schedule)}">${timeline}</div><div class="legend">${[...new Set(timeline ? row.cells : [])].map((kind) => `<span><i class="key ${kind}"></i>${esc(names[kind])}</span>`).join('')}</div><div class="intervals" tabindex="0" aria-label="${esc(t.intervals)}">${intervals}</div><div class="foot"><span>${esc(t.note)}<br>${esc(t.time)}${day ? ' · ' + esc(day.date) : ''}</span><span>${esc(t.updated)} ${esc(stamp(updated,this._hass.language))}</span></div></ha-card>`;
      this._patch(markup);
      this.shadowRoot.querySelector('.refresh').onclick = () => this._load(true);
      this.shadowRoot.querySelectorAll('[data-day]').forEach((button) => { button.onclick = () => { this._day = Number(button.dataset.day); this._render(); }; });
      this.shadowRoot.querySelector('select').onchange = (event) => { this._group = event.target.value; this._render(); };
    }
  }
  if (!customElements.get('dtek-outage-card')) customElements.define('dtek-outage-card', DtekOutageCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === 'dtek-outage-card')) window.customCards.push({ type: 'dtek-outage-card', name: 'DTEK · Компактний графік / Compact schedule', description: 'Building status and daily outage timeline. Стан будинку та графік відключень.', preview: true });
