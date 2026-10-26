import { zoneKey, isUkrainian,  el, date, number } from "./account-ui.js?v=2.0.0-rc5";

const words = {
  en: {
    check: "Check whether DTEK has these readings", loading: "Checking…",
    no_attempt: "There is no submission recorded by this Home Assistant. Your DTEK records are in Reading history.",
    matched: "The date and readings match records in DTEK for every tariff zone.",
    partial: "A matching record was found for only some tariff zones. Check the remaining zones in the cabinet.",
    ambiguous: "Several records match. Check the result in the cabinet.",
    not_found: "No matching record yet. This does not mean DTEK rejected the readings.",
    meter_changed: "The meter has changed since this submission. Check the result in the cabinet.",
    invalid_attempt: "This submission cannot be compared with the history.",
    note: "A matching record does not establish that this request created it or that the monthly calculation is final. This check never resends readings or unlocks submission.",
    error: "Could not check the result. Try again later.", rate_limited: "Please wait at least a minute before checking again.",
    api_changed: "This DTEK service is unavailable or incompatible. Open Settings → System → Repairs for integration updates and support.",
    auth_required: "Sign in again in the integration settings, then repeat the check.",
    attempt: "Submitted readings", checked: "Checked", GENERAL: "Single zone", DAY: "Day", NIGHT: "Night", unit: "kWh",
  },
  uk: {
    check: "Перевірити, чи є ці покази в ДТЕК", loading: "Перевіряємо…",
    no_attempt: "Цей Home Assistant ще не передавав покази. Записи ДТЕК доступні в історії показів.",
    matched: "Дата та покази збігаються із записами ДТЕК для всіх тарифних зон.",
    partial: "Збіг знайдено лише для частини тарифних зон. Перевірте решту в кабінеті.",
    ambiguous: "Збігаються кілька записів. Перевірте результат у кабінеті.",
    not_found: "Відповідного запису поки немає. Це не означає, що ДТЕК відхилив покази.",
    meter_changed: "Після цієї передачі лічильник змінився. Перевірте результат у кабінеті.",
    invalid_attempt: "Цю передачу неможливо зіставити з історією.",
    note: "Збіг не доводить, що саме цей запит створив запис або що місячний розрахунок остаточний. Перевірка не передає покази повторно та не розблоковує передачу.",
    error: "Не вдалося перевірити результат. Спробуйте пізніше.", rate_limited: "Зачекайте щонайменше хвилину перед повторною перевіркою.",
    api_changed: "Цей сервіс ДТЕК недоступний або несумісний. Відкрийте Налаштування → Система → Виправлення для оновлень інтеграції та підтримки.",
    auth_required: "Увійдіть повторно в налаштуваннях інтеграції, а потім повторіть перевірку.",
    attempt: "Передані покази", checked: "Перевірено", GENERAL: "Одна зона", DAY: "День", NIGHT: "Ніч", unit: "кВт·год",
  },
};

class DtekAccountReadback extends HTMLElement {
  constructor() { super(); this.attachShadow({mode: "open"}); this._seq = 0; }
  configure(hass, entity) {
    if (entity !== this._entity || hass?.user?.id !== this._hass?.user?.id || hass?.connection !== this._hass?.connection) this.reset();
    this._hass = hass; this._entity = entity; this.render();
  }
  reset() { this._seq++; this._data = null; this._error = null; this._busy = false; }
  disconnectedCallback() { queueMicrotask(() => { if (!this.isConnected) this.reset(); }); }
  get w() { return words[isUkrainian(this._hass?.language) ? "uk" : "en"]; }
  async check() {
    if (this._busy) return;
    const seq = ++this._seq;
    this._busy = true; this._data = null; this._error = null; this.render();
    try {
      const data = await this._hass.callWS({type: "dtek_monitor/account_readback", entity_id: this._entity});
      if (seq === this._seq && this.isConnected) this._data = data;
    } catch (error) {
      if (seq === this._seq) this._error = error.code || "error";
    } finally {
      if (seq === this._seq) { this._busy = false; this.render(); }
    }
  }
  render() {
    const w = this.w, box = el("section"), button = el("button", this._busy ? w.loading : w.check);
    button.type = "button"; button.disabled = this._busy; button.onclick = () => this.check(); box.append(button);
    if (this._error) { const p = el("p", w[this._error] || w.error); p.setAttribute("role", "alert"); box.append(p); }
    if (this._data) {
      const data = this._data, p = el("p", w[data.status] || w.error); p.setAttribute("role", "status"); box.append(p);
      if (data.attempt) {
        box.append(el("p", `${w.attempt}: ${(data.attempt.readings || []).map(r => `${w[zoneKey(r.zone)] || r.zone}: ${number(r.value, this._hass.language)} ${w.unit}`).join("; ")}`));
        box.append(el("small", w.note));
      }
      box.append(el("small", `${w.checked}: ${date(data.fetched_at, this._hass.language, true)}`));
    }
    this.shadowRoot.replaceChildren(el("style", `:host{display:block;margin-top:16px}button{font:inherit;padding:10px 14px;min-height:44px;border:1px solid var(--divider-color,#aaa);border-radius:10px;background:transparent;color:var(--primary-text-color);cursor:pointer}button:disabled{opacity:.5}p,small{line-height:1.5;overflow-wrap:anywhere}small{display:block;margin-top:8px;color:var(--secondary-text-color)}[role=alert]{color:var(--error-color,#b22)}`), box);
  }
}
if (!customElements.get("dtek-account-readback")) customElements.define("dtek-account-readback", DtekAccountReadback);
