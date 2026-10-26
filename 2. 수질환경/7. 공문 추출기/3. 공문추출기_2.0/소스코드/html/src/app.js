/* 검사의뢰 공문 추출기 v2.0 — 화면·폴더 관리
   v2.0: 공문별 폴더 · 시행공문/성적서 대조 · 처리기한(별표2) · 공휴일 달력 · 메모·이력(Word/PDF) · 첨부 HWPX · 워터마크 */
(function () {
'use strict';
const E = window.OdtEngine, E2 = window.OdtEngine2, X = window.MiniXlsx, DG = window.DocGen;
const STATUS_FILE = '_처리상태.json';   // 완료 체크·처리 기록 (v1.x와 같은 파일)
const NOTES_FILE = '_시료이력.json';    // v2.0: 시료접수일·메모·이력·직접 입력 시료
const SETTINGS_FILE = '_설정.json';     // v2.0: 휴일·처리기간·폴더 정리 설정
const DONE_DIR = '성적처리완료';
const STD_RE = /^기준표\.(xlsx|csv)$/i;
const HISTORY_MAX = 2000;
const WEEK = ['일', '월', '화', '수', '목', '금', '토'];

const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const today = () => E2.ymd(new Date());
const nowIso = () => new Date().toISOString();
const shortNo = v => { const m = /-(\d+)$/.exec(v || ''); return m ? m[1] : (v || ''); };
const fmtDay = s => { if (!s) return ''; const d = E2.toDate(s); return `${s.slice(5).replace('-', '.')}(${WEEK[d.getDay()]})`; };
const fmtFull = s => { if (!s) return ''; const d = E2.toDate(s); return `${s.slice(0, 4)}. ${+s.slice(5, 7)}. ${+s.slice(8, 10)}.(${WEEK[d.getDay()]})`; };
const uid = () => Math.random().toString(36).slice(2, 10);

/* ───── 파일 종류 ───── */
const IGNORE = nm => /^(~\$|\.|_)/.test(nm) || STD_RE.test(nm) || /^기준표/.test(nm) || /^공문추출/.test(nm) || /\.(html?|py|json|md|zip|ini|db|lnk|tmp|exe|bat)$/i.test(nm);
const kindOf = nm => /\.odt$/i.test(nm) ? 'odt' : /\.pdf$/i.test(nm) ? 'pdf' : /\.hwpx$/i.test(nm) ? 'hwpx' : /\.(jpe?g|png|gif|bmp|webp)$/i.test(nm) ? 'img' : /\.(tiff?)$/i.test(nm) ? 'tif' : 'doc';
const isHistoryDoc = nm => /^이력_/.test(nm);
const SKIP_DIR = nm => nm === DONE_DIR || /^[_.]/.test(nm) || /^공문추출기/.test(nm);

/* ───── 열 정의 ───── */
const COLS = [
  { k: '접수일', doc: 1, def: 1 },
  { k: '의뢰기관', doc: 1, def: 1 },
  { k: '의뢰자', doc: 1, def: 1 },
  { k: '발신명의', doc: 1, def: 1 },
  { k: '시행', doc: 1, def: 1 },
  { k: '시료번호', def: 1 },
  { k: '검사항목', def: 1, wrap: 1 },
  { k: '시료채취일', def: 1 },
  { k: '시료접수일', doc: 1, def: 1, v2: 1 },
  { k: '처리기한', def: 1, v2: 1 },
  { k: '진행', doc: 1, def: 1, v2: 1, label: '시행공문·성적서' },
  { k: '결과', v2: 1, wrap: 1 },
  { k: '메모', doc: 1, v2: 1 },
  { k: '기준', wrap: 1 },
  { k: '지역구분', wrap: 1 },
  { k: '시료채취자', doc: 1 },
  { k: '접수', label: '접수번호', doc: 1, fmt: shortNo },
  { k: '시행일', doc: 1 }, { k: '제목', doc: 1, wrap: 1 },
  { k: '기준출처' }, { k: '채취시각' }, { k: '채취일출처' }, { k: '업종/성상', wrap: 1 }, { k: '시료량', wrap: 1 },
  { k: '채취지점', wrap: 1 }, { k: '비고', wrap: 1 }, { k: '기타', wrap: 1 },
  { k: '우편번호', doc: 1 }, { k: '주소', doc: 1 }, { k: '전화번호', doc: 1 }, { k: '이메일', doc: 1 }, { k: '폴더', doc: 1 }, { k: '파일명', doc: 1 },
];
const XLSX_EXTRA = ['시료접수일', '처리기한', '남은기간', '기한결정항목', '시행공문', '성적서', '성적서접수번호', '판정', '결과', '메모', '폴더'];
const XLSX_W = { 상태: 9, 접수: 30, 접수일: 11, 의뢰기관: 10, 의뢰자: 12, 발신명의: 18, 시행: 22, 시행일: 11, 제목: 40, 시료번호: 18, 검사항목: 34, 기준: 30, 기준출처: 10, 지역구분: 28, 시료채취일: 16, 채취시각: 8, 채취일출처: 9, 시료채취자: 9, '업종/성상': 22, 시료량: 22, 채취지점: 24, 비고: 18, 기타: 24, 우편번호: 8, 주소: 36, 전화번호: 14, 이메일: 22, 확인필요: 40, 파일명: 44,
  시료접수일: 11, 처리기한: 11, 남은기간: 10, 기한결정항목: 12, 시행공문: 30, 성적서: 30, 성적서접수번호: 16, 판정: 8, 결과: 40, 메모: 40, 폴더: 40 };

function loadPref(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } }
function savePref(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* 무시 */ } }
function loadCols() {
  try { const v = JSON.parse(loadPref('odt-cols-v20', 'null')); if (Array.isArray(v) && v.length) return v; } catch (e) { /* 무시 */ }
  return COLS.filter(c => c.def).map(c => c.k);
}
function saveCols() { savePref('odt-cols-v20', JSON.stringify(state.cols)); }

const DEFAULT_SETTINGS = () => ({
  version: 1,
  holidays: { api: {}, fetched: {}, custom: {}, work: {} }, // api: 인터넷 공휴일, custom: 사용자 지정 휴일, work: 근무일로 지정
  stdDays: {},           // 처리기간 사용자 설정 {항목: 일수}
  dueBasis: 'max',       // 처리기한 기준: 'max' 가장 긴 항목 | 'min' 가장 짧은 항목
  imminent: 1,           // 남은 근무일 n일 이하 → 빨간색
  soon: 3,               // n일 이하 → 주황색
  organize: { auto: false, asked: false }, // 공문별 폴더 자동 정리
  nestDone: true,        // 처리 완료 시 공문 폴더를 성적처리완료로 옮김
  watermark: true,       // 의뢰공문 우측 상단에 시료접수일 표시
});
const state = {
  root: null, savedHandle: null,
  docs: [], doneDocs: [], doneCount: 0,
  inbox: { replies: [], reports: [], attach: [], requests: [], groups: [] },
  cache: new Map(), fileCache: new Map(),
  status: { version: 1, checked: {}, history: [] },
  notes: { version: 1, cases: {} },
  settings: DEFAULT_SETTINGS(),
  hol: new Set(), holName: new Map(), work: new Set(), stdDays: E2.stdDaysTable(),
  stdTable: [], stdFile: '', stdFilled: 0,
  excluded: [], busy: false, lastScan: 0,
  sort: { key: '접수일', dir: -1 },
  detailMode: loadPref('odt-detail-mode', 'side'), viewer: 'req', previewCache: new Map(),
  filter: { q: '', org: '', state: 'pending', warn: false },
  cols: loadCols(), selected: null,
};

/* ───── 압축 해제 ───── */
async function inflateRaw(data) {
  const ds = new DecompressionStream('deflate-raw');
  return new Uint8Array(await new Response(new Blob([data]).stream().pipeThrough(ds)).arrayBuffer());
}

/* ───── 폴더 핸들 저장 (IndexedDB) ───── */
function idb() { return new Promise((res, rej) => { const r = indexedDB.open('odt-extractor', 1); r.onupgradeneeded = () => r.result.createObjectStore('kv'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); }); }
async function idbGet(k) { try { const db = await idb(); return await new Promise(res => { const q = db.transaction('kv').objectStore('kv').get(k); q.onsuccess = () => res(q.result); q.onerror = () => res(null); }); } catch (e) { return null; } }
async function idbSet(k, v) { try { const db = await idb(); await new Promise(res => { const t = db.transaction('kv', 'readwrite'); t.objectStore('kv').put(v, k); t.oncomplete = res; t.onerror = res; }); } catch (e) { /* 무시 */ } }

/* ───── 공통 UI ───── */
let toastTimer;
function toast(msg, kind) {
  const t = $('#toast'); t.textContent = msg; t.className = 'toast' + (kind === 'err' ? ' err' : ''); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, kind === 'err' ? 7000 : 3500);
}
function busy(on, text) { $('#busy').hidden = !on; if (text) $('#busyText').textContent = text; }
function modal(title, html, okLabel, opts = {}) {
  return new Promise(resolve => {
    $('#modalTitle').textContent = title; $('#modalBody').innerHTML = html;
    $('#modal').querySelector('.modal-box').style.width = opts.width || '';
    const ok = $('#modalOk'), cancel = $('#modalCancel');
    ok.textContent = okLabel || '확인'; ok.className = 'btn ' + (opts.danger ? 'danger' : 'primary');
    cancel.hidden = !!opts.infoOnly; cancel.textContent = opts.cancelLabel || '취소';
    $('#modal').hidden = false;
    const done = v => { $('#modal').hidden = true; ok.onclick = cancel.onclick = null; document.removeEventListener('keydown', onKey); resolve(v); };
    const onKey = e => { if (e.key === 'Escape' && !$('#datePop').hidden) return; if (e.key === 'Escape') done(false); };
    ok.onclick = () => { if (opts.validate && !opts.validate()) return; done(opts.collect ? opts.collect() || true : true); };
    cancel.onclick = () => done(false);
    document.addEventListener('keydown', onKey);
    if (opts.onOpen) opts.onOpen($('#modalBody')); else ok.focus();
  });
}
const info = (title, html, opts = {}) => modal(title, html, '닫기', { infoOnly: true, ...opts });

/* ───── 시작 ───── */
async function init() {
  bindUi();
  if (!('showDirectoryPicker' in window) || typeof DecompressionStream === 'undefined') { showUnsupported(); return; }
  if (window.pdfjsLib) { try { window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'about:blank'; } catch (e) { /* 무시 */ } }
  const h = await idbGet('root');
  if (h) {
    state.savedHandle = h;
    let p = 'prompt'; try { p = await h.queryPermission({ mode: 'readwrite' }); } catch (e) { /* 무시 */ }
    if (p === 'granted') { await connect(h); return; }
    showWelcome(h.name);
  } else showWelcome();
}
function showUnsupported() {
  $('#btnPick').disabled = true;
  $('#emptyBox').innerHTML = `<div class="notice"><b>이 브라우저에서는 사용할 수 없습니다.</b><br>공문 폴더를 읽고 파일을 옮기려면 <b>Microsoft Edge</b> 또는 <b>Chrome</b>(최신 버전)에서 이 파일을 열어 주세요.</div>`;
}
function showWelcome(savedName) {
  $('#toolbar').hidden = true; $('#bottombar').hidden = true; $('#grid').hidden = true; $('#emptyBox').hidden = false; $('#banner').hidden = true;
  $('#emptyBox').innerHTML = `
    <h2>공문 폴더를 연결하세요</h2>
    <ol>
      <li><b>공문 폴더 선택</b>을 누르고, 검사의뢰 공문(ODT)·시행공문·시험성적서(PDF)를 모아 두는 폴더를 고릅니다.</li>
      <li>브라우저가 폴더 접근 허용을 물으면 <b>파일 보기 및 편집 허용</b>을 누릅니다. (공문별 폴더 만들기·파일 옮기기에 필요)</li>
      <li>폴더 안의 공문을 모두 읽어 <b>시료 1개당 1행</b>으로 보여 주고, 시행공문·성적서를 공문과 짝지어 줍니다.</li>
    </ol>
    ${savedName ? `<p>지난번에 쓰던 폴더: <b>${esc(savedName)}</b></p><button class="btn primary" id="btnReconnect">${esc(savedName)} 다시 연결</button>` : ''}
    <button class="btn ${savedName ? '' : 'primary'}" id="btnPick2">공문 폴더 선택</button>`;
  const rc = $('#btnReconnect'); if (rc) rc.onclick = reconnect;
  $('#btnPick2').onclick = pickFolder;
}
async function pickFolder() {
  try {
    const h = await window.showDirectoryPicker({ id: 'odt-folder', mode: 'readwrite' });
    await idbSet('root', h); state.savedHandle = h; await connect(h);
  } catch (e) { if (e.name !== 'AbortError') toast('폴더 선택 실패: ' + e.message, 'err'); }
}
async function reconnect() {
  const h = state.savedHandle; if (!h) return pickFolder();
  try {
    const p = await h.requestPermission({ mode: 'readwrite' });
    if (p === 'granted') await connect(h); else toast('폴더 접근이 허용되지 않았습니다.', 'err');
  } catch (e) { toast('다시 연결하지 못했습니다. [공문 폴더 선택]으로 다시 골라 주세요. (' + e.message + ')', 'err'); }
}
window.__odtConnect = h => connect(h); // 시험·자동화용
window.__odtState = () => state;       // 시험용

async function connect(h) {
  state.root = h; state.cache.clear(); state.fileCache.clear(); state.previewCache.clear(); state.selected = null;
  $('#folderName').textContent = h.name; $('#btnRefresh').disabled = false;
  await readStatus(); await readNotes(); await readSettings();
  await scan();
  refreshHolidays(false);
}

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

/* ───── 폴더 읽기 ───── */
async function listDir(dir, path) {
  const files = [], dirs = [];
  for await (const [name, h] of dir.entries()) {
    const nm = name.normalize('NFC');
    if (h.kind === 'directory') { dirs.push({ name, nm, handle: h }); continue; }
    if (IGNORE(nm)) { if (STD_RE.test(nm) && !path) files.push({ dir, path, name, nm, handle: h, kind: 'std' }); continue; }
    files.push({ dir, path, name, nm, handle: h, kind: kindOf(nm) });
  }
  for (const f of files) { try { const file = await f.handle.getFile(); f.size = file.size; f.mtime = file.lastModified; } catch (e) { f.size = 0; f.mtime = 0; } }
  files.sort((a, b) => a.nm.localeCompare(b.nm, 'ko')); dirs.sort((a, b) => a.nm.localeCompare(b.nm, 'ko'));
  return { files, dirs };
}
const fkey = f => `${f.path}/${f.nm}|${f.size}|${f.mtime}`;
async function fileBytes(f) { return new Uint8Array(await (await f.handle.getFile()).arrayBuffer()); }
// ODT 읽기 → {result, reply, error}
async function parseOdtEntry(f) {
  const ck = 'odt:' + fkey(f);
  if (state.fileCache.has(ck)) return state.fileCache.get(ck);
  const out = {};
  try {
    if (!f.size) throw new Error('빈 파일 (다운로드 중이거나 손상된 파일)');
    out.result = await E.extractOdt(await fileBytes(f), f.nm, inflateRaw);
    if (E2.isReply(out.result)) out.reply = E2.parseReply(out.result);
  } catch (e) { out.error = (e && e.message) || String(e); }
  state.fileCache.set(ck, out);
  return out;
}
// PDF 텍스트 → 시험성적서이면 해석 결과, 아니면 null
async function pdfTextPages(bytes) {
  const doc = await window.pdfjsLib.getDocument({ data: bytes, isEvalSupported: false }).promise;
  const pages = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const p = await doc.getPage(i), vp = p.getViewport({ scale: 1 }), tc = await p.getTextContent();
    pages.push({ w: vp.width, h: vp.height, items: tc.items.filter(t => t.str != null).map(t => ({ s: t.str, x: t.transform[4], y: vp.height - t.transform[5], w: t.width, h: Math.abs(t.transform[3]) || 10 })) });
    if (i === 1 && !pages[0].items.some(t => /접|수|번|호/.test(t.s))) break; // 성적서 아님 (스캔 PDF 등) — 첫 쪽만 확인
  }
  doc.destroy && doc.destroy();
  return pages;
}
async function parseReportEntry(f) {
  const ck = 'pdf:' + fkey(f);
  if (state.fileCache.has(ck)) return state.fileCache.get(ck);
  let rep = null;
  if (window.pdfjsLib && f.size) {
    try { const r = E2.parseReportPdf(await pdfTextPages(await fileBytes(f)), f.nm); if (r.samples.length) rep = r; } catch (e) { rep = null; }
  }
  state.fileCache.set(ck, rep);
  return rep;
}
async function parseHwpxEntry(f) {
  const ck = 'hwpx:' + fkey(f);
  if (state.fileCache.has(ck)) return state.fileCache.get(ck);
  let h = null; try { h = await E2.parseHwpx(await fileBytes(f), inflateRaw); } catch (e) { h = { grids: [], paras: [], error: e.message }; }
  state.fileCache.set(ck, h);
  return h;
}
// 폴더 하나의 파일 분류: 의뢰공문 / 시행공문 / 성적서 / 첨부
async function classifyFiles(files, progress) {
  const out = { requests: [], replies: [], reports: [], attach: [], std: null };
  for (const f of files) {
    if (f.kind === 'std') { out.std = f; continue; }
    if (f.kind === 'odt') {
      const p = await parseOdtEntry(f); progress && progress();
      if (p.reply) out.replies.push({ f, info: p.reply, result: p.result });
      else out.requests.push({ f, p });
    } else if (f.kind === 'pdf' && !isHistoryDoc(f.nm)) {
      const rep = await parseReportEntry(f); progress && progress();
      if (rep) out.reports.push({ f, rep }); else out.attach.push(f);
    } else if (!isHistoryDoc(f.nm)) out.attach.push(f);
  }
  return out;
}
async function getDoneDir(create) { try { return await state.root.getDirectoryHandle(DONE_DIR, create ? { create: true } : undefined); } catch (e) { return null; } }

/* ───── 읽기 전체 (scan) ───── */
const keyOfReq = req => req.p && req.p.result && req.p.result.doc.접수 ? req.p.result.doc.접수 : 'file:' + req.f.nm;
async function scan(opts = {}) {
  if (!state.root) return;
  if (state.busy) { state.pendingScan = { ...(state.pendingScan || {}), ...opts }; return; } // 읽는 중이면 끝난 뒤 한 번 더
  state.busy = true;
  let organizeNow = false;
  try {
    if (!opts.quiet) busy(true, '공문 폴더 읽는 중…');
    let n = 0; const prog = () => { n++; if (!opts.quiet && n % 4 === 0) busy(true, `파일 읽는 중… ${n}`); };
    const top = await listDir(state.root, '');
    const rc = await classifyFiles(top.files, prog);
    const inbox = { replies: rc.replies, reports: rc.reports, attach: rc.attach, requests: rc.requests.map(x => ({ ...x, dir: state.root })), groups: [] };
    const cases = [], other = [];
    for (const d of top.dirs) {
      if (SKIP_DIR(d.nm)) continue;
      const L = await listDir(d.handle, d.nm);
      const C = await classifyFiles(L.files, prog);
      if (C.requests.length) {
        const multi = new Set(C.requests.map(keyOfReq)).size > 1;
        cases.push({ dir: d.handle, name: d.nm, C, multi });
        if (multi) inbox.groups.push({ dir: d.handle, name: d.nm, C });
      } else { inbox.replies.push(...C.replies); inbox.reports.push(...C.reports); inbox.attach.push(...C.attach); }
      L.dirs.forEach(x => other.push(d.nm + '/' + x.nm));
    }
    state.inbox = inbox; state.excluded = other;
    const docs = [];
    for (const c of cases) for (const req of c.C.requests) docs.push(await makeDoc(req, c.dir, c.name, c.multi ? subsetFor(req, c.C) : c.C, 'root', !c.multi));
    for (const req of inbox.requests) docs.push(await makeDoc(req, state.root, '', subsetFor(req, { replies: [], reports: [], attach: inbox.attach.filter(f => f.dir === state.root) }), 'root', false));
    state.docs = docs;
    await scanDone(opts);
    await loadStd(rc.std);
    E.markDuplicates(state.docs.filter(d => d.result).map(d => d.result));
    E.markDuplicates(state.doneDocs.filter(d => d.result).map(d => d.result));
    state.stdFilled = E.applyStdTable([...state.docs, ...state.doneDocs].filter(d => d.result).map(d => d.result), state.stdTable);
    for (const d of state.docs) matchDoc(d, inbox);
    for (const d of state.doneDocs) matchDoc(d, { replies: [], reports: [] });
    state.lastScan = Date.now();
    render();
    const loose = inbox.requests.length + inbox.groups.reduce((a, g) => a + g.C.requests.length, 0);
    if (loose && !opts.noOrganize) organizeNow = state.settings.organize.auto ? 'auto' : (!state.settings.organize.asked ? 'ask' : '');
  } catch (e) {
    if (e && e.name === 'NotAllowedError') { toast('폴더 접근 권한이 없습니다. 다시 연결해 주세요.', 'err'); showWelcome(state.root.name); }
    else { console.error(e); toast('폴더를 읽지 못했습니다: ' + explain(e), 'err'); }
  } finally { state.busy = false; busy(false); }
  if (state.pendingScan) { const p = state.pendingScan; state.pendingScan = null; return scan(p); }
  if (organizeNow === 'auto') await organizeAll(true);
  else if (organizeNow === 'ask') await askOrganize();
}
// 여러 공문이 한 폴더에 있을 때: 붙임 이름이 맞는 첨부만 그 공문 것으로 봄
function subsetFor(req, C) {
  const names = E2.attachmentNames(req.p.result ? req.p.result.doc.본문 : []);
  return { replies: [], reports: [], attach: C.attach.filter(f => names.length && E2.attachScore(f.nm, names) >= 0.6), shared: true };
}
async function makeDoc(req, dir, dirName, C, loc, organized) {
  const f = req.f, p = req.p;
  const d = { id: `${loc}|${fkey(f)}`, f, name: f.name, nm: f.nm, handle: f.handle, loc, dir, dirName, organized, C: C || { replies: [], reports: [], attach: [] }, base: p.result || null, error: p.error };
  d.key = p.result && p.result.doc.접수 ? p.result.doc.접수 : 'file:' + f.nm;
  d.result = await augment(d);
  return d;
}
// 시료 표가 없는 공문: 직접 입력 > 첨부 HWPX > 원래 결과
async function augment(d) {
  const base = d.base; if (!base) return null;
  const n = peekNotes(d.key);
  if (n.manual && n.manual.length) { try { return E2.samplesFromManual(base, n.manual); } catch (e) { console.error(e); } }
  if (base.warnings.includes('시료표 미인식')) {
    const hw = d.C.attach.filter(f => f.kind === 'hwpx');
    if (hw.length) {
      const list = []; for (const f of hw) list.push({ name: f.nm, parsed: await parseHwpxEntry(f) });
      const r = E2.samplesFromAttachments(base, list); if (r) return r;
    }
  }
  return base;
}
async function scanDone(opts) {
  state.doneDocs = []; state.doneCount = 0;
  const doneDir = await getDoneDir(false); if (!doneDir) return;
  const L = await listDir(doneDir, DONE_DIR);
  state.doneCount = L.files.filter(f => f.kind === 'odt').length + L.dirs.length;
  if (state.filter.state !== 'done') return;
  let i = 0;
  const C0 = await classifyFiles(L.files.filter(f => f.kind === 'odt'));
  for (const req of C0.requests) state.doneDocs.push(await makeDoc(req, doneDir, '', { replies: [], reports: [], attach: [] }, 'done', false));
  for (const d of L.dirs) {
    const S = await listDir(d.handle, DONE_DIR + '/' + d.nm);
    const C = await classifyFiles(S.files);
    for (const req of C.requests) state.doneDocs.push(await makeDoc(req, d.handle, d.nm, C, 'done', true));
    if (!opts.quiet && ++i % 5 === 0) busy(true, `완료 공문 읽는 중… ${i} / ${L.dirs.length}`);
  }
}
async function loadStd(en) {
  state.stdTable = []; state.stdFile = '';
  if (!en) return;
  try {
    const b = await fileBytes(en);
    const rows = /\.csv$/i.test(en.nm) ? E.parseCsv(E.decodeText(b)) : await E.readXlsxRows(b, inflateRaw);
    state.stdTable = E.parseStdTable(rows); state.stdFile = en.nm;
  } catch (e) { toast(`기준표(${en.nm})를 읽지 못했습니다. 엑셀에서 열려 있다면 닫고 [새로고침] 하세요. (${explain(e)})`, 'err'); }
}

/* ───── 대조: 의뢰공문 ↔ 시행공문 ↔ 성적서 ───── */
function matchDoc(d, inbox) {
  d.match = { replies: [], reports: [], got: 0, total: 0, extra: [], replyOk: false, reportState: 'none' };
  if (!d.result) return;
  const doc = d.result.doc, nos = d.result.rows.map(r => r.시료번호).filter(Boolean);
  const replies = [], reports = [];
  if (!d.C.shared) for (const x of d.C.replies) replies.push({ ...x, inCase: true, score: 1 });
  for (const x of inbox.replies || []) { const s = E2.matchReply(doc, x.info); if (s > 0) { replies.push({ ...x, score: s }); (x.usedBy = x.usedBy || new Set()).add(d.key); } }
  if (!d.C.shared) for (const x of d.C.reports) reports.push({ ...x, inCase: true, m: E2.matchReport(doc, nos, x.rep) });
  for (const x of inbox.reports || []) { const m = E2.matchReport(doc, nos, x.rep); if (m.level !== 'none') { reports.push({ ...x, m }); (x.usedBy = x.usedBy || new Set()).add(d.key); } }
  const got = new Set(); reports.forEach(x => x.m.matched.forEach(n => got.add(n)));
  const extra = [...new Set(reports.flatMap(x => x.m.extra))], orgBad = reports.some(x => x.m.orgGood === false && x.m.level !== 'none');
  d.match = { replies, reports, got: got.size, total: nos.length, extra, orgBad,
    replyOk: replies.some(x => x.score === 1),
    reportState: !reports.length ? 'none' : (nos.length && got.size === nos.length && !extra.length && !orgBad ? 'full' : 'partial') };
  for (const r of d.result.rows) {
    r._rep = null;
    for (const x of reports) {
      const s = x.rep.samples.find(s => E2.noKey(s.시료명) === E2.noKey(r.시료번호) && (x.inCase || E2.noKey(s.공문번호) === E2.noKey(doc.시행)));
      if (s) { r._rep = { s, f: x.f }; break; }
    }
  }
}
const readyToFinish = d => d.match && d.match.replyOk && d.match.reportState === 'full';

/* ───── 처리기한 ───── */
function caseRecv(d) {
  const n = peekNotes(d.key);
  if (n.recv) return { date: n.recv, est: false, before13: !!n.before13 };
  const dd = d.result && d.result.doc.접수일;
  return dd ? { date: dd, est: true, before13: !!n.before13 } : null;
}
function rowDue(d, r) {
  if (!d.result || !r.시료번호) return null;
  const rc = caseRecv(d); if (!rc) return null;
  const items = (r._items || []).map(i => i.name);
  if (!items.length) return null;
  const sd = E2.sampleDeadline(items, rc.date, state.hol, state.stdDays, { countReceiptDay: rc.before13, basis: state.settings.dueBasis, ...dayOpt() });
  sd.est = rc.est;
  sd.rem = sd.due ? E2.remaining(today(), sd.due, state.hol, dayOpt()) : null;
  return sd;
}
function dueClass(sd, finished) {
  if (!sd || !sd.rem || finished) return '';
  if (sd.rem.overdue) return 'due-over';
  if (sd.rem.days <= state.settings.imminent) return 'due-imm';
  if (sd.rem.days <= state.settings.soon) return 'due-soon';
  return '';
}
const remText = rem => !rem ? '' : rem.overdue ? `${-rem.days}일 초과` : rem.days === 0 ? '오늘 마감' : `D-${rem.days}`;
function docDueMin(d) {
  let best = null;
  if (d.result) for (const r of d.result.rows) { const sd = rowDue(d, r); if (sd && sd.due && (!best || sd.due < best.due)) best = sd; }
  return best;
}

/* ───── 상태 판정 · 정렬 · 필터 ───── */
const isChecked = d => d.loc === 'root' && !!state.status.checked[d.key];
const docRows = d => d.result ? d.result.rows : [{ 파일명: d.nm, 확인필요: '읽기 실패: ' + d.error }];
function docWarn(d) { return d.error ? true : docRows(d).some(r => r.확인필요); }
function isUrgent(d) { if (d.loc !== 'root') return false; const m = docDueMin(d); return !!(m && m.rem && (m.rem.overdue || m.rem.days <= state.settings.soon)); }
function sortVal(d, key) {
  const r = docRows(d)[0] || {};
  const rno = () => { const n = shortNo(r.접수); return /^\d+$/.test(n) ? n.padStart(10, '0') : ''; };
  if (key === '접수') return rno() || (state.sort.dir > 0 ? '~' : '') + (r.접수 || d.nm);
  if (key === '접수일') return (r.접수일 || (state.sort.dir > 0 ? '9999' : '0000')) + '|' + rno();
  if (key === '처리기한') { const m = docDueMin(d); return m && m.due ? m.due : (state.sort.dir > 0 ? '9999' : '0000'); }
  if (key === '시료접수일') { const rc = caseRecv(d); return rc ? rc.date : ''; }
  if (key === '진행') return d.match ? (d.match.replyOk ? 2 : 0) + (d.match.reportState === 'full' ? 2 : d.match.reportState === 'partial' ? 1 : 0) + '' : '';
  return String(r[key] == null ? '' : r[key]);
}
function visibleDocs() {
  const f = state.filter;
  const src = f.state === 'done' ? state.doneDocs : state.docs;
  const q = f.q.trim().toLowerCase();
  const list = src.filter(d => {
    if (f.state === 'checked' && !isChecked(d)) return false;
    if (f.state === 'unchecked' && isChecked(d)) return false;
    if (f.state === 'urgent' && !isUrgent(d)) return false;
    if (f.state === 'ready' && !readyToFinish(d)) return false;
    const rows = docRows(d);
    if (f.org && (rows[0].의뢰기관 || '') !== f.org) return false;
    if (f.warn && !docWarn(d)) return false;
    if (q && !d.nm.toLowerCase().includes(q) && !(d.dirName || '').toLowerCase().includes(q) && !rows.some(r => E.COLUMNS.some(c => String(r[c] || '').toLowerCase().includes(q))) && !(peekNotes(d.key).memo || '').toLowerCase().includes(q)) return false;
    return true;
  });
  const { key, dir } = state.sort;
  list.sort((a, b) => { const va = sortVal(a, key), vb = sortVal(b, key); return (va < vb ? -1 : va > vb ? 1 : 0) * dir || a.nm.localeCompare(b.nm, 'ko'); });
  return list;
}
function checkedGroups() {
  const by = new Map();
  for (const d of state.docs) if (isChecked(d)) { if (!by.has(d.key)) by.set(d.key, []); by.get(d.key).push(d); }
  return [...by.entries()].map(([key, docs]) => ({ key, docs }));
}

/* ───── 칸 값 ───── */
function progressHtml(d) {
  if (!d.match || !d.result) return { html: '', text: '' };
  const m = d.match, nrep = m.replies.length;
  const a = m.replyOk ? `<span class="pill ok" title="${esc(m.replies.map(x => x.f.nm).join('\n'))}">시행 ✔</span>` : nrep ? `<span class="pill part" title="공문번호는 같지만 기관명이 다릅니다">시행 △</span>` : `<span class="pill none">시행 —</span>`;
  const b = m.reportState === 'full' ? `<span class="pill ok" title="${esc(m.reports.map(x => x.f.nm).join('\n'))}">성적서 ${m.got}/${m.total}</span>`
    : m.reportState === 'partial' ? `<span class="pill part" title="${esc(['일부만 일치', ...m.reports.map(x => x.f.nm), m.extra.length ? '공문에 없는 시료: ' + m.extra.join(', ') : '', m.orgBad ? '의뢰기관 다름' : ''].filter(Boolean).join('\n'))}">성적서 ${m.got}/${m.total}${m.extra.length ? '+' + m.extra.length : ''}</span>` : `<span class="pill none">성적서 —</span>`;
  const text = `${m.replyOk ? '시행공문 일치' : nrep ? '시행공문 일부' : '시행공문 없음'} · ${m.reportState === 'none' ? '성적서 없음' : `성적서 ${m.got}/${m.total}`}`;
  return { html: a + ' ' + b, text };
}
function resultText(r) {
  if (!r._rep) return '';
  const s = r._rep.s;
  return (s.판정 ? s.판정 + ' — ' : '') + s.결과.map(x => `${x.항목명 || x.항목} ${x.결과}`).join(', ');
}
function cellOf(d, r, c, finished) {
  const k = c.k;
  if (k === '시료접수일') {
    if (!d.result) return { html: '' };
    const rc = caseRecv(d);
    const btn = d.loc === 'root' ? ` data-act="recv" title="눌러서 시료접수일 입력 (달력)"` : '';
    if (!rc) return { html: `<span class="recv-cell empty"${btn}>입력</span>`, text: '' };
    return { html: `<span class="recv-cell${rc.est ? ' est' : ''}"${btn}>${esc(fmtDay(rc.date))}${rc.est ? '<small> 추정</small>' : ''}${rc.before13 ? '<small> 13시前</small>' : ''}</span>`, text: rc.date + (rc.est ? ' (공문 접수일 기준)' : '') };
  }
  if (k === '처리기한') {
    const sd = rowDue(d, r); if (!sd) return { html: '' };
    if (!sd.due) return { html: `<span class="muted" title="처리기간이 정해지지 않은 항목: ${esc(sd.unknown.join(', '))}">기간 미설정</span>`, text: '' };
    const cls = dueClass(sd, finished);
    const tip = `${sd.item} ${sd.days}일 (${sd.why})${sd.unknown.length ? '\n기간 미설정 항목: ' + sd.unknown.join(', ') : ''}${sd.flagged.length ? '\n준용 항목(확인 필요): ' + sd.flagged.join(', ') : ''}${sd.est ? '\n시료접수일 미입력 — 공문 접수일 기준' : ''}`;
    return { html: `<span class="due ${cls}" title="${esc(tip)}">${esc(fmtDay(sd.due))} <b>${finished ? '완료' : esc(remText(sd.rem))}</b>${sd.unknown.length || sd.flagged.length ? '<sup>*</sup>' : ''}</span>`, text: sd.due, cls: cls ? 'td-' + cls : '' };
  }
  if (k === '진행') { const p = progressHtml(d); return { html: p.html, text: p.text }; }
  if (k === '결과') { const t = resultText(r); const bad = r._rep && /부적합/.test(r._rep.s.판정); return { html: t ? `<span class="${bad ? 'res-bad' : ''}">${esc(t)}</span>` : '', text: t }; }
  if (k === '메모') { const n = peekNotes(d.key); const cnt = (n.log || []).filter(x => !x.auto).length; const t = (n.memo || '').split('\n')[0]; return { html: (cnt ? `<span class="badge">${cnt}</span> ` : '') + esc(t), text: n.memo || '' }; }
  if (k === '폴더') return { html: esc(d.dirName || (d.loc === 'root' ? '(정리 전)' : '')), text: d.dirName || '' };
  const v = r[k] == null ? '' : r[k];
  return { text: v, html: esc(c.fmt ? c.fmt(v) : v) };
}

/* ───── 그리기 ───── */
function activeCols() { return COLS.filter(c => state.cols.includes(c.k)); }
function render() {
  $('#toolbar').hidden = false; $('#bottombar').hidden = false;
  renderOrgOptions(); renderBanner();
  $('#fState').querySelector('option[value=done]').textContent = `성적처리완료 폴더 (${state.doneCount})`;
  const cols = activeCols(), list = visibleDocs(), isDone = state.filter.state === 'done';
  const grid = $('#grid'), empty = $('#emptyBox');
  if (!list.length) {
    grid.hidden = true; empty.hidden = false;
    const none = (isDone ? state.doneDocs : state.docs).length === 0;
    empty.innerHTML = none
      ? (isDone ? '<h2>성적처리완료 폴더가 비어 있습니다</h2>' : `<h2>공문 폴더에 의뢰 공문(ODT)이 없습니다</h2><p>검사의뢰 공문(ODT)을 <b>${esc(state.root.name)}</b> 폴더에 저장한 뒤 <b>새로고침</b>을 누르세요. 이 창으로 돌아오면 자동으로 다시 읽습니다.</p>`)
      : '<h2>조건에 맞는 공문이 없습니다</h2><p>검색어나 필터를 바꿔 보세요.</p>';
  } else {
    empty.hidden = true; grid.hidden = false;
    const s = state.sort;
    let th = `<tr><th class="c-chk">${isDone ? '되돌리기' : `<input type="checkbox" id="chkAll" title="보이는 공문 모두 완료 체크">`}</th>`;
    for (const c of cols) th += `<th data-k="${esc(c.k)}" class="${s.key === c.k ? 'sorted' : ''}" data-dir="${s.dir > 0 ? '▲' : '▼'}">${esc(c.label || c.k)}</th>`;
    th += `<th data-k="확인필요" class="${s.key === '확인필요' ? 'sorted' : ''}" data-dir="${s.dir > 0 ? '▲' : '▼'}">확인필요</th></tr>`;
    grid.tHead.innerHTML = th;
    const parts = [];
    for (const d of list) {
      const rows = docRows(d), n = rows.length, chk = isChecked(d), finished = isDone;
      const dup = d.result && d.result.duplicate;
      const cls = [chk && 'is-checked', isDone && 'is-done', dup && 'is-dup', d.error && 'is-err', state.selected === d.id && 'is-sel', readyToFinish(d) && !chk && !isDone && 'is-ready'].filter(Boolean).join(' ');
      rows.forEach((r, i) => {
        let tr = `<tr data-id="${esc(d.id)}" class="${cls}${i === 0 ? ' grp-first' : ''}">`;
        if (i === 0) tr += `<td class="c-chk" rowspan="${n}">${isDone ? `<button class="btn small" data-act="restore" title="공문 폴더로 되돌리기">되돌리기</button>` : `<input type="checkbox" data-act="check" ${chk ? 'checked' : ''} title="이 공문 완료 체크">`}</td>`;
        if (d.error) { tr += `<td class="c-warn err wrap" colspan="${cols.length + 1}">⚠ 읽기 실패 — <b>${esc(d.nm)}</b> : ${esc(d.error)}</td></tr>`; parts.push(tr); return; }
        for (const c of cols) {
          if (c.doc && i > 0) continue;
          const v = cellOf(d, r, c, finished);
          const span = c.doc && n > 1 ? ` rowspan="${n}"` : '';
          let extra = (c.wrap ? 'wrap' : '') + (v.cls ? ' ' + v.cls : '');
          let html = v.html;
          if (c.k === '시료채취일' && r.시료채취일 === '채취일자 확인 필요') extra += ' cell-warn';
          if (c.k === '시료채취일' && r.채취일출처 === '본문') html += '<span class="badge" title="공문 본문 문장에서 찾은 날짜">본문</span>';
          if (c.k === '시료번호' && r.시료출처) html += `<span class="badge" title="시료 목록 출처">${esc(r.시료출처 === '직접 입력' ? '직접' : '첨부')}</span>`;
          if (c.k === '기준' && /기준표/.test(r.기준출처 || '')) html += '<span class="badge ok" title="기준표에서 찾은 값 포함">기준표</span>';
          tr += `<td class="${extra.trim()}"${span} title="${esc(v.text)}">${html}</td>`;
        }
        const w = r.확인필요 || '';
        tr += `<td class="c-warn${d.error ? ' err' : ''}" title="${esc(w)}">${w ? '⚠ ' + esc(w) : ''}</td></tr>`;
        parts.push(tr);
      });
    }
    grid.tBodies[0].innerHTML = parts.join('');
    const all = $('#chkAll');
    if (all) { const vis = list.filter(d => d.loc === 'root'); all.checked = vis.length > 0 && vis.every(isChecked); all.indeterminate = !all.checked && vis.some(isChecked); }
  }
  renderStats(list);
  renderDetail();
}
function renderOrgOptions() {
  const sel = $('#fOrg'), cur = state.filter.org;
  const orgs = [...new Set([...state.docs, ...state.doneDocs].map(d => (docRows(d)[0] || {}).의뢰기관).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko'));
  sel.innerHTML = '<option value="">기관 전체</option>' + orgs.map(o => `<option ${o === cur ? 'selected' : ''}>${esc(o)}</option>`).join('');
}
function unmatchedInbox() {
  const ib = state.inbox;
  return { replies: ib.replies.filter(x => !x.usedBy || !x.usedBy.size), reports: ib.reports.filter(x => !x.usedBy || !x.usedBy.size), attach: ib.attach.filter(f => !state.docs.some(d => !d.organized && d.C.attach.includes(f))) };
}
function renderBanner() {
  const b = $('#banner'), ib = state.inbox;
  const loose = ib.requests.length + ib.groups.reduce((a, g) => a + g.C.requests.length, 0);
  const um = unmatchedInbox(), bits = [];
  if (loose && state.filter.state !== 'done') bits.push(`<span>공문별 폴더로 정리되지 않은 공문 <b>${loose}</b>건</span><button class="btn small primary" data-act="organize">공문별 폴더로 정리</button>`);
  if (um.replies.length || um.reports.length || um.attach.length) bits.push(`<span class="muted">짝을 찾지 못한 파일: 시행공문 ${um.replies.length} · 성적서 ${um.reports.length} · 첨부 ${um.attach.length}</span><button class="btn small" data-act="inbox">목록 보기</button>`);
  if (!window.pdfjsLib) bits.push('<span class="res-err">PDF 읽기 기능을 불러오지 못해 성적서를 대조할 수 없습니다.</span>');
  b.hidden = !bits.length; b.innerHTML = bits.join('<span class="sep"></span>');
}
function renderStats(list) {
  const docs = state.docs, live = docs.filter(d => !(d.result && d.result.duplicate));
  const samples = live.reduce((a, d) => a + (d.result ? d.result.rows.filter(r => r.시료번호).length : 0), 0);
  const warn = docs.filter(docWarn).length, err = docs.filter(d => d.error).length, dup = docs.length - live.length;
  let over = 0, imm = 0;
  for (const d of live) { if (isChecked(d)) continue; const m = docDueMin(d); if (m && m.rem) { if (m.rem.overdue) over++; else if (m.rem.days <= state.settings.imminent) imm++; } }
  const ready = live.filter(d => readyToFinish(d)).length;
  const groups = checkedGroups();
  $('#btnDone').textContent = `완료 체크한 공문 처리 완료 (${groups.length})`;
  $('#btnDone').disabled = !groups.length || state.filter.state === 'done';
  const bits = [`공문 <b>${live.length}</b>건`, `시료 <b>${samples}</b>개`];
  if (over) bits.push(`<span class="res-err">기한 초과 <b>${over}</b></span>`);
  if (imm) bits.push(`<span class="res-err">임박 <b>${imm}</b></span>`);
  bits.push(`성적서 도착 <b>${ready}</b>`, `확인필요 <b>${warn}</b>`, `완료체크 <b>${groups.length}</b>`);
  if (dup) bits.push(`중복 ${dup}`); if (err) bits.push(`읽기실패 ${err}`);
  bits.push(state.stdFile ? `<span title="기준표에서 채운 항목 수">기준표 ${state.stdTable.length}행 · ${state.stdFilled}항목</span>` : '기준표 없음');
  if (list.length !== (state.filter.state === 'done' ? state.doneDocs : docs).length) bits.push(`표시 ${list.length}건`);
  $('#stats').innerHTML = bits.join(' · ');
}

/* ───── 상세 패널 ───── */
function highlightDates(p) {
  return esc(p).replace(/((?:\d{4}|&#39;\d{2}|'\d{2})\s*[.\-\/]\s*\d{1,2}\s*[.\-\/]\s*\d{1,2}\.?(?:\s*\([월화수목금토일]\))?)/g, '<mark>$1</mark>');
}
const sec = (title, body, extra) => `<section class="dsec"><h4>${title}${extra ? `<span class="h4-act">${extra}</span>` : ''}</h4>${body}</section>`;
function dueSection(d) {
  const rc = caseRecv(d), n = peekNotes(d.key), live = d.loc === 'root';
  let h = `<div class="recv-row"><span class="lbl">시료접수일</span>`;
  h += live ? `<button class="btn small date-btn" data-act="recv">${rc ? esc(fmtFull(rc.date)) : '날짜 선택'} ▾</button>` : `<b>${rc ? esc(fmtFull(rc.date)) : '-'}</b>`;
  if (rc && rc.est) h += `<span class="muted small">공문 접수일 기준(추정)</span>${live ? ' <button class="btn small link" data-act="recv-doc">이 날짜로 확정</button>' : ''}`;
  h += `</div>`;
  if (live) h += `<label class="chk small"><input type="checkbox" data-act="before13" ${n.before13 ? 'checked' : ''}> 13시 이전 접수 (접수일을 처리기간에 포함)</label>`;
  const rows = d.result.rows.filter(r => r.시료번호);
  const trs = rows.map(r => {
    const sd = rowDue(d, r);
    if (!sd) return `<tr><td>${esc(r.시료번호)}</td><td colspan="3" class="muted">-</td></tr>`;
    const cls = dueClass(sd, d.loc !== 'root');
    return `<tr><td>${esc(r.시료번호)}</td><td>${sd.item ? `${esc(sd.item)} ${sd.days}일${sd.flagged.length ? ' <sup title="준용 항목 — 확인 필요">*</sup>' : ''}` : '<span class="muted">미설정</span>'}${sd.unknown.length ? `<div class="muted small">미설정: ${esc(sd.unknown.join(', '))}</div>` : ''}</td><td>${esc(fmtDay(sd.due))}</td><td class="${cls ? 'td-' + cls : ''}">${d.loc !== 'root' ? '완료' : esc(remText(sd.rem))}</td></tr>`;
  }).join('');
  h += `<table class="mini"><tr><th>시료</th><th>기간(결정 항목)</th><th>처리기한</th><th>남은 기간</th></tr>${trs}</table>`;
  h += `<p class="muted small">[별표 2] 표준처리기간 — 토·일·공휴일·지정 휴일 제외, 13시 이후 접수는 접수일 제외. 시료에 항목이 여러 개면 <b>${state.settings.dueBasis === 'min' ? '가장 짧은' : '가장 긴'} 항목</b> 기준(설정에서 변경). 남은 기간은 근무일, 초과 일수는 달력일 기준.</p>`;
  return sec('처리기한', h, `<button class="btn small link" data-act="settings">휴일·처리기간 설정</button>`);
}
function progressSection(d) {
  const m = d.match; let h = '';
  h += `<div class="sub">시행공문</div>`;
  h += m.replies.length ? '<ul class="flist2">' + m.replies.map((x, i) => `<li><span class="pill ${x.score === 1 ? 'ok' : 'part'}">${x.score === 1 ? '일치' : '기관 확인'}</span> ${esc(x.f.nm)} <span class="muted small">(${esc(x.info.관련기관)} ${esc(x.info.관련공문번호)}${x.info.부적합 ? ', 부적합' : ''}${x.inCase ? ', 공문 폴더 안' : ''})</span> <button class="btn small link" data-act="view:rep:${i}">보기</button></li>`).join('') + '</ul>'
    : `<p class="muted small">아직 없습니다. 시행공문(결과 알림 ODT)을 공문 폴더에 넣으면 본문의 '○○과-1234(날짜)호' 번호로 찾아 연결합니다.</p>`;
  h += `<div class="sub">시험성적서</div>`;
  h += m.reports.length ? '<ul class="flist2">' + m.reports.map((x, i) => `<li><span class="pill ${x.m.level === 'full' ? 'ok' : 'part'}">${x.m.matched.length}/${m.total}</span> ${esc(x.f.nm)}${x.m.missing.length && x.m.matched.length ? `<div class="muted small">이 파일에 없는 시료: ${esc(x.m.missing.join(', '))}</div>` : ''}${x.m.extra.length ? `<div class="res-err small">공문에 없는 시료: ${esc(x.m.extra.join(', '))}</div>` : ''}${x.m.orgGood === false ? `<div class="res-err small">의뢰기관 다름: ${esc(x.rep.의뢰기관)}</div>` : ''} <button class="btn small link" data-act="view:pdf:${i}">보기</button></li>`).join('') + '</ul>'
    : `<p class="muted small">아직 없습니다. 성적서 PDF를 공문 폴더에 넣으면 공문번호·시료명으로 찾아 연결합니다.</p>`;
  const rows = d.result.rows.filter(r => r._rep);
  if (rows.length) {
    h += `<div class="sub">결과</div><table class="mini"><tr><th>시료</th><th>접수번호</th><th>결과</th><th>판정</th></tr>` + rows.map(r => {
      const s = r._rep.s;
      return `<tr><td>${esc(r.시료번호)}</td><td>${esc(s.접수번호)}</td><td>${s.결과.map(x => `${esc(x.항목명 || x.항목)} <b>${esc(x.결과)}</b>${x.기준 ? `<span class="muted small">(${esc(x.기준)})</span>` : ''}`).join('<br>')}</td><td class="${/부적합/.test(s.판정) ? 'res-bad' : ''}">${esc(s.판정)}</td></tr>`;
    }).join('') + '</table>';
  }
  const ready = readyToFinish(d);
  return sec('시행공문 · 시험성적서', h, d.loc === 'root' ? (ready ? '<span class="pill ok">완료 가능</span>' : '') : '');
}
function attachSection(d) {
  let h = '';
  const atts = d.C.attach;
  h += atts.length ? '<ul class="flist2">' + atts.map((f, i) => `<li>${esc(f.nm)} <button class="btn small link" data-act="view:att:${i}">보기</button></li>`).join('') + '</ul>' : '<p class="muted small">첨부 파일 없음</p>';
  if (d.loc === 'root') {
    const um = unmatchedInbox();
    const pool = [...um.attach.map((f, i) => ({ t: 'att', f, i, label: '첨부' })), ...um.replies.map((x, i) => ({ t: 'rep', f: x.f, i, label: '시행공문' })), ...um.reports.map((x, i) => ({ t: 'pdf', f: x.f, i, label: '성적서' }))];
    if (pool.length) h += `<details class="pool"><summary>짝을 찾지 못한 파일 ${pool.length}개 — 이 공문에 넣기</summary><ul class="flist2">${pool.map(p => `<li><span class="muted small">${p.label}</span> ${esc(p.f.path ? p.f.path + '/' : '')}${esc(p.f.nm)} <button class="btn small link" data-act="adopt:${p.t}:${p.i}">이 공문 폴더로 옮기기</button></li>`).join('')}</ul></details>`;
  }
  return sec('첨부 파일 (추가 자료)', h);
}
function notesSection(d) {
  const n = peekNotes(d.key), live = true;
  const samples = d.result.rows.map(r => r.시료번호).filter(Boolean);
  const log = (n.log || []).slice().sort((a, b) => (a.date + a.at < b.date + b.at ? -1 : 1));
  let h = `<textarea class="memo" data-act="memo" placeholder="이 공문에 대한 메모 (자동 저장)">${esc(n.memo || '')}</textarea>`;
  h += `<div class="sub">시료 이력</div>`;
  h += log.length ? `<table class="mini log"><tr><th>일자</th><th>시료</th><th>내용</th><th></th></tr>${log.map(x => `<tr class="${x.auto ? 'auto' : ''}"><td>${esc(x.date)}</td><td>${esc(x.sample || '전체')}</td><td>${esc(x.text)}</td><td><button class="btn small link" data-act="log-del:${esc(x.id)}" title="삭제">✕</button></td></tr>`).join('')}</table>` : '<p class="muted small">기록 없음</p>';
  if (live) h += `<div class="log-add"><input type="date" id="logDate" value="${today()}"><select id="logSample"><option value="">전체 시료</option>${samples.map(s => `<option>${esc(s)}</option>`).join('')}</select><input type="text" id="logText" placeholder="이력 내용 (예: 재시험 요청, 추가 시료 접수)"><button class="btn small primary" data-act="log-add">추가</button></div>`;
  h += `<div class="hist-btns"><button class="btn small" data-act="hist:docx">이력 문서 Word</button><button class="btn small" data-act="hist:pdf">이력 문서 PDF</button><span class="muted small">의뢰공문·시행공문·성적서·첨부를 그림으로 넣고 이력을 덧붙입니다.</span></div>`;
  return sec('메모 · 이력', h);
}
function extractedHtml(d) {
  const res = d.result;
  let h = '';
  if (d.error) h += `<ul class="warnlist"><li>읽기 실패: ${esc(d.error)}</li></ul>`;
  if (!res) return h;
  const warns = [...new Set(res.rows.map(r => r.확인필요).filter(Boolean).join(' / ').split(' / ').filter(Boolean))];
  if (warns.length) h += `<ul class="warnlist">${warns.map(w => `<li>${esc(w)}${w === '시료표 미인식' ? ' — 첨부 파일(HWPX)이 없으면 아래 <b>[시료 직접 입력]</b>으로 넣을 수 있습니다.' : ''}</li>`).join('')}</ul>`;
  h += dueSection(d) + progressSection(d) + attachSection(d) + notesSection(d);
  const dd = res.doc, rs = res.rows.filter(r => r.시료번호);
  const srcNote = res.source ? `<span class="muted small">${res.source.type === 'manual' ? '직접 입력한 시료' : '첨부 ' + esc((res.source.files || []).join(', ')) + '에서 읽은 시료'}</span>` : '';
  h += sec(`추출된 시료 (${rs.length})`, srcNote + `<table class="mini"><tr><th>시료번호</th><th>검사항목</th><th>기준</th><th>지역</th><th>채취일</th></tr>`
    + rs.map(r => `<tr><td>${esc(r.시료번호)}</td><td>${esc(r.검사항목)}</td><td>${esc(r.기준)}</td><td>${esc(r.지역구분)}</td><td>${esc(r.시료채취일)}${r.채취일출처 === '본문' ? ' (본문)' : ''}</td></tr>`).join('') + '</table>',
    d.loc === 'root' ? `<button class="btn small link" data-act="manual">${peekNotes(d.key).manual ? '직접 입력 수정' : '시료 직접 입력'}</button>` : '');
  h += sec('공문 정보', `<dl>
    <dt>파일</dt><dd>${esc(d.nm)}${d.loc === 'done' ? ' <span class="badge">처리완료</span>' : ''}</dd>
    <dt>폴더</dt><dd>${esc(d.dirName || (d.loc === 'root' ? '공문 폴더 (정리 전)' : DONE_DIR))}</dd>
    <dt>의뢰기관</dt><dd>${esc(dd.의뢰기관)} / ${esc(dd.의뢰자)}</dd>
    <dt>발신명의</dt><dd>${esc(dd.발신명의)}</dd>
    <dt>시행</dt><dd>${esc(dd.시행)} (${esc(dd.시행일)})</dd>
    <dt>접수</dt><dd>${esc(dd.접수)} (${esc(dd.접수일)})</dd>
    <dt>시료채취자</dt><dd>${esc(dd.시료채취자)} ${dd.기안자직위 ? '(' + esc(dd.기안자직위) + ')' : ''}</dd>
    <dt>주소</dt><dd>${esc(dd.우편번호)} ${esc(dd.주소)}</dd>
    <dt>연락처</dt><dd>${esc(dd.전화번호)} ${esc(dd.이메일)}</dd>
  </dl>`);
  for (const t of res.tables || []) h += sec('시료 표 원문', `<table class="mini">` + (t.raw || [t.headers]).map((row, i) => `<tr>${row.map(c => i === 0 ? `<th>${esc(c)}</th>` : `<td>${esc(c)}</td>`).join('')}</tr>`).join('') + '</table>');
  if (dd.본문 && dd.본문.length) h += sec('본문', `<div class="paras">${dd.본문.map(p => `<p>${highlightDates(p)}</p>`).join('')}</div>`);
  return h;
}
function viewerList(d) {
  const L = [{ k: 'req', label: '의뢰공문', type: 'odt', f: d.f, req: true }];
  d.C.attach.forEach((f, i) => L.push({ k: 'att:' + i, label: '첨부: ' + f.nm.replace(/\.[^.]+$/, ''), type: f.kind, f }));
  if (d.match) {
    d.match.replies.forEach((x, i) => L.push({ k: 'rep:' + i, label: '시행공문' + (d.match.replies.length > 1 ? ' ' + (i + 1) : ''), type: 'odt', f: x.f }));
    d.match.reports.forEach((x, i) => L.push({ k: 'pdf:' + i, label: '성적서' + (d.match.reports.length > 1 ? ' ' + (i + 1) : ''), type: 'pdf', f: x.f }));
  }
  return L;
}
function renderDetail() {
  const box = $('#detail');
  const d = findDoc(state.selected);
  if (!d) { box.hidden = true; box.className = 'detail'; box.dataset.id = ''; return; }
  const same = box.dataset.id === d.id;
  if (!same) state.viewer = 'req';
  const keep = { a: (box.querySelector('.pane-ext') || {}).scrollTop || 0, b: (box.querySelector('.pane-org') || {}).scrollTop || 0 };
  const mode = state.detailMode;
  box.hidden = false; box.className = 'detail mode-' + mode;
  const r0 = docRows(d)[0] || {};
  const seg = [['ext', '추출 결과'], ['org', '원본 보기'], ['side', '나란히']].map(([k, l]) => `<button class="seg-btn${mode === k ? ' on' : ''}" data-act="mode-${k}">${l}</button>`).join('');
  let h = `<div class="detail-head"><h3 title="${esc(d.nm)}">${esc(r0.제목 || d.nm)}</h3><div class="seg">${seg}</div><button class="btn small" data-act="close">닫기</button></div>`;
  h += '<div class="detail-body">';
  if (mode !== 'org') h += `<div class="pane pane-ext">${extractedHtml(d)}</div>`;
  if (mode !== 'ext') {
    const L = viewerList(d); if (!L.find(x => x.k === state.viewer)) state.viewer = 'req';
    const cur = L.find(x => x.k === state.viewer);
    h += `<div class="pane pane-org"><div class="pv-tabs">${L.map(x => `<button class="pv-tab${x.k === state.viewer ? ' on' : ''}" data-act="view:${x.k}" title="${esc(x.f.nm)}">${esc(x.label)}</button>`).join('')}</div>
      <div class="pv-tools"><span class="muted">${esc(cur.f.nm)}</span><span class="spacer"></span>${cur.req ? `<label class="chk small" title="의뢰공문 우측 상단에 시료접수일 표시 (원본 파일은 바꾸지 않음)"><input type="checkbox" data-act="wm" ${state.settings.watermark ? 'checked' : ''}> 접수일 워터마크</label>` : ''}<button class="btn small" data-act="pv-big">새 창으로 크게 보기·인쇄</button><button class="btn small" data-act="pv-download" title="원본 파일을 내려받아 한글 등에서 엽니다">원본 파일 열기</button></div><div class="pv" id="pv"><div class="muted pv-msg">불러오는 중…</div></div></div>`;
  }
  h += '</div><div class="detail-foot">';
  if (d.loc === 'done') h += `<button class="btn" data-act="restore">공문 폴더로 되돌리기</button>`;
  else h += `<button class="btn ${isChecked(d) ? '' : 'primary'}" data-act="check-toggle">${isChecked(d) ? '완료 체크 해제' : '완료 체크'}</button>${!d.organized ? '<button class="btn" data-act="organize-one">이 공문 폴더 만들기</button>' : ''}`;
  h += `<span class="spacer"></span><span class="muted small">${esc(d.dirName ? '폴더: ' + d.dirName : '')}</span></div>`;
  box.innerHTML = h;
  box.dataset.id = d.id;
  if (same) { const a = box.querySelector('.pane-ext'), b = box.querySelector('.pane-org'); if (a) a.scrollTop = keep.a; if (b) b.scrollTop = keep.b; }
  if (mode !== 'ext') showPreview(d, same ? keep.b : 0);
}

/* ───── 원본 보기 (ODT · PDF · HWPX · 그림) ───── */
const WM_CSS = `.wm-wrap{position:relative;width:max-content;max-width:100%;margin:0 auto}
.wm-stamp{position:absolute;top:.5cm;right:.25cm;border:2.5px solid rgba(200,30,30,.6);color:rgba(190,25,25,.72);border-radius:8px;padding:5px 12px;font:600 13px/1.35 "Malgun Gothic","맑은 고딕",sans-serif;text-align:center;transform:rotate(-5deg);background:rgba(255,255,255,.4);z-index:3;pointer-events:none;white-space:nowrap}
.wm-stamp b{font-size:15px}`;
function wmHtml(d) {
  const n = peekNotes(d.key); if (!n.recv) return '';
  return `<div class="wm-stamp">시료접수일<br><b>${esc(fmtFull(n.recv))}</b>${n.before13 ? '<br><small>13시 이전 접수</small>' : ''}</div>`;
}
async function odtPreview(f) {
  const ck = 'pv:' + fkey(f);
  if (state.previewCache.has(ck)) return state.previewCache.get(ck);
  const r = await E.renderOdtHtml(await fileBytes(f), inflateRaw);
  if (!document.getElementById('odt-css')) { const st = document.createElement('style'); st.id = 'odt-css'; st.textContent = r.css + WM_CSS; document.head.appendChild(st); }
  if (state.previewCache.size > 40) state.previewCache.delete(state.previewCache.keys().next().value);
  state.previewCache.set(ck, r);
  return r;
}
async function pdfPreviewHtml(f, pages) {
  const ck = 'pdfpv:' + fkey(f) + '|' + (pages || []).join(',');
  if (state.previewCache.has(ck)) return state.previewCache.get(ck);
  const cs = await DG.pdfToCanvases(await fileBytes(f), pages, 1.6);
  const html = cs.map(c => `<div class="pdf-page"><img src="${c.toDataURL('image/png')}" alt=""></div>`).join('');
  state.previewCache.set(ck, html);
  return html;
}
async function viewerHtml(d, v) {
  if (v.type === 'odt') { const r = await odtPreview(v.f); return v.req && state.settings.watermark ? `<div class="wm-wrap">${wmHtml(d)}${r.html}</div>` : r.html; }
  if (v.type === 'pdf') return pdfPreviewHtml(v.f);
  if (v.type === 'hwpx') { const h = await parseHwpxEntry(v.f); return E2.hwpxHtml(h, v.f.nm); }
  if (v.type === 'img') { const b = await fileBytes(v.f); const url = URL.createObjectURL(new Blob([b], { type: DG.IMG_MIME[v.f.nm.split('.').pop().toLowerCase()] })); return `<div class="pdf-page"><img src="${url}" alt=""></div>`; }
  return `<div class="notice">이 형식(${esc(v.f.nm.split('.').pop())})은 화면에 표시할 수 없습니다. [원본 파일 열기]로 내려받아 여세요.</div>`;
}
async function showPreview(d, scrollTop) {
  const v = viewerList(d).find(x => x.k === state.viewer) || viewerList(d)[0];
  try {
    const html = await viewerHtml(d, v);
    const pv = $('#pv');
    if (!pv || state.selected !== d.id || state.viewer !== v.k) return;
    pv.innerHTML = html; fitPreview();
    if (scrollTop) { const b = $('#detail .pane-org'); if (b) b.scrollTop = scrollTop; }
  } catch (e) {
    console.error(e);
    const pv = $('#pv'); if (pv) pv.innerHTML = `<div class="notice">표시할 수 없습니다: ${esc(explain(e))}</div>`;
  }
}
function fitPreview() {
  const pv = $('#pv'); if (!pv) return;
  const page = pv.querySelector('.wm-wrap') || pv.querySelector('.odt-page'); if (!page) return;
  page.style.zoom = '';
  const avail = pv.clientWidth - 24, w = page.offsetWidth;
  if (w > avail && avail > 100) page.style.zoom = (avail / w).toFixed(3);
}
async function openPreviewWindow(d) {
  const v = viewerList(d).find(x => x.k === state.viewer) || viewerList(d)[0];
  try {
    const html = await viewerHtml(d, v);
    const css = (await odtPreview(d.f)).css;
    const w = window.open('', '_blank');
    if (!w) { toast('팝업이 차단되었습니다. 주소창 오른쪽의 팝업 차단 아이콘에서 허용해 주세요.', 'err'); return; }
    w.document.write(`<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>${esc(v.f.nm)}</title><style>body{margin:0;background:#80868f;padding:24px}${css}${WM_CSS}.odt-page{box-shadow:0 2px 12px rgba(0,0,0,.35);padding:1cm 1.5cm}.pdf-page{text-align:center;margin:0 auto 16px}.pdf-page img{max-width:100%;box-shadow:0 2px 12px rgba(0,0,0,.35);background:#fff}@media print{body{background:#fff;padding:0}.odt-page,.pdf-page img{box-shadow:none}.odt-page{padding:0}.pdf-page{page-break-after:always;margin:0}}</style></head><body>${html}</body></html>`);
    w.document.close();
  } catch (e) { toast('열지 못했습니다: ' + explain(e), 'err'); }
}
async function downloadFile(f) {
  try {
    const url = URL.createObjectURL(new Blob([await fileBytes(f)]));
    const a = document.createElement('a'); a.href = url; a.download = f.nm; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast('파일을 내려받았습니다. 브라우저의 다운로드 목록에서 열면 한글(또는 기본 프로그램)로 열립니다.');
  } catch (e) { toast('파일을 열지 못했습니다: ' + explain(e), 'err'); }
}

/* ───── 체크 ───── */
function setChecked(d, on) {
  if (!d || d.loc !== 'root') return;
  if (on) state.status.checked[d.key] = { at: nowIso(), file: d.nm };
  else delete state.status.checked[d.key];
  saveStatusSoon();
}
function findDoc(id) { return [...state.docs, ...state.doneDocs].find(x => x.id === id); }

/* ───── 파일·폴더 이동 ───── */
function explain(e) {
  const n = e && e.name;
  if (n === 'NoModificationAllowedError' || n === 'InvalidModificationError' || n === 'InvalidStateError') return '파일이 다른 프로그램(한글·엑셀·PDF 뷰어 등)에서 열려 있어 처리할 수 없습니다. 파일을 닫고 다시 시도하세요.';
  if (n === 'NotFoundError') return '파일이 이미 옮겨졌거나 없습니다. [새로고침] 후 다시 확인하세요.';
  if (n === 'NotAllowedError' || n === 'SecurityError') return '폴더 쓰기 권한이 없습니다. 폴더를 다시 연결해 주세요.';
  if (n === 'QuotaExceededError') return '저장 공간이 부족합니다.';
  return (e && e.message) || String(e);
}
async function exists(dir, name) { try { await dir.getFileHandle(name); return true; } catch (e) { return false; } }
async function dirExists(dir, name) { try { await dir.getDirectoryHandle(name); return true; } catch (e) { return false; } }
async function uniqueName(dir, name) {
  if (!(await exists(dir, name))) return name;
  const dot = name.lastIndexOf('.'), base = dot > 0 ? name.slice(0, dot) : name, ext = dot > 0 ? name.slice(dot) : '';
  for (let k = 2; k < 1000; k++) { const c = `${base} (${k})${ext}`; if (!(await exists(dir, c))) return c; }
  throw new Error('같은 이름의 파일이 너무 많습니다.');
}
async function uniqueDirName(parent, name) {
  if (!(await dirExists(parent, name)) && !(await exists(parent, name))) return name;
  for (let k = 2; k < 1000; k++) { const c = `${name} (${k})`; if (!(await dirExists(parent, c))) return c; }
  throw new Error('같은 이름의 폴더가 너무 많습니다.');
}
// 복사 → 크기 확인 → 원본 삭제 (실패하면 복사본을 지우고 원본 유지). keep=true면 복사만
async function moveFile(srcDir, name, dstDir, keep) {
  const fh = await srcDir.getFileHandle(name);
  const target = await uniqueName(dstDir, name.normalize('NFC'));
  if (!keep && typeof fh.move === 'function') {
    try { await fh.move(dstDir, target); if (await exists(dstDir, target)) return target; } catch (e) { /* 아래 방식으로 다시 시도 */ }
    if (await exists(dstDir, target) && !(await exists(srcDir, name))) return target;
  }
  const file = await fh.getFile();
  const nh = await dstDir.getFileHandle(target, { create: true });
  try {
    const w = await nh.createWritable(); await w.write(file); await w.close();
    if ((await nh.getFile()).size !== file.size) throw new Error('복사한 파일 크기가 원본과 다릅니다.');
  } catch (e) { await dstDir.removeEntry(target).catch(() => {}); throw e; }
  if (keep) return target;
  try { await srcDir.removeEntry(name); }
  catch (e) { await dstDir.removeEntry(target).catch(() => {}); throw e; }
  return target;
}
// 폴더 옮기기: 대상에 새 폴더를 만들고 안의 파일을 하나씩 옮긴 뒤 빈 폴더를 지움. 실패하면 옮긴 파일을 되돌림
async function moveDir(parent, name, dstParent) {
  const src = await parent.getDirectoryHandle(name);
  const tname = await uniqueDirName(dstParent, name.normalize('NFC'));
  const dst = await dstParent.getDirectoryHandle(tname, { create: true });
  const moved = [];
  try {
    for await (const [n, h] of src.entries()) {
      if (h.kind === 'directory') { await moveDir(src, n, dst); moved.push({ dir: true, n }); }
      else { const to = await moveFile(src, n, dst); moved.push({ n, to }); }
    }
  } catch (e) {
    for (const m of moved.reverse()) { try { if (m.dir) await moveDir(dst, m.n, src); else await moveFile(dst, m.to, src); } catch (e2) { /* 되돌리기 실패는 아래 메시지로 안내 */ } }
    await dstParent.removeEntry(tname).catch(() => {});
    throw e;
  }
  await parent.removeEntry(name).catch(() => {}); // 빈 폴더 삭제 (남은 파일이 있으면 그대로 둠)
  return tname;
}

/* ───── 공문별 폴더 정리 ───── */
// 의뢰공문 1건 + 첨부(붙임 이름 일치, 또는 3분 안에 함께 저장된 파일)를 "의뢰기관_제목_시행" 폴더로
async function organizeOne(req, srcDir, pool, siblings) {
  const doc = req.p.result ? req.p.result.doc : { 파일명: req.f.nm };
  const key = keyOfReq(req);
  const names = E2.attachmentNames(doc.본문 || []);
  const base = E2.caseFolderName(doc);
  let name = base, dir = null;
  for (let k = 2; k < 50; k++) {
    if (await dirExists(state.root, name)) {
      const d0 = await state.root.getDirectoryHandle(name), L = await listDir(d0, name);
      let clash = false;
      for (const f of L.files.filter(f => f.kind === 'odt')) { const p = await parseOdtEntry(f); if (!p.reply && p.result && (p.result.doc.접수 || 'file:' + f.nm) !== key) clash = true; }
      if (!clash) { dir = d0; break; }
      name = `${base} (${k})`;
    } else { dir = await state.root.getDirectoryHandle(name, { create: true }); break; }
  }
  if (!dir) throw new Error('폴더 이름을 정하지 못했습니다.');
  const take = [];
  for (const f of pool) {
    if (f.taken || f.dir !== srcDir) continue;
    const score = names.length ? E2.attachScore(f.nm, names) : 0;
    // 붙임 이름이 안 맞으면: 3분 안에 함께 저장된 의뢰공문이 이 공문 하나뿐일 때만 (여러 공문을 한꺼번에 복사한 경우 제외)
    const close = s => Math.abs((f.mtime || 0) - (s.f.mtime || 0)) <= 180000;
    const near = names.length && /^(hwpx|img|tif|doc|pdf)$/.test(f.kind) && close(req) && !siblings.some(s => s !== req && s.f !== req.f && close(s));
    if (score >= 0.6 || near) take.push(f);
  }
  const moved = [];
  moved.push({ from: req.f.nm, to: await moveFile(srcDir, req.f.name, dir) });
  for (const f of take) { try { moved.push({ from: f.nm, to: await moveFile(srcDir, f.name, dir) }); f.taken = true; } catch (e) { /* 첨부는 실패해도 계속 */ } }
  state.status.history.unshift({ at: nowIso(), action: '폴더정리', key, folder: name, files: moved });
  addLog(key, `공문 폴더 정리: ${name}${take.length ? ` (첨부 ${take.length}개 포함)` : ''}`, '', true);
  return { dir, name, moved };
}
async function organizeAll(silent) {
  const ib = state.inbox, jobs = [];
  for (const req of ib.requests) jobs.push({ req, srcDir: state.root, pool: ib.attach, siblings: ib.requests });
  for (const g of ib.groups) for (const req of g.C.requests) jobs.push({ req, srcDir: g.dir, pool: g.C.attach.map(f => f), siblings: g.C.requests, group: g });
  if (!jobs.length) return;
  busy(true, `공문별 폴더 만드는 중… 0 / ${jobs.length}`);
  const ok = [], fail = [];
  for (let i = 0; i < jobs.length; i++) {
    const j = jobs[i];
    try { const r = await organizeOne(j.req, j.srcDir, j.pool, j.siblings); ok.push(r.name); } catch (e) { fail.push(`${j.req.f.nm}: ${explain(e)}`); }
    busy(true, `공문별 폴더 만드는 중… ${i + 1} / ${jobs.length}`);
  }
  for (const g of ib.groups) await state.root.removeEntry(g.name).catch(() => {}); // 비었으면 삭제
  await writeStatus(); await writeNotes();
  busy(false);
  await scan({ quiet: true, noOrganize: true });
  if (fail.length) await info('공문별 폴더 정리', `<p class="res-ok">정리한 공문 ${ok.length}건</p><h4 class="res-err">정리하지 못한 공문 ${fail.length}건</h4><ul class="flist">${fail.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`);
  else if (!silent || ok.length) toast(`공문 ${ok.length}건을 공문별 폴더로 정리했습니다.`);
}
async function askOrganize() {
  const ib = state.inbox, n = ib.requests.length + ib.groups.reduce((a, g) => a + g.C.requests.length, 0);
  const ex = [...ib.requests, ...ib.groups.flatMap(g => g.C.requests)].slice(0, 6).map(r => `<li>${esc(E2.caseFolderName(r.p.result ? r.p.result.doc : { 파일명: r.f.nm }))}</li>`).join('');
  const r = await modal('공문별 폴더 정리', `<p>공문 폴더에 정리되지 않은 의뢰공문 <b>${n}건</b>이 있습니다. 공문마다 <b>의뢰기관_제목_시행번호</b> 폴더를 만들고 공문과 첨부 파일(붙임)을 옮깁니다.</p><ul class="flist">${ex}${n > 6 ? '<li>…</li>' : ''}</ul>
    <p class="muted">시행공문·성적서는 처리 완료할 때 해당 공문 폴더로 옮겨집니다. 원본 내용은 바뀌지 않습니다.</p>
    <label class="chk"><input type="checkbox" id="orgAuto" checked> 앞으로 새 공문은 묻지 않고 자동으로 정리</label>`, '정리하기', { cancelLabel: '나중에', collect: () => ({ auto: $('#orgAuto').checked }) });
  state.settings.organize.asked = true;
  if (r) state.settings.organize.auto = !!r.auto;
  await writeSettings();
  if (r) await organizeAll(false);
}

/* ───── 처리 완료 ───── */
async function processChecked() {
  const groups = checkedGroups();
  if (!groups.length) return toast('완료 체크한 공문이 없습니다.');
  const batchKeys = new Set(groups.map(g => g.key)), doneKeys = new Set();
  const rowsHtml = groups.map(g => {
    const d = g.docs[0], m = d.match || { replies: [], reports: [] };
    return `<tr><td>${esc((d.result && d.result.doc.제목) || d.nm)}</td><td>${m.replyOk ? '<span class="pill ok">일치</span>' : m.replies.length ? '<span class="pill part">확인</span>' : '<span class="pill none">없음</span>'}</td><td>${m.reportState === 'full' ? `<span class="pill ok">${m.got}/${m.total}</span>` : m.reportState === 'partial' ? `<span class="pill part">${m.got}/${m.total}</span>` : '<span class="pill none">없음</span>'}</td></tr>`;
  }).join('');
  const r = await modal('처리 완료', `<p>완료 체크한 공문 <b>${groups.length}건</b>을 처리합니다.</p>
    <ol><li>짝지은 <b>시행공문·시험성적서</b>를 각 공문 폴더(의뢰기관_제목_시행번호)로 옮깁니다. 다른 공문과 함께 쓰는 성적서는 복사합니다.</li>
    <li>${state.settings.nestDone ? `공문 폴더를 <b>${DONE_DIR}</b> 폴더 안으로 옮깁니다.` : '공문 폴더는 공문 폴더에 그대로 둡니다.'}</li></ol>
    <table class="mini"><tr><th>공문</th><th>시행공문</th><th>성적서</th></tr>${rowsHtml}</table>
    <label class="chk"><input type="checkbox" id="optNest" ${state.settings.nestDone ? 'checked' : ''}> 공문 폴더를 ${DONE_DIR}로 옮기기</label>
    <label class="chk"><input type="checkbox" id="optPartial"> 일부만 일치하는 성적서·기관 확인이 필요한 시행공문도 함께 옮기기</label>`, '처리 완료', { width: 'min(760px, calc(100vw - 32px))', collect: () => ({ nest: $('#optNest').checked, partial: $('#optPartial').checked }) });
  if (!r) return;
  if (state.settings.nestDone !== r.nest) { state.settings.nestDone = r.nest; saveSettingsSoon(); }
  busy(true, '처리하는 중…');
  const okList = [], failList = [];
  try {
    const doneDir = r.nest ? await getDoneDir(true) : null;
    for (const g of groups) {
      const d = g.docs[0];
      try {
        // 1) 공문 폴더 확보 (정리 전이면 먼저 정리)
        let caseDir = d.dir, caseName = d.dirName;
        if (!d.organized) {
          const pool = d.C.attach.map(f => f);
          const res = await organizeOne({ f: d.f, p: { result: d.base } }, d.dir, pool, []);
          for (const o of g.docs.slice(1)) if (!o.organized) await moveFile(o.dir, o.name, res.dir).catch(() => {});
          caseDir = res.dir; caseName = res.name;
        }
        // 2) 시행공문·성적서 옮기기
        const m = d.match || { replies: [], reports: [] }, files = [];
        for (const x of m.replies) {
          if (x.inCase || (x.score < 1 && !r.partial)) continue;
          files.push({ from: x.f.nm, to: await moveFile(x.f.dir, x.f.name, caseDir), kind: '시행공문' });
        }
        for (const x of m.reports) {
          if (x.inCase || (x.m.level !== 'full' && !r.partial && !(x.m.matched.length && !x.m.extra.length && x.m.orgGood !== false))) continue;
          // 다른 공문도 쓰는 성적서: 아직 처리하지 않는 공문이 있거나, 이번 묶음에서 뒤에 처리할 공문이 있으면 복사
          const users = [...((state.inbox.reports.find(y => y.f === x.f) || {}).usedBy || [])];
          const left = users.filter(k => k !== d.key && (!batchKeys.has(k) || !doneKeys.has(k)));
          const keep = left.length > 0;
          files.push({ from: x.f.nm, to: await moveFile(x.f.dir, x.f.name, caseDir, keep), kind: keep ? '성적서(복사)' : '성적서' });
        }
        // 3) 성적처리완료로
        let finalName = caseName;
        if (r.nest && doneDir) finalName = DONE_DIR + '/' + await moveDir(state.root, caseName, doneDir);
        doneKeys.add(g.key);
        delete state.status.checked[g.key];
        state.status.history.unshift({ at: nowIso(), action: '처리완료', key: g.key, folder: finalName, files });
        addLog(g.key, `처리 완료 — ${files.length ? files.map(f => f.kind).join(', ') + ' 정리, ' : ''}${finalName}`, '', true);
        okList.push({ title: (d.result && d.result.doc.제목) || d.nm, folder: finalName, files });
      } catch (e) { console.error(e); failList.push({ file: d.nm, msg: explain(e) }); }
    }
    await writeStatus(); await writeNotes();
  } catch (e) { failList.push({ file: '(전체)', msg: explain(e) }); }
  busy(false);
  state.selected = null;
  await scan({ quiet: true, noOrganize: true });
  let html = `<p class="res-ok">처리 완료 <b>${okList.length}</b>건</p><ul class="flist">${okList.map(o => `<li><b>${esc(o.title)}</b><br><span class="muted">${esc(o.folder)}${o.files.length ? ' · ' + esc(o.files.map(f => f.kind + ' ' + f.to).join(', ')) : ''}</span></li>`).join('')}</ul>`;
  if (failList.length) html += `<h4 class="res-err">처리하지 못한 공문 ${failList.length}건</h4><ul class="flist">${failList.map(f => `<li><b>${esc(f.file)}</b><br>${esc(f.msg)}</li>`).join('')}</ul><p>실패한 공문은 완료 체크가 그대로 남아 있습니다. 원인을 해결한 뒤 다시 [처리 완료]를 누르세요.</p>`;
  await info('처리 완료 결과', html);
}
async function restore(d) {
  if (!d || d.loc !== 'done') return;
  const isFolder = !!d.dirName;
  const ok = await modal('되돌리기', `<p><b>${esc(isFolder ? d.dirName : d.nm)}</b><br>이 ${isFolder ? '공문 폴더' : '공문'}를 <b>${esc(state.root.name)}</b> 폴더로 되돌립니다. 완료 체크는 해제됩니다.${isFolder ? '<br><span class="muted">폴더 안의 시행공문·성적서도 함께 옮겨집니다.</span>' : ''}</p>`, '되돌리기');
  if (!ok) return;
  busy(true, '되돌리는 중…');
  try {
    const doneDir = await getDoneDir(false);
    const to = isFolder ? await moveDir(doneDir, d.dirName, state.root) : await moveFile(doneDir, d.name, state.root);
    delete state.status.checked[d.key];
    state.status.history.unshift({ at: nowIso(), action: '되돌리기', key: d.key, files: [{ from: d.dirName || d.nm, to }] });
    addLog(d.key, `되돌리기 — ${to}`, '', true);
    await writeStatus(); await writeNotes();
    toast(`되돌렸습니다: ${to}`);
  } catch (e) { toast('되돌리지 못했습니다: ' + explain(e), 'err'); }
  busy(false); state.selected = null;
  await scan({ quiet: true, noOrganize: true });
}
// 짝을 찾지 못한 파일을 이 공문 폴더로
async function adopt(d, t, i) {
  const um = unmatchedInbox();
  const f = t === 'att' ? um.attach[i] : t === 'rep' ? (um.replies[i] || {}).f : (um.reports[i] || {}).f;
  if (!f) return;
  try {
    let dir = d.dir;
    if (!d.organized) { const res = await organizeOne({ f: d.f, p: { result: d.base } }, d.dir, d.C.attach.map(x => x), []); dir = res.dir; }
    const to = await moveFile(f.dir, f.name, dir);
    state.status.history.unshift({ at: nowIso(), action: '파일연결', key: d.key, files: [{ from: f.nm, to }] });
    addLog(d.key, `파일 연결: ${to}`, '', true);
    await writeStatus();
    toast(`옮겼습니다: ${to}`);
  } catch (e) { toast('옮기지 못했습니다: ' + explain(e), 'err'); }
  state.selected = null; await scan({ quiet: true, noOrganize: true });
  const nd = state.docs.find(x => x.key === d.key); if (nd) { state.selected = nd.id; render(); }
}
async function organizeSelected(d) {
  try {
    const res = await organizeOne({ f: d.f, p: { result: d.base } }, d.dir, d.C.attach.map(x => x), []);
    await writeStatus(); toast(`폴더를 만들었습니다: ${res.name}`);
  } catch (e) { toast('폴더를 만들지 못했습니다: ' + explain(e), 'err'); }
  await scan({ quiet: true, noOrganize: true });
  const nd = state.docs.find(x => x.key === d.key); if (nd) { state.selected = nd.id; render(); }
}
function showInbox() {
  const um = unmatchedInbox();
  const li = (f, extra) => `<li>${esc(f.path ? f.path + '/' : '')}<b>${esc(f.nm)}</b>${extra ? ` <span class="muted">— ${esc(extra)}</span>` : ''}</li>`;
  info('짝을 찾지 못한 파일', `
    <p class="muted">공문 폴더에 있지만 어느 의뢰공문과도 짝지어지지 않은 파일입니다. 해당 의뢰공문이 아직 없거나, 공문번호·시료명이 다를 수 있습니다. 의뢰공문 상세 화면의 [첨부 파일] 칸에서 직접 넣을 수 있습니다.</p>
    <h4>시행공문 ${um.replies.length}</h4><ul class="flist">${um.replies.map(x => li(x.f, `관련 ${x.info.관련기관} ${x.info.관련공문번호}`)).join('') || '<li class="muted">없음</li>'}</ul>
    <h4>시험성적서 ${um.reports.length}</h4><ul class="flist">${um.reports.map(x => li(x.f, `공문번호 ${x.rep.공문번호} · ${x.rep.의뢰기관} · 시료 ${x.rep.samples.map(s => s.시료명).slice(0, 4).join(', ')}${x.rep.samples.length > 4 ? ' 외' : ''}`)).join('') || '<li class="muted">없음</li>'}</ul>
    <h4>첨부·기타 ${um.attach.length}</h4><ul class="flist">${um.attach.map(f => li(f)).join('') || '<li class="muted">없음</li>'}</ul>`, { width: 'min(820px, calc(100vw - 32px))' });
}

/* ───── 시료 직접 입력 (첨부 시료 목록을 읽지 못할 때) ───── */
async function manualInput(d) {
  const n = peekNotes(d.key);
  const cur = n.manual && n.manual.length ? n.manual : d.result.rows.filter(r => r.시료번호).map(r => ({ no: r.시료번호, items: r.검사항목, std: r.기준, date: /확인/.test(r.시료채취일) ? '' : r.시료채취일, note: r.비고 || '' }));
  const tsv = ['시료번호\t검사항목\t기준\t채취일\t비고', ...cur.map(x => [x.no, x.items, x.std, x.date, x.note].map(v => String(v || '').replace(/[\t\n]/g, ' ')).join('\t'))].join('\n');
  const preview = () => {
    const list = E2.parsePastedSamples($('#manText').value);
    $('#manPrev').innerHTML = list.length ? `<table class="mini"><tr><th>시료번호</th><th>검사항목</th><th>기준</th><th>채취일</th><th>비고</th></tr>${list.map(x => `<tr><td>${esc(x.no)}</td><td>${esc(x.items)}</td><td>${esc(x.std)}</td><td>${esc(x.date)}</td><td>${esc(x.note)}</td></tr>`).join('')}</table><p class="muted small">시료 ${list.length}개</p>` : '<p class="muted">시료가 없습니다.</p>';
  };
  const r = await modal('시료 직접 입력', `<p>시료 목록을 <b>엑셀·한글 표에서 복사해 붙여넣거나</b> 직접 입력합니다. 한 줄에 시료 1개, 칸은 탭(엑셀 복사 시 자동)으로 구분합니다. 첫 줄 머리글(시료번호/하천명·검사항목·기준·채취일·비고)이 있으면 열을 자동으로 맞춥니다.<br><span class="muted small">검사항목 칸이 비어 있으면 위 줄의 항목을 씁니다 (병합 칸 복사 대응).</span></p>
    <textarea id="manText" class="mantext" spellcheck="false">${esc(tsv)}</textarea><div id="manPrev"></div>
    ${n.manual ? '<label class="chk"><input type="checkbox" id="manClear"> 직접 입력을 지우고 자동 추출로 되돌리기</label>' : ''}`, '저장', {
    width: 'min(860px, calc(100vw - 32px))',
    onOpen: () => { $('#manText').addEventListener('input', preview); preview(); $('#manText').focus(); },
    collect: () => ({ list: E2.parsePastedSamples($('#manText').value), clear: !!($('#manClear') && $('#manClear').checked) }),
  });
  if (!r) return;
  const nn = notesOf(d.key);
  if (r.clear) { delete nn.manual; addLog(d.key, '직접 입력 시료 삭제 (자동 추출로 되돌림)', '', true); }
  else { nn.manual = r.list; addLog(d.key, `시료 직접 입력 ${r.list.length}개`, '', true); }
  await writeNotes();
  await scan({ quiet: true, noOrganize: true });
}

/* ───── 달력 (날짜 선택 · 휴일 지정) ───── */
function calendarHtml(y, m, opt = {}) {
  const first = new Date(y, m, 1, 12), start = E2.addDays(first, -first.getDay()), H = state.settings.holidays, t = today();
  let h = `<div class="cal"><div class="cal-head"><button class="btn small" data-cal="prev">◀</button><b>${y}년 ${m + 1}월</b><button class="btn small" data-cal="next">▶</button></div><div class="cal-grid">${WEEK.map((w, i) => `<div class="cal-w ${i === 0 ? 'sun' : i === 6 ? 'sat' : ''}">${w}</div>`).join('')}`;
  for (let i = 0; i < 42; i++) {
    const dt = E2.addDays(start, i), ds = E2.ymd(dt), wd = dt.getDay();
    const cls = ['cal-d', dt.getMonth() !== m && 'other', wd === 0 && 'sun', wd === 6 && 'sat',
      state.hol.has(ds) && (H.custom[ds] != null ? 'cust' : 'hol'), state.work.has(ds) && 'work', ds === t && 'today', opt.sel === ds && 'sel'].filter(Boolean).join(' ');
    const nm = state.work.has(ds) ? '근무일로 지정' : state.holName.get(ds) || '';
    h += `<button class="${cls}" data-day="${ds}" title="${esc(nm)}">${dt.getDate()}${nm && opt.names ? `<small>${esc(nm.replace(/대체공휴일/, '대체'))}</small>` : ''}</button>`;
  }
  return h + '</div></div>';
}
let dpState = null;
function openDatePicker(anchor, value, onPick) {
  const pop = $('#datePop'), base = value ? E2.toDate(value) : new Date();
  dpState = { y: base.getFullYear(), m: base.getMonth(), value, onPick };
  const draw = () => {
    pop.innerHTML = calendarHtml(dpState.y, dpState.m, { sel: dpState.value }) + `<div class="cal-foot"><button class="btn small" data-cal="today">오늘</button><span class="spacer"></span><span class="legend"><i class="lg hol"></i>공휴일 <i class="lg cust"></i>지정 휴일</span><button class="btn small" data-cal="close">닫기</button></div>`;
  };
  draw();
  const r = anchor.getBoundingClientRect();
  pop.hidden = false;
  pop.style.left = Math.max(8, Math.min(window.innerWidth - pop.offsetWidth - 8, r.left)) + 'px';
  pop.style.top = (r.bottom + pop.offsetHeight + 8 > window.innerHeight ? Math.max(8, r.top - pop.offsetHeight - 4) : r.bottom + 4) + 'px';
  pop.onclick = e => {
    e.stopPropagation();
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.cal === 'prev') { if (--dpState.m < 0) { dpState.m = 11; dpState.y--; } draw(); }
    else if (b.dataset.cal === 'next') { if (++dpState.m > 11) { dpState.m = 0; dpState.y++; } draw(); }
    else if (b.dataset.cal === 'today') { pop.hidden = true; onPick(today()); }
    else if (b.dataset.cal === 'close') pop.hidden = true;
    else if (b.dataset.day) { pop.hidden = true; onPick(b.dataset.day); }
  };
}
function pickRecv(d, anchor) {
  const rc = caseRecv(d);
  openDatePicker(anchor, rc ? rc.date : today(), ds => setRecv(d, ds));
}
function setRecv(d, ds) {
  const n = notesOf(d.key), old = n.recv;
  n.recv = ds;
  addLog(d.key, `시료접수일 ${old ? `변경 ${old} → ` : '입력 '}${ds}`, '', true);
  saveNotesSoon(); render();
}

/* ───── 설정 (휴일 · 처리기간 · 기타) ───── */
async function showSettings(tab) {
  let cy = new Date().getFullYear(), cm = new Date().getMonth(), cur = tab || 'hol';
  const S = state.settings, H = S.holidays;
  const itemsInUse = [...new Set(state.docs.flatMap(d => d.result ? d.result.rows.flatMap(r => (r._items || []).map(i => i.name)) : []))];
  const draw = () => {
    const body = $('#modalBody');
    let h = `<div class="tabs">${[['hol', '휴일 달력'], ['std', '처리기간'], ['etc', '기타']].map(([k, l]) => `<button class="tab${cur === k ? ' on' : ''}" data-tab="${k}">${l}</button>`).join('')}</div>`;
    if (cur === 'hol') {
      const monthHol = [...state.holName.entries()].filter(([d0]) => d0.startsWith(`${cy}-${String(cm + 1).padStart(2, '0')}`) && state.hol.has(d0)).sort();
      const fetched = Object.entries(H.fetched || {}).map(([y, f]) => `${y}년: ${f.at ? `인터넷 ${f.n}일 (${f.at.slice(0, 10)})` : `내장 목록 사용 — ${esc(f.error || '')}`}`).join('<br>');
      h += `<div class="hol-wrap">${calendarHtml(cy, cm, { names: true })}<div class="hol-side">
        <p class="small">날짜를 누르면 바뀝니다.<br>· 평일 → <span class="lg-t cust">지정 휴일</span> (기관 휴무일 등)<br>· 공휴일·토·일 → <span class="lg-t work">근무일로 지정</span><br>· 다시 누르면 원래대로</p>
        <h4>${cm + 1}월 휴일</h4><ul class="flist2 small">${monthHol.map(([d0, n0]) => `<li>${esc(fmtDay(d0))} ${esc(n0)}${H.custom[d0] != null ? ' <span class="muted">(지정)</span>' : ''}</li>`).join('') || '<li class="muted">없음</li>'}</ul>
        ${[...state.work].filter(d0 => d0.startsWith(`${cy}-${String(cm + 1).padStart(2, '0')}`)).map(d0 => `<div class="small">근무일 지정: ${esc(fmtDay(d0))}</div>`).join('')}
        <h4>공휴일 자료</h4><p class="small">${fetched || '아직 가져오지 않음 (내장 2026·2027년 목록 사용)'}</p>
        <button class="btn small" data-act="hol-fetch">인터넷에서 공휴일 다시 가져오기</button><div id="holMsg" class="small muted"></div></div></div>`;
    } else if (cur === 'std') {
      const names = [...new Set([...E2.STD_DAYS.map(x => x[0]), ...itemsInUse, ...Object.keys(S.stdDays)])];
      h += `<div class="basis"><b>시료 처리기한 기준</b> — 한 시료에 검사항목이 여러 개일 때
        <label class="chk"><input type="radio" name="basis" value="max" ${S.dueBasis !== 'min' ? 'checked' : ''}> 가장 <b>긴</b> 항목 기준 (예: BOD·SS → BOD 9일)</label>
        <label class="chk"><input type="radio" name="basis" value="min" ${S.dueBasis === 'min' ? 'checked' : ''}> 가장 <b>짧은</b> 항목 기준 (예: BOD·SS → SS 5일)</label></div>
        <p class="small muted">[별표 2] 표준처리기간(시험검사기간 + 행정처리기간). 별표에 없는 항목은 비고 5에 따라 유사 항목을 준용하며, 기관 기준에 맞게 '사용자 설정'에 일수를 넣으면 그 값을 씁니다.</p>
        <table class="mini"><tr><th>항목</th><th>기본(일)</th><th>근거</th><th>사용자 설정(일)</th></tr>${names.map(k => { const def = E2.STD_DAYS.find(x => x[0] === k); return `<tr${itemsInUse.includes(k) ? ' class="inuse"' : ''}><td>${esc(k)}</td><td>${def && def[1] != null ? def[1] : '<span class="res-err">없음</span>'}</td><td class="small">${esc(def ? def[2] : '별표2에 없음 — 설정 필요')}</td><td><input type="number" min="1" max="99" class="num" data-std="${esc(k)}" value="${S.stdDays[k] != null ? esc(S.stdDays[k]) : ''}" placeholder="${def && def[1] != null ? def[1] : ''}"></td></tr>`; }).join('')}</table>
        <p class="small muted">굵은 행: 현재 공문에 있는 항목</p>`;
    } else {
      h += `<div class="opts">
        <label class="chk"><input type="checkbox" data-opt="organize.auto" ${S.organize.auto ? 'checked' : ''}> 새 의뢰공문을 공문별 폴더(의뢰기관_제목_시행번호)로 자동 정리</label>
        <label class="chk"><input type="checkbox" data-opt="nestDone" ${S.nestDone ? 'checked' : ''}> 처리 완료 시 공문 폴더를 ${DONE_DIR} 폴더로 옮기기</label>
        <label class="chk"><input type="checkbox" data-opt="watermark" ${S.watermark ? 'checked' : ''}> 의뢰공문 우측 상단에 시료접수일 워터마크 표시 (화면·인쇄·이력 문서, 원본 파일은 그대로)</label>
        <div class="row">처리기한 <b>빨간색</b>: 남은 근무일 <input type="number" min="0" max="10" class="num" data-opt="imminent" value="${S.imminent}"> 일 이하 (기한 초과는 빨간 바탕)</div>
        <div class="row">처리기한 <b>주황색</b>: 남은 근무일 <input type="number" min="0" max="20" class="num" data-opt="soon" value="${S.soon}"> 일 이하</div>
        <p class="small muted">설정은 공문 폴더의 ${SETTINGS_FILE}에 저장되어 같은 폴더를 쓰는 다른 PC에도 적용됩니다.</p></div>`;
    }
    body.innerHTML = h;
  };
  const onClick = async e => {
    const t = e.target.closest('[data-tab],[data-cal],[data-day],[data-act]'); if (!t) return;
    if (t.dataset.tab) { cur = t.dataset.tab; draw(); return; }
    if (t.dataset.cal === 'prev') { if (--cm < 0) { cm = 11; cy--; } draw(); return; }
    if (t.dataset.cal === 'next') { if (++cm > 11) { cm = 0; cy++; } draw(); return; }
    if (t.dataset.day) {
      const ds = t.dataset.day, wd = E2.toDate(ds).getDay();
      if (H.custom[ds] != null) delete H.custom[ds];
      else if (H.work[ds]) delete H.work[ds];
      else if (state.hol.has(ds) || wd === 0 || wd === 6) H.work[ds] = true;
      else H.custom[ds] = '지정 휴일';
      applySettings(); saveSettingsSoon(); draw(); return;
    }
    if (t.dataset.act === 'hol-fetch') { $('#holMsg').textContent = '가져오는 중…'; const r = await refreshHolidays(true); draw(); const m = $('#holMsg'); if (m) m.textContent = r.join(' · '); }
  };
  const onChange = e => {
    const t = e.target;
    if (t.name === 'basis') { S.dueBasis = t.value; }
    else if (t.dataset.std) { const v = t.value.trim(); if (v === '' || !(+v > 0)) delete S.stdDays[t.dataset.std]; else S.stdDays[t.dataset.std] = +v; }
    else if (t.dataset.opt) {
      const v = t.type === 'checkbox' ? t.checked : Math.max(0, +t.value || 0);
      if (t.dataset.opt === 'organize.auto') { S.organize.auto = v; S.organize.asked = true; } else S[t.dataset.opt] = v;
    } else return;
    applySettings(); saveSettingsSoon();
  };
  await info('휴일 · 처리기간 설정', '', {
    width: 'min(900px, calc(100vw - 32px))',
    onOpen: body => { draw(); body.addEventListener('click', onClick); body.addEventListener('change', onChange); },
  });
  const body = $('#modalBody'); body.removeEventListener('click', onClick); body.removeEventListener('change', onChange);
  await writeSettings(); render();
}

/* ───── 이력 문서 (Word · PDF) ───── */
async function saveBlob(bytes, name, kind) {
  const T = { xlsx: ['엑셀 파일', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'], docx: ['Word 문서', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'], pdf: ['PDF 문서', 'application/pdf'] }[kind];
  if (window.showSaveFilePicker) {
    try {
      const h = await window.showSaveFilePicker({ id: 'odt-save-' + kind, suggestedName: name, types: [{ description: T[0], accept: { [T[1]]: ['.' + kind] } }] });
      const w = await h.createWritable(); await w.write(bytes); await w.close();
      toast(`저장했습니다: ${h.name}`); return true;
    } catch (e) {
      if (e.name === 'AbortError') return false;
      if (e.name === 'NoModificationAllowedError' || e.name === 'InvalidModificationError') { toast('같은 이름의 파일이 열려 있어 저장할 수 없습니다. 파일을 닫거나 다른 이름으로 저장하세요.', 'err'); return false; }
    }
  }
  const url = URL.createObjectURL(new Blob([bytes], { type: T[1] }));
  const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  toast(`다운로드 폴더에 저장했습니다: ${name}`); return true;
}
const RENDERABLE = f => /^(hwpx|img|pdf)$/.test(f.kind);
async function makeHistory(d, fmt) {
  const m = d.match || { replies: [], reports: [] };
  const samples = d.result.rows.map(r => r.시료번호).filter(Boolean);
  const atts = d.C.attach;
  const canFolder = !!(d.dirName && d.dir);
  const o = await modal(`이력 문서 만들기 (${fmt === 'pdf' ? 'PDF' : 'Word'})`, `
    <div class="form"><label>대상 시료 <select id="hSample"><option value="">공문 전체 (시료 ${samples.length}개)</option>${samples.map(s => `<option>${esc(s)}</option>`).join('')}</select></label>
    <h4>그림으로 넣을 문서</h4>
    <label class="chk"><input type="checkbox" id="hReq" checked> 의뢰공문</label>
    <label class="chk" style="margin-left:22px"><input type="checkbox" id="hWm" ${state.settings.watermark ? 'checked' : ''} ${peekNotes(d.key).recv ? '' : 'disabled'}> 시료접수일 워터마크 ${peekNotes(d.key).recv ? '' : '<span class="muted small">(시료접수일 입력 후 사용)</span>'}</label>
    <label class="chk"><input type="checkbox" id="hRep" ${m.replies.length ? 'checked' : 'disabled'}> 시행공문 ${m.replies.length ? `(${m.replies.length})` : '<span class="muted small">(없음)</span>'}</label>
    <label class="chk"><input type="checkbox" id="hPdf" ${m.reports.length ? 'checked' : 'disabled'}> 시험성적서 ${m.reports.length ? `(${m.reports.length}개 파일, 대상 시료 쪽만)` : '<span class="muted small">(없음)</span>'}</label>
    <label class="chk"><input type="checkbox" id="hAtt" ${atts.length ? 'checked' : 'disabled'}> 추가 자료 (공문 폴더의 HWPX·그림·PDF) ${atts.length ? `(${atts.length})` : '<span class="muted small">(없음)</span>'}</label>
    <h4>저장</h4>
    <label class="chk"><input type="checkbox" id="hFolder" ${canFolder ? 'checked' : 'disabled'}> 공문 폴더에 저장 ${canFolder ? `<span class="muted small">(${esc(d.dirName)})</span>` : '<span class="muted small">(공문 폴더 정리 후 사용)</span>'}</label></div>`, '만들기', {
    collect: () => ({ sample: $('#hSample').value, req: $('#hReq').checked, wm: $('#hWm').checked, rep: $('#hRep').checked, pdf: $('#hPdf').checked, att: $('#hAtt').checked, folder: $('#hFolder').checked }),
  });
  if (!o) return;
  busy(true, '이력 문서 만드는 중… (문서를 그림으로 바꾸는 중)');
  try {
    const blocks = await historyBlocks(d, o);
    busy(true, '이력 문서 저장하는 중…');
    const stamp = today().replace(/-/g, '');
    const fname = E2.safeName(`이력_${o.sample || (d.result.doc.시행 || '공문')}_${stamp}.${fmt}`, 120);
    const bytes = fmt === 'pdf' ? await DG.buildPdf(DG.layoutPages(blocks, `${d.result.doc.의뢰기관} ${d.result.doc.시행} 시료 처리 이력`)) : await DG.buildDocx(blocks, blocks[0].text);
    let saved = false;
    if (o.folder && canFolder) {
      const name = await uniqueName(d.dir, fname);
      const fh = await d.dir.getFileHandle(name, { create: true }); const w = await fh.createWritable(); await w.write(bytes); await w.close();
      toast(`공문 폴더에 저장했습니다: ${name}`); saved = true;
    } else saved = await saveBlob(bytes, fname, fmt);
    if (saved) { addLog(d.key, `이력 문서 작성 (${fmt === 'pdf' ? 'PDF' : 'Word'}${o.sample ? ', ' + o.sample : ''})`, o.sample, true); await writeNotes(); render(); }
  } catch (e) { console.error(e); toast('이력 문서를 만들지 못했습니다: ' + explain(e), 'err'); }
  busy(false);
}
async function historyBlocks(d, o) {
  const doc = d.result.doc, n = peekNotes(d.key), m = d.match || { replies: [], reports: [] };
  const rows = d.result.rows.filter(r => r.시료번호 && (!o.sample || r.시료번호 === o.sample));
  const rc = caseRecv(d), B = [];
  B.push({ t: 'title', text: `시료 처리 이력 — ${o.sample || doc.제목}` });
  B.push({ t: 'kv', rows: [
    ['의뢰기관', `${doc.의뢰기관} (${doc.의뢰자})`], ['의뢰공문', doc.제목], ['공문번호(시행)', `${doc.시행}${doc.시행일 ? ' (' + doc.시행일 + ')' : ''}`],
    ['접수', `${doc.접수}${doc.접수일 ? ' (' + doc.접수일 + ')' : ''}`], ['시료접수일', rc ? `${fmtFull(rc.date)}${rc.est ? ' (공문 접수일 기준)' : ''}${rc.before13 ? ', 13시 이전 접수' : ''}` : '-'],
    ['시료채취자', doc.시료채취자], ['폴더', d.dirName || '-'], ['작성일', fmtFull(today())],
  ] });
  B.push({ t: 'table', head: ['시료번호', '검사항목', '처리기한', '성적서 접수번호', '결과', '판정'], widths: [16, 22, 12, 14, 26, 10], rows: rows.map(r => {
    const sd = rowDue(d, r), s = r._rep && r._rep.s;
    return [r.시료번호, r.검사항목, sd && sd.due ? `${sd.due} (${sd.item} ${sd.days}일)` : '-', s ? s.접수번호 : '-', s ? s.결과.map(x => `${x.항목명 || x.항목} ${x.결과}`).join(', ') : '-', s ? s.판정 : '-'];
  }) });
  const css = (await odtPreview(d.f)).css + WM_CSS + '.odt-page{padding:1cm 1.2cm}';
  const odtImg = async (f, wm) => { const r = await odtPreview(f); return DG.htmlToCanvas(`<div style="padding:8px 0">${wm ? `<div class="wm-wrap">${wmHtml(d)}${r.html}</div>` : r.html}</div>`, css, 820, 2); };
  let sn = 0;
  if (o.req) { B.push({ t: 'h', text: `${++sn}. 의뢰공문` }); B.push({ t: 'img', canvas: await odtImg(d.f, o.wm && n.recv), caption: d.f.nm }); }
  if (o.rep && m.replies.length) { B.push({ t: 'h', text: `${++sn}. 시행공문 (결과 알림)` }); for (const x of m.replies) B.push({ t: 'img', canvas: await odtImg(x.f, false), caption: x.f.nm }); }
  if (o.pdf && m.reports.length) {
    B.push({ t: 'h', text: `${++sn}. 시험성적서` });
    for (const x of m.reports) {
      const want = new Set(rows.map(r => E2.noKey(r.시료번호)));
      const pages = x.rep.samples.filter(s => want.has(E2.noKey(s.시료명))).flatMap(s => s.쪽 || []);
      if (!pages.length) continue;
      const cs = await DG.pdfToCanvases(await fileBytes(x.f), pages, 2);
      cs.forEach((c, i) => B.push({ t: 'img', canvas: c, caption: `${x.f.nm} — ${pages[i]}쪽` }));
    }
  }
  if (o.att && d.C.attach.length) {
    B.push({ t: 'h', text: `${++sn}. 추가 자료` });
    for (const f of d.C.attach) {
      try {
        if (f.kind === 'hwpx') { const h = await parseHwpxEntry(f); B.push({ t: 'img', canvas: await DG.htmlToCanvas(E2.hwpxHtml(h, ''), '', 900, 2), caption: f.nm }); }
        else if (f.kind === 'img') B.push({ t: 'img', canvas: await DG.imageToCanvas(await fileBytes(f), f.nm), caption: f.nm });
        else if (f.kind === 'pdf') { const cs = await DG.pdfToCanvases(await fileBytes(f), null, 2); cs.forEach((c, i) => B.push({ t: 'img', canvas: c, caption: `${f.nm} — ${i + 1}쪽` })); }
        else B.push({ t: 'p', text: `· ${f.nm} (그림으로 넣을 수 없는 형식 — 공문 폴더의 원본 파일 참고)`, muted: true });
      } catch (e) { B.push({ t: 'p', text: `· ${f.nm} (변환 실패: ${explain(e)})`, muted: true }); }
    }
  }
  B.push({ t: 'h', text: `${++sn}. 메모 · 이력` });
  if (n.memo) B.push({ t: 'p', text: n.memo });
  const log = (n.log || []).filter(x => !o.sample || !x.sample || x.sample === o.sample).sort((a, b) => (a.date + a.at < b.date + b.at ? -1 : 1));
  if (log.length) B.push({ t: 'table', head: ['일자', '시료', '내용'], widths: [14, 18, 68], rows: log.map(x => [x.date, x.sample || '전체', x.text + (x.auto ? ' (자동 기록)' : '')]) });
  if (!n.memo && !log.length) B.push({ t: 'p', text: '기록 없음', muted: true });
  return B;
}

/* ───── 엑셀 저장 ───── */
function exportRow(d, r, st) {
  const sd = rowDue(d, r), p = progressHtml(d), n = peekNotes(d.key), rc = caseRecv(d), s = r._rep && r._rep.s;
  const extra = {
    시료접수일: rc ? rc.date + (rc.est ? ' (추정)' : '') : '', 처리기한: sd && sd.due ? sd.due : '', 남은기간: sd && sd.rem && st === '처리대기' ? remText(sd.rem) : '',
    기한결정항목: sd && sd.item ? `${sd.item} ${sd.days}일` : '', 시행공문: d.match ? d.match.replies.map(x => x.f.nm).join(', ') : '',
    성적서: d.match ? d.match.reports.map(x => x.f.nm).join(', ') : '', 성적서접수번호: s ? s.접수번호 : '', 판정: s ? s.판정 : '', 결과: resultText(r).replace(/^.*? — /, ''),
    메모: [n.memo || '', ...(n.log || []).filter(x => !x.auto && (!x.sample || x.sample === r.시료번호)).map(x => `${x.date} ${x.text}`)].filter(Boolean).join('\n'), 폴더: d.dirName || '',
  };
  void p;
  return extra;
}
async function exportExcel() {
  const list = visibleDocs();
  if (!list.length) return toast('저장할 공문이 없습니다.');
  const cols = [...E.COLUMNS]; cols.splice(cols.indexOf('시료채취일') + 1, 0, ...XLSX_EXTRA.filter(k => k !== '폴더' && k !== '메모')); cols.splice(cols.indexOf('확인필요'), 0, '메모', '폴더');
  const header = ['상태', ...cols];
  const rows = [], meta = [];
  for (const d of list) {
    const st = d.loc === 'done' ? '처리완료' : isChecked(d) ? '완료체크' : '처리대기';
    for (const r of docRows(d)) {
      const ex = d.result ? exportRow(d, r, st) : {};
      rows.push([st, ...cols.map(c => ex[c] != null ? ex[c] : r[c] == null ? '' : r[c])]);
      const sd = d.result && st === '처리대기' ? rowDue(d, r) : null;
      meta.push({ dup: !!(d.result && d.result.duplicate), st, urgent: !!(sd && sd.rem && (sd.rem.overdue || sd.rem.days <= state.settings.imminent)) });
    }
  }
  const iWarn = header.indexOf('확인필요'), iDate = header.indexOf('시료채취일'), iDue = header.indexOf('처리기한'), iRem = header.indexOf('남은기간');
  const bytes = X.buildXlsx([{
    name: '공문추출', columns: header.map(h => ({ header: h, width: XLSX_W[h] || 12 })), rows,
    styleOf: (ri, k, v) => meta[ri].dup ? 3 : ((k === iWarn && v) || (k === iDate && v === '채취일자 확인 필요') || ((k === iDue || k === iRem) && meta[ri].urgent)) ? 2 : (k === 0 && meta[ri].st !== '처리대기') ? 4 : 0,
  }]);
  await saveBlob(bytes, `공문추출_${today()}.xlsx`, 'xlsx');
}

/* ───── 기준표 양식 ───── */
const unitOf = item => ({ '생태독성': 'TU', '색도': '도', 'pH': '' })[item] != null ? ({ '생태독성': 'TU', '색도': '도', 'pH': '' })[item] : 'mg/L';
async function makeStdTemplate() {
  const results = [...state.docs, ...state.doneDocs].filter(d => d.result).map(d => d.result);
  const miss = E.missingStdPairs(results);
  const hasStd = !!state.stdFile;
  if (!miss.length) return toast(hasStd ? '기준이 비어 있는 항목이 없습니다.' : '공문이 없어 양식을 만들 수 없습니다.');
  const fname = hasStd ? '기준표_추가필요.xlsx' : '기준표.xlsx';
  const ok = await modal('기준표 양식 만들기', `<p>현재 공문에서 기준이 비어 있는 <b>지역구분 × 항목 ${miss.length}개</b>를 모아 <b>${esc(state.root.name)}\\${fname}</b> 파일을 만듭니다.</p>
    <ol><li>엑셀로 열어 <b>기준값</b> 칸을 채우고 저장합니다.</li>${hasStd ? `<li>채운 행을 기존 <b>${esc(state.stdFile)}</b>에 옮겨 붙이고 저장합니다.</li>` : ''}<li>엑셀을 닫고 이 화면에서 <b>새로고침</b>을 누르면 기준이 채워집니다.</li></ol>
    <p class="muted">지역구분을 비우거나 * 로 쓰면 모든 지역에 같은 기준을 적용합니다.</p>`, '만들기');
  if (!ok) return;
  const rows = miss.map(m => [m.지역구분, m.항목, '', unitOf(m.항목), `${m.건수}건 (예: ${m.예시})`]);
  const guide = [
    ['기준표 작성 방법'], ['1. [기준표] 시트의 기준값 칸을 채우고 저장합니다. (파일 이름은 반드시 기준표.xlsx)'],
    ['2. 지역구분은 공문에 적힌 값(가, 나, 청정, 특례, 기타, 하수처리구역내 등)을 그대로 씁니다.'],
    ['3. 지역구분을 비우거나 * 로 쓰면 모든 지역에 적용합니다. 같은 항목에 지역별 기준이 있으면 지역이 맞는 쪽이 우선입니다.'],
    ['4. 공문에 기준이 적혀 있으면 공문 값을 우선하고, 기준표는 빈 항목만 채웁니다.'],
    ['5. 항목 이름은 BOD, TOC, SS, T-N, T-P, n-H(광), ABS, 생태독성, 색도 등 프로그램 표준명을 씁니다. (총인·총질소 등도 인식)'],
  ];
  const bytes = X.buildXlsx([
    { name: '기준표', columns: [{ header: '지역구분', width: 30 }, { header: '항목', width: 14 }, { header: '기준값', width: 10 }, { header: '단위', width: 8 }, { header: '참고(해당 시료)', width: 26 }], rows, styleOf: (ri, k) => k === 2 ? 2 : 0 },
    { name: '작성 안내', columns: [{ header: '안내', width: 110 }], rows: guide },
  ]);
  try {
    const fh = await state.root.getFileHandle(fname, { create: true });
    const w = await fh.createWritable(); await w.write(bytes); await w.close();
    await info('기준표 양식', `<p><b>${esc(fname)}</b> 파일을 공문 폴더에 만들었습니다.</p><p>기준값을 채워 저장한 뒤 엑셀을 닫고 <b>새로고침</b>을 누르세요.</p>`);
  } catch (e) { toast('양식을 만들지 못했습니다: ' + explain(e), 'err'); }
}

/* ───── 열 선택 ───── */
function renderColMenu() {
  const m = $('#colMenu');
  m.innerHTML = `<div class="cols">${COLS.map(c => `<label><input type="checkbox" value="${esc(c.k)}" ${state.cols.includes(c.k) ? 'checked' : ''}> ${esc(c.label || c.k)}</label>`).join('')}</div>
    <div class="pop-actions"><button class="btn small" data-act="cols-default">기본값</button><button class="btn small" data-act="cols-all">전체 표시</button></div>`;
}

/* ───── 도움말 ───── */
function showHelp() {
  info('사용 방법', `
    <h4>1. 공문 모으기</h4><p>검사의뢰 공문(ODT)과 첨부(HWPX·그림·PDF), 시행공문(결과 알림 ODT), 시험성적서(PDF)를 모두 공문 폴더에 저장합니다. 이 창으로 돌아오면 자동으로 다시 읽습니다.</p>
    <h4>2. 공문별 폴더</h4><p>의뢰공문마다 <b>의뢰기관_제목_시행번호</b> 폴더를 만들어 공문과 붙임 파일을 옮깁니다(처음 한 번 확인). 시료 표가 공문 본문에 없고 HWPX로 첨부된 경우 첨부 표에서 시료를 읽고, 읽지 못하면 [시료 직접 입력]으로 붙여넣습니다.</p>
    <h4>3. 처리기한</h4><p>[시료접수일] 칸을 눌러 달력에서 날짜를 고르면 [별표 2] 표준처리기간으로 기한과 남은 근무일을 계산합니다. 시료에 항목이 여러 개면 <b>설정에서 고른 기준</b>(가장 긴 항목 / 가장 짧은 항목)을 씁니다. 토·일·공휴일·지정 휴일은 빼고, 13시 이후 접수는 접수일을 빼고 셉니다(13시 이전 접수 체크 시 포함). 임박은 빨간 글씨, 초과는 빨간 바탕입니다. 공휴일은 인터넷에서 가져오고, [휴일·처리기간] 달력에서 날짜를 눌러 휴일을 추가할 수 있습니다.</p>
    <h4>4. 시행공문·성적서 대조</h4><p>시행공문 본문의 의뢰 공문번호, 성적서의 공문번호·시료명·의뢰기관이 모두 맞으면 <span class="pill ok">시행 ✔</span> <span class="pill ok">성적서 n/n</span>으로 표시합니다. 일부만 맞으면 <span class="pill part">△</span>입니다.</p>
    <h4>5. 완료 체크 → 처리 완료</h4><p>맨 앞 칸을 체크하고 <b>[처리 완료]</b>를 누르면 시행공문·성적서가 공문 폴더로 옮겨지고, 공문 폴더는 <b>${DONE_DIR}</b>로 옮겨집니다. [성적처리완료 폴더] 보기에서 되돌릴 수 있습니다.</p>
    <h4>6. 메모·이력</h4><p>상세 화면에서 메모와 시료별 이력을 적고, <b>[이력 문서 Word/PDF]</b>로 의뢰공문·시행공문·성적서·추가 자료를 그림으로 넣은 이력 문서를 만듭니다.</p>
    <h4>7. 워터마크</h4><p>시료접수일을 입력하면 의뢰공문 우측 상단에 접수일 도장이 표시됩니다(화면·인쇄·이력 문서). 원본 ODT 파일은 바꾸지 않습니다.</p>
    <h4>저장 파일</h4><p class="small">${STATUS_FILE}(완료 체크·처리 기록) · ${NOTES_FILE}(시료접수일·메모·이력) · ${SETTINGS_FILE}(휴일·처리기간 설정) — 모두 공문 폴더에 있습니다.</p>`, { width: 'min(760px, calc(100vw - 32px))' });
}

/* ───── 이벤트 ───── */
function bindUi() {
  $('#btnPick').onclick = pickFolder;
  $('#btnRefresh').onclick = () => scan();
  $('#btnHelp').onclick = showHelp;
  $('#btnDone').onclick = processChecked;
  $('#btnExcel').onclick = exportExcel;
  $('#btnStd').onclick = makeStdTemplate;
  $('#btnSettings').onclick = () => showSettings();
  $('#fWm').onchange = e => { state.settings.watermark = e.target.checked; saveSettingsSoon(); renderDetail(); };
  let qt;
  $('#fSearch').oninput = e => { clearTimeout(qt); qt = setTimeout(() => { state.filter.q = e.target.value; render(); }, 150); };
  $('#fOrg').onchange = e => { state.filter.org = e.target.value; render(); };
  $('#fState').onchange = async e => { state.filter.state = e.target.value; state.selected = null; if (e.target.value === 'done') await scan({ noOrganize: true }); else render(); };
  $('#fWarn').onchange = e => { state.filter.warn = e.target.checked; render(); };
  $('#btnCols').onclick = e => { e.stopPropagation(); const m = $('#colMenu'); if (m.hidden) { renderColMenu(); m.hidden = false; } else m.hidden = true; };
  $('#colMenu').addEventListener('click', e => e.stopPropagation());
  $('#colMenu').addEventListener('change', e => {
    if (e.target.type !== 'checkbox') return;
    const k = e.target.value;
    state.cols = e.target.checked ? COLS.map(c => c.k).filter(x => x === k || state.cols.includes(x)) : state.cols.filter(x => x !== k);
    saveCols(); render();
  });
  $('#colMenu').addEventListener('click', e => {
    const a = e.target.dataset.act;
    if (a === 'cols-default') state.cols = COLS.filter(c => c.def).map(c => c.k);
    else if (a === 'cols-all') state.cols = COLS.map(c => c.k);
    else return;
    saveCols(); renderColMenu(); render();
  });
  document.addEventListener('click', e => { $('#colMenu').hidden = true; if (!e.target.closest('#datePop')) $('#datePop').hidden = true; });
  $('#banner').addEventListener('click', e => {
    const a = e.target.dataset.act;
    if (a === 'organize') organizeAll(false); else if (a === 'inbox') showInbox();
  });

  const grid = $('#grid');
  grid.tHead.addEventListener('click', e => {
    const th = e.target.closest('th[data-k]'); if (!th) return;
    const k = th.dataset.k;
    state.sort = state.sort.key === k ? { key: k, dir: -state.sort.dir } : { key: k, dir: k === '접수일' ? -1 : 1 };
    render();
  });
  grid.tHead.addEventListener('change', e => {
    if (e.target.id !== 'chkAll') return;
    const on = e.target.checked;
    for (const d of visibleDocs()) if (d.loc === 'root') setChecked(d, on);
    render();
  });
  grid.tBodies[0].addEventListener('click', e => {
    const tr = e.target.closest('tr[data-id]'); if (!tr) return;
    const d = findDoc(tr.dataset.id); if (!d) return;
    const act = e.target.closest('[data-act]') && e.target.closest('[data-act]').dataset.act;
    if (act === 'check') { setChecked(d, e.target.checked); render(); return; }
    if (act === 'restore') { restore(d); return; }
    if (act === 'recv') { e.stopPropagation(); pickRecv(d, e.target.closest('[data-act]')); return; }
    if (e.target.closest('td.c-chk')) return;
    state.selected = state.selected === d.id ? null : d.id;
    render();
  });
  const det = $('#detail');
  det.addEventListener('click', e => {
    const el = e.target.closest('[data-act]'); if (!el) return;
    const act = el.dataset.act;
    const d = findDoc(det.dataset.id);
    if (act === 'close') { state.selected = null; render(); }
    else if (act.startsWith('mode-')) { state.detailMode = act.slice(5); savePref('odt-detail-mode', state.detailMode); renderDetail(); }
    else if (!d) return;
    else if (act.startsWith('view:')) { state.viewer = act.slice(5); if (state.detailMode === 'ext') { state.detailMode = 'side'; savePref('odt-detail-mode', 'side'); } renderDetail(); }
    else if (act === 'pv-big') openPreviewWindow(d);
    else if (act === 'pv-download') { const v = viewerList(d).find(x => x.k === state.viewer) || viewerList(d)[0]; downloadFile(v.f); }
    else if (act === 'check-toggle') { setChecked(d, !isChecked(d)); render(); }
    else if (act === 'restore') restore(d);
    else if (act === 'recv') { e.stopPropagation(); pickRecv(d, el); }
    else if (act === 'recv-doc') { const rc = caseRecv(d); if (rc) setRecv(d, rc.date); }
    else if (act === 'settings') showSettings('std');
    else if (act === 'manual') manualInput(d);
    else if (act === 'organize-one') organizeSelected(d);
    else if (act.startsWith('adopt:')) { const [, t, i] = act.split(':'); adopt(d, t, +i); }
    else if (act.startsWith('hist:')) makeHistory(d, act.slice(5));
    else if (act === 'log-add') {
      const text = $('#logText').value.trim(); if (!text) { $('#logText').focus(); return; }
      const n = notesOf(d.key); n.log = n.log || [];
      n.log.push({ id: uid(), at: nowIso(), date: $('#logDate').value || today(), sample: $('#logSample').value, text, auto: false });
      saveNotesSoon(); render();
    } else if (act.startsWith('log-del:')) {
      const id = act.slice(8), n = notesOf(d.key); n.log = (n.log || []).filter(x => x.id !== id); saveNotesSoon(); render();
    }
  });
  det.addEventListener('change', e => {
    const act = e.target.dataset.act, d = findDoc(det.dataset.id); if (!d) return;
    if (act === 'before13') { const n = notesOf(d.key); n.before13 = e.target.checked; addLog(d.key, `13시 이전 접수 ${e.target.checked ? '지정' : '해제'}`, '', true); saveNotesSoon(); render(); }
    else if (act === 'wm') { state.settings.watermark = e.target.checked; $('#fWm').checked = e.target.checked; saveSettingsSoon(); renderDetail(); }
  });
  det.addEventListener('input', e => {
    if (e.target.dataset.act !== 'memo') return;
    const d = findDoc(det.dataset.id); if (!d) return;
    notesOf(d.key).memo = e.target.value; saveNotesSoon();
  });
  det.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.id === 'logText') { e.preventDefault(); det.querySelector('[data-act=log-add]').click(); } });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('#modal').hidden && $('#datePop').hidden && state.selected) { state.selected = null; render(); } });
  window.addEventListener('focus', () => { if (state.root && !state.busy && $('#modal').hidden && Date.now() - state.lastScan > 2000) scan({ quiet: true }); });
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(fitPreview, 150); });
  window.addEventListener('beforeunload', () => { if (saveTimer) writeStatus(); if (notesTimer) writeNotes(); if (setTimer) writeSettings(); });
}

init();
})();
