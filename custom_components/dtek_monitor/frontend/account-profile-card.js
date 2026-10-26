import { isUkrainian,  embeddedCSS, date } from './account-ui.js?v=2.0.0-rc5';
import { accountCardEditor } from './account-card-editor.js?v=2.0.0-rc5';
import { accountNumber, copyValue } from './account-number.js?v=2.0.0-rc5';
const words = {
  en: {title:'DTEK account',loading:'Loading…',refresh:'Refresh',show:'Show meter identifiers',hide:'Hide meter identifiers',copy:'Copy',copied:'Copied',copyError:'Copy unavailable; select the visible value.',address:'Address',eics:'EIC · distribution points',installation:'EIC',model:'Meter model',serial:'Meter number',zones:'Tariff scheme',power:'Contract power',details:'Meter details',manufacture:'Manufacture year',installed:'Installation date',verified:'Last verification year',next:'Next verification year',agreement:'Agreement date',type:'Installation type',seals:'Seals',seal:'Seal number',place:'Location',removed:'Removal date',replacement:'Replacement records in the cabinet',replacementNote:'The cabinet reports replacement records. Open the cabinet for their details.',none:'None reported',unknown:'Not provided',fetched:'Profile fetched',stale:'Account refresh is unavailable. Any retained data is dated below.',partial:'Meter details are unavailable. Address and EICs may still be available from the account list.',error:'Profile unavailable or access denied.',},
  uk: {title:'Особовий рахунок ДТЕК',loading:'Завантаження…',refresh:'Оновити',show:'Показати реквізити лічильника',hide:'Сховати реквізити лічильника',copy:'Копіювати',copied:'Скопійовано',copyError:'Копіювання недоступне; виділіть видиме значення.',address:'Адреса',eics:'EIC · точки розподілу',installation:'EIC',model:'Модель лічильника',serial:'Номер лічильника',zones:'Тарифна схема',power:'Договірна потужність',details:'Відомості про лічильник',manufacture:'Рік виготовлення',installed:'Дата встановлення',verified:'Рік останньої повірки',next:'Рік наступної повірки',agreement:'Дата договору',type:'Тип об’єкта',seals:'Пломби',seal:'Номер пломби',place:'Місце встановлення',removed:'Дата зняття',replacement:'Записів про заміну в кабінеті',replacementNote:'У кабінеті є записи про заміну. Перегляньте їхні подробиці в кабінеті.',none:'Не зазначено',unknown:'Не надано',fetched:'Профіль отримано',stale:'Оновлення рахунку недоступне. Нижче вказана дата збережених даних.',partial:'Відомості про лічильник недоступні. Адреса та EIC можуть бути доступні зі списку рахунків.',error:'Профіль недоступний або немає дозволу на перегляд.',},
};
const css=':host{display:block}ha-card{padding:20px;overflow:hidden}h2{font-size:1.3em;margin:0 0 12px}h3{font-size:1.08em;margin:16px 0 10px}p{line-height:1.5;overflow-wrap:anywhere}.address{font-size:1.1em;font-weight:600}.muted{color:var(--secondary-text-color);font-size:.9em}.error{color:var(--error-color,#b22)}.controls{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}button{font:inherit;color:var(--primary-text-color);background:transparent;border:1px solid var(--divider-color,#aaa);border-radius:7px;padding:8px;min-height:40px;cursor:pointer}button:disabled{opacity:.5}dl{display:grid;grid-template-columns:minmax(100px,1fr) minmax(0,1.3fr);gap:10px;margin:12px 0}dt{color:var(--secondary-text-color)}dd{margin:0;overflow-wrap:anywhere}dd button{margin-left:8px}summary{cursor:pointer;padding:10px 0}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.9em}th,td{text-align:start;vertical-align:top;padding:8px;border-bottom:1px solid var(--divider-color,#aaa)}@media(max-width:500px){ha-card{padding:14px}dl{grid-template-columns:minmax(90px,1fr) minmax(0,1.1fr)}}';
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
class DtekAccountProfileCard extends HTMLElement{
  static get workspaceVersion() { return 1; }
  constructor(){super();this.attachShadow({mode:'open'});this._seq=0;}
  setConfig(config){if(typeof config.entity!=='string'||!config.entity)throw new Error('Set an account entity');const changed=this._config?.entity!==config.entity;this._config={...config};this.toggleAttribute('embedded',!!config.embedded);if(changed)this._reset();this._render();if(changed&&this.isConnected&&this._hass)this._load(false);}
  _reset(){this._seq++;this._data=null;this._error=null;this._busy=false;this._revealed=false;this._viewKey=null;}
  set hass(hass){const changed=this._hass&&(this._hass.user?.id!==hass.user?.id||this._hass.connection!==hass.connection||this._hass.user?.is_admin!==hass.user?.is_admin);const lang=isUkrainian(hass.language)?'uk':'en';const render=lang!==this._lang;const first=!this._hass;this._hass=hass;this._lang=lang;if(changed)this._reset();const stamp=hass.states?.[this._config?.entity]?.last_updated;const refresh=stamp!==this._stamp;this._stamp=stamp;if(render||changed)this._render();if(this.isConnected&&this._config&&(first||changed||refresh)&&!this._busy)this._load(this._revealed,!first&&!changed);}
  connectedCallback(){if(this._hass&&this._config)this._load(false);}
  disconnectedCallback(){this._reset();this._render();}
  get t(){return words[this._lang||'en'];}
  getCardSize(){return 4;}
  static getConfigElement(){return accountCardEditor();}
  static getStubConfig(){return {entity:'sensor.example_account_data_updated'};}
  async _load(reveal,background=false){
    const seq=++this._seq;this._busy=true;this._error=null;
    // Hiding removes raw values immediately, including while a reveal is pending.
    if(!reveal&&!background){this._revealed=false;this._data=null;}
    if(!background)this._render();
    try{const data=await this._hass.callWS({type:'dtek_monitor/account_profile',entity_id:this._config.entity,reveal});if(seq!==this._seq||!this.isConnected)return;this._data=data;this._revealed=reveal;}
    catch(_){if(seq===this._seq){this._error=this.t.error;this._data=null;this._revealed=false;}}
    finally{if(seq===this._seq&&this.isConnected){this._busy=false;this._render();}}
  }
  _button(text,fn){const b=el('button',text);b.type='button';b.addEventListener('click',fn);return b;}
  _time(value){return date(value,this._lang||'en',true);}
  _row(dl,label,value,copy=false){const dd=el('dd',value===null||value===undefined||value===''?this.t.unknown:String(value));if(copy&&value&&this._revealed){const b=this._button(this.t.copy,async()=>{try{await copyValue(String(value));b.textContent=this.t.copied;}catch(_){b.textContent=this.t.copyError;}});b.setAttribute('aria-label',`${this.t.copy}: ${label}`);dd.append(b);}dl.append(el('dt',label),dd);}
  _render(){
    if(!this._config)return;
    // Unchanged background responses must not replace controls, the account eye,
    // or expanded details. A new fetch timestamp updates its own text node.
    const d=this._data,t=this.t,{fetched_at,...content}=d||{};
    const key=JSON.stringify([this._config,this._lang,content,this._busy,this._error,this._revealed]);
    const stamp=d?`${t.fetched}: ${this._time(fetched_at)} (Europe/Kyiv)`:'';
    if(key===this._viewKey){if(this._stampNode&&this._stampNode.textContent!==stamp)this._stampNode.textContent=stamp;return;}
    this._viewKey=key;
    const opened=this.shadowRoot.querySelector('details')?.open||false;
    const card=el('ha-card');card.append(el('h2',this._config.title||t.title,'card-title'));
    if(!this._config.embedded)card.append(accountNumber(this._hass,this._config.entity));
    if(d){card.append(el('p',d.address||t.unknown,'address'));if(!d.available)card.append(el('p',t.stale,'error'));else if(!d.metadata_available)card.append(el('p',t.partial,'muted'));}
    const controls=el('div',undefined,'controls');const refresh=this._button(this._busy?t.loading:t.refresh,()=>this._load(this._revealed));refresh.disabled=this._busy;controls.append(refresh);
    const privacy=this._button(this._revealed?t.hide:t.show,()=>this._load(!this._revealed));privacy.disabled=this._busy;controls.append(privacy);card.append(controls);
    if(this._error)card.append(el('p',this._error,'error'));
    if(d){const dl=el('dl');for(const [label,value,copy] of [...(d.eics?.length===1&&d.eics[0]===d.installation_eic?[[t.installation,d.installation_eic,true]]:[[t.eics,d.eics?.join('\n'),true],[t.installation,d.installation_eic,true]]),[t.model,d.model],[t.serial,d.serial,true],[t.zones,d.zone_scheme],[t.power,d.contract_power_kw?`${Number(d.contract_power_kw)} kW`:null],[t.next,d.next_verification_year]])this._row(dl,label,value,copy);card.append(dl);
      const details=el('details');details.open=opened;details.append(el('summary',t.details));const dd=el('dl');for(const [label,value] of [[t.manufacture,d.manufacture_year],[t.installed,d.installation_date],[t.verified,d.verification_year],[t.agreement,d.agreement_date],[t.type,d.installation_type],[t.replacement,d.replacement_records]])this._row(dd,label,value);details.append(dd);
      if(d.replacement_records>0)details.append(el('p',t.replacementNote,'muted'));
      details.append(el('h3',t.seals));if(!d.seals?.length)details.append(el('p',d.seals?t.none:t.unknown,'muted'));
      for(const seal of d.seals||[]){const list=el('dl');for(const [label,value,copy]of[[t.seal,seal.number,true],[t.type,seal.type],[t.place,seal.place],[t.installed,seal.installed],[t.removed,seal.removed]])this._row(list,label,value,copy);details.append(list);}card.append(details);
      this._stampNode=el('p',stamp,'muted');card.append(this._stampNode);
    }
    this.shadowRoot.replaceChildren(el('style',css+embeddedCSS),card);
  }
}
if(!customElements.get('dtek-account-profile-card'))customElements.define('dtek-account-profile-card',DtekAccountProfileCard);
window.customCards=window.customCards||[];if (!window.customCards.some(card => card.type === 'dtek-account-profile-card')) window.customCards.push({type:'dtek-account-profile-card',name:'DTEK account profile',description:'Address, EICs and meter details.'});
