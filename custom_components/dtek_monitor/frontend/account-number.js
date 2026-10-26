import { isUkrainian } from "./account-ui.js?v=2.0.0-rc5";
import { accountCardEditor } from "./account-card-editor.js?v=2.0.0-rc5";
export async function copyValue(value){
  if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(value);return;}
  const input=document.createElement('textarea');input.value=value;input.style.cssText='position:fixed;left:-10000px';document.body.append(input);
  try{input.select();if(!document.execCommand('copy'))throw new Error('Copy unavailable');}finally{input.remove();}
}

/* Display privacy only: HA permissions, not masking, protect account access. */
class DtekAccountNumber extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:"open"}); this._seq=0; this._number=null;
  }
  set hass(value) {
    const first=!this._hass;
    const changed=this._hass && (this._hass.user?.id!==value?.user?.id || this._hass.user?.is_admin!==value?.user?.is_admin || this._hass.connection!==value?.connection);
    this._hass=value;
    if(changed){this._seq++;this._number=null;this._masked=null;this._pending=false;this._error=false;}
    this._render();
    if((first||changed)&&this.isConnected)this._load(false);
  }
  set entity(value) {
    if (value===this._entity) return;
    this._entity=value; this._seq++; this._number=null; this._masked=null;
    this._pending=false; this._error=false;
    this._render();
    if(this.isConnected) this._load(false);
  }
  connectedCallback() { this._load(false); }
  disconnectedCallback() { this._seq++; this._number=null; this._pending=false; this._render(); }
  get words() {
    return isUkrainian(this._hass?.language)
      ? {account:"Особовий рахунок",show:"Показати номер рахунку",hide:"Сховати номер рахунку",error:"Номер недоступний",loading:"Завантаження…",copy:"Копіювати номер рахунку",copied:"Скопійовано",copyError:"Копіювання недоступне; виділіть номер."}
      : {account:"Account number",show:"Show account number",hide:"Hide account number",error:"Account number unavailable",loading:"Loading…",copy:"Copy account number",copied:"Copied",copyError:"Copy unavailable; select the number."};
  }
  async _load(reveal) {
    if(!this._hass || !this._entity || !this.isConnected) {this._render();return;}
    const seq=++this._seq; this._pending=reveal; this._error=false; this._render();
    try {
      const data=await this._hass.callWS({type:"dtek_monitor/account_identity",entity_id:this._entity,reveal});
      if(seq!==this._seq || !this.isConnected)return;
      if(typeof data.masked!=="string" || (reveal && !/^[0-9]+$/.test(data.number))) throw new Error("Invalid identity");
      this._masked=data.masked; this._number=reveal ? data.number : null;
    } catch (_) {
      if(seq!==this._seq || !this.isConnected)return;
      this._number=null; this._error=true;
    } finally {
      if(seq===this._seq && this.isConnected) {this._pending=false;this._render();}
    }
  }
  _toggle() {
    if(this._number || this._pending) {
      this._seq++; this._number=null; this._pending=false; this._error=false; this._render();
    } else this._load(true);
  }
  _render() {
    const w=this.words;
    const key=JSON.stringify([w,this._number,this._masked,this._pending,this._error]);
    if(key===this._renderKey)return;
    this._renderKey=key;
    const style=document.createElement("style");
    style.textContent=":host{display:block;margin:12px 0}.line{display:flex;align-items:center;gap:8px;flex-wrap:wrap}button{display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--divider-color,#aaa);border-radius:6px;background:transparent;color:var(--primary-text-color);cursor:pointer;min-width:40px;min-height:40px}svg{width:22px;height:22px}.value{font-variant-numeric:tabular-nums;overflow-wrap:anywhere}small{color:var(--error-color,#b22)}";
    const line=document.createElement("div");line.className="line";
    const text=document.createElement("span");text.className="value";
    text.textContent=`${w.account}: ${this._number || this._masked || "••••"}`;
    const button=document.createElement("button");button.type="button";
    button.setAttribute("aria-label",this._number || this._pending ? w.hide : w.show);
    button.title=button.getAttribute("aria-label");button.setAttribute("aria-pressed",String(!!this._number));
    button.addEventListener("click",()=>this._toggle());
    const ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg");
    svg.setAttribute("viewBox","0 0 24 24");svg.setAttribute("fill","none");svg.setAttribute("stroke","currentColor");svg.setAttribute("stroke-width","1.6");svg.setAttribute("aria-hidden","true");
    const eye=document.createElementNS(ns,"path");eye.setAttribute("d","M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z");
    const pupil=document.createElementNS(ns,"circle");pupil.setAttribute("cx","12");pupil.setAttribute("cy","12");pupil.setAttribute("r","3");svg.append(eye,pupil);
    if(this._number) {const slash=document.createElementNS(ns,"path");slash.setAttribute("d","m3 3 18 18");svg.append(slash);}
    button.append(svg);line.append(text,button);
    if(this._number){const copy=document.createElement("button");copy.type="button";copy.textContent=w.copy;const value=this._number;copy.addEventListener("click",async()=>{try{await copyValue(value);copy.textContent=w.copied;}catch(_){copy.textContent=w.copyError;}});line.append(copy);}
    const feedback=document.createElement("small");feedback.textContent=this._error?w.error:this._pending?w.loading:"";
    if(this._error)feedback.setAttribute("role","alert");
    this.shadowRoot.replaceChildren(style,line,feedback);
  }
}
if(!customElements.get("dtek-account-number"))customElements.define("dtek-account-number",DtekAccountNumber);

export function accountNumber(hass, entity) {
  const el=document.createElement("dtek-account-number");el.hass=hass;el.entity=entity;return el;
}

/* Resolve navigation locally through the same account permission check as the eye.
 * No DTEK request, full account number, or default-to-Odesa link is needed. */
class DtekCabinetLink extends HTMLElement {
  constructor() {super();this.attachShadow({mode:"open"});this._seq=0;}
  set hass(value) {
    const first=!this._hass;
    const changed=this._hass && (this._hass.user?.id!==value?.user?.id || this._hass.connection!==value?.connection || this._hass.user?.is_admin!==value?.user?.is_admin);
    this._hass=value;
    if(changed){this._seq++;this.shadowRoot.replaceChildren();}
    if((first||changed)&&this.isConnected)this._load();
  }
  set label(value){this._label=value;const link=this.shadowRoot.querySelector('a');if(link&&link.textContent!==value)link.textContent=value;}
  get label(){return this._label;}
  set entity(value) {
    if(this._entity===value)return;
    this._entity=value;this._seq++;this.shadowRoot.replaceChildren();
    if(this.isConnected)this._load();
  }
  connectedCallback(){this._load();}
  disconnectedCallback(){this._seq++;this.shadowRoot.replaceChildren();}
  async _load() {
    if(!this._hass || !this._entity)return;
    const seq=++this._seq;
    try {
      const data=await this._hass.callWS({type:"dtek_monitor/account_identity",entity_id:this._entity,reveal:false});
      if(seq!==this._seq || !this.isConnected)return;
      // Accept only the operator cabinet root, never arbitrary navigation URLs.
      if(typeof data.cabinet_url!=="string" || !/^https:\/\/my\.dtek-[a-z]+\.com\.ua\/$/.test(data.cabinet_url))return;
      const style=document.createElement("style");style.textContent="a{color:var(--primary-color,#0288d1)}";
      const link=document.createElement("a");link.textContent=this.label;link.href=data.cabinet_url;link.target="_blank";link.rel="noopener noreferrer";
      this.shadowRoot.replaceChildren(style,link);
    } catch(_) {
      // Missing/unauthorized accounts have no link; the meter form owns its errors.
      if(seq===this._seq)this.shadowRoot.replaceChildren();
    }
  }
}
if(!customElements.get("dtek-cabinet-link"))customElements.define("dtek-cabinet-link",DtekCabinetLink);
export function cabinetLink(hass, entity, label) {
  const el=document.createElement("dtek-cabinet-link");el.hass=hass;el.entity=entity;el.label=label;return el;
}

class DtekAccountNumberCard extends HTMLElement {
  constructor() {super();this.attachShadow({mode:"open"});}
  setConfig(config) {
    if(!config.entity || typeof config.entity!=="string") throw new Error("Set an account entity");
    this._config={...config};this._render();
  }
  set hass(value) {this._hass=value;if(!this._identity)this._render();else this._identity.hass=value;}
  getCardSize() {return 1;}
  static getConfigElement() { return accountCardEditor(); }
  static getStubConfig() {return {entity:"sensor.example_account_data_updated"};}
  _render() {
    if(!this._config || !this._hass)return;
    const card=document.createElement("ha-card");card.style.padding="4px 16px";
    this._identity=accountNumber(this._hass,this._config.entity);card.append(this._identity);
    this.shadowRoot.replaceChildren(card);
  }
}
if(!customElements.get("dtek-account-number-card"))customElements.define("dtek-account-number-card",DtekAccountNumberCard);
window.customCards=window.customCards||[];
if (!window.customCards.some(card => card.type === 'dtek-account-number-card')) window.customCards.push({type:'dtek-account-number-card',name:"DTEK account number",description:"Show or hide the account number with your HA read permissions."});
