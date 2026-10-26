/* Shared local grid contract and civil-time labels. Never infer missing cells. */
export const GRID_TYPES = ["outage", "possible", "clear", "forecast", "forecast_clear", "unknown"];

export function validateGrid(data) {
  if (!data || !Array.isArray(data.days) || data.days.length > 7 || data.days.some(day =>
    !day || !/^\d{4}-\d{2}-\d{2}$/.test(day.date) || !Array.isArray(day.slots) || day.slots.length > 50 ||
    day.slots.some(slot => !slot || !/^\d{2}:\d{2}$/.test(slot.label) || !/^[+-]\d{4}$/.test(slot.offset)) ||
    !Array.isArray(day.rows) || day.rows.length > 100 || day.rows.some(row =>
      !row || typeof row.id !== "string" || typeof row.label !== "string" ||
      !Array.isArray(row.cells) || row.cells.length !== day.slots.length || row.cells.some(kind => !GRID_TYPES.includes(kind))
    )
  )) throw new Error("Invalid grid");
  for (const day of data.days) for (const row of day.rows) timelineSegments(day, row);
  return data;
}

export function slotLabel(day, index, offsets = false) {
  if (index >= day.slots.length) return "24:00" + (offsets ? ` UTC${day.slots.at(-1).offset}` : "");
  const whole = Math.floor(index), slot = day.slots[whole];
  const [hour, minute] = slot.label.split(":").map(Number);
  const value = Math.round(hour * 60 + minute + (index - whole) * 30);
  const label = `${String(Math.floor(value / 60)).padStart(2,"0")}:${String(value % 60).padStart(2,"0")}`;
  return label + (offsets ? ` UTC${slot.offset}` :
    day.slots.filter(other => other.label === slot.label).length > 1 ? ` (UTC${slot.offset})` : "");
}

export function endLabel(day, index, offsets = false) {
  return index === day.slots.length - 1 ? "24:00" + (offsets ? ` UTC${day.slots[index].offset}` : "") : slotLabel(day, index + 1, offsets);
}

export function gridIntervals(day, row, splitOffsets = false) {
  const result = [];
  const cuts = splitOffsets ? day.slots.flatMap((slot, i) => i && slot.offset !== day.slots[i-1].offset ? [i*30] : []) : [];
  for (const segment of timelineSegments(day, row)) {
    const points = [segment.start, ...cuts.filter(x=>segment.start<x && x<segment.end), segment.end];
    for (let i=0;i<points.length-1;i++) {
      const start=points[i]/30, end=points[i+1]/30-1, kind=segment.kind;
      const offset=day.slots[Math.floor(start)].offset, last=result.at(-1);
      if(last?.kind===kind && (!splitOffsets || last.offset===offset)) last.end=end;
      else result.push({kind,start,end,offset});
    }
  }
  return result;
}

export function timelineSegments(day, row) {
  if (row.segments !== undefined) {
    if (!Array.isArray(row.segments) || !row.segments.length || row.segments.length>4096) throw new Error("Invalid segments");
    let cursor=0;
    for (const part of row.segments) {
      if (!part || !Number.isFinite(part.start) || !Number.isFinite(part.end) ||
          part.start!==cursor || part.end<=part.start || part.end>day.slots.length*30 || !GRID_TYPES.includes(part.kind)) throw new Error("Invalid segments");
      cursor=part.end;
    }
    if(cursor!==day.slots.length*30) throw new Error("Incomplete segments");
    return row.segments;
  }
  // Older integrations publish only half-hour cells. Preserve their precision.
  const result=[];
  row.cells.forEach((kind,i)=>{
    const last=result.at(-1);
    if(last?.kind===kind) last.end=(i+1)*30;
    else result.push({start:i*30,end:(i+1)*30,kind});
  });
  return result;
}

export function hourColumns(day) {
  return day.slots.flatMap((slot,i)=>i%2 ? [] : [{start:i*30,end:Math.min(i+2,day.slots.length)*30,label:slot.label,offset:slot.offset}]);
}

export function clippedSegments(day, row, start, end) {
  return timelineSegments(day,row).filter(p=>p.start<end && p.end>start)
    .map(p=>({...p,start:Math.max(start,p.start),end:Math.min(end,p.end)}));
}

export async function callGridWS(hass, message) {
  let timer;
  try {
    return await Promise.race([hass.callWS(message), new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error("Grid request timed out")), 20000);
    })]);
  } finally { clearTimeout(timer); }
}
