/* Official text is primary; interpretation never turns missing notices into all-clear. */
import { isUkrainian } from "./account-ui.js?v=2.0.0-rc6";

export function noticeSource(attrs) {
  try {
    const url = new URL(attrs?.provider_notice_source);
    if (url.protocol === "https:" && !url.username && !url.password && !url.port &&
        /^(?:www\.)?dtek-(?:oem|kem|krem|dnem)\.com\.ua$/.test(url.hostname)) return url.href;
  } catch (_) { /* A missing/invalid link must not hide the announcement. */ }
  return "";
}

export function noticeView(attrs, language, now = Date.now()) {
  const uk = isUkrainian(language), text = String(attrs?.provider_notice_text || "").trim();
  const present = attrs && ("provider_notice_state" in attrs || "schedule_applies" in attrs);
  const expiry = Date.parse(attrs?.provider_notice_valid_until);
  const unavailable = present && (attrs.provider_notice_state === "unavailable" ||
    attrs.provider_notice_error || !Number.isFinite(expiry) || now >= expiry);
  const kind = !present ? "hidden" : unavailable ? "unavailable" : !text ? "hidden" :
    attrs.schedule_applies === false ? "warning" : "info";
  return {kind, text, source: noticeSource(attrs),
    title: uk ? "📢 Оголошення ДТЕК" : "📢 DTEK announcement",
    message: kind === "hidden" ? "" : kind === "unavailable" ?
      (uk ? "Не вдалося перевірити оголошення ДТЕК." : "Could not check DTEK announcements.") : kind === "warning" ?
      (uk ? "ДТЕК повідомляє про екстрені відключення. Графік може не відповідати фактичним відключенням." : "DTEK reports emergency outages. Actual outages may differ from the timetable.") :
      (uk ? "Є повідомлення щодо відключень." : "There is an announcement about outages."),
  };
}

export function noticeLabel(attrs, language, now = Date.now()) {
  const view = noticeView(attrs, language, now), uk = isUkrainian(language);
  return view.kind === "hidden" ? "" : view.kind === "unavailable" ? view.message :
    (uk ? "Є оголошення ДТЕК" : "DTEK announcement available");
}

function checkedStamp(value) {
  const date = new Date(value || "");
  if (!Number.isFinite(date.getTime())) return "";
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Kyiv", day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(date).map(p => [p.type, p.value]));
  return `${parts.day}.${parts.month}.${parts.year} ${parts.hour}:${parts.minute}`;
}

export function renderProviderNotice(container, attrs, language) {
  const view = noticeView(attrs, language), uk = isUkrainian(language);
  container.hidden = view.kind === "hidden";
  container.dataset.tone = view.kind;
  // Mount once: polling must preserve the reader's expanded text and scroll position.
  if (!container.firstChild) {
    container.style.cssText = "padding:12px;border-inline-start:3px solid var(--divider-color,#abb8c3);border-radius:4px;line-height:1.5;overflow-wrap:anywhere;margin:8px 0;color:var(--primary-text-color,inherit)";
    const title = document.createElement("strong"), message = document.createElement("p"),
      details = document.createElement("details"), summary = document.createElement("summary"),
      text = document.createElement("p"), meta = document.createElement("div"),
      checked = document.createElement("span"), link = document.createElement("a");
    title.className = "notice-title"; message.className = "notice-message";
    message.style.margin = "4px 0 8px"; message.setAttribute("role", "status");
    summary.style.cursor = "pointer"; text.style.whiteSpace = "pre-line";
    checked.style.fontVariantNumeric = "tabular-nums";
    meta.style.cssText = "display:flex;flex-wrap:wrap;gap:4px 12px;font-size:.85em;color:var(--secondary-text-color,#647280);margin-top:8px";
    link.target = "_blank"; link.rel = "noopener noreferrer";
    details.append(summary, text); meta.append(checked, link); container.append(title, message, details, meta);
  }
  const [title, message, details, meta] = container.children,
    [summary, text] = details.children, [checked, link] = meta.children;
  const set = (node, value) => {if (node.textContent !== value) node.textContent = value;};
  container.style.borderInlineStartColor = view.kind === "warning" ? "var(--warning-color,#bf851f)" : "var(--divider-color,#abb8c3)";
  title.hidden = view.kind === "unavailable"; set(title, view.title); set(message, view.message);
  set(summary, view.kind === "unavailable" ?
    (uk ? "Останнє отримане повідомлення" : "Last retrieved announcement") :
    (uk ? "Читати повідомлення" : "Read announcement"));
  set(text, view.text); details.hidden = !view.text;
  const stamp = checkedStamp(attrs?.provider_notice_checked_at);
  set(checked, stamp ? `${view.kind === "unavailable" ?
    (uk ? "Остання успішна перевірка" : "Last successful check") : (uk ? "Перевірено" : "Checked")}: ${stamp}` : "");
  checked.hidden = !stamp;
  link.hidden = !view.source;
  if (view.source) {if (link.href !== view.source) link.href = view.source;} else link.removeAttribute("href");
  set(link, uk ? "Відкрити сайт ДТЕК ↗" : "Open DTEK website ↗");
  meta.hidden = !stamp && !view.source;
}
