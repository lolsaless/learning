/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/04_저장파일_공휴일.js] 저장 파일·공휴일 가져오기
   하는 일 : _처리상태/_시료이력/_설정 JSON 읽고 쓰기, 자동 이력 기록, 설정 적용(휴일 집합), 인터넷 공휴일
   주요 이름: readStatus, writeNotes, addLog, readSettings, applySettings, refreshHolidays, HOLIDAY_SOURCES
   이럴 때 고침: 공휴일 주소, 저장 형식
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── JSON 파일 (공문 폴더에 저장) ───── */
async function readJson(name) {
  try { const fh = await state.root.getFileHandle(name); return JSON.parse(await (await fh.getFile()).text()); } catch (e) { return null; }
}
async function writeJson(name, obj) {
  const fh = await state.root.getFileHandle(name, { create: true });
  const w = await fh.createWritable(); await w.write(JSON.stringify(obj, null, 1)); await w.close();
}
async function readStatus() {
  const j = await readJson(STATUS_FILE);
  state.status = { version: 1, checked: (j && j.checked) || {}, history: (j && j.history) || [] };
}
let saveTimer;
function saveStatusSoon() { clearTimeout(saveTimer); saveTimer = setTimeout(writeStatus, 250); }
async function writeStatus() {
  clearTimeout(saveTimer); saveTimer = null;
  try { state.status.updated = nowIso(); state.status.history = state.status.history.slice(0, HISTORY_MAX); await writeJson(STATUS_FILE, state.status); }
  catch (e) { toast('처리상태 저장 실패: ' + explain(e), 'err'); }
}
async function readNotes() {
  const j = await readJson(NOTES_FILE);
  state.notes = { version: 1, cases: (j && j.cases) || {} };
}
let notesTimer;
function saveNotesSoon() { clearTimeout(notesTimer); notesTimer = setTimeout(writeNotes, 400); }
async function writeNotes() {
  clearTimeout(notesTimer); notesTimer = null;
  try { state.notes.updated = nowIso(); await writeJson(NOTES_FILE, state.notes); }
  catch (e) { toast('메모·이력 저장 실패: ' + explain(e), 'err'); }
}
const notesOf = key => (state.notes.cases[key] = state.notes.cases[key] || { log: [] });
const peekNotes = key => state.notes.cases[key] || { log: [] };
function addLog(key, text, sample, auto) {
  const n = notesOf(key); n.log = n.log || [];
  n.log.push({ id: uid(), at: nowIso(), date: today(), sample: sample || '', text, auto: !!auto });
  saveNotesSoon();
}
async function readSettings() {
  const j = await readJson(SETTINGS_FILE), d = DEFAULT_SETTINGS();
  const s = j && typeof j === 'object' ? j : {};
  state.settings = { ...d, ...s, holidays: { ...d.holidays, ...(s.holidays || {}) }, organize: { ...d.organize, ...(s.organize || {}) } };
  applySettings();
}
let setTimer;
function saveSettingsSoon() { clearTimeout(setTimer); setTimer = setTimeout(writeSettings, 300); }
async function writeSettings() {
  clearTimeout(setTimer); setTimer = null;
  try { await writeJson(SETTINGS_FILE, state.settings); } catch (e) { toast('설정 저장 실패: ' + explain(e), 'err'); }
}
function applySettings() {
  const H = state.settings.holidays;
  state.hol = new Set(); state.holName = new Map();
  for (const y of Object.keys(E2.HOLIDAYS_BUILTIN)) for (const [d, n] of Object.entries(E2.HOLIDAYS_BUILTIN[y])) { state.hol.add(d); state.holName.set(d, n); }
  for (const [d, n] of Object.entries(H.api || {})) { state.hol.add(d); state.holName.set(d, n); }
  for (const [d, n] of Object.entries(H.custom || {})) { state.hol.add(d); state.holName.set(d, n || '지정 휴일'); }
  state.work = new Set(Object.keys(H.work || {}));
  for (const d of state.work) state.hol.delete(d);
  state.stdDays = E2.stdDaysTable(state.settings.stdDays);
  $('#fWm').checked = !!state.settings.watermark;
}
const dayOpt = () => ({ workdays: state.work });

/* ───── 공휴일 (인터넷) ───── */
const HOLIDAY_SOURCES = [
  y => `https://holidays.hyunbin.page/${y}.json`,
  y => `https://date.nager.at/api/v3/PublicHolidays/${y}/KR`,
];
async function fetchHolidayYear(y) {
  let lastErr = '';
  for (const src of HOLIDAY_SOURCES) {
    const url = src(y);
    try {
      const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 7000);
      const r = await fetch(url, { signal: ctl.signal, cache: 'no-store' }); clearTimeout(t);
      if (!r.ok) { lastErr = `${url} → ${r.status}`; continue; }
      const data = E2.parseHolidayJson(await r.json());
      if (Object.keys(data).filter(d => d.startsWith(String(y))).length >= 8) return { url, data };
      lastErr = `${url} → 자료 부족`;
    } catch (e) { lastErr = `${url} → ${e.name === 'AbortError' ? '응답 없음' : (e.message || e)}`; }
  }
  throw new Error(lastErr || '가져오기 실패');
}
async function refreshHolidays(force) {
  const H = state.settings.holidays, y0 = new Date().getFullYear(), out = [];
  let changed = false;
  for (const y of [y0, y0 + 1]) {
    const f = H.fetched[y];
    if (!force && f && f.at && (Date.now() - Date.parse(f.at)) < 30 * 86400000) continue;
    try {
      const { url, data } = await fetchHolidayYear(y);
      for (const k of Object.keys(H.api)) if (k.startsWith(y + '-')) delete H.api[k];
      Object.assign(H.api, data);
      H.fetched[y] = { at: nowIso(), src: url, n: Object.keys(data).length };
      changed = true; out.push(`${y}년 ${Object.keys(data).length}일`);
    } catch (e) { out.push(`${y}년 실패 (${e.message})`); if (!H.fetched[y]) H.fetched[y] = { error: e.message, tried: nowIso() }; }
  }
  if (changed) { applySettings(); await writeSettings(); if (state.docs.length) render(); }
  return out;
}
