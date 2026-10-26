import { zoneKey, isUkrainian,  date, number, embeddedCSS } from "./account-ui.js?v=2.0.0-rc5";
/* Local references only. No operation in this editor submits readings to DTEK. */
const words = {
  en: {
    advanced: "Advanced settings", calibration: "Calibrate against the official meter", calibrationHelp: "Read the official meter now. The home sensor reading will be captured when you review the correction.", locked: "Wait for the readings operation to finish.",
    title: "Home Assistant energy source", load: "Load / refresh energy source", link: "Link an energy sensor", replace: "Replace binding", cancel: "Cancel",
    mode: "Reading mode", offset: "Estimate from a secondary meter", direct: "Read the official meter directly",
    freshness: "Source availability check", reported: "Require recent reports", availability: "Trust the integration's availability status",
    availabilityHelp: "For sources that report only when the counter changes. Use only if the device integration marks the sensor unavailable on connection loss. A stuck numeric state cannot be detected in this mode. The age limit does not apply.",
    entity: "Cumulative energy sensor", age: "Maximum data age (minutes)", power: "Maximum plausible input power (kW)",
    actual: "Actual official meter reading (kWh)", general: "Single zone", day: "Day", night: "Night",
    review: "Review binding", calibrate: "Review new reference pair", save: "Save local reference", remove: "Remove binding",
    checked: "The source measures this account's grid import and the correct tariff zone. For an estimate, I verified that both readings describe the same moment.",
    reviewHelp: "Check both readings and their time. With availability-based checking, verify the current physical reading even when the last HA report is older. This saves a local reference only; nothing is sent to DTEK. Confirmation expires after three minutes.",
    help: "Choose a cumulative grid-import energy sensor for this apartment. A sensor after an inverter, for another apartment or for only part of the loads is unsuitable. Each tariff zone needs its own sensor.",
    use: "Use proposed readings in the form", proposal: "Proposed cumulative meter reading", source: "Source reading", actualLabel: "Official reading", correction: "Correction", at: "Source sample received by HA",
    reference: "Saved reference", saved: "Local reference saved. Future estimates include this correction; submission is a separate action.",
    removeCheck: "Remove this local binding and its calibration history. This does not change DTEK readings.",
    staleHelp: "A received HA state is not proof of a fresh device measurement. Check that the device keeps counting and reports reliably. A reset or jump requires a new verified reference.",
    source_stale: "Source data is too old. Refresh the device before using it.", source_unavailable: "The source is unavailable; missing data is not zero consumption.",
    source_reset: "The counter decreased. Verify the meter and create a new reference pair.", source_changed: "The source identity or unit changed. Replace the binding after checking the meter.",
    source_jump: "An implausible increase was detected. Check the source and create a new reference pair.",
    energy_changed: "The reference, meter or source changed. Reload and review again.", energy_confirmation_expired: "This source snapshot expired or was used. Capture a new one.",
    invalid_energy_source: "Choose a registered cumulative energy sensor (Wh, kWh or MWh), excluding DTEK billing sensors.",
    invalid_energy: "Check every source and numeric value. Use a dot for decimals; values must be non-negative.",
    energy_store_unavailable: "Local references could not be read or saved. Source proposals are disabled; manual meter entry remains available.",
    unauthorized: "An active administrator needs access to this account and every selected source.", unavailable: "Could not complete the operation. Check availability and try again.",
    pending_or_blocked: "DTEK currently blocks meter entry. Existing local references can still be calibrated; try a new binding later.",
    not_available: "The account is no longer available.", auth_required: "Reauthenticate the DTEK personal account.", rate_limited: "DTEK has limited requests; try later.",
    history: "Reference history", noContext: "Load an available DTEK meter before creating a binding.", mismatch: "This binding belongs to a different meter. Replace it before using a proposal.",
  },
  uk: {
    advanced: "Додаткові налаштування", calibration: "Звірити з основним лічильником", calibrationHelp: "Зніміть покази основного лічильника зараз. Відлік домашнього датчика буде отримано під час перевірки коригування.", locked: "Дочекайтеся завершення операції з показами.",
    title: "Джерело енергії Home Assistant", load: "Завантажити / оновити джерело", link: "Прив’язати датчик енергії", replace: "Замінити прив’язку", cancel: "Скасувати",
    mode: "Режим показів", offset: "Розрахунок за додатковим лічильником", direct: "Пряме читання розрахункового лічильника",
    freshness: "Перевірка доступності джерела", reported: "Вимагати свіжі повідомлення", availability: "Довіряти статусу доступності інтеграції",
    availabilityHelp: "Для джерел, що повідомляють лише зміну лічильника. Обирайте, тільки якщо інтеграція робить датчик недоступним при втраті зв’язку. Зависле числове значення в цьому режимі не виявляється. Обмеження віку не діє.",
    entity: "Датчик накопиченої енергії", age: "Максимальний вік даних (хвилини)", power: "Максимальна правдоподібна вхідна потужність (кВт)",
    actual: "Фактичні покази основного лічильника (кВт·год)", general: "Одна зона", day: "День", night: "Ніч",
    review: "Перевірити прив’язку", calibrate: "Перевірити нову опорну пару", save: "Зберегти локальну прив’язку", remove: "Видалити прив’язку",
    checked: "Джерело вимірює споживання з мережі саме цього рахунку та потрібної тарифної зони. Для розрахунку я перевірив, що обидва покази відповідають одному моменту.",
    reviewHelp: "Перевірте обидва покази та час. У режимі доступності звірте поточні фізичні покази, навіть якщо останнє повідомлення HA давніше. Зберігається лише локальна прив’язка; у ДТЕК нічого не передається. Підтвердження діє три хвилини.",
    help: "Оберіть накопичувальний датчик споживання з мережі для цієї квартири. Датчик після інвертора, іншої квартири або частини навантажень не підходить. Кожна тарифна зона потребує окремого датчика.",
    use: "Підставити запропоновані покази у форму", proposal: "Запропоновані накопичувальні покази", source: "Покази джерела", actualLabel: "Основний лічильник", correction: "Коригування", at: "Відлік джерела отримано HA",
    reference: "Збережена опорна пара", saved: "Локальну прив’язку збережено. Наступні розрахунки враховують коригування; передача в ДТЕК виконується окремо.",
    removeCheck: "Видалити локальну прив’язку та історію її коригувань. Покази в ДТЕК не змінюються.",
    staleHelp: "Отриманий стан HA не гарантує свіжого вимірювання пристрою. Перевірте безперервність обліку та надійність зв’язку. Після скидання чи стрибка потрібна нова перевірена опорна пара.",
    source_stale: "Дані джерела застаріли. Оновіть пристрій перед використанням.", source_unavailable: "Джерело недоступне; відсутність даних не означає нульове споживання.",
    source_reset: "Покази зменшилися. Перевірте лічильник та створіть нову опорну пару.", source_changed: "Змінилася ідентичність або одиниця джерела. Перевірте лічильник та замініть прив’язку.",
    source_jump: "Виявлено неправдоподібне зростання. Перевірте джерело та створіть нову опорну пару.",
    energy_changed: "Прив’язка, лічильник або джерело змінилися. Завантажте та перевірте дані знову.", energy_confirmation_expired: "Цей відлік прострочений або вже використаний. Отримайте новий.",
    invalid_energy_source: "Оберіть зареєстрований накопичувальний датчик енергії (Wh, kWh або MWh), крім розрахункових датчиків ДТЕК.",
    invalid_energy: "Перевірте джерела та всі числа. Для дробової частини використовуйте крапку; значення мають бути невід’ємними.",
    energy_store_unavailable: "Не вдалося прочитати або зберегти локальні прив’язки. Підказки вимкнено; ручне введення показів залишається доступним.",
    unauthorized: "Потрібен активний адміністратор із доступом до рахунку та кожного джерела.", unavailable: "Не вдалося виконати дію. Перевірте доступність та повторіть спробу.",
    pending_or_blocked: "ДТЕК зараз блокує введення. Наявну локальну прив’язку можна коригувати; нову створіть пізніше.",
    not_available: "Рахунок більше недоступний.", auth_required: "Повторно авторизуйте кабінет ДТЕК.", rate_limited: "ДТЕК обмежив запити; спробуйте пізніше.",
    history: "Історія опорних пар", noContext: "Для нової прив’язки спочатку завантажте доступний лічильник ДТЕК.", mismatch: "Прив’язка стосується іншого лічильника. Замініть її перед використанням підказки.",
  },
};
export function energyMessage(language, code) { const w = words[isUkrainian(language) ? "uk" : "en"]; return w[code]; }
function el(tag, text) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; return e; }

export class DtekEnergyEditor extends HTMLElement {
  static get workspaceVersion() { return 2; }
  constructor() { super(); this.attachShadow({mode: "open"}); this._seq = 0; this._fields = {mode: "offset", freshness: "reported", entities: {}, references: {}, age: "15", power: "30"}; }
  configure(hass, entity, context, compact = false, options = {}) { this._options=options; this._compact = compact; const languageChanged = this._hass?.language !== hass?.language; this._hass = hass; this._entity = entity; const changed = languageChanged || this._context !== context; this._context = context; if (changed || !this.shadowRoot.firstChild) this.render(); }
  disconnectedCallback() { queueMicrotask(() => { if (!this.isConnected) { this._seq++; this._busy = false; this._draft = null; } }); }
  get hasDraft() { return !!this._draft || this._editing || Object.values(this._fields.references).some(v => v !== ""); }
  get busy() { return !!this._busy; }
  get mutating() { return this._busy && this._action!=="get"; }
  set locked(value) { if(this._locked!==value){this._locked=value;this.render();} }
  emit(name, detail) { this.dispatchEvent(new CustomEvent(name,{detail,bubbles:true,composed:true})); }
  invalidate() { this._seq++;this._busy=false;this._data=null;this._error=null;this.render(); }
  get w() { return words[isUkrainian(this._hass?.language) ? "uk" : "en"]; }
  request(action, extra = {}) { return this._hass.callWS({type: "dtek_monitor/account_energy", entity_id: this._entity, action, ...extra}); }
  async act(action) {
    if (this._busy || (this._locked && action!=="get")) return;
    this._action=action;
    const seq = ++this._seq; this._busy = true; this._error = null; this._saved = false; this.render();this.emit("energy-operation");
    try {
      const binding = this._data?.binding;
      let result;
      if (action === "get") result = await this.request("get");
      else if (action === "preview") {
        const extra = {revision: binding?.revision || null, references: {...this._fields.references}};
        if (this._editing) extra.config = {mode: this._fields.mode, freshness: this._fields.freshness, entities: {...this._fields.entities}, max_age: Number(this._fields.age) * 60, max_power_kw: this._fields.power};
        result = await this.request("preview", extra);
      } else if (action === "save") result = await this.request("save", {confirmation: this._draft.confirmation});
      else result = await this.request("remove", {revision: binding.revision});
      if (seq !== this._seq) return;
      if (action === "get") this._data = result;
      else if (action === "preview") this._draft = result;
      else {
        this._draft = null; this._editing = false; this._data = null; this._fields.references = {}; this._saved = action === "save";this.emit("energy-binding-changed");
        const fresh = await this.request("get");
        if (seq !== this._seq) return;
        this._data = fresh;
      }
    } catch (error) {
      if (seq !== this._seq) return;
      this._error = error?.code || "unavailable";
      if (action === "get" || action === "save" || action === "remove") this._data = null;
      if (action === "save") this._draft = null;
      if (["save","remove"].includes(action)) this.emit("energy-binding-changed");
    } finally { if (seq === this._seq) { this._busy = false; this.render();this.emit("energy-operation"); } }
  }
  async calibrate(values) {
    if (this._busy) return;
    if (!this._data) await this.act("get");
    if (this._data?.binding?.mode !== "offset") {this._error = "energy_changed"; this.render(); return;}
    this._editing = false; this._fields.references = {...values}; await this.act("preview");
  }
  button(text, fn) { const b = el("button", text); b.type = "button"; b.disabled = this._busy || this._locked; b.addEventListener("click", fn); return b; }
  gate(root, text, button) {
    const label = el("label"), input = el("input"); label.className = "check"; input.type = "checkbox"; input.disabled = this._busy || this._locked;
    input.addEventListener("change", () => {button.disabled = !input.checked || this._busy || this._locked;}); label.append(input, el("span", text)); root.append(label, button); button.disabled = true;
  }
  field(root, name, value, change, type = "text") {
    const label = el("label", name), input = el("input"); input.type = type; input.value = value || ""; input.disabled = this._busy || this._locked;
    input.setAttribute("aria-label", name); input.addEventListener("input", () => change(input.value)); label.append(input); root.append(label); return input;
  }
  render() {
    if (!this._hass) return;
    if (this._compact && !this._settingsOpen && !this._draft) { this.renderCompact(); return; }
    const w = this.w, root = el("section"), binding = this._data?.binding;
    if (this._compact) root.append(this.button(isUkrainian(this._hass.language) ? "Закрити налаштування датчика" : "Close sensor settings", () => {this._settingsOpen=false;this.render();}));
    if(!this._options.settingsOnly)root.append(el("h3", w.title));
    if(!this._options.settingsOnly || this._editing || !binding)root.append(el("p", w.help));
    if(this._locked){const note=el("p",w.locked);note.setAttribute("role","status");root.append(note);}
    if (this._error) { const p = el("p", w[this._error] || w.unavailable); p.setAttribute("role", "alert"); root.append(p); }
    if (this._saved) { const p = el("p", w.saved); p.setAttribute("role", "status"); root.append(p); }
    if (this._draft) {
      root.append(el("p", w.reviewHelp), el("p", `${this._draft.binding.serial} · ${w[this._draft.binding.mode]} · ${w[this._draft.binding.freshness || "reported"]}`));
      for (const [zone, row] of Object.entries(this._draft.change.changes)) {
        root.append(el("h4", w[zoneKey(zone).toLowerCase()]), el("p", `${w.source}: ${row.source} kWh`), el("p", `${w.at}: ${date(row.source_at,this._hass.language,true)}`));
        if (row.actual !== null) root.append(el("p", `${w.actualLabel}: ${row.actual} kWh`));
        if (row.correction !== null) root.append(el("p", `${w.correction}: ${row.correction} kWh`));
      }
      root.append(this.button(w.cancel, () => {this._draft = null; this.render();}));
      this.gate(root, w.checked, this.button(w.save, () => this.act("save")));
    } else {
      if(!this._options.settingsOnly || !this._data)root.append(this.button(w.load, () => this.act("get")));
      if (binding && !(this._options.settingsOnly && this._editing)) {
        if(!this._options.settingsOnly)root.append(el("p", `${binding.serial} · ${w[binding.mode]} · ${w[binding.freshness || "reported"]}`));
        const matches = !this._context?.serial || this._context.serial === binding.serial;
        if (!matches) root.append(el("p", w.mismatch));
        for (const [zone, row] of Object.entries(binding.zones)) {
          const reading = this._data.readings?.[zone];
          root.append(el("h4", w[zoneKey(zone).toLowerCase()]), el("p", this._options.settingsOnly?(this._hass.states?.[row.entity_id]?.attributes?.friendly_name || row.entity_id):row.entity_id));
          if (binding.mode === "offset" && !this._options.settingsOnly) root.append(el("p", `${w.reference} — ${w.actualLabel}: ${number(row.anchor_meter,this._hass.language)} kWh; ${w.source}: ${number(row.anchor_source,this._hass.language)} kWh`));
          if (reading?.error) root.append(el("p", w[reading.error] || w.unavailable));
          else if (reading) root.append(el("p", this._options.settingsOnly?`${w.proposal}: ${number(reading.send_value,this._hass.language)} ${isUkrainian(this._hass.language)?"кВт·год":"kWh"}`:`${w.proposal}: ${reading.value} kWh → ${reading.send_value}`), el("p", `${w.at}: ${date(reading.source.at,this._hass.language,true)}`));
        }
        if (!this._options.settingsOnly && this._data.ready && matches && this._context?.serial && !this._context.blocked) root.append(this.button(w.use, () => this.dispatchEvent(new CustomEvent("energy-proposal", {detail: {values: Object.fromEntries(Object.entries(this._data.readings).map(([z, r]) => [z, r.send_value])), token: this._data.proposal}, bubbles: true, composed: true}))));
        const history = el("details"); history.append(el("summary", w.history));
        if(this._options.settingsOnly){history.append(el("p",`${binding.serial} · ${w[binding.mode]} · ${w[binding.freshness || "reported"]}`));for(const [zone,row] of Object.entries(binding.zones)){history.append(el("p",`${w[zoneKey(zone).toLowerCase()]} · ${row.entity_id}`));if(binding.mode==="offset")history.append(el("p",`${w.actualLabel}: ${number(row.anchor_meter,this._hass.language)}; ${w.source}: ${number(row.anchor_source,this._hass.language)} ${isUkrainian(this._hass.language)?"кВт·год":"kWh"}`));}}
        for (const record of [...binding.history].reverse()) {
          history.append(el("p", date(record.at,this._hass.language,true)));
          for (const [zone, row] of Object.entries(record.changes)) history.append(el("p", `${w[zoneKey(zone).toLowerCase()]}: ${row.actual ?? "—"} / ${row.source} kWh · ${w.correction}: ${row.correction ?? "—"}`));
        }
        root.append(history);
      }
      if(this._options.settingsOnly && this._data && !this._editing)root.append(this.button(isUkrainian(this._hass.language)?"Оновити покази датчика":"Refresh sensor readings",()=>this.act("get")));
      if (this._data && !this._editing) root.append(this.button(binding ? w.replace : w.link, () => {
        this._editing = true; this._fields = {mode: binding?.mode || "offset", freshness: binding?.freshness || "reported", entities: Object.fromEntries(Object.entries(binding?.zones || {}).map(([z,r])=>[z,r.entity_id])), references: {}, age: String((binding?.max_age || 900)/60), power: binding?.max_power_kw || "30"}; this.render();
      }));
      if (this._editing) {
        if (!this._context?.serial || this._context.blocked) root.append(el("p", this._context?.blocked?w.pending_or_blocked:w.noContext));
        else {
          const label = el("label", w.mode), select = el("select"); select.disabled = this._busy || this._locked; select.setAttribute("aria-label", w.mode);
          for (const mode of ["offset", "direct"]) { const option = el("option", w[mode]); option.value = mode; select.append(option); }
          select.value = this._fields.mode; select.addEventListener("change", () => {this._fields.mode = select.value; this.render();}); label.append(select); root.append(label);
          for (const z of this._context.zones) {
            const input = this.field(root, `${w[zoneKey(z.zone).toLowerCase()]} · ${w.entity}`, this._fields.entities[z.zone], value => {this._fields.entities[z.zone] = value;});
            input.setAttribute("list", "energy-sources");
          }
          const list = el("datalist"); list.id = "energy-sources";
          for (const [id, state] of Object.entries(this._hass.states || {})) if (state.attributes?.device_class === "energy" && ["total", "total_increasing"].includes(state.attributes.state_class) && ["Wh","kWh","MWh"].includes(state.attributes.unit_of_measurement)) { const option = el("option"); option.value = id; option.label = state.attributes.friendly_name || id; list.append(option); }
          root.append(list);
          if (this._fields.mode === "offset") this.referenceFields(root, this._context.zones.map(z => z.zone));
          let advanced=root;if(this._options.settingsOnly){advanced=el("details");advanced.open=!!this._advancedOpen;advanced.append(el("summary",w.advanced));advanced.ontoggle=()=>{this._advancedOpen=advanced.open;};root.append(advanced);}
          const freshnessLabel = el("label", w.freshness), freshnessSelect = el("select");
          freshnessSelect.disabled = this._busy || this._locked; freshnessSelect.setAttribute("aria-label", w.freshness);
          for (const mode of ["reported", "availability"]) { const option = el("option", w[mode]); option.value = mode; freshnessSelect.append(option); }
          freshnessSelect.value = this._fields.freshness;
          freshnessSelect.addEventListener("change", () => {this._fields.freshness = freshnessSelect.value; this.render();});
          freshnessLabel.append(freshnessSelect); advanced.append(freshnessLabel);
          if (this._fields.freshness === "availability") advanced.append(el("p", w.availabilityHelp));
          else this.field(advanced, w.age, this._fields.age, value => {this._fields.age = value;}, "number");
          this.field(advanced, w.power, this._fields.power, value => {this._fields.power = value;}, "number");
          if(this._options.settingsOnly)advanced.append(el("small",w.staleHelp));
          root.append(this.button(w.review, () => this.act("preview")));
        }
        root.append(this.button(w.cancel, () => {this._editing = false; this._fields.references={}; this.render();}));
      } else if (binding?.mode === "offset" && (!this._context?.serial || this._context.serial===binding.serial)) {
        let calibration=root;if(this._options.settingsOnly){calibration=el("details");calibration.open=!!this._calibrationOpen;calibration.append(el("summary",w.calibration),el("p",w.calibrationHelp));calibration.ontoggle=()=>{this._calibrationOpen=calibration.open;};root.append(calibration);}
        this.referenceFields(calibration, Object.keys(binding.zones));
        calibration.append(this.button(w.calibrate, () => this.act("preview")));
      }
      if (binding && !this._editing) { const details = el("details"); details.append(el("summary", w.remove)); this.gate(details, w.removeCheck, this.button(w.remove, () => this.act("remove"))); root.append(details); }
    }
    if(!this._options.settingsOnly)root.append(el("small", w.staleHelp));
    const style = el("style", embeddedCSS+`:host{display:block;margin-top:20px;border-top:1px solid var(--divider-color,#ddd)}h3{font-size:1.05em}p,small{line-height:1.5;overflow-wrap:anywhere}label{display:block;margin:12px 0}input,select{box-sizing:border-box;width:100%;margin-top:6px}button,input,select{font:inherit;color:var(--primary-text-color);background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#aaa);border-radius:6px;padding:10px}button{margin:6px 6px 6px 0;cursor:pointer}button:disabled{opacity:.5;cursor:default}.check{display:flex;gap:10px;align-items:flex-start}.check input{width:auto;flex-shrink:0}small{display:block;margin-top:12px;color:var(--secondary-text-color)}[role=alert]{color:var(--error-color,#b22)}details{margin:12px 0}summary{cursor:pointer}`);
    this.shadowRoot.replaceChildren(style, root);
  }
  renderCompact() {
    const uk=isUkrainian(this._hass.language), w=this.w, root=el("section"), binding=this._data?.binding;
    const title=el("h3",uk?"Підказка від домашнього лічильника":"Home meter suggestion");root.append(title);
    if(this._error){const message=el("p",w[this._error]||w.unavailable);message.setAttribute("role","alert");root.append(message);}
    if(binding){
      for(const [zone,row] of Object.entries(binding.zones)){
        const reading=this._data.readings?.[zone], name=this._hass.states?.[row.entity_id]?.attributes?.friendly_name || w.entity;
        if(reading?.error)root.append(el("p",w[reading.error]||w.unavailable));
        else if(reading){const value=el("p",`${w[zoneKey(zone).toLowerCase()]} · ${number(reading.send_value,this._hass.language)} ${uk?"кВт·год":"kWh"}`);value.className="value";root.append(value,el("small",`${name} · ${date(reading.source.at,this._hass.language,true)}`));}
      }
      const matches=this._context?.serial===binding.serial;
      if(this._context?.serial&&!matches)root.append(el("p",w.mismatch));
      if(this._data.ready&&matches&&!this._context.blocked)root.append(this.button(uk?"Підставити":"Use suggestion",()=>this.dispatchEvent(new CustomEvent("energy-proposal",{detail:{values:Object.fromEntries(Object.entries(this._data.readings).map(([z,r])=>[z,r.send_value])),token:this._data.proposal},bubbles:true,composed:true}))));

    }else root.append(el("p",this._data?(uk?"Датчик не підключений. Покази можна ввести вручну.":"No sensor connected. You can enter readings manually."):(uk?"Можна використати накопичувальний датчик енергії своєї квартири.":"You can use a cumulative energy sensor for this apartment.")));
    root.append(this.button(uk?"Оновити":"Refresh suggestion",()=>this.act("get")));
    root.append(this.button(uk?"Налаштувати датчик":"Sensor settings",async()=>{if(this._options.externalSettings){this.emit("energy-settings");return;}this._settingsOpen=true;this.render();if(!this._data)await this.act("get");}));
    this.shadowRoot.replaceChildren(el("style",embeddedCSS+`:host{display:block;margin-top:20px}section{padding:16px;border:1px solid var(--divider-color,#ddd);border-radius:12px}h3{margin:0 0 8px;font-size:1em}p{line-height:1.5}.value{font-size:1.15em;font-weight:600}small{display:block;color:var(--secondary-text-color);overflow-wrap:anywhere}button{font:inherit;padding:10px;border:1px solid var(--divider-color,#aaa);border-radius:8px;color:var(--primary-text-color);background:transparent;margin:12px 8px 0 0;cursor:pointer}button:disabled{opacity:.5}`),root);
  }
  referenceFields(root, zones) { for (const zone of zones) this.field(root, `${this.w[zoneKey(zone).toLowerCase()]} · ${this.w.actual}`, this._fields.references[zone], value => {this._fields.references[zone] = value;}); }
}
if (!customElements.get("dtek-energy-editor")) customElements.define("dtek-energy-editor", DtekEnergyEditor);
