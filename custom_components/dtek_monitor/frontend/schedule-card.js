import { isUkrainian, cabinetGroupNotice, embeddedCSS } from "./account-ui.js?v=2.0.0-rc5";
import "./schedule-grid.js?v=2.0.0-rc5";
/* Publication status remains visible when HA's calendar cannot show events. */
class DtekScheduleCard extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:"open"}); this._seq=0;
    this.shadowRoot.innerHTML=`<style>
      :host{display:block}ha-card{overflow:hidden}h2{overflow-wrap:anywhere;font-size:1.2em;margin:0;padding:16px 16px 0}
      .status,.group-notice{padding:16px;line-height:1.5;overflow-wrap:anywhere}
      .error{color:var(--error-color,#b22)}small{display:block;color:var(--secondary-text-color);margin-top:4px}
    .views{display:flex;gap:8px;padding:0 16px 14px}.views button{font:inherit;min-height:40px;padding:8px 14px;border-radius:9px;border:1px solid var(--divider-color,#bcc);color:var(--primary-text-color);background:var(--card-background-color);cursor:pointer}.views button[aria-pressed=true]{background:var(--primary-color,#1685a6);color:var(--text-primary-color,#fff)}[hidden]{display:none!important}
    :host([embedded]) .status,:host([embedded]) .group-notice{padding:0 0 16px}:host([embedded]) dtek-schedule-grid{--dtek-grid-padding:0}
    ${embeddedCSS}</style><ha-card><h2 class="card-title"></h2><div class="status" role="status"></div><div class="views"><button class="grid-view" type="button"></button><button class="list-view" type="button"></button></div><dtek-schedule-grid></dtek-schedule-grid><div class="calendar"></div></ha-card>`;
    this._view="grid";
    for(const view of ["grid","list"])this.shadowRoot.querySelector(`.${view}-view`).onclick=()=>{this._view=view;this._render();};
  }
  setConfig(config) {
    if(typeof config.status_entity!=="string" || !Array.isArray(config.entities)
      || !config.entities.length || config.entities.some(e=>typeof e!=="string" || !e.startsWith("calendar.")))
      throw new Error("Set status_entity and calendar entities");
    this._config={...config,entities:[...config.entities]}; this.toggleAttribute("embedded",!!config.embedded); this._key=null; this._view=config.view || "grid"; this._render();
  }
  set hass(value) { this._hass=value; this._render(); }
  getCardSize() { return 6; }
  disconnectedCallback() { this._seq++; this._key=null; }
  connectedCallback() { this._render(); }
  _render() {
    if(!this._hass || !this._config) return;
    const uk=isUkrainian(this._hass.language),state=this._hass.states[this._config.status_entity];
    let status=state?.state || "unknown";
    if(["selected","auto_selected","cabinet_selected"].includes(status))status=state.attributes.schedule_status || "current";
    if(status.startsWith("schedule_"))status=status.slice(9);
    const words=uk ? {
      current:"Графік на сьогодні опубліковано.",empty:"Сьогодні планових відключень немає — графік перевірено.",
      missing:"ДТЕК відповідає, але повного графіка на сьогодні ще немає.",
      unpublished:"ДТЕК призупинив публікацію графіків.",unsupported:"Графік цього оператора не підтримується.",
      partial:"Графік на сьогодні неповний. Відсутні дані не означають відсутність відключень.",
      forecast:"Доступний лише прогноз. Планові відключення на сьогодні не підтверджені.",
      error:"Не вдалося отримати дані ДТЕК. Інтеграція повторить запит автоматично.",
      address_pending:"Підбираємо будинок за адресою рахунку…",
      address_confirmation:"Уточніть будинок у налаштуванні «Будинок і група відключень».",
      address_lookup_unavailable:"Довідник адрес ДТЕК тимчасово недоступний. Автопідбір повториться; дані рахунку працюють окремо.",
      no_address:"Прив’яжіть адресу будинку в налаштуваннях особистого кабінету.",
      not_selected:"У будинку кілька груп або групу ще не підтверджено. Оберіть свою в налаштуваннях.",
      cabinet_unavailable:"Кабінет не підтвердив актуальну групу квартири. Можна обрати її вручну; графіки будинку доступні окремо.",
      cabinet_group_mismatch:"Група з кабінету не збігається з групами будинку. Перевірте адресу й оберіть групу вручну.",
      group_unavailable:"ДТЕК більше не підтверджує обрану групу для будинку. Перевірте особистий вибір.",
      labels_hidden:"ДТЕК приховав групи. Особистий графік поки не визначено.",
      address_unavailable:"Дані адреси зараз недоступні. Перевірте підключення будинку.",
      unknown:"Стан графіка поки невідомий.", unavailable:"Дані інтеграції зараз недоступні.",
      frontend:"Не вдалося відкрити календар на панелі. Оновіть сторінку.",
    } : {
      current:"Today's schedule is published.",empty:"No planned outages today — the schedule is verified.",
      missing:"DTEK responded, but a complete schedule for today is not available yet.",
      unpublished:"DTEK has paused schedule publication.",unsupported:"This operator's schedule is not supported.",
      partial:"Today's schedule is incomplete. Missing data does not mean no outages.",
      forecast:"Only a forecast is available. Today's planned outages are unconfirmed.",
      error:"Could not fetch DTEK data. The integration will retry automatically.",
      address_pending:"Finding the building for this account…",
      address_confirmation:"Confirm the building in Building and outage group settings.",
      address_lookup_unavailable:"The DTEK address directory is temporarily unavailable. Matching will retry; account data works independently.",
      no_address:"Link a building address in the personal account settings.",
      not_selected:"The building has multiple or unverified groups. Choose yours in settings.",
      cabinet_unavailable:"The cabinet could not verify your apartment group. You can select it manually; building schedules remain separate.",
      cabinet_group_mismatch:"The cabinet group does not match the building groups. Check the address and select your group manually.",
      group_unavailable:"DTEK no longer confirms the selected group for this building. Review your selection.",
      labels_hidden:"DTEK has hidden group labels. Your personal schedule is not determined yet.",
      address_unavailable:"Address data is unavailable. Check the building connection.",
      unknown:"The schedule status is not known yet.",unavailable:"Integration data is unavailable.",
      frontend:"Could not open the dashboard calendar. Reload the page.",
    };
    this.shadowRoot.querySelector("h2").textContent=this._config.title || (uk?"Графік ДТЕК":"DTEK schedule");
    const feedback=this.shadowRoot.querySelector(".status");
    // The grid reports its selected date, independently of today's list status.
    feedback.hidden=this._view==="grid";
    feedback.textContent=words[status] || words.unknown;
    let notice=this.shadowRoot.querySelector(".group-notice");
    if(!notice) {
      notice=document.createElement("div");notice.className="group-notice";
      notice.setAttribute("role","status");feedback.after(notice);
    }
    notice.textContent=cabinetGroupNotice(state?.attributes,this._hass.language);
    notice.hidden=!notice.textContent;
    if(state?.attributes.selection_source==="cabinet") {
      const source=document.createElement("small");
      source.textContent=uk?"Групу визначено за особовим рахунком ДТЕК.":"Group identified from your DTEK personal account.";
      feedback.append(source);
    }
    feedback.classList.toggle("error",status==="error");
    if(state?.attributes.status_date) {
      const small=document.createElement("small");
      small.textContent=`${state.attributes.status_date} · Europe/Kyiv`;feedback.append(small);
    }
    const available=this._config.entities.filter(e=>["on","off"].includes(this._hass.states[e]?.state));
    const allowed=["current","empty","partial","forecast"].includes(status);
    const entities=allowed && this._view==="list" ? available : [], key=JSON.stringify(entities);
    if(key!==this._key) {
      this._key=key;const seq=++this._seq;this._calendar=null;
      this.shadowRoot.querySelector(".calendar").replaceChildren();
      if(entities.length)this._loadCalendar(entities,seq,words.frontend);
    }
    if(this._calendar)this._calendar.hass=this._hass;
    this.shadowRoot.querySelector(".views").hidden=!!this._config.hide_view_switcher;
    const grid=this.shadowRoot.querySelector("dtek-schedule-grid");grid.hidden=this._view!=="grid";
    if(this._view==="grid")grid.setContext(this._hass,this._config.status_entity);
    this.shadowRoot.querySelector(".calendar").hidden=this._view!=="list";
    for(const view of ["grid","list"]){const b=this.shadowRoot.querySelector(`.${view}-view`);b.textContent=uk?(view==="grid"?"Сітка":"Список"):(view==="grid"?"Grid":"List");b.setAttribute("aria-pressed",String(this._view===view));}
  }
  async _loadCalendar(entities,seq,error) {
    try {
      const helpers=await window.loadCardHelpers();
      if(seq!==this._seq || !this.isConnected)return;
      const card=helpers.createCardElement({type:"calendar",entities,initial_view:"listWeek"});
      card.hass=this._hass;this._calendar=card;
      this.shadowRoot.querySelector(".calendar").replaceChildren(card);
    } catch (_) {
      if(seq!==this._seq || !this.isConnected)return;
      const message=document.createElement("p");message.className="status error";message.textContent=error;
      this.shadowRoot.querySelector(".calendar").replaceChildren(message);
    }
  }
}
if(!customElements.get("dtek-schedule-card"))customElements.define("dtek-schedule-card",DtekScheduleCard);
window.customCards=window.customCards || [];
if (!window.customCards.some(card => card.type === 'dtek-schedule-card')) window.customCards.push({type:'dtek-schedule-card',name:"DTEK schedule",description:"Schedule with publication and connection status"});
