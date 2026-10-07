// plan.js — DOM layer of the plan builder. All logic lives in plan-core.js; this file renders state,
// copies values, keeps the schedule in localStorage and sends Umami events (names only, no schedule contents).
import { LIMITS, TEMPLATES, validate, fields, moments, fromJSON, newStep, importText, importWarnings, parseImport } from "./plan-core.js";

const STORAGE = "fuelsteps-plan";
const S = JSON.parse(document.getElementById("plan-i18n").textContent);
const lang = document.documentElement.lang || "en";
const $ = (id) => document.getElementById(id);
const el = (tag, attrs = {}, ...children) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "checked") n.checked = !!v;
    else if (v !== false && v != null) n.setAttribute(k, v === true ? "" : v);
  }
  n.append(...children);
  return n;
};
const fmt = (s, vars) => s.replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const numText = (n) => Number(n).toLocaleString(lang, { maximumFractionDigits: 2 });
const track = (name, data) => { if (typeof window.umami !== "undefined") window.umami.track(name, { ...data, lang }); }; // page language, so events can be split per language

// storage may be blocked (site data off, private mode): the builder still works, it just forgets on reload
let saved = null;
try { saved = localStorage.getItem(STORAGE); } catch (e) { /* no storage */ }
let schedule = fromJSON(saved) || structuredClone(TEMPLATES[0].schedule);

function save() {
  try { localStorage.setItem(STORAGE, JSON.stringify(schedule)); } catch (e) { /* no storage */ }
}

// no clipboard API (http, old browser): copy through a hidden textarea and the legacy command
function legacyCopy(text) {
  const ta = el("textarea", { readonly: true, style: "position:fixed;left:-9999px;top:0", "aria-hidden": "true" });
  ta.value = text;
  document.body.append(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) { /* not supported */ }
  ta.remove();
  return ok;
}

async function copyText(text, button) {
  let ok = false;
  try { await navigator.clipboard.writeText(text); ok = true; } catch (e) { ok = legacyCopy(text); }
  button.dataset.label ??= button.textContent; // the original label survives repeated clicks
  button.textContent = ok ? S.copied : S.copy_failed;
  button.classList.toggle("done", ok);
  setTimeout(() => { button.textContent = button.dataset.label; button.classList.remove("done"); }, ok ? 1200 : 2500);
}

function stepInput(type, value, attrs, onChange) {
  return el("input", { type, value, ...attrs, oninput: (e) => { onChange(e.target); render(); } });
}

// "after" = distance/time after the previous moment, "at" = fixed position from the start (written as @21)
function modeSelect(s) {
  const sel = el("select", { class: "mode", "aria-label": S.col_mode, onchange: (e) => { s.abs = e.target.value === "at"; if (s.abs) s.repeat = 1; render(true); } },
    el("option", { value: "after" }, S.opt_after), el("option", { value: "at" }, S.opt_at));
  sel.value = s.abs ? "at" : "after";
  return sel;
}

// repeat as a picker 1–30 (the watch limit): no typing, nothing to validate; a fixed position never repeats
function repeatSelect(s) {
  const sel = el("select", { "aria-label": S.col_repeat, disabled: !!s.abs, onchange: (e) => { s.repeat = Number(e.target.value); render(); } });
  for (let n = 1; n <= LIMITS.repeatMax; n++) sel.append(el("option", { value: n }, String(n)));
  sel.value = String(Number.isInteger(s.repeat) && s.repeat >= 1 && s.repeat <= LIMITS.repeatMax ? s.repeat : 1);
  if (sel.value !== String(s.repeat)) s.repeat = Number(sel.value);
  return sel;
}

// move a step to another position, rebuild, and put focus back on its handle
function moveStep(from, to) {
  if (to < 0 || to >= schedule.steps.length || to === from) return;
  const [s] = schedule.steps.splice(from, 1);
  schedule.steps.splice(to, 0, s);
  render(true);
  $("plan-steps").querySelectorAll("tr")[to]?.querySelector(".handle button")?.focus();
}

// drag a row by its handle (mouse, touch, pen): the row stays where it is in the DOM and a lifted card follows the
// pointer, an amber line marks the drop spot; the schedule changes on release
const GRIP_ICON = '<svg viewBox="0 0 14 22" aria-hidden="true"><circle cx="4" cy="4" r="2"/><circle cx="10" cy="4" r="2"/><circle cx="4" cy="11" r="2"/><circle cx="10" cy="11" r="2"/><circle cx="4" cy="18" r="2"/><circle cx="10" cy="18" r="2"/></svg>';

function startDrag(e, tr, handle) {
  if (e.button !== 0 && e.pointerType === "mouse") return;
  e.preventDefault();
  const body = $("plan-steps");
  const from = [...body.children].indexOf(tr);
  try { handle.setPointerCapture(e.pointerId); } catch (err) { /* keep going: the listeners below sit on the document */ }
  const stopScroll = (ev) => ev.preventDefault(); // touch fallback when touch-action is ignored
  document.addEventListener("touchmove", stopScroll, { passive: false });
  tr.classList.add("dragging");
  document.body.classList.add("dragging"); // no text selection while a finger or mouse drags the row
  const start = tr.getBoundingClientRect();
  const startY = start.top + start.height / 2;
  let to = from;
  const clearMarks = () => body.querySelectorAll(".drop-before, .drop-after").forEach((r) => r.classList.remove("drop-before", "drop-after"));
  const move = (ev) => {
    if (ev.pointerId !== e.pointerId) return;
    tr.style.transform = `translateY(${ev.clientY - startY}px)`;
    // drop spot: before the first other row whose middle lies below the pointer, else after the last one
    const rows = [...body.children].filter((r) => r !== tr);
    const target = rows.findIndex((r) => { const b = r.getBoundingClientRect(); return ev.clientY < b.top + b.height / 2; });
    clearMarks();
    if (target < 0) { to = rows.length; rows[rows.length - 1]?.classList.add("drop-after"); } else { to = target; rows[target].classList.add("drop-before"); }
    if (to === from) clearMarks(); // back on its own spot: no line
  };
  const end = (ev) => {
    if (ev.pointerId !== e.pointerId) return;
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", end);
    document.removeEventListener("pointercancel", end);
    document.removeEventListener("touchmove", stopScroll);
    tr.classList.remove("dragging");
    tr.style.transform = "";
    document.body.classList.remove("dragging");
    clearMarks();
    if (ev.type !== "pointercancel" && to !== from) moveStep(from, to); else render(true);
  };
  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", end);
  document.addEventListener("pointercancel", end);
}

function renderSteps(v) {
  const body = $("plan-steps");
  body.replaceChildren();
  const lim = LIMITS[schedule.unit];
  const unit = S[schedule.unit];
  schedule.steps.forEach((s, i) => {
    const bad = v.steps[i] !== null;
    const tr = el("tr", { class: bad ? "bad" : "" });
    const handle = el("button", { class: "grip", type: "button", title: S.drag, "aria-label": S.drag,
      onkeydown: (e) => { if (e.key === "ArrowUp") { e.preventDefault(); moveStep(i, i - 1); } if (e.key === "ArrowDown") { e.preventDefault(); moveStep(i, i + 1); } } });
    handle.innerHTML = GRIP_ICON; // static SVG, no user content
    const handleCell = el("td", { class: "handle" }, handle);
    handleCell.addEventListener("pointerdown", (e) => startDrag(e, tr, handle)); // the whole cell is the touch target
    tr.append(
      handleCell,
      el("td", { class: "rep", "data-label": S.col_repeat }, repeatSelect(s)),
      el("td", { class: "size", "data-label": unit }, modeSelect(s), stepInput("number", s.size, { min: 0, max: lim.max, step: lim.step, "aria-label": S.col_mode + " (" + unit + ")" }, (t) => { s.size = t.valueAsNumber; })),
      el("td", { class: "text", "data-label": S.col_text }, stepInput("text", s.text, { maxlength: LIMITS.fieldMax, "aria-label": S.col_text }, (t) => { s.text = t.value; })),
      el("td", { class: "carbs", "data-label": S.col_carbs }, stepInput("number", s.carbs || "", { min: 0, max: LIMITS.carbsMax, step: 1, placeholder: "0", "aria-label": S.col_carbs }, (t) => { s.carbs = Number.isNaN(t.valueAsNumber) ? 0 : t.valueAsNumber; })),
      el("td", { class: "caf", "data-label": S.col_caf }, el("input", { type: "checkbox", checked: s.caf, "aria-label": S.col_caf, onchange: (e) => { s.caf = e.target.checked; render(); } })),
      el("td", { class: "del" }, el("button", { class: "icon-btn", type: "button", title: S.delete, "aria-label": S.delete, onclick: () => { schedule.steps.splice(i, 1); render(true); } }, "✕")));
    body.append(tr);
  });
  $("plan-add").disabled = schedule.steps.length >= LIMITS.maxSteps;
}

function renderErrors(v) {
  const ul = $("plan-errors");
  ul.replaceChildren();
  if (v.name) ul.append(el("li", {}, S["err_" + v.name]));
  if (schedule.steps.length === 0) ul.append(el("li", {}, S.err_no_steps));
  v.steps.forEach((e, i) => { if (e) ul.append(el("li", {}, fmt(S.field_step, { n: i + 1 }) + ": " + S["err_" + e])); });
  v.warnings.forEach((w, i) => { if (w) ul.append(el("li", { class: "warn" }, fmt(S.field_step, { n: i + 1 }) + ": " + S["warn_" + w])); });
  // which validation problems people run into, once per code per visit (no field contents)
  for (const code of new Set([v.name, ...v.steps, ...v.warnings].filter(Boolean))) {
    if (!reportedErrors.has(code)) { reportedErrors.add(code); track("plan_error", { code }); }
  }
}
const reportedErrors = new Set();

// the 10 Garmin Connect fields; name and unit are typed/picked in the app, only the step lines get a copy button
function fieldRows() {
  const f = fields(schedule);
  return [
    { key: "name", label: S.name, value: f.name, copy: false },
    { key: "unit", label: S.unit, value: S["unit_" + f.unit], copy: false },
    ...f.steps.map((v, i) => ({ key: "step" + (i + 1), label: fmt(S.field_step, { n: i + 1 }), value: v, copy: true })),
  ];
}

function renderFields() {
  const ol = $("plan-fields");
  ol.replaceChildren();
  for (const r of fieldRows()) {
    const li = el("li", {}, el("span", { class: "lbl" }, r.label));
    if (r.copy) {
      li.append(el("code", { class: r.value === "-" ? "dash" : "" }, r.value),
        el("button", { class: "copy", type: "button", onclick: (e) => {
          copyText(r.value, e.currentTarget);
          track("plan_copy", { field: r.key, unit: schedule.unit, steps: schedule.steps.length });
        } }, S.copy));
    } else {
      li.append(el("span", { class: "val" }, r.value));
    }
    ol.append(li);
  }
}

function renderImport() {
  const text = importText(schedule);
  $("plan-import").textContent = text;
  // live length against the Import field limit; line breaks count as one character, like in Garmin Connect
  const count = $("plan-import-count");
  count.textContent = `${text.length} / ${LIMITS.importMax}`;
  count.className = "count" + (text.length > LIMITS.importMax ? " bad" : text.length >= LIMITS.importMax - 26 ? " warn" : "");
  const warn = { semicolon: S.warn_import_semicolon, long: fmt(S.warn_import_long, { max: LIMITS.importMax }) };
  $("plan-import-warn").textContent = importWarnings(schedule).map((w) => warn[w]).join(" ");
}

function renderMoments() {
  const m = moments(schedule);
  const body = $("plan-moments");
  body.replaceChildren();
  const unit = S[schedule.unit];
  for (const r of m.rows) {
    body.append(el("tr", {},
      el("td", {}, r.before ? S.before : `${numText(r.at)} ${unit}`),
      el("td", {}, r.label),
      el("td", {}, r.carbs > 0 ? `${r.carbs} g` : ""),
      el("td", {}, r.caf ? el("span", { class: "tag" }, "caf") : "")));
  }
  const parts = [fmt(S.total, { g: m.totalCarbs, n: m.count })];
  if (m.cafCount) parts.push(fmt(S.total_caf, { n: m.cafCount }));
  if (m.perHour !== null) parts.push(fmt(S.per_hour, { g: numText(m.perHour) }));
  $("plan-totals").textContent = m.rows.length ? parts.join(" · ") : "";
}

// rebuild = true after a structural change (move, delete): the row buttons hold focus, but the table must follow the schedule
function render(rebuild = false) {
  const v = validate(schedule);
  if (document.activeElement !== $("plan-name")) $("plan-name").value = schedule.name;
  document.querySelectorAll('#plan-unit input[name="unit"]').forEach((r) => { r.checked = r.value === schedule.unit; });
  // while typing in a step input the table is not rebuilt, so the input keeps focus and its half-typed value; the row state is refreshed in place
  if (rebuild || !document.activeElement || !$("plan-steps").contains(document.activeElement)) renderSteps(v);
  else $("plan-steps").querySelectorAll("tr").forEach((tr, i) => tr.classList.toggle("bad", v.steps[i] !== null));
  renderErrors(v);
  renderFields();
  renderImport();
  renderMoments();
  save();
}

$("plan-name").addEventListener("input", (e) => { schedule.name = e.target.value; render(); });
document.querySelectorAll('#plan-unit input[name="unit"]').forEach((r) => r.addEventListener("change", (e) => { schedule.unit = e.target.value; render(); }));
$("plan-template").addEventListener("change", (e) => {
  const choice = e.target.value; // "" = the placeholder, "empty" = start blank, otherwise a template id
  e.target.value = "";
  if (!choice) return;
  const tpl = TEMPLATES.find((t) => t.id === choice);
  if (schedule.steps.length && !confirm(S.template_confirm)) return;
  schedule = tpl ? structuredClone(tpl.schedule) : { name: "", unit: schedule.unit, steps: [] };
  track("plan_template", { id: choice });
  render();
});
$("plan-add").addEventListener("click", () => { schedule.steps.push(newStep()); render(); });
$("plan-copy-all").addEventListener("click", (e) => {
  copyText(fieldRows().map((r) => `${r.label}: ${r.value}`).join("\n"), e.currentTarget);
  const m = moments(schedule);
  track("plan_copy_all", { unit: schedule.unit, steps: schedule.steps.length, moments: m.count, caf: m.cafCount, total_g: m.totalCarbs });
});
$("plan-import-copy").addEventListener("click", (e) => {
  const text = importText(schedule);
  copyText(text, e.currentTarget);
  track("plan_copy_import", { unit: schedule.unit, steps: schedule.steps.length, len: text.length });
});
$("plan-ai-copy").addEventListener("click", (e) => {
  copyText($("plan-ai-prompt").textContent, e.currentTarget);
  track("plan_copy_prompt", {});
});
// an import text from an AI assistant (or typed) replaces the schedule, so the moments table checks it
$("plan-ai-load").addEventListener("click", () => {
  const parsed = parseImport($("plan-ai-paste").value);
  $("plan-ai-msg").textContent = parsed ? "" : S.ai_load_bad;
  track("plan_load_import", { ok: !!parsed });
  if (!parsed) return;
  schedule = parsed;
  render(true);
  $("plan-name").scrollIntoView({ behavior: "smooth", block: "start" });
});

render();
