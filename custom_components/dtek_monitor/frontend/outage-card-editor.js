import { outageText } from "./outage-card-text.js?v=2.0.0-rc4";
import { callGridWS } from "./schedule-grid-data.js?v=2.0.0-rc4";

class DtekOutageCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({mode: "open"}); this._seq = 0; }
  setConfig(config) { this._config = {...config}; this._render(); }
  set hass(hass) {
    if (hass.user?.id !== this._hass?.user?.id || hass.connection !== this._hass?.connection) {
      this._seq++; this._buildings = undefined; this._loading = false;
    }
    this._hass = hass; this._render();
    if (this.isConnected && !this._buildings && !this._loading) this._load();
  }
  connectedCallback() { this._render(); if (this._hass && !this._buildings) this._load(); }
  disconnectedCallback() { this._seq++; this._loading = false; this._buildings = undefined; }
  async _load() {
    if (!this._hass || this._loading) return;
    const seq = ++this._seq; this._loading = true; this._error = false; this._render();
    try {
      const data = await callGridWS(this._hass, {type: "dtek_monitor/buildings"});
      if (seq !== this._seq || !this.isConnected) return;
      if (!Array.isArray(data) || data.some(item => typeof item.status_entity !== "string" || typeof item.address !== "string" || !Array.isArray(item.groups))) throw new Error("Invalid buildings");
      this._buildings = data;
    } catch (_) { if (seq === this._seq) { this._buildings = []; this._error = true; } }
    finally { if (seq === this._seq) { this._loading = false; this._render(); } }
  }
  _emit() {
    this.dispatchEvent(new CustomEvent("config-changed", {detail: {config: {...this._config}}, bubbles: true, composed: true}));
  }
  _render() {
    if (!this._hass || !this._config) return;
    const t = outageText(this._hass.language);
    if (!this._address) {
      const style = document.createElement("style");
      style.textContent = ":host{display:block;color:var(--primary-text-color)}label{display:block;margin:16px 0}input,select,button{box-sizing:border-box;width:100%;min-height:44px;font:inherit;padding:10px;border:1px solid var(--divider-color,#aaa);border-radius:8px;color:inherit;background:var(--card-background-color,#fff)}label span{display:block;margin-bottom:6px}p{line-height:1.5;color:var(--secondary-text-color)}button{cursor:pointer}[hidden]{display:none!important}";
      this.shadowRoot.append(style);
      const field = tag => {const row = document.createElement("label"), label = document.createElement("span"), input = document.createElement(tag); row.append(label,input); this.shadowRoot.append(row); return [input,label];};
      [this._address,this._addressLabel] = field("select");
      [this._title,this._titleLabel] = field("input");
      [this._group,this._groupLabel] = field("select");
      this._title.type = "text";
      this._title.oninput = () => {this._config = {...this._config,title: this._title.value}; this._emit();};
      this._group.onchange = () => {this._config = {...this._config}; if (this._group.value) this._config.group = this._group.value; else delete this._config.group; this._emit();};
      this._address.onchange = () => {
        const building = this._buildings?.find(item => item.status_entity === this._address.value);
        if (!building) return;
        this._config = {...this._config, status_entity: building.status_entity};
        for (const key of ["entity", "updated_entity"]) { if (building[key]) this._config[key] = building[key]; else delete this._config[key]; }
        delete this._config.group; this._render(); this._emit();
      };
      this._feedback = document.createElement("p"); this._feedback.setAttribute("role","status");
      this._retry = document.createElement("button"); this._retry.type = "button"; this._retry.onclick = () => this._load();
      this._help = document.createElement("p"); this.shadowRoot.append(this._feedback, this._retry, this._help);
    }
    for (const [input,label,text] of [[this._address,this._addressLabel,t.address], [this._title,this._titleLabel,t.titleField], [this._group,this._groupLabel,t.initialGroup]]) {
      label.textContent = text; input.setAttribute("aria-label",text);
    }
    const selected = this._config.status_entity || "", buildings = this._buildings || [];
    const current = buildings.find(item => item.status_entity === selected);
    const choices = [{value:"",label:t.selectAddress},...buildings.map(item => ({value:item.status_entity,label:item.address}))];
    if (selected && !current) choices.push({value:selected,label:`${t.missingAddress}: ${selected}`});
    const groups = [{value:"",label:t.autoGroup},...(current?.groups || []).map(group => ({value:group,label:group}))];
    if (this._config.group && !groups.some(item => item.value === this._config.group)) groups.push({value:this._config.group,label:this._config.group});
    for (const [control,options,value] of [[this._address,choices,selected],[this._group,groups,this._config.group || ""]]) {
      const signature = JSON.stringify(options);
      if (control._options !== signature) {
        control._options = signature;
        control.replaceChildren(...options.map(item => { const option=document.createElement("option"); option.value=item.value; option.textContent=item.label; return option; }));
      }
      if (control.value !== value) control.value = value;
    }
    // HA state refreshes must not replace an unfinished title or steal focus.
    if (this.shadowRoot.activeElement !== this._title) this._title.value = this._config.title || "";
    this._feedback.textContent = this._loading ? t.loading : this._error ? t.loadFailed : this._buildings?.length === 0 ? t.noBuildings : "";
    this._retry.textContent = t.retry; this._retry.disabled = this._loading;
    this._help.textContent = t.help;
  }
}
if (!customElements.get("dtek-outage-card-editor")) customElements.define("dtek-outage-card-editor", DtekOutageCardEditor);
