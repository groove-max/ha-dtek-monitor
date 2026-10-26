import { zoneKey, isUkrainian,  embeddedCSS, date } from "./account-ui.js?v=2.0.0-rc5";
import { accountCardEditor } from "./account-card-editor.js?v=2.0.0-rc5";
/* DTEK account history. No external assets or credentials in the browser. */
import { accountNumber, cabinetLink } from "./account-number.js?v=2.0.0-rc5";
const words = {
  en: {
    photo: "📷 Photo available in DTEK", photoOpen: "Open photos in the DTEK cabinet", controller: "Controller comment",
    compare: "Compare with previous year", comparison: "Consumption for matching periods", pairNote: "Only months closed and published in both years are included. Partial totals cover the listed months, not the whole year or season. Winter here means January, February and December of the same calendar year. Negative corrections remain included.", yearTotal: "Year", winter: "Winter", spring: "Spring", summer: "Summer", autumn: "Autumn", coverage: "Included months", difference: "Difference", complete: "Complete", partial: "Partial", title: "DTEK account history", year: "Year", refresh: "Refresh history", loading: "Loading…",
    consumption: "Monthly consumption", readings: "Meter readings", period: "Month", value: "Value",
    zone: "Tariff scale", energy: "Energy type", source: "Source", status: "Status", date: "Date (Kyiv)",
    active: "Active", inactive: "Inactive", blocked: "Blocked", unknown: "Unknown",
    showAll: "Show all DTEK records", hiddenInactive: "Inactive records hidden", onlyInactive: "Only inactive records are available. Select ‘Show all DTEK records’ to view them.",
    missing: "No data", open: "Open month", future: "Future month", closed: "Closed month",
    fetched: "Data fetched", empty: "No readings returned for this year.", previous: "Previous", next: "Next",
    note: "Only closed months are plotted. Missing periods are gaps. Negative values are retained as reported by DTEK.",
    scope: "History belongs to the account. DTEK does not identify the meter for each old record; readings are not subtracted to calculate consumption.",
    api: "This DTEK service is unavailable or incompatible. Open Settings → System → Repairs for updates and support.", consumptionUnavailable: "Monthly consumption is temporarily unavailable. Reading history remains available.", comparisonUnavailable: "Comparison is unavailable because consumption could not be loaded for one of the years.",
    failure: "Could not load history. Try again later.", auth: "Reauthenticate the personal account in Settings → Devices & services.",
    limited: "Please wait before trying again (at least 60 seconds after a request; longer if DTEK limits requests).",
    denied: "This account is unavailable or you do not have permission to view it.",
    stale: "Refresh failed. The previously fetched result remains displayed with its original date.",
    total: "Total", page: "Page", general: "Single zone", day: "Day", night: "Night",
  },
  uk: {
    photo: "📷 ДТЕК має фото", photoOpen: "Відкрити фото в кабінеті ДТЕК", controller: "Коментар контролера",
    compare: "Порівняти з попереднім роком", comparison: "Споживання за однакові періоди", pairNote: "Враховано лише місяці, закриті та опубліковані в обох роках. Часткові підсумки охоплюють перелічені місяці, а не весь рік чи сезон. Зима тут — січень, лютий і грудень одного календарного року. Від’ємні коригування збережено.", yearTotal: "Рік", winter: "Зима", spring: "Весна", summer: "Літо", autumn: "Осінь", coverage: "Враховані місяці", difference: "Різниця", complete: "Повний", partial: "Частковий", title: "Історія особового рахунку ДТЕК", year: "Рік", refresh: "Оновити історію", loading: "Завантаження…",
    consumption: "Місячне споживання", readings: "Покази лічильника", period: "Місяць", value: "Значення",
    zone: "Тарифна шкала", energy: "Тип енергії", source: "Джерело", status: "Статус", date: "Дата (Київ)",
    active: "Активний", inactive: "Неактивний", blocked: "Заблокований", unknown: "Невідомо",
    showAll: "Показати всі записи ДТЕК", hiddenInactive: "Приховано неактивних записів", onlyInactive: "Є лише неактивні записи. Увімкніть «Показати всі записи ДТЕК», щоб переглянути їх.",
    missing: "Немає даних", open: "Незакритий місяць", future: "Майбутній місяць", closed: "Закритий місяць",
    fetched: "Дані отримано", empty: "За цей рік показів не отримано.", previous: "Назад", next: "Далі",
    note: "Графік містить лише закриті місяці. Пропуски означають відсутність даних. Від'ємні значення збережено так, як їх надає ДТЕК.",
    scope: "Історія належить рахунку. ДТЕК не вказує лічильник для кожного старого запису; різниця показів не використовується для обчислення споживання.",
    api: "Цей сервіс ДТЕК недоступний або несумісний. Відкрийте Налаштування → Система → Виправлення для оновлень і підтримки.", consumptionUnavailable: "Місячне споживання тимчасово недоступне. Історія показів залишається доступною.", comparisonUnavailable: "Порівняння недоступне: не вдалося завантажити споживання за один із років.",
    failure: "Не вдалося завантажити історію. Спробуйте пізніше.", auth: "Виконайте повторний вхід у кабінет: Налаштування → Пристрої та служби.",
    limited: "Зачекайте перед повторною спробою (щонайменше 60 секунд після запиту; довше за обмежень ДТЕК).",
    denied: "Рахунок недоступний або у вас немає дозволу на перегляд.",
    stale: "Оновлення не вдалося. Показано попередній результат із початковою датою отримання.",
    total: "Разом", page: "Сторінка", general: "Одна зона", day: "День", night: "Ніч",
  },
};
const css = `
  :host { display:block; container-type:inline-size; } ha-card { padding:20px; overflow:hidden; }
  h2 { font-size:1.3em; margin:0 0 16px; } h3 { font-size:1.08em; margin:20px 0 12px; }
  .controls { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  label { display:flex; align-items:center; gap:8px; }
  select, button { font:inherit; color:var(--primary-text-color); background:var(--card-background-color); border:1px solid var(--divider-color,#aaa); border-radius:8px; padding:8px 12px; min-height:40px; }
  button { cursor:pointer; } button:disabled { opacity:.5; cursor:default; }
  p { line-height:1.5; margin:12px 0; } .muted { color:var(--secondary-text-color); font-size:.9em; }
  .error { color:var(--error-color,#b71c1c); } .scroll { overflow-x:auto; }
  table { border-collapse:collapse; width:100%; font-size:.9em; }
  th,td { padding:9px 8px; border-bottom:1px solid var(--divider-color,#ddd); text-align:start; vertical-align:top; }
  th { font-weight:600; white-space:nowrap; } .numeric { font-variant-numeric:tabular-nums; white-space:nowrap; }
  .inactive,.blocked { color:var(--secondary-text-color); }
  .pill { padding:3px 6px; border:1px solid var(--divider-color,#aaa); border-radius:6px; white-space:nowrap; }
  .pagination { display:flex; gap:12px; align-items:center; justify-content:flex-end; margin-top:12px; }
  svg { display:block; width:100%; min-width:300px; height:auto; } svg text { font:16px sans-serif; fill:var(--secondary-text-color); }
  .bar { fill:var(--primary-color,#0288d1); } .negative { fill:var(--warning-color,#c67a00); }
  .axis { stroke:var(--divider-color,#aaa); stroke-width:1; }
  @container(max-width:500px) {
    table.readings thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
    table.readings,table.readings tbody{display:block}
    table.readings tr{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:14px 0;border-bottom:1px solid var(--divider-color,#ddd)}
    table.readings td{display:block;border:0;padding:0;white-space:normal;overflow-wrap:anywhere}
    table.readings td::before{content:attr(data-label);display:block;font-size:.8em;color:var(--secondary-text-color);margin-bottom:4px}
    table.readings td:nth-child(2){font-size:1.1em;font-weight:600}
    table.readings td:nth-child(5){display:none}
    .pagination{justify-content:space-between}
  }
  @media(max-width:500px) { ha-card {padding:14px;} h2 {font-size:1.15em;} }
`;
function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function svgElement(tag, attrs = {}, text) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  if (text !== undefined) el.textContent = text;
  return el;
}
class DtekAccountHistoryCard extends HTMLElement {
  static get workspaceVersion() { return 1; }
  constructor() { super(); this.attachShadow({mode:"open"}); this._seq=0; this._page=0; this._showInactive=false; }
  setConfig(config) {
    if (!config.entity || typeof config.entity !== "string") throw new Error("Specify an account sensor in entity.");
    const year = config.year ?? Number(new Intl.DateTimeFormat("en", {year:"numeric", timeZone:"Europe/Kyiv"}).format(new Date()));
    if (!Number.isInteger(year) || year < 2000 || year > Number(new Intl.DateTimeFormat("en", {year:"numeric", timeZone:"Europe/Kyiv"}).format(new Date()))) throw new Error("Invalid history year.");
    const changed = !this._config || config.entity !== this._config.entity || config.year !== this._config.year;
    this._config = {...config}; this.toggleAttribute("embedded", !!config.embedded);
    if (changed) { this._year=year; this._compare=false; this._showInactive=false; this._data=null; this._error=null; this._seq++; this._busy=false; this._page=0; }
    this._render();
    if (changed && this.isConnected && this._hass) this._load(false);
  }
  set hass(hass) {
    const changedUser = this._hass && (this._hass.user?.id !== hass.user?.id || this._hass.connection !== hass.connection);
    const initial = !this._hass || changedUser;
    if (changedUser) { this._seq++; this._showInactive=false; this._page=0; this._data=null; this._error=null; this._busy=false; this._render(); }
    const lang = isUkrainian(hass.language) ? "uk" : "en";
    const languageChanged = lang !== this._lang;
    this._hass=hass; this._lang=lang;
    if (languageChanged) this._render();
    if (initial && this.isConnected && this._config) this._load(false);
  }
  connectedCallback() { if (this._hass && this._config) this._load(false); }
  disconnectedCallback() { this._seq++; this._busy=false; }
  getCardSize() { return 12; }
  static getConfigElement() { return accountCardEditor(); }
  static getStubConfig() { return {entity:"sensor.example_account_data_updated"}; }
  get t() { return words[this._lang || "en"]; }
  format(value) { return value === null || value === undefined ? "—" : new Intl.NumberFormat(this._lang || "en", {maximumFractionDigits:3}).format(Number(value)); }
  zone(value) { return ({GENERAL:this.t.general,DAY:this.t.day,NIGHT:this.t.night})[zoneKey(value)] || value; }
  async _load(force) {
    if (!this._hass || !this._config || (this._busy && this._loadingYear===this._year)) return;
    const sequence=++this._seq, year=this._year, entity=this._config.entity;
    this._busy=true; this._loadingYear=year; this._error=null; this._render();
    try {
      const data=await this._hass.callWS({type:"dtek_monitor/account_history",entity_id:entity,year,force,compare:!!this._compare});
      if (sequence!==this._seq || !this.isConnected) return;
      if (data.year!==year || !Array.isArray(data.months) || !Array.isArray(data.readings)) throw new Error("Invalid history response");
      this._data=data; this._page=0;
    } catch (err) {
      if (sequence!==this._seq || !this.isConnected) return;
      this._error = err.code === "api_changed" ? "api" : err.code === "rate_limited" ? "limited" : err.code === "auth_required" ? "auth" : ["unauthorized","not_available"].includes(err.code) ? "denied" : "failure";
      if (this._error === "denied" || this._error === "auth") this._data=null;
    } finally {
      if (sequence===this._seq && this.isConnected) { this._busy=false; this._render(); }
    }
  }
  _render() {
    if (!this._config) return;
    const t=this.t, root=this.shadowRoot;
    const opened = [...root.querySelectorAll("details")].map(d => d.open);
    root.replaceChildren(element("style",css + embeddedCSS));
    const card=element("ha-card"); root.append(card);
    card.append(element("h2",this._config.title || (this._config.view === "readings" ? t.readings : this._config.view === "consumption" ? t.consumption : t.title), "card-title"));
    if (!this._config.embedded) card.append(accountNumber(this._hass, this._config.entity));
    const controls=element("div",undefined,"controls"), label=element("label",t.year), select=element("select");
    select.setAttribute("aria-label",t.year);
    const current=Number(new Intl.DateTimeFormat("en",{year:"numeric",timeZone:"Europe/Kyiv"}).format(new Date()));
    for(let year=current;year>=2000;year--) { const opt=element("option",String(year));opt.value=String(year);select.append(opt); }
    select.value=String(this._year);
    select.addEventListener("change",()=>{ this._year=Number(select.value);this._compare=false;this._data=null;this._page=0;this._load(false); });
    label.append(select);controls.append(label);
    const refresh=element("button",this._busy?t.loading:t.refresh);refresh.disabled=this._busy;refresh.addEventListener("click",()=>this._load(true));controls.append(refresh);
    const compare=element("button",t.compare);compare.disabled=this._busy||this._year<=2000;compare.addEventListener("click",()=>{this._compare=true;this._load(false);});if (this._config.view !== "readings") controls.append(compare);card.append(controls);
    if(this._error) { const error=element("p",t[this._error],"error");error.setAttribute("role","alert");card.append(error);if(this._data)card.append(element("p",t.stale,"muted")); }
    if(!this._data || this._data.year!==this._year) return;
    const data=this._data;
    const fetched = new Intl.DateTimeFormat(this._lang || "en",{dateStyle:"medium",timeStyle:"short",timeZone:"Europe/Kyiv"}).format(new Date(data.fetched_at));
    card.append(element("p",`${t.fetched}: ${fetched} (Europe/Kyiv)`,"muted"));
    if (this._config.view !== "readings") {
    card.append(element("h3",`${t.consumption} · ${data.year}`));
    if (data.unavailable?.includes("meter_consumption")) { card.append(element("p",t.consumptionUnavailable,"error")); } else {
    card.append(this._chart(data.months));card.append(element("p",t.note,"muted"));
    const details=element("details"),summary=element("summary",`${t.consumption} · kWh`);details.append(summary);
    const monthTable=this._table([t.period,t.total,t.zone,t.status]);
    for(const month of data.months) {
      const row=element("tr");row.append(element("td",month.period),element("td",this.format(month.value),"numeric"));
      const zones=Object.entries(month.zones).map(([key,value])=>`${this.zone(key)}: ${this.format(value)}`).join("; ");
      row.append(element("td",zones||"—"),element("td",t[month.status]||month.status));monthTable.body.append(row);
    }
    details.append(monthTable.wrap);card.append(details);
    }
    if(data.comparison_unavailable) card.append(element("p",t.comparisonUnavailable,"muted"));
    if(data.comparison){const c=data.comparison;card.append(element("h3",`${t.comparison} · ${c.year} / ${c.previous_year}`),element("p",t.pairNote,"muted"));
      const totals=this._table([t.period,`${c.year} · kWh`,`${c.previous_year} · kWh`,`${t.difference} · kWh`,t.coverage]);
      for(const p of c.periods){const row=element("tr");for(const value of [p.period==="year"?t.yearTotal:t[p.period],this.format(p.current),this.format(p.previous),this.format(p.difference),`${p.complete?t.complete:t.partial}: ${p.months.map(m=>String(m).padStart(2,"0")).join(", ")||"—"}`])row.append(element("td",value));totals.body.append(row);}card.append(totals.wrap);
      const monthly=this._table([t.period,String(c.year),String(c.previous_year),`${t.difference} · kWh`]);for(const p of c.months){const row=element("tr");for(const value of [String(p.month).padStart(2,"0"),this.format(p.current),this.format(p.previous),p.comparable?this.format(p.difference):t.missing])row.append(element("td",value));monthly.body.append(row);}card.append(monthly.wrap);
      card.append(element("p",`${t.fetched} ${c.previous_year}: ${new Intl.DateTimeFormat(this._lang||"en",{dateStyle:"medium",timeStyle:"short",timeZone:"Europe/Kyiv"}).format(new Date(c.fetched_at.previous))} (Europe/Kyiv)`,"muted"));
    }
    }
    if (this._config.view === "consumption") { [...root.querySelectorAll("details")].forEach((d,i) => d.open=opened[i]||false); return; }
    const inactiveCount=data.readings.filter(r=>r.status==="inactive").length;
    const readings=data.readings.filter(r=>this._showInactive||r.status!=="inactive");
    card.append(element("h3",`${t.readings} · ${readings.length}`));card.append(element("p",t.scope,"muted"));
    const filter=element("label"),showAll=element("input");showAll.type="checkbox";showAll.checked=this._showInactive;
    showAll.addEventListener("change",()=>{this._showInactive=showAll.checked;this._page=0;this._render();});
    filter.append(showAll,document.createTextNode(t.showAll));card.append(filter);
    if(!this._showInactive&&inactiveCount)card.append(element("p",`${t.hiddenInactive}: ${inactiveCount}`,"muted"));
    if(!readings.length) {card.append(element("p",data.readings.length?t.onlyInactive:t.empty));return;}
    if(readings.some(r=>r.has_photo))card.append(cabinetLink(this._hass,this._config.entity,t.photoOpen));
    const table=this._table([t.date,t.value,t.status,t.zone,t.energy,t.source]);
    table.wrap.querySelector("table").classList.add("readings");
    const pageSize=10, pages=Math.ceil(readings.length/pageSize);this._page=Math.min(this._page,pages-1);
    for(const record of readings.slice(this._page*pageSize,(this._page+1)*pageSize)) {
      const row=element("tr",undefined,record.status);
      const local=date(record.date_time, this._lang, true);
      row.append(element("td",local,"numeric"),element("td",this.format(record.value),"numeric"));
      const status=element("td");status.append(element("span",t[record.status]||t.unknown,"pill"));row.append(status,element("td",this.zone(record.zone)),element("td",record.energy),element("td",record.source||"—"));
      if(record.has_photo)status.append(element("small",t.photo));
      if(record.controller_note)row.lastChild.append(element("p",`${t.controller}: ${record.controller_note}`));
      table.body.append(row);
    }
    card.append(table.wrap);
    const pagination=element("div",undefined,"pagination"), prev=element("button",t.previous), next=element("button",t.next);
    prev.disabled=this._page===0;next.disabled=this._page>=pages-1;
    prev.addEventListener("click",()=>{this._page--;this._render();});next.addEventListener("click",()=>{this._page++;this._render();});
    pagination.append(prev,element("span",`${t.page} ${this._page+1} / ${pages}`),next);card.append(pagination);
    [...root.querySelectorAll("details")].forEach((d,i) => d.open=opened[i]||false);
    for (const table of root.querySelectorAll("table")) { const labels=[...table.querySelectorAll("th")].map(h=>h.textContent); for (const row of table.querySelectorAll("tbody tr")) [...row.children].forEach((cell,i)=>cell.dataset.label=labels[i]); }
  }
  _table(headers) {
    const wrap=element("div",undefined,"scroll"),table=element("table"),head=element("thead"),tr=element("tr"),body=element("tbody");
    for(const title of headers)tr.append(element("th",title));head.append(tr);table.append(head,body);wrap.append(table);return {wrap,body};
  }
  _chart(months) {
    const wrap=element("div",undefined,"scroll"),svg=svgElement("svg",{viewBox:"0 0 600 240",role:"img","aria-label":`${this.t.consumption}, kWh`});
    const values=months.filter(m=>m.status==="closed" && m.value!==null).map(m=>Number(m.value));
    const min=Math.min(0,...values),max=Math.max(0,...values),span=max-min||1,y=v=>195-(v-min)/span*160,zero=y(0);
    svg.append(svgElement("line",{x1:45,y1:zero,x2:590,y2:zero,class:"axis"}));
    for(const value of new Set([min,max,0])) svg.append(svgElement("text",{x:40,y:y(value)+4,"text-anchor":"end"},this.format(value)));
    svg.append(svgElement("text",{x:45,y:18},"kWh"));
    months.forEach((month,i)=>{
      const x=53+i*44;
      svg.append(svgElement("text",{x:x+13,y:225,"text-anchor":"middle"},month.period.slice(5)));
      if(month.status!=="closed" || month.value===null){ svg.append(svgElement("text",{x:x+13,y:zero-8,"text-anchor":"middle"},"—"));return; }
      const value=Number(month.value),top=Math.min(y(value),zero),height=Math.max(Math.abs(y(value)-zero),1);
      const bar=svgElement("rect",{x,y:top,width:26,height,class:value<0?"bar negative":"bar","data-period":month.period,tabindex:0});
      const description=`${month.period}: ${this.format(month.value)} kWh`;bar.setAttribute("aria-label",description);bar.append(svgElement("title",{},description));svg.append(bar);
    });
    wrap.append(svg);return wrap;
  }
}
if(!customElements.get("dtek-account-history-card")) customElements.define("dtek-account-history-card",DtekAccountHistoryCard);
window.customCards=window.customCards||[];
if (!window.customCards.some(card => card.type === 'dtek-account-history-card')) window.customCards.push({type:'dtek-account-history-card',name:"DTEK account history",description:"Dated meter readings and monthly consumption for a personal account."});
