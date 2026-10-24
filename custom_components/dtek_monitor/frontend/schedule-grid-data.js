/* Shared local grid contract and civil-time labels. Never infer missing cells. */
export const GRID_TYPES = ["outage", "possible", "clear", "forecast", "forecast_clear", "unknown"];

export function validateGrid(data) {
  if (!data || !Array.isArray(data.days) || data.days.length > 7 || data.days.some(day =>
    !day || !/^\d{4}-\d{2}-\d{2}$/.test(day.date) || !Array.isArray(day.slots) || day.slots.length > 50 ||
    day.slots.some(slot => !slot || !/^\d{2}:\d{2}$/.test(slot.label) || !/^[+-]\d{4}$/.test(slot.offset)) ||
    !Array.isArray(day.rows) || day.rows.length > 64 || day.rows.some(row =>
      !row || typeof row.id !== "string" || typeof row.label !== "string" ||
      !Array.isArray(row.cells) || row.cells.length !== day.slots.length || row.cells.some(kind => !GRID_TYPES.includes(kind))
    )
  )) throw new Error("Invalid grid");
  return data;
}

export function slotLabel(day, index, offsets = false) {
  const slot = day.slots[index];
  return slot.label + (offsets ? ` UTC${slot.offset}` :
    day.slots.filter(other => other.label === slot.label).length > 1 ? ` (UTC${slot.offset})` : "");
}

export function endLabel(day, index, offsets = false) {
  return index === day.slots.length - 1 ? "24:00" + (offsets ? ` UTC${day.slots[index].offset}` : "") : slotLabel(day, index + 1, offsets);
}

export function gridIntervals(day, row, splitOffsets = false) {
  const result = [];
  row.cells.forEach((kind, index) => {
    const last = result.at(-1), offset = day.slots[index].offset;
    if (last?.kind === kind && (!splitOffsets || last.offset === offset)) last.end = index;
    else result.push({kind, start: index, end: index, offset});
  });
  return result;
}

export async function callGridWS(hass, message) {
  let timer;
  try {
    return await Promise.race([hass.callWS(message), new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error("Grid request timed out")), 20000);
    })]);
  } finally { clearTimeout(timer); }
}
