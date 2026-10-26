import { isUkrainian, date, embeddedCSS } from "./account-ui.js?v=2.0.0-rc5";
import { cabinetLink } from "./account-number.js?v=2.0.0-rc5";
const words={
 en:{title:"DTEK documents",refresh:"Refresh documents",loading:"Checking documents…",empty:"DTEK has not returned any documents for this account. This does not confirm completion of a controller inspection.",note:"Documents published by DTEK. Downloading an act does not sign it or acknowledge agreement with it.",download:"Download PDF",checked:"Checked",unavailable:"Documents are temporarily unavailable. Try again later or open the DTEK cabinet.",api_changed:"The document service is incompatible. Check Home Assistant Repairs for updates and support.",document_format:"This document format is not supported here. Open it in the DTEK cabinet.",document_too_large:"This document exceeds 2 MB. Download it in the DTEK cabinet.",document_missing:"This document is no longer listed. Refresh the list.",cabinet:"Open DTEK cabinet"},
 uk:{title:"Документи ДТЕК",refresh:"Оновити документи",loading:"Перевіряємо документи…",empty:"ДТЕК поки не повернув документів для цього рахунку. Це не підтверджує завершення перевірки контролера.",note:"Документи, опубліковані ДТЕК. Завантаження акта не означає його підписання чи згоди з ним.",download:"Завантажити PDF",checked:"Перевірено",unavailable:"Документи тимчасово недоступні. Спробуйте пізніше або відкрийте кабінет ДТЕК.",api_changed:"Сервіс документів несумісний. Відкрийте «Виправлення» у HA для оновлень і підтримки.",document_format:"Цей формат документа тут не підтримується. Відкрийте його в кабінеті ДТЕК.",document_too_large:"Документ перевищує 2 МБ. Завантажте його в кабінеті ДТЕК.",document_missing:"Документ більше не відображається. Оновіть список.",cabinet:"Відкрити кабінет ДТЕК"}
};
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
class DtekDocuments extends HTMLElement {
 constructor(){super();this.attachShadow({mode:"open"});this._seq=0;}
 setConfig(config){if(this._config?.entity!==config.entity){this._seq++;this._data=null;this._error=null;this._busy=false;this._loaded=false;}this._config={...config};this.render();}
 set hass(hass){const changed=this._hass&&(this._hass.user?.id!==hass.user?.id||this._hass.user?.is_admin!==hass.user?.is_admin||this._hass.connection!==hass.connection);this._hass=hass;if(changed){this._seq++;this._data=null;this._error=null;this._loaded=false;this._busy=false;}this.render();if(!this._loaded&&this._config&&this.isConnected)this.load();}
 connectedCallback(){if(this._hass&&!this._loaded)this.load();}
 disconnectedCallback(){this._seq++;this._loaded=false;this._busy=false;this._data=null;}
 async load(id){if(this._busy||!this._hass)return;const seq=++this._seq;this._busy=true;this._loaded=true;this._error=null;this.render();
  try{const data=await this._hass.callWS({type:"dtek_monitor/account_documents",entity_id:this._config.entity,...(id?{document_id:id}:{})});if(seq!==this._seq||!this.isConnected)return;
   if(id){if(data.mime_type!=="application/pdf"||typeof data.data!=="string"||data.data.length>3*1024*1024)throw {code:"document_format"};const raw=Uint8Array.from(atob(data.data),c=>c.charCodeAt(0));const url=URL.createObjectURL(new Blob([raw],{type:"application/pdf"}));const a=el("a");a.href=url;a.download=data.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}else this._data=data;
  }catch(error){if(seq===this._seq){this._error=error?.code||"unavailable";if(!id)this._data=null;}}
  finally{if(seq===this._seq){this._busy=false;this.render();}}
 }
 render(){if(!this._config)return;const t=words[isUkrainian(this._hass?.language)?"uk":"en"];
  // HA publishes unrelated state changes frequently. Keep the permission-checked
  // footer connected, and touch the document body only when its view changes.
  if(!this._body){const style=el("style");style.textContent=embeddedCSS+`:host{display:block}p{line-height:1.5}ul{padding:0;list-style:none}li{padding:12px 0;border-bottom:1px solid var(--divider-color,#ddd);overflow-wrap:anywhere}button{font:inherit;border:1px solid var(--divider-color,#aaa);border-radius:8px;padding:10px;margin:6px 0;color:var(--primary-text-color);background:var(--card-background-color,#fff);cursor:pointer}button:disabled{opacity:.5}small{display:block;color:var(--secondary-text-color)}`;this._body=el("section");this.shadowRoot.append(style,this._body);}
  if(this._hass){if(!this._cabinet){this._cabinet=cabinetLink(this._hass,this._config.entity,t.cabinet);this.shadowRoot.append(this._cabinet);}else{this._cabinet.hass=this._hass;this._cabinet.entity=this._config.entity;this._cabinet.label=t.cabinet;}}
  const key=JSON.stringify([this._config.entity,this._hass?.language,this._busy,this._error,this._data]);
  if(key===this._viewKey)return;this._viewKey=key;
  const card=el("section");
  card.append(el("p",t.note));const refresh=el("button",this._busy?t.loading:t.refresh);refresh.disabled=this._busy;refresh.onclick=()=>this.load();card.append(refresh);
  if(this._error){const error=el("p",t[this._error]||t.unavailable);error.setAttribute("role","alert");card.append(error);}
  if(this._data){const ul=el("ul");for(const row of this._data.documents){const li=el("li"),name=el("div",row.name),button=el("button",t.download);button.setAttribute("aria-label",`${t.download}: ${row.name}`);button.disabled=this._busy;button.onclick=()=>this.load(row.id);li.append(name,button);ul.append(li);}card.append(this._data.documents.length?ul:el("p",t.empty),el("small",`${t.checked}: ${date(this._data.checked_at,this._hass?.language,true)}`));}
  this._body.replaceChildren(card);
 }
}
if(!customElements.get("dtek-account-documents"))customElements.define("dtek-account-documents",DtekDocuments);
