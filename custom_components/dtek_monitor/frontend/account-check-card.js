import { zoneKey, isUkrainian,  embeddedCSS } from "./account-ui.js?v=2.0.0-rc5";
import { accountCardEditor } from "./account-card-editor.js?v=2.0.0-rc5";
import { accountNumber } from "./account-number.js?v=2.0.0-rc5";
import { energyMessage } from "./account-energy-editor.js?v=2.0.0-rc5";
const words={
  en:{title:"DTEK reading checks",refresh:"Refresh journal",loading:"Loading…",empty:"No checks yet. Use Check readings without submission on this account’s device.",note:"These are cumulative meter readings for submission, not monthly consumption. Check mode: nothing is submitted to DTEK. Results are snapshots taken at the displayed time.",on:"Scheduled checks enabled",off:"Scheduled checks disabled",daily:"Every day",window:"Each day in the reporting window",ready:"Ready to review",blocked:"Needs attention",error:"Check failed",checking:"Checking…",interrupted:"Interrupted; not repeated",idle:"Not checked yet",manual:"Manual",scheduled:"Scheduled",general:"Single zone",day:"Day",night:"Night",date:"Checked (Kyiv)",value:"Cumulative meter reading (kWh)",status:"Result",source:"Sensor reported",failed:"Could not load the check journal.",no_energy_source:"No energy source is bound to this account.",check_cabinet:"A previous submission is unresolved. Check the DTEK cabinet before preparing new readings.",pending_or_blocked:"DTEK has pending or blocked readings. Check the cabinet.",unsupported_meter:"This meter configuration is not supported for submission.",already_sent:"These values were already accepted today.",invalid_readings:"The estimate is below the previous reading or outside the meter’s limits.",auth_required:"Sign in to the cabinet again in the integration settings.",rate_limited:"DTEK limited requests. Try later.",service_unavailable:"The cabinet is unavailable.",check_store_unavailable:"The local journal is unavailable. Checks are stopped until this is resolved.",check_failed:"The check could not be completed."},
  uk:{title:"Перевірки показів ДТЕК",refresh:"Оновити журнал",loading:"Завантаження…",empty:"Перевірок ще немає. На пристрої цього рахунку натисніть «Перевірити покази без передачі».",note:"Це накопичувальні покази лічильника для передачі, а не споживання за місяць. Режим перевірки: нічого не передається в ДТЕК. Результати збережені на вказаний час.",on:"Перевірки за розкладом увімкнено",off:"Перевірки за розкладом вимкнено",daily:"Щодня",window:"Щодня у вікні передачі",ready:"Готово до перегляду",blocked:"Потребує уваги",error:"Помилка перевірки",checking:"Перевірка…",interrupted:"Перервано; повтору не було",idle:"Ще не перевірено",manual:"Вручну",scheduled:"За розкладом",general:"Одна зона",day:"День",night:"Ніч",date:"Перевірено (Київ)",value:"Накопичувальні покази лічильника (кВт·год)",status:"Результат",source:"Датчик повідомив",failed:"Не вдалося завантажити журнал перевірок.",no_energy_source:"До цього рахунку не прив’язано джерело енергії.",check_cabinet:"Результат попередньої передачі невідомий. Перевірте кабінет ДТЕК перед новою передачею.",pending_or_blocked:"У ДТЕК є очікувані або заблоковані покази. Перевірте кабінет.",unsupported_meter:"Ця конфігурація лічильника не підтримує передачу тут.",already_sent:"Ці значення вже прийняті сьогодні.",invalid_readings:"Розрахунок менший за попередні покази або виходить за межі лічильника.",auth_required:"Увійдіть у кабінет повторно в налаштуваннях інтеграції.",rate_limited:"ДТЕК обмежив запити. Спробуйте пізніше.",service_unavailable:"Кабінет недоступний.",check_store_unavailable:"Локальний журнал недоступний. Перевірки зупинено до усунення проблеми.",check_failed:"Не вдалося завершити перевірку."},
};
function el(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}
class DtekAccountCheckCard extends HTMLElement {
  constructor(){super();this.attachShadow({mode:"open"});this._seq=0;}
  static getConfigElement(){return accountCardEditor();}
  static getStubConfig(){return {entity:"sensor.example_account_data_updated"};}
  getCardSize(){return 4;}
  setConfig(config){
    if(!config.entity || typeof config.entity!=="string")throw new Error("Set an account entity");
    const changed=config.entity!==this._config?.entity;this._config={...config};this.toggleAttribute("embedded",!!config.embedded);
    if(changed){this._seq++;this._data=null;this._error=false;this._pending=false;}
    this.render();if(changed && this.isConnected)this.load();
  }
  set hass(hass){const first=!this._hass;this._hass=hass;if(first){this.render();if(this.isConnected)this.load();}}
  connectedCallback(){this.render();this.load();}
  disconnectedCallback(){this._seq++;this._pending=false;}
  get w(){return words[isUkrainian(this._hass?.language)?"uk":"en"];}
  async load(){
    if(!this._hass || !this._config || !this.isConnected || this._pending)return;
    const seq=++this._seq;this._pending=true;this._error=false;this.render();
    try{
      const data=await this._hass.callWS({type:"dtek_monitor/account_checks",entity_id:this._config.entity});
      if(seq!==this._seq)return;
      if(!Array.isArray(data.history))throw new Error("Invalid journal");
      this._data=data;
    }catch(_){if(seq===this._seq){this._error=true;this._data=null;}}
    finally{if(seq===this._seq){this._pending=false;this.render();}}
  }
  date(value){const date=new Date(value);return Number.isNaN(date.valueOf())?"—":date.toLocaleString(isUkrainian(this._hass?.language)?"uk-UA":"en-GB",{timeZone:"Europe/Kyiv",dateStyle:"short",timeStyle:"short"});}
  reason(code){return this.w[code]||energyMessage(this._hass?.language,code)||this.w.check_failed;}
  render(){
    if(!this._config || !this._hass)return;
    const w=this.w,card=el("ha-card"),style=el("style");
    style.textContent=":host{display:block}ha-card{padding:16px;overflow:hidden}h2{margin:0;font-size:20px}p{overflow-wrap:anywhere}.note{color:var(--secondary-text-color)}button{min-height:44px;padding:8px 12px;font:inherit;background:transparent;color:var(--primary-text-color);border:1px solid var(--divider-color,#aaa);border-radius:6px;cursor:pointer}.rows{overflow:auto}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;padding:10px 6px;border-bottom:1px solid var(--divider-color,#ddd)}small{display:block}.error{color:var(--error-color,#b22)}";
    card.append(el("h2",this._config.title||w.title));if(!this._config.embedded)card.append(accountNumber(this._hass,this._config.entity));
    const note=el("p",w.note);note.className="note";card.append(note);
    const refresh=el("button",this._pending?w.loading:w.refresh);refresh.type="button";refresh.disabled=this._pending;refresh.addEventListener("click",()=>this.load());card.append(refresh);
    if(this._error){const msg=el("p",w.failed);msg.setAttribute("role","alert");card.append(msg);}
    const data=this._data;
    if(data){
      card.append(el("p",data.schedule_enabled?`${w.on} · ${data.frequency==="reading_window"?w.window:w.daily} · ${data.time} · Europe/Kyiv`:w.off));
      if(data.reason==="check_store_unavailable")card.append(el("p",this.reason(data.reason)));
      if(!data.history.length)card.append(el("p",w.empty));
      else {
        const scroll=el("div"),table=el("table"),head=el("tr"),thead=el("thead"),body=el("tbody");scroll.className="rows";
        for(const label of [w.date,w.status,w.value])head.append(el("th",label));thead.append(head);table.append(thead,body);
        for(const run of [...data.history].reverse()){
          const row=el("tr"),date=el("td",this.date(run.at)),status=el("td",w[run.status]||w.error),value=el("td");date.append(el("small",w[run.trigger]||""));
          if(run.reason)status.append(el("small",this.reason(run.reason)));
          const readings=run.readings||[];
          if(!readings.length)value.textContent="—";
          for(const r of readings){const label={GENERAL:w.general,DAY:w.day,NIGHT:w.night}[zoneKey(r.zone)]||r.zone;value.append(el("div",`${label}: ${r.value}`));if(r.source_at)value.append(el("small",`${w.source}: ${this.date(r.source_at)}`));}
          row.append(date,status,value);body.append(row);
        }
        scroll.append(table);card.append(scroll);
      }
    }
    style.textContent+=embeddedCSS;this.shadowRoot.replaceChildren(style,card);
  }
}
if(!customElements.get("dtek-account-check-card"))customElements.define("dtek-account-check-card",DtekAccountCheckCard);
window.customCards=window.customCards||[];
if (!window.customCards.some(card => card.type === 'dtek-account-check-card')) window.customCards.push({type:'dtek-account-check-card',name:"DTEK reading checks",description:"Read-only per-account check journal. Nothing is submitted to DTEK."});
