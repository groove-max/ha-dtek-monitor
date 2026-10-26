import "./account-energy-editor.js?v=2.0.0-rc5";
import { isUkrainian, el, embeddedCSS} from "./account-ui.js?v=2.0.0-rc5";

// Owns the settings lifecycle; source proposals stay in the readings card.
class DtekEnergySettings extends HTMLElement {
  static get workspaceVersion(){return 1;}
  constructor(){super();this.attachShadow({mode:"open"});this._seq=0;}
  setConfig(config){this._config={...config};}
  set hass(hass){this._hass=hass;this._editor?.configure(hass,this._config.entity,this._context,false,{settingsOnly:true});this.labels();}
  get hasDraft(){return !!this._editor?.hasDraft;}
  get busy(){return !!this._loading || !!this._editor?.busy;}
  get mutating(){return !!this._editor?.mutating;}
  refreshBinding(){if(!this.hasDraft&&!this.busy)this._editor?.act("get");}
  set locked(value){if(this._editor)this._editor.locked=value;}
  disconnectedCallback(){this._seq++;this._loading=false;this._started=false;}
  labels(){
    if(!this._retry)return;
    const uk=isUkrainian(this._hass.language);
    this._retry.textContent=uk?"Оновити дані лічильника ДТЕК":"Refresh DTEK meter data";
    this._refreshTitle.textContent=uk?"Оновлення даних лічильника ДТЕК":"DTEK meter data refresh";
    this._retry.disabled=this.busy || this.hasDraft;
    this._status.textContent=this._loading?(uk?"Завантаження датчика та даних лічильника…":"Loading the source and meter data…"):this._contextError?(uk?"Не вдалося завантажити лічильник ДТЕК. Наявну прив’язку можна звірити локально; для нової прив’язки оновіть дані пізніше.":"Could not load the DTEK meter. You can calibrate an existing binding locally; refresh later to create a new binding."):"";
  }
  async open(force=false){
    if(!this.isConnected || !this._hass || this._hass.user?.is_admin===false || this._loading || this.hasDraft || this._editor?.busy || (this._started&&!force))return;
    if(!this._editor){
      this._editor=document.createElement("dtek-energy-editor");
      this._status=el("p");this._status.setAttribute("role","status");
      this._retry=el("button");this._retry.type="button";this._retry.onclick=()=>this.open(true);
      const refresh=el("details");this._refreshTitle=el("summary");refresh.append(this._refreshTitle,this._retry);
      this.shadowRoot.append(el("style",embeddedCSS+`:host{display:block;min-width:0}p{line-height:1.5;overflow-wrap:anywhere;color:var(--secondary-text-color)}p:empty{display:none}button{font:inherit;padding:10px;border:1px solid var(--divider-color,#aaa);border-radius:8px;color:inherit;background:transparent;cursor:pointer}button:disabled{opacity:.5}details{margin-top:20px}summary{cursor:pointer}summary+button{margin-top:10px}`),this._status,this._editor,refresh);
      this._editor.addEventListener("energy-operation",()=>this.labels());
      this._editor.addEventListener("input",()=>this.labels());
      this._editor.addEventListener("click",()=>queueMicrotask(()=>this.labels()));
    }
    const seq=++this._seq;this._started=true;this._loading=true;this._editor.hidden=true;this.labels();
    this._editor.configure(this._hass,this._config.entity,this._context,false,{settingsOnly:true});
    const [context]=await Promise.allSettled([
      Promise.resolve().then(()=>this._hass.callWS({type:"dtek_monitor/account_submission",entity_id:this._config.entity,action:"context"})),
      this._editor.act("get"),
    ]);
    if(seq!==this._seq || !this.isConnected)return;
    this._contextError=context.status!=="fulfilled";this._context=this._contextError?null:context.value;
    this._editor.configure(this._hass,this._config.entity,this._context,false,{settingsOnly:true});
    this._loading=false;this._editor.hidden=false;this.labels();
    this.dispatchEvent(new CustomEvent("energy-operation",{bubbles:true,composed:true}));
  }
}
if(!customElements.get("dtek-energy-settings"))customElements.define("dtek-energy-settings",DtekEnergySettings);
