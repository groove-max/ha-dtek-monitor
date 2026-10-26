import { isUkrainian, el} from "./account-ui.js?v=2.0.0-rc5";

// A small host for HA's existing options schemas. The backend owns validation,
// confirmation steps and persistence; ordinary hass updates only reach ha-form.
const words={
  en:{title:"DTEK settings",link:"Add account to DTEK",unlink:"Unlink account from DTEK",loading:"Opening settings…",close:"Close",cancel:"Cancel",next:"Continue",save:"Save",done:"Settings saved.",failed:"Could not open settings. Try again or use integration settings.",uncertain:"The result could not be received. Changes may have been saved. Close this window and check the settings before trying again.",unsupported:"This form needs the Home Assistant integration settings.",fallback:"Open integration settings",discard:"Discard the changes in this form?",keep:"Keep editing",discardAction:"Discard and close",reloading:"Settings saved. Home Assistant is updating the account…",reloadFailed:"Settings were saved, but the account has not finished loading. Refresh the account list once it is available.",scope:"Selected account",cabinet:"These settings apply to this DTEK cabinet. Each dashboard card chooses its displayed account separately."},
  uk:{title:"Налаштування ДТЕК",link:"Додати рахунок до ДТЕК",unlink:"Відв’язати рахунок від ДТЕК",loading:"Відкриваємо налаштування…",close:"Закрити",cancel:"Скасувати",next:"Продовжити",save:"Зберегти",done:"Налаштування збережено.",failed:"Не вдалося відкрити налаштування. Спробуйте ще раз або відкрийте налаштування інтеграції.",uncertain:"Не вдалося отримати результат. Зміни могли зберегтися. Закрийте вікно та перевірте налаштування перед повторною спробою.",unsupported:"Цю форму потрібно відкрити в налаштуваннях інтеграції Home Assistant.",fallback:"Відкрити налаштування інтеграції",discard:"Скасувати зміни в цій формі?",keep:"Продовжити редагування",discardAction:"Скасувати зміни та закрити",reloading:"Налаштування збережено. Home Assistant оновлює рахунок…",reloadFailed:"Налаштування збережено, але рахунок ще завантажується. Оновіть список рахунків, коли він буде доступний.",scope:"Обраний рахунок",cabinet:"Ці налаштування стосуються кабінету ДТЕК. Рахунок для відображення обирається окремо в кожній картці."},
};

async function loadForm(){
  if(customElements.get("ha-form"))return;
  // Use Lovelace's editor loader rather than importing hashed frontend bundles.
  const helpers=await window.loadCardHelpers();
  const card=helpers.createCardElement({type:"button"});
  await card.constructor.getConfigElement();
  if(!customElements.get("ha-form"))throw new Error("HA form unavailable");
}

class DtekAccountOptions extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});this._seq=0;}
  setConfig(config){this._config={...config};}
  set hass(hass){this._hass=hass;if(this._form)this._form.hass=hass;}
  get busy(){return !!this._busy;}
  get active(){return !!this._dialog?.open;}
  get t(){return words[isUkrainian(this._hass.language)?"uk":"en"];}
  disconnectedCallback(){this._seq++;this._cleanup();}
  api(method,data){return this._hass.callApi(method,`config/config_entries/options/flow/${this._flowId}`,data);}
  async _delete(hass,id){if(id)try{await hass.callApi("DELETE",`config/config_entries/options/flow/${id}`);}catch(_){/* already finished or disconnected */}}
  _cleanup(){const id=this._flowId;this._flowId=null;this._delete(this._hass,id);this._dialog?.close();this._busy=false;}
  button(text,action){const b=el("button",text);b.type="button";b.onclick=action;return b;}
  local(key,fallback=""){return this._localize?.(`component.dtek_monitor.options.${key}`,this._step?.description_placeholders)||fallback;}
  paragraph(content){const e=el(customElements.get("ha-markdown")?"ha-markdown":"p");if(e.localName==="ha-markdown")e.content=content;else e.textContent=content;return e;}
  async open(action,account){
    if(this.active||!this._hass.user?.is_admin)return;
    const seq=++this._seq,hass=this._hass;this._action=action;this._dirty=false;this._failed=false;this._finished=false;this._flowId=null;this._reloadReady=false;this._step=null;this._form=null;
    this._dialog=el("dialog");this._dialog.setAttribute("aria-labelledby","options-title");
    this._title=el("h3",this.t.title);this._title.id="options-title";
    const scope=el("p",`${this.t.scope}: ${account.address||""} · ${account.masked}`,"scope");
    this._body=el("div");this._status=el("p",this.t.loading);this._status.setAttribute("role","status");this._actions=el("div",undefined,"actions");
    this._close=this.button(this.t.cancel,()=>this.close());
    this._discard=el("section");this._discard.hidden=true;this._discard.setAttribute("role","alert");this._discard.append(el("p",this.t.discard),this.button(this.t.keep,()=>{this._discard.hidden=true;this._close.focus();}),this.button(this.t.discardAction,()=>this.close(true)));
    this._dialog.append(this._title,scope);
    if(["accounts","monitoring"].includes(action))this._dialog.append(el("p",this.t.cabinet));
    const footer=el("footer");footer.append(this._actions,this._close);this._dialog.append(this._body,this._status,this._discard,footer);
    this._dialog.addEventListener("cancel",e=>{e.preventDefault();this.close();});
    this.shadowRoot.replaceChildren(el("style",`:host{display:contents}dialog{box-sizing:border-box;width:min(600px,calc(100vw - 24px));max-height:calc(100dvh - 32px);overflow:auto;margin:auto;padding:24px;border:1px solid var(--divider-color,#aaa);border-radius:16px;color:var(--primary-text-color);background:var(--card-background-color,#fff)}dialog::backdrop{background:#0008}h3{margin-top:0}p{line-height:1.5;overflow-wrap:anywhere}p:empty{display:none}.scope{color:var(--secondary-text-color)}ha-form,ha-markdown{display:block;margin:16px 0}button,a{font:inherit;overflow-wrap:anywhere}button{padding:10px 14px;margin:8px 8px 0 0;border:1px solid var(--divider-color,#aaa);border-radius:8px;background:transparent;color:inherit;cursor:pointer}button:disabled{opacity:.5}.menu button{display:block;width:100%;text-align:left}footer{display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start}footer .actions:not(.menu){display:contents}footer .menu{width:100%}footer button{margin-right:0}.actions:not(.menu) button{background:var(--primary-color);border-color:var(--primary-color);color:var(--text-primary-color,#fff)}a{color:var(--primary-color)}section{padding:12px;border:1px solid var(--warning-color,#c88b20);border-radius:8px;margin-top:16px}[hidden]{display:none!important}@media(max-width:420px){dialog{padding:18px}}`),this._dialog);
    this._dialog.showModal();this.setBusy(true);
    try{
      const [localize,,localizeSelector]=await Promise.all([hass.loadBackendTranslation("options","dtek_monitor"),loadForm(),hass.loadBackendTranslation("selector","dtek_monitor")]);
      if(seq!==this._seq||!this.isConnected)return;
      this._localize=localize;
      this._localizeSelector=localizeSelector;
      const result=await hass.callWS({type:"dtek_monitor/account_options",entity_id:account.entity_id,action});
      if(seq!==this._seq||!this.isConnected){this._delete(hass,result.flow_id);return;}
      this._entryId=result.entry_id;this._flowId=result.flow_id;
      const step=await this.api("GET");if(seq!==this._seq)return;this.renderStep(step);
    }catch(_){if(seq===this._seq){this._failed=true;this._status.textContent=this.t.failed;this.fallback();}}
    finally{if(seq===this._seq)this.setBusy(false);}
  }
  fallback(){const a=el("a",this.t.fallback);a.href="/config/integrations/integration/dtek_monitor"+(this._entryId?`?config_entry=${encodeURIComponent(this._entryId)}`:"");a.target="_blank";a.rel="noopener noreferrer";this._body.append(a);}
  setBusy(value){this._busy=value;if(this._form)this._form.disabled=value||this._failed;this._close.disabled=value;for(const b of this._actions.querySelectorAll("button"))b.disabled=value||this._failed;this.dispatchEvent(new CustomEvent("options-operation",{bubbles:true,composed:true}));}
  renderStep(step,submitted){
    const same=this._step?.step_id===step.step_id;this._step=step;this._form=null;this._body.replaceChildren();this._actions.replaceChildren();this._status.textContent="";
    this._title.textContent=this.local(`step.${step.step_id}.title`,this.t.title);
    if(step.type==="create_entry"){
      this._title.textContent=this.t.done;this._flowId=null;this._finished=true;this._dirty=false;this._status.textContent=this.t.done;this._close.textContent=this.t.close;return;
    }
    if(step.type==="abort"){
      this._flowId=null;this._dirty=false;this._body.append(this.paragraph(this.local(`abort.${step.reason}`,this.t.failed)));return;
    }
    const description=this.local(`step.${step.step_id}.description`);if(description)this._body.append(this.paragraph(description));
    if(step.type==="menu"){
      this._actions.className="actions menu";
      for(const option of step.menu_options)this._actions.append(this.button(this.local(`step.${step.step_id}.menu_options.${option}`,option),()=>this.submit({next_step_id:option})));
    }else if(step.type==="form"){
      this._actions.className="actions";this._form=el("ha-form");this._form.hass=this._hass;
      this._values=Object.fromEntries(step.data_schema.filter(f=>"default" in f).map(f=>[f.name,structuredClone(f.default)]));
      if(same&&submitted)Object.assign(this._values,submitted);
      this._form.schema=step.data_schema;this._form.data=this._values;this._form.error=step.errors||{};
      this._form.computeLabel=f=>this.local(`step.${step.step_id}.data.${f.name}`,f.name);
      this._form.computeHelper=f=>this.local(`step.${step.step_id}.data_description.${f.name}`);
      this._form.computeError=code=>this.local(`error.${code}`,code);
      this._form.localizeValue=(key,values)=>this._localizeSelector?.(`component.dtek_monitor.selector.${key}`,values);
      this._form.addEventListener("value-changed",e=>{if(this.busy)return;this._values={...e.detail.value};this._form.data=this._values;this._dirty=true;});
      this._body.append(this._form);
      const final=["account_schedule_groups","account_reminder_settings","account_notice_settings","account_check_settings","account_selection"].includes(step.step_id);
      this._actions.append(this.button(this.local(`step.${step.step_id}.submit`,step.step_id==="account_link_confirm"?this.t.link:step.step_id==="account_unlink_confirm"?this.t.unlink:final?this.t.save:this.t.next),()=>{if(this._form.reportValidity())this.submit({...this._values});}));
    }else{this._failed=true;this._status.textContent=this.t.unsupported;this.fallback();}
  }
  async submit(data){
    if(this.busy||this._failed||!this._flowId)return;
    const seq=this._seq;this.setBusy(true);this._discard.hidden=true;
    try{
      const step=await this.api("POST",data);if(seq!==this._seq)return;this.renderStep(step,data);
      if(this._finished){
        this._status.textContent=this.t.reloading;let ready=false;
        for(let i=0;i<20;i++){
          const {config_entry:entry}=await this._hass.callWS({type:"config_entries/get_single",entry_id:this._entryId});
          if(seq!==this._seq)return;
          if(entry.state==="loaded"){ready=true;break;}
          await new Promise(resolve=>setTimeout(resolve,500));
        }
        this._status.textContent=ready?this.t.done:this.t.reloadFailed;
        this._reloadReady=ready;
      }
    }catch(_){if(seq===this._seq){this._failed=true;this._status.textContent=this._finished?this.t.reloadFailed:this.t.uncertain;}}
    finally{if(seq===this._seq)this.setBusy(false);}
  }
  close(discard=false){
    if(this.busy)return;
    if(this._dirty&&!this._finished&&!discard){this._discard.hidden=false;this._discard.querySelector("button").focus();return;}
    this._seq++;this._cleanup();this.dispatchEvent(new CustomEvent("options-closed",{detail:{saved:this._finished,ready:this._reloadReady},bubbles:true,composed:true}));
  }
}
if(!customElements.get("dtek-account-options"))customElements.define("dtek-account-options",DtekAccountOptions);
