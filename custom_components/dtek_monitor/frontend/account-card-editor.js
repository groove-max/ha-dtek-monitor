import { isUkrainian } from "./account-ui.js?v=2.0.0-rc5";
/* Card-local account selection. No global active account or billing operations. */
const words = {
  en: {workspaceHelp:"Choose the account shown in this card. For two apartments, add two My DTEK cards. The switching option below affects only this card; it does not add or remove DTEK accounts.", account:"Personal account", title:"Title (optional)", year:"Initial year (optional)", choose:"Choose an account", missing:"Current entity is unavailable", loading:"Loading accounts…", empty:"No readable accounts are connected. Select accounts in the integration settings.", error:"Could not load accounts.", retry:"Refresh account list", help:"This choice applies only to this card. Connect additional accounts in Settings → Devices & services → DTEK Monitor → Configure → Select personal accounts."},
  uk: {workspaceHelp:"Оберіть рахунок для цієї картки. Для двох квартир додайте дві картки My DTEK. Дозвіл перемикання нижче стосується лише цієї картки; він не додає й не видаляє рахунки ДТЕК.", account:"Особовий рахунок", title:"Заголовок (необов’язково)", year:"Початковий рік (необов’язково)", choose:"Оберіть рахунок", missing:"Поточна сутність недоступна", loading:"Завантаження рахунків…", empty:"Немає підключених доступних рахунків. Оберіть їх у налаштуваннях інтеграції.", error:"Не вдалося завантажити рахунки.", retry:"Оновити список рахунків", help:"Цей вибір стосується лише цієї картки. Додайте інші рахунки: Налаштування → Пристрої та служби → DTEK Monitor → Налаштувати → Вибрати особові рахунки."},
};
export function accountCardEditor() { return document.createElement("dtek-account-card-editor"); }
class DtekAccountCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:"open"}); this._seq=0; }
  setConfig(config) { this._config={...config}; this._render(); }
  set hass(hass) {
    const changed=this._hass?.connection!==hass.connection || this._hass?.user?.id!==hass.user?.id;
    this._hass=hass;
    if(changed) {this._seq++;this._accounts=undefined;this._pending=false;this._loaded=false;}
    this._render();
    if(!this._loaded && !this._pending && this.isConnected) this._load();
  }
  connectedCallback() {this._render();if(this._hass && !this._loaded)this._load();}
  disconnectedCallback() {this._seq++;this._pending=false;this._loaded=false;}
  get w() {return words[isUkrainian(this._hass?.language)?"uk":"en"];}
  async _load() {
    if(!this._hass || this._pending)return;
    const seq=++this._seq;this._pending=true;this._error=false;this._render();
    try {
      const accounts=await this._hass.callWS({type:"dtek_monitor/accounts"});
      if(seq!==this._seq)return;
      if(!Array.isArray(accounts))throw new Error("Invalid account list");
      this._accounts=accounts;
    } catch (_) {if(seq===this._seq){this._error=true;this._accounts=[];}}
    finally {if(seq===this._seq){this._pending=false;this._loaded=true;this._render();}}
  }
  _change(key,value) {
    this._config={...this._config};
    if(value==="")delete this._config[key];else this._config[key]=value;
    this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:{...this._config}},bubbles:true,composed:true}));
  }
  _render() {
    if(!this._config || !this._hass)return;
    const w=this.w;
    if(!this._select) {
      const style=document.createElement("style");style.textContent=":host{display:block;color:var(--primary-text-color)}label{display:block;margin:12px 0}input,select,button{box-sizing:border-box;max-width:100%;min-height:44px;font:inherit;color:inherit;background:var(--card-background-color,white);border:1px solid var(--divider-color,#aaa);border-radius:6px;padding:8px}select,input{display:block;width:100%;margin-top:6px}p{color:var(--secondary-text-color);overflow-wrap:anywhere}button{cursor:pointer}";
      this.shadowRoot.append(style);
      const field=(tag,key)=>{const label=document.createElement("label"),text=document.createElement("span"),el=document.createElement(tag);label.append(text,el);this.shadowRoot.append(label);el.dataset.key=key;return [el,text,label];};
      [this._select,this._selectLabel]=field("select","entity");
      this._select.addEventListener("change",()=>this._change("entity",this._select.value));
      [this._title,this._titleLabel,this._titleRow]=field("input","title");
      this._title.addEventListener("input",()=>this._change("title",this._title.value));
      [this._year,this._yearLabel,this._yearRow]=field("input","year");this._year.type="number";this._year.min="2000";this._year.max="2100";this._year.step="1";
      this._year.addEventListener("input",()=>{if(this._year.checkValidity())this._change("year",this._year.value===""?"":Number(this._year.value));});
      this._feedback=document.createElement("p");this._feedback.setAttribute("role","status");
      this._retry=document.createElement("button");this._retry.type="button";this._retry.addEventListener("click",()=>this._load());
      this._help=document.createElement("p");this.shadowRoot.append(this._feedback,this._retry,this._help);
    }
    this._select.setAttribute("aria-label",w.account);this._selectLabel.textContent=w.account;this._titleLabel.textContent=w.title;this._yearLabel.textContent=w.year;
    this._titleRow.hidden=this._config.type==="custom:dtek-account-number-card";
    this._yearRow.hidden=this._config.type!=="custom:dtek-account-history-card";
    // Keep input nodes, focus, selection and in-progress typing across HA updates.
    for(const [input,value] of [[this._title,this._config.title??""],[this._year,this._config.year??""]]) {
      if(this.shadowRoot.activeElement!==input && input.value!==String(value))input.value=String(value);
    }
    const selected=this._config.entity||"";
    const accounts=this._accounts||[];
    const current=accounts.find(a=>a.entity_id===selected || a.entities?.includes(selected));
    const options=[{value:"",label:w.choose},...accounts.map(a=>({value:a===current?selected:a.entity_id,label:`${a.masked} — ${a.address}`}))];
    if(selected && !current)options.push({value:selected,label:`${w.missing}: ${selected}`});
    const signature=JSON.stringify(options);
    if(signature!==this._options) {
      this._options=signature;this._select.replaceChildren(...options.map(o=>{const el=document.createElement("option");el.value=o.value;el.textContent=o.label;return el;}));
    }
    if (this._config.type === "custom:dtek-account-workspace-card" && !this._scope) {
      const label=document.createElement("label");this._scope=document.createElement("input");this._scope.type="checkbox";this._scope.style.width="auto";this._scopeText=document.createElement("span");label.append(this._scope,this._scopeText);this.shadowRoot.append(label);this._scope.onchange=()=>this._change("show_account_selector",this._scope.checked);
    }
    if(this._scope){this._scope.checked=this._config.show_account_selector!==false;this._scopeText.textContent=isUkrainian(this._hass.language)?"Дозволити перемикання рахунків у цій картці":"Allow switching accounts in this card";}
    this._select.value=selected;
    this._feedback.textContent=this._pending?w.loading:this._error?w.error:this._loaded&&!accounts.length?w.empty:"";
    this._retry.textContent=w.retry;this._retry.disabled=this._pending;this._help.textContent=this._config.type==="custom:dtek-account-workspace-card"?w.workspaceHelp:w.help;
  }
}
if(!customElements.get("dtek-account-card-editor"))customElements.define("dtek-account-card-editor",DtekAccountCardEditor);
