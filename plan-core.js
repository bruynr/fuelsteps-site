// plan-core.js — pure logic for the plan builder, mirrors ScheduleParser.mc in the app repo.
// Imported by plan.js (browser) and plan-core.test.js (node --test). No DOM, no I/O.

export const LIMITS = {
  km: { min: 0.5, max: 100, step: 0.5 },
  miles: { min: 0.5, max: 100, step: 0.5 }, // same rules as km; 1 mile = 1609.344 m on the watch
  min: { min: 5, max: 600, step: 5 },
  repeatMax: 30, nameMax: 16, fieldMax: 40, maxSteps: 12, carbsMax: 9999,
  importMax: 1000, // maxLength of a schedule field in Garmin Connect (settings.xml); the total store is ~8 KB
  textAdvice: 16, // longer labels are cut off on the watch (alert and field draw the label in one line)
};
export const DEFAULT_TEXT = "Gel";

// digits only, 1-4 of them (ScheduleParser.parseWhole)
function parseWhole(s) {
  return /^[0-9]{1,4}$/.test(s) ? Number(s) : null;
}

// digits with at most one . or , (ScheduleParser.parseDecimal), max 8 chars, at least one digit
function parseDecimal(s) {
  if (s.length < 1 || s.length > 8 || !/^[0-9.,]*$/.test(s) || !/[0-9]/.test(s)) return null;
  if ((s.match(/[.,]/g) || []).length > 1) return null;
  return Number(s.replace(",", "."));
}

// "25g" → 25; bare numbers are product text, "Gel 100" is a Maurten gel (ScheduleParser.parseCarbs)
function parseCarbs(s) {
  if (s.length > 1 && /[gG]$/.test(s)) return parseWhole(s.slice(0, -1));
  return null;
}

// "[repeat]x size [text] [carbsg] [caf]" or "@position [text] [carbsg] [caf]" → step or null
export function parseStepText(raw) {
  if (typeof raw !== "string") return null;
  const tokens = raw.split(/[ \t\r\n]+/).filter(Boolean);
  if (tokens.length === 0) return null;
  const first = tokens[0];
  let repeat = 1;
  let sizeText = first;
  const abs = first[0] === "@";
  if (abs) sizeText = first.slice(1); // no repeat prefix: parseDecimal rejects "x"
  const xs = abs ? [] : first.match(/[xX]/g) || [];
  if (xs.length > 1) return null;
  if (xs.length === 1) {
    const pos = first.search(/[xX]/);
    repeat = parseWhole(first.slice(0, pos));
    if (repeat === null) return null;
    sizeText = first.slice(pos + 1);
  }
  const size = parseDecimal(sizeText);
  if (size === null) return null;
  let last = tokens.length - 1; // consumed from the back: caf, then carbs
  let caf = false;
  if (last >= 1 && tokens[last].toLowerCase() === "caf") { caf = true; last--; }
  let carbs = 0;
  if (last >= 1) {
    const c = parseCarbs(tokens[last]);
    if (c !== null) { carbs = c; last--; }
  }
  const text = tokens.slice(1, last + 1).join(" ") || DEFAULT_TEXT;
  return { size, repeat, text, carbs, caf, abs };
}

function num(n) {
  return Number.isFinite(n) ? String(Math.round(n * 100) / 100) : "?"; // 7.5 → "7.5", 5 → "5", empty field → "?"
}

// step → canonical field text: repeat omitted when 1 (never with @), carbs omitted when 0, text always written
export function formatStep(step) {
  const text = String(step.text || "").trim().split(/\s+/).filter(Boolean).join(" ") || DEFAULT_TEXT;
  const parts = [(step.abs ? "@" : step.repeat > 1 ? step.repeat + "x" : "") + num(step.size), text];
  if (step.carbs > 0) parts.push(step.carbs + "g");
  if (step.caf) parts.push("caf");
  return parts.join(" ");
}

const mk = (size, repeat, text, carbs, caf, abs = false) => ({ size, repeat, text, carbs, caf, abs });

export function newStep() {
  return mk(5, 1, DEFAULT_TEXT, 25, false);
}

export const TEMPLATES = [
  { id: "gel5", schedule: { name: "Gel 5 km", unit: "km", steps: [mk(5, 3, "Gel", 25, true)] } },
  { id: "marathon7", schedule: { name: "Marathon", unit: "km", steps: [
    mk(0, 1, "Gel", 25, false), mk(7, 1, "Gel", 25, false), mk(7, 1, "Dextro", 15, false), mk(7, 1, "Gel CAF", 25, true), mk(7, 2, "Gel", 25, false),
  ] } },
  { id: "time30", schedule: { name: "Every 30 min", unit: "min", steps: [mk(30, 6, "Gel", 25, false)] } },
];

const isInt = (n) => Number.isInteger(n);
const normText = (t) => String(t || "").trim().split(/\s+/).filter(Boolean).join(" ") || DEFAULT_TEXT;

// same rules as ScheduleParser.parse/parseStep plus the Garmin Connect field limits
export function validate(schedule) {
  const lim = LIMITS[schedule.unit];
  const name = String(schedule.name ?? "").trim();
  const nameErr = name.length === 0 ? "name_empty" : name.length > LIMITS.nameMax ? "name_long" : null;
  const steps = [];
  const warnings = [];
  let total = 0;
  schedule.steps.forEach((s, i) => {
    let err = null;
    const size = s.abs ? Number(s.size) - total : Number(s.size); // an absolute position becomes the step after the previous moment
    if (!isInt(s.repeat) || s.repeat < 1 || s.repeat > LIMITS.repeatMax) err = "repeat";
    else if (s.abs && s.repeat !== 1) err = "abs_repeat";
    else if (s.abs && i > 0 && !(size >= lim.min)) err = "abs_back";
    else if (size === 0 && (i > 0 || s.repeat > 1)) err = "zero_first";
    else if (size !== 0 && !(size >= lim.min)) err = "size_min";
    else if (!isInt(s.carbs) || s.carbs < 0 || s.carbs > LIMITS.carbsMax) err = "carbs";
    else if (formatStep(s).length > LIMITS.fieldMax) err = "field_long";
    if (!err) {
      total += size * s.repeat;
      if (total > lim.max) err = "total_max";
    }
    steps.push(err);
    let warn = null;
    if (!err) {
      const back = parseStepText(formatStep(s));
      // the watch would read the text differently (last word eaten as grams, or as the caf flag)
      if (!back || back.text !== normText(s.text) || back.carbs !== s.carbs || back.caf !== !!s.caf) warn = "roundtrip";
      else if (s.carbs === 0 && /^[0-9]+$/.test(normText(s.text).split(" ").pop())) warn = "bare_number"; // "Gel 25" with 0 g probably meant 25g ("Gel 100" is a product, so a hint, not an error)
      else if (normText(s.text).length > LIMITS.textAdvice) warn = "text_long";
    }
    warnings.push(warn);
  });
  const ok = !nameErr && schedule.steps.length > 0 && steps.every(e => e === null);
  return { ok, name: nameErr, steps, warnings };
}

// a step the watch could run at all: whole repeat within the limit and a number as size (keeps the preview bounded while typing)
const runnable = (s) => Number.isInteger(s.repeat) && s.repeat >= 1 && s.repeat <= LIMITS.repeatMax && Number.isFinite(Number(s.size));

// every alert moment with its cumulative position; "#n" numbering inside a repeated step; steps that are not runnable are skipped
export function moments(schedule) {
  const rows = [];
  let at = 0, totalCarbs = 0, cafCount = 0;
  schedule.steps.forEach((s, i) => {
    if (!runnable(s)) return;
    const text = normText(s.text);
    for (let n = 1; n <= s.repeat; n++) {
      at = s.abs ? Number(s.size) : Math.round((at + Number(s.size)) * 1000) / 1000;
      rows.push({ at, label: s.repeat > 1 ? `${text} #${n}` : text, carbs: s.carbs, caf: !!s.caf, before: i === 0 && Number(s.size) === 0 });
      totalCarbs += s.carbs;
      if (s.caf) cafCount++;
    }
  });
  const perHour = schedule.unit === "min" && at > 0 ? Math.round(totalCarbs / (at / 60) * 10) / 10 : null;
  return { rows, totalCarbs, count: rows.length, cafCount, perHour };
}

// localStorage → schedule; null unless it looks like one (max 12 steps, coerced numbers; abs false when saved before v2)
export function fromJSON(text) {
  let o;
  try { o = JSON.parse(text); } catch { return null; }
  if (!o || typeof o !== "object" || Array.isArray(o)) return null;
  if (typeof o.name !== "string" || !(o.unit in LIMITS) || !Array.isArray(o.steps)) return null;
  const steps = o.steps.slice(0, LIMITS.maxSteps).map(s => mk(Number(s?.size), Number(s?.repeat), String(s?.text ?? DEFAULT_TEXT), Number(s?.carbs), Boolean(s?.caf), Boolean(s?.abs)));
  return { name: o.name, unit: o.unit, steps };
}

// the Import field: the whole schedule in one paste, [name, unit, ...step lines]; joined with ";" (the app also accepts newlines)
export function importSegments(schedule) {
  return [String(schedule.name ?? "").trim(), schedule.unit, ...schedule.steps.map(formatStep)];
}

// one segment per line so people can read it; the ";" keeps it valid if Garmin Connect drops the line breaks
export function importText(schedule) {
  return importSegments(schedule).join(";\n");
}

// import text (from the builder, an AI assistant or typed) → schedule, or null when it isn't one:
// "name;km|miles|min;step;step;…", separated by ; and/or line breaks (also ";\n" and "\r\n"); blank segments are skipped, like the watch does
export function parseImport(text) {
  return readImport(text).schedule;
}

// unit words people and AI assistants write in the six site languages → the watch token; "mi" stays out (looks like min)
const UNIT_WORDS = {
  km: ["km", "kms", "kilometer", "kilometers", "kilometre", "kilometres", "kilomètre", "kilomètres", "kilómetro", "kilómetros", "chilometro", "chilometri"],
  miles: ["miles", "mile", "meile", "meilen", "mijl", "mijlen", "mille", "milles", "milla", "millas", "miglio", "miglia"],
  min: ["min", "mins", "minute", "minutes", "minuten", "minuut", "minuto", "minutos", "minuti"],
};
const unitOf = (s) => {
  if (s === undefined) return null;
  const w = s.toLowerCase().replace(/\.$/, "");
  return Object.keys(UNIT_WORDS).find((u) => UNIT_WORDS[u].includes(w)) ?? null;
};

// { schedule, error, step }: error says why a pasted text is not an import text ("empty", "unit", "steps", "step"; step = its number).
// AI assistants wrap the text in code fences, bullets, bold or a sentence before and after; that is stripped here,
// the builder writes clean text back, so the watch never sees it
export function readImport(text) {
  const fail = (error) => ({ schedule: null, error });
  if (typeof text !== "string") return fail("empty");
  const segs = text.split(/\r?\n/).filter((line) => !/^\s*```/.test(line)).join("\n")
    .replace(/`|\*\*/g, "")
    .split(/[;\r\n]/).map((s) => s.trim().replace(/^[-*•]\s+/, "")).filter(Boolean);
  if (segs.length === 0) return fail("empty");
  const isUnit = (s) => unitOf(s) !== null;
  let at = segs.findIndex((s, i) => i > 0 && isUnit(s)) - 1; // the name precedes the unit
  if (at >= 0 && isUnit(segs[at + 2])) at++; // a name like "Miles" or "Km" after a sentence: the unit is the next segment
  if (at < 0) return fail("unit");
  const rest = segs.slice(at + 2);
  while (rest.length && !/^[@\d]/.test(rest[rest.length - 1])) rest.pop(); // a closing sentence, not a step
  if (rest.length === 0) return fail("steps");
  const steps = rest.slice(0, LIMITS.maxSteps).map(parseStepText);
  const bad = steps.indexOf(null);
  if (bad >= 0) return { ...fail("step"), step: bad + 1 };
  return { schedule: { name: segs[at], unit: unitOf(segs[at + 1]), steps }, error: null };
}

// "start blank": no steps, the unit stays and so does the name (an empty name is the most common validation error)
export function blankSchedule(schedule, fallbackName) {
  return { name: String(schedule.name ?? "").trim() || fallbackName, unit: schedule.unit, steps: [] };
}

// "semicolon": a ; in the name or a step text would split the import on the watch; "long": over the paste limit
export function importWarnings(schedule) {
  const out = [];
  if (importSegments(schedule).some((seg) => seg.includes(";"))) out.push("semicolon");
  if (importText(schedule).length > LIMITS.importMax) out.push("long");
  return out;
}
