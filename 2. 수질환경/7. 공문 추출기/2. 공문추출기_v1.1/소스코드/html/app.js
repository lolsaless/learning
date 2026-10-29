/* 검사의뢰 공문 추출기 — 화면·폴더 관리 */
(function () {
'use strict';
const E = window.OdtEngine, X = window.MiniXlsx;
const STATUS_FILE = '_처리상태.json';
const DONE_DIR = '성적처리완료';
const STD_RE = /^기준표\.(xlsx|csv)$/i;
const HISTORY_MAX = 1000;

const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const nowIso = () => new Date().toISOString();
const shortNo = v => { const m = /-(\d+)$/.exec(v || ''); return m ? m[1] : (v || ''); };

/* ───── 열 정의 (doc: 공문 단위 값 → 시료 여러 행을 하나로 묶어 표시) ───── */
// v1.1 기본 열 순서: 접수일, 의뢰기관, 의뢰자, 발신명의, 시행, 시료번호, 검사항목, 시료채취일 (나머지는 [열 선택])
const COLS = [
  { k: '접수일', doc: 1, def: 1 },
  { k: '의뢰기관', doc: 1, def: 1 },
  { k: '의뢰자', doc: 1, def: 1 },
  { k: '발신명의', doc: 1, def: 1 },
  { k: '시행', doc: 1, def: 1 },
  { k: '시료번호', def: 1 },
  { k: '검사항목', def: 1, wrap: 1 },
  { k: '시료채취일', def: 1 },
  { k: '기준', wrap: 1 },
  { k: '지역구분', wrap: 1 },
  { k: '시료채취자', doc: 1 },
  { k: '접수', label: '접수번호', doc: 1, fmt: shortNo },
  { k: '시행일', doc: 1 }, { k: '제목', doc: 1, wrap: 1 },
  { k: '기준출처' }, { k: '채취시각' }, { k: '채취일출처' }, { k: '업종/성상', wrap: 1 }, { k: '시료량', wrap: 1 },
  { k: '채취지점' }, { k: '비고', wrap: 1 }, { k: '기타', wrap: 1 },
  { k: '우편번호', doc: 1 }, { k: '주소', doc: 1 }, { k: '전화번호', doc: 1 }, { k: '이메일', doc: 1 }, { k: '파일명', doc: 1 },
];
const XLSX_W = { 상태: 9, 접수: 30, 접수일: 11, 의뢰기관: 10, 의뢰자: 12, 발신명의: 18, 시행: 22, 시행일: 11, 제목: 40, 시료번호: 18, 검사항목: 34, 기준: 30, 기준출처: 10, 지역구분: 28, 시료채취일: 16, 채취시각: 8, 채취일출처: 9, 시료채취자: 9, '업종/성상': 22, 시료량: 22, 채취지점: 10, 비고: 18, 기타: 24, 우편번호: 8, 주소: 36, 전화번호: 14, 이메일: 22, 확인필요: 40, 파일명: 44 };

function loadCols() {
  try { const v = JSON.parse(localStorage.getItem('odt-cols-v11') || 'null'); if (Array.isArray(v) && v.length) return v; } catch (e) { /* 저장소 사용 불가 */ }
  return COLS.filter(c => c.def).map(c => c.k);
}
function saveCols() { try { localStorage.setItem('odt-cols-v11', JSON.stringify(state.cols)); } catch (e) { /* 무시 */ } }

function loadPref(k, d) { try { return localStorage.getItem(k) || d; } catch (e) { return d; } }
function savePref(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* 무시 */ } }
const state = {
  root: null, savedHandle: null,
  docs: [], doneDocs: [], doneCount: 0, cache: new Map(),
  status: { version: 1, checked: {}, history: [] },
  stdTable: [], stdFile: '', stdFilled: 0,
  excluded: [], busy: false, lastScan: 0,
  sort: { key: '접수일', dir: -1 }, // v1.1: 최근 접수 공문이 위로
  detailMode: loadPref('odt-detail-mode', 'side'), previewCache: new Map(),
  filter: { q: '', org: '', state: 'pending', warn: false },
  cols: loadCols(), selected: null,
};

/* ───── 압축 해제 (브라우저 내장) ───── */
async function inflateRaw(data) {
  const ds = new DecompressionStream('deflate-raw');
  const stream = new Blob([data]).stream().pipeThrough(ds);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/* ───── 폴더 핸들 저장 (IndexedDB) ───── */
function idb() {
  return new Promise((res, rej) => { const r = indexedDB.open('odt-extractor', 1); r.onupgradeneeded = () => r.result.createObjectStore('kv'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
}
async function idbGet(k) {
  try { const db = await idb(); return await new Promise(res => { const q = db.transaction('kv').objectStore('kv').get(k); q.onsuccess = () => res(q.result); q.onerror = () => res(null); }); } catch (e) { return null; }
}
async function idbSet(k, v) {
  try { const db = await idb(); await new Promise(res => { const t = db.transaction('kv', 'readwrite'); t.objectStore('kv').put(v, k); t.oncomplete = res; t.onerror = res; }); } catch (e) { /* 무시 */ }
}

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
    const ok = $('#modalOk'), cancel = $('#modalCancel');
    ok.textContent = okLabel || '확인'; ok.className = 'btn ' + (opts.danger ? 'danger' : 'primary');
    cancel.hidden = !!opts.infoOnly;
    $('#modal').hidden = false; ok.focus();
    const done = v => { $('#modal').hidden = true; ok.onclick = cancel.onclick = null; document.removeEventListener('keydown', onKey); resolve(v); };
    const onKey = e => { if (e.key === 'Escape') done(false); };
    ok.onclick = () => done(true); cancel.onclick = () => done(false);
    document.addEventListener('keydown', onKey);
  });
}
const info = (title, html) => modal(title, html, '닫기', { infoOnly: true });

/* ───── 시작 ───── */
async function init() {
  bindUi();
  if (!('showDirectoryPicker' in window) || typeof DecompressionStream === 'undefined') { showUnsupported(); return; }
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
  $('#toolbar').hidden = true; $('#bottombar').hidden = true; $('#grid').hidden = true; $('#emptyBox').hidden = false;
  $('#emptyBox').innerHTML = `
    <h2>공문 폴더를 연결하세요</h2>
    <ol>
      <li><b>공문 폴더 선택</b>을 누르고, 검사의뢰 공문(ODT)을 모아 두는 폴더를 고릅니다.</li>
      <li>브라우저가 폴더 접근 허용을 물으면 <b>파일 보기 및 편집 허용</b>을 누릅니다. (처리 완료 공문을 옮기기 위해 필요)</li>
      <li>폴더 안의 공문을 모두 읽어 <b>시료 1개당 1행</b>으로 보여 줍니다.</li>
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
// 시험·자동화용: 폴더 핸들을 직접 넘겨 연결
window.__odtConnect = h => connect(h);

async function connect(h) {
  state.root = h; state.cache.clear(); state.selected = null;
  $('#folderName').textContent = h.name; $('#btnRefresh').disabled = false;
  await readStatus();
  await scan();
}

/* ───── 처리상태 파일 (_처리상태.json) ───── */
async function readStatus() {
  state.status = { version: 1, checked: {}, history: [] };
  try {
    const fh = await state.root.getFileHandle(STATUS_FILE);
    const j = JSON.parse(await (await fh.getFile()).text());
    if (j && typeof j === 'object') state.status = { version: 1, checked: j.checked || {}, history: j.history || [] };
  } catch (e) { /* 없으면 새로 만듦 */ }
}
let saveTimer;
function saveStatusSoon() { clearTimeout(saveTimer); saveTimer = setTimeout(writeStatus, 250); }
async function writeStatus() {
  clearTimeout(saveTimer);
  try {
    state.status.updated = nowIso();
    state.status.history = state.status.history.slice(0, HISTORY_MAX);
    const fh = await state.root.getFileHandle(STATUS_FILE, { create: true });
    const w = await fh.createWritable(); await w.write(JSON.stringify(state.status, null, 1)); await w.close();
  } catch (e) { toast('처리상태 저장 실패: ' + explain(e), 'err'); }
}

/* ───── 폴더 읽기 ───── */
async function listFiles(dir) {
  const odt = [], other = []; let std = null;
  for await (const [name, h] of dir.entries()) {
    if (h.kind !== 'file') continue;
    const nm = name.normalize('NFC');
    if (nm.startsWith('~$') || nm.startsWith('.')) continue;
    if (/\.odt$/i.test(nm)) odt.push({ name, nm, handle: h });
    else if (STD_RE.test(nm)) std = { name, nm, handle: h };
    else if (nm !== STATUS_FILE) other.push(nm);
  }
  odt.sort((a, b) => a.nm.localeCompare(b.nm, 'ko'));
  return { odt, other, std };
}
async function parseEntry(en, loc) {
  const file = await en.handle.getFile();
  const ck = `${loc}|${en.nm}|${file.size}|${file.lastModified}`;
  if (state.cache.has(ck)) return Object.assign(state.cache.get(ck), { handle: en.handle, name: en.name });
  const d = { id: ck, name: en.name, nm: en.nm, loc, size: file.size };
  try {
    if (!file.size) throw new Error('빈 파일 (다운로드 중이거나 손상된 파일)');
    d.result = await E.extractOdt(new Uint8Array(await file.arrayBuffer()), en.nm, inflateRaw);
  } catch (e) { d.error = (e && e.message) || String(e); }
  d.key = d.result && d.result.doc.접수 ? d.result.doc.접수 : 'file:' + en.nm;
  d.handle = en.handle;
  state.cache.set(ck, d);
  return d;
}
async function getDoneDir(create) {
  try { return await state.root.getDirectoryHandle(DONE_DIR, create ? { create: true } : undefined); } catch (e) { return null; }
}
async function scan(opts = {}) {
  if (!state.root || state.busy) return;
  state.busy = true;
  try {
    const { odt, other, std } = await listFiles(state.root);
    if (!opts.quiet) busy(true, `공문 읽는 중… 0 / ${odt.length}`);
    const docs = [];
    for (let i = 0; i < odt.length; i++) {
      docs.push(await parseEntry(odt[i], 'root'));
      if (!opts.quiet && (i % 3 === 2 || i === odt.length - 1)) busy(true, `공문 읽는 중… ${i + 1} / ${odt.length}`);
    }
    state.docs = docs; state.excluded = other;
    const doneDir = await getDoneDir(false);
    if (doneDir) {
      const dl = await listFiles(doneDir); state.doneCount = dl.odt.length;
      if (state.filter.state === 'done') {
        const dd = [];
        for (let i = 0; i < dl.odt.length; i++) { dd.push(await parseEntry(dl.odt[i], 'done')); if (!opts.quiet && i % 5 === 4) busy(true, `완료 공문 읽는 중… ${i + 1} / ${dl.odt.length}`); }
        state.doneDocs = dd;
      } else state.doneDocs = [];
    } else { state.doneCount = 0; state.doneDocs = []; }
    await loadStd(std);
    E.markDuplicates(state.docs.filter(d => d.result).map(d => d.result));
    E.markDuplicates(state.doneDocs.filter(d => d.result).map(d => d.result));
    state.stdFilled = E.applyStdTable([...state.docs, ...state.doneDocs].filter(d => d.result).map(d => d.result), state.stdTable);
    state.lastScan = Date.now();
    render();
  } catch (e) {
    if (e && e.name === 'NotAllowedError') { toast('폴더 접근 권한이 없습니다. 다시 연결해 주세요.', 'err'); showWelcome(state.root.name); }
    else toast('폴더를 읽지 못했습니다: ' + explain(e), 'err');
  } finally { state.busy = false; busy(false); }
}
async function loadStd(en) {
  state.stdTable = []; state.stdFile = '';
  if (!en) return;
  try {
    const b = new Uint8Array(await (await en.handle.getFile()).arrayBuffer());
    const rows = /\.csv$/i.test(en.nm) ? E.parseCsv(E.decodeText(b)) : await E.readXlsxRows(b, inflateRaw);
    state.stdTable = E.parseStdTable(rows); state.stdFile = en.nm;
  } catch (e) { toast(`기준표(${en.nm})를 읽지 못했습니다. 엑셀에서 열려 있다면 닫고 [새로고침] 하세요. (${explain(e)})`, 'err'); }
}

/* ───── 상태 판정 ───── */
const isChecked = d => d.loc === 'root' && !!state.status.checked[d.key];
const docRows = d => d.result ? d.result.rows : [{ 파일명: d.nm, 확인필요: '읽기 실패: ' + d.error }];
function docWarn(d) { return d.error ? true : docRows(d).some(r => r.확인필요); }
function sortVal(d, key) {
  const r = docRows(d)[0] || {};
  const rno = () => { const n = shortNo(r.접수); return /^\d+$/.test(n) ? n.padStart(10, '0') : ''; };
  if (key === '접수') return rno() || (state.sort.dir > 0 ? '~' : '') + (r.접수 || d.nm);
  if (key === '접수일') return (r.접수일 || (state.sort.dir > 0 ? '9999' : '0000')) + '|' + rno();
  return String(r[key] == null ? '' : r[key]);
}
function visibleDocs() {
  const f = state.filter;
  const src = f.state === 'done' ? state.doneDocs : state.docs;
  const q = f.q.trim().toLowerCase();
  const list = src.filter(d => {
    if (f.state === 'checked' && !isChecked(d)) return false;
    if (f.state === 'unchecked' && isChecked(d)) return false;
    const rows = docRows(d);
    if (f.org && (rows[0].의뢰기관 || '') !== f.org) return false;
    if (f.warn && !docWarn(d)) return false;
    if (q && !d.nm.toLowerCase().includes(q) && !rows.some(r => E.COLUMNS.some(c => String(r[c] || '').toLowerCase().includes(q)))) return false;
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

/* ───── 그리기 ───── */
function activeCols() { return COLS.filter(c => state.cols.includes(c.k)); }
function render() {
  $('#toolbar').hidden = false; $('#bottombar').hidden = false;
  renderOrgOptions();
  $('#fState').options[3].textContent = `성적처리완료 폴더 (${state.doneCount})`;
  const cols = activeCols(), list = visibleDocs(), isDone = state.filter.state === 'done';
  const grid = $('#grid'), empty = $('#emptyBox');
  if (!list.length) {
    grid.hidden = true; empty.hidden = false;
    const none = (isDone ? state.doneDocs : state.docs).length === 0;
    empty.innerHTML = none
      ? (isDone ? '<h2>성적처리완료 폴더가 비어 있습니다</h2>' : `<h2>공문 폴더에 ODT 파일이 없습니다</h2><p>검사의뢰 공문(ODT)을 <b>${esc(state.root.name)}</b> 폴더에 저장한 뒤 <b>새로고침</b>을 누르세요. 이 창으로 돌아오면 자동으로 다시 읽습니다.</p>`)
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
      const rows = docRows(d), n = rows.length, chk = isChecked(d);
      const dup = d.result && d.result.duplicate;
      const cls = [chk && 'is-checked', isDone && 'is-done', dup && 'is-dup', d.error && 'is-err', state.selected === d.id && 'is-sel'].filter(Boolean).join(' ');
      rows.forEach((r, i) => {
        let tr = `<tr data-id="${esc(d.id)}" class="${cls}${i === 0 ? ' grp-first' : ''}">`;
        if (i === 0) tr += `<td class="c-chk" rowspan="${n}">${isDone ? `<button class="btn small" data-act="restore" title="공문 폴더로 되돌리기">되돌리기</button>` : `<input type="checkbox" data-act="check" ${chk ? 'checked' : ''} title="이 공문 완료 체크">`}</td>`;
        if (d.error) { tr += `<td class="c-warn err wrap" colspan="${cols.length + 1}">⚠ 읽기 실패 — <b>${esc(d.nm)}</b> : ${esc(d.error)}</td></tr>`; parts.push(tr); return; }
        for (const c of cols) {
          if (c.doc && i > 0) continue;
          let v = r[c.k] == null ? '' : r[c.k];
          const span = c.doc && n > 1 ? ` rowspan="${n}"` : '';
          let extra = c.wrap ? 'wrap' : '';
          let html = esc(c.fmt ? c.fmt(v) : v);
          if (c.k === '시료채취일' && v === '채취일자 확인 필요') extra += ' cell-warn';
          if (c.k === '시료채취일' && r.채취일출처 === '본문') html += '<span class="badge" title="공문 본문 문장에서 찾은 날짜">본문</span>';
          if (c.k === '기준' && /기준표/.test(r.기준출처 || '')) html += '<span class="badge ok" title="기준표에서 찾은 값 포함">기준표</span>';
          tr += `<td class="${extra}"${span} title="${esc(v)}">${html}</td>`;
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
function renderStats(list) {
  const docs = state.docs, live = docs.filter(d => !(d.result && d.result.duplicate));
  const samples = live.reduce((a, d) => a + (d.result ? d.result.rows.filter(r => r.시료번호).length : 0), 0);
  const warn = docs.filter(docWarn).length, err = docs.filter(d => d.error).length, dup = docs.length - live.length;
  const groups = checkedGroups();
  $('#btnDone').textContent = `완료 체크한 공문 처리 완료 (${groups.length})`;
  $('#btnDone').disabled = !groups.length || state.filter.state === 'done';
  const bits = [`공문 <b>${live.length}</b>건`, `시료 <b>${samples}</b>개`, `확인필요 <b>${warn}</b>`, `완료체크 <b>${groups.length}</b>`];
  if (dup) bits.push(`중복 ${dup}`); if (err) bits.push(`읽기실패 ${err}`);
  if (state.excluded.length) bits.push(`<span title="${esc(state.excluded.join('\n'))}">ODT 아님 ${state.excluded.length}</span>`);
  bits.push(state.stdFile ? `<span title="기준표에서 채운 항목 수">기준표 ${state.stdTable.length}행 · ${state.stdFilled}항목 적용</span>` : '기준표 없음');
  if (list.length !== (state.filter.state === 'done' ? state.doneDocs : docs).length) bits.push(`표시 ${list.length}건`);
  $('#stats').innerHTML = bits.join(' · ');
}
function highlightDates(p) {
  return esc(p).replace(/((?:\d{4}|&#39;\d{2}|'\d{2})\s*[.\-\/]\s*\d{1,2}\s*[.\-\/]\s*\d{1,2}\.?(?:\s*\([월화수목금토일]\))?)/g, '<mark>$1</mark>');
}
function extractedHtml(d) {
  const res = d.result;
  let h = '';
  if (d.error) h += `<ul class="warnlist"><li>읽기 실패: ${esc(d.error)}</li></ul>`;
  if (!res) return h;
  const warns = [...new Set(res.rows.map(r => r.확인필요).filter(Boolean).join(' / ').split(' / ').filter(Boolean))];
  if (warns.length) h += `<ul class="warnlist">${warns.map(w => `<li>${esc(w)}</li>`).join('')}</ul>`;
  const dd = res.doc;
  h += `<dl>
    <dt>파일</dt><dd>${esc(d.nm)}${d.loc === 'done' ? ' <span class="badge">처리완료</span>' : ''}</dd>
    <dt>의뢰기관</dt><dd>${esc(dd.의뢰기관)} / ${esc(dd.의뢰자)}</dd>
    <dt>발신명의</dt><dd>${esc(dd.발신명의)}</dd>
    <dt>시행</dt><dd>${esc(dd.시행)} (${esc(dd.시행일)})</dd>
    <dt>접수</dt><dd>${esc(dd.접수)} (${esc(dd.접수일)})</dd>
    <dt>시료채취자</dt><dd>${esc(dd.시료채취자)} ${dd.기안자직위 ? '(' + esc(dd.기안자직위) + ')' : ''}</dd>
    <dt>주소</dt><dd>${esc(dd.우편번호)} ${esc(dd.주소)}</dd>
    <dt>연락처</dt><dd>${esc(dd.전화번호)} ${esc(dd.이메일)}</dd>
  </dl>`;
  const rs = res.rows.filter(r => r.시료번호);
  h += `<h4>추출된 시료 (${rs.length})</h4><table class="mini"><tr><th>시료번호</th><th>검사항목</th><th>기준</th><th>지역</th><th>채취일</th></tr>`
    + rs.map(r => `<tr><td>${esc(r.시료번호)}</td><td>${esc(r.검사항목)}</td><td>${esc(r.기준)}</td><td>${esc(r.지역구분)}</td><td>${esc(r.시료채취일)}${r.채취일출처 === '본문' ? ' (본문)' : ''}</td></tr>`).join('') + '</table>';
  for (const t of res.tables || []) {
    h += `<h4>공문 시료 표 원문</h4><table class="mini">` + (t.raw || [t.headers]).map((row, i) => `<tr>${row.map(c => i === 0 ? `<th>${esc(c)}</th>` : `<td>${esc(c)}</td>`).join('')}</tr>`).join('') + '</table>';
  }
  if (dd.본문 && dd.본문.length) h += `<h4>본문</h4><div class="paras">${dd.본문.map(p => `<p>${highlightDates(p)}</p>`).join('')}</div>`;
  return h;
}
// v1.1: 상세 패널 — [추출 결과] [원본 보기] [나란히] 전환, 원본(ODT)을 서식 그대로 표시
function renderDetail() {
  const box = $('#detail');
  const d = [...state.docs, ...state.doneDocs].find(x => x.id === state.selected);
  if (!d) { box.hidden = true; box.className = 'detail'; box.dataset.id = ''; return; }
  const same = box.dataset.id === d.id;
  const keep = { a: (box.querySelector('.pane-ext') || {}).scrollTop || 0, b: (box.querySelector('.pane-org') || {}).scrollTop || 0 };
  const mode = state.detailMode;
  box.hidden = false; box.className = 'detail mode-' + mode;
  const r0 = docRows(d)[0] || {};
  const seg = [['ext', '추출 결과'], ['org', '원본 보기'], ['side', '나란히']].map(([k, l]) => `<button class="seg-btn${mode === k ? ' on' : ''}" data-act="mode-${k}">${l}</button>`).join('');
  let h = `<div class="detail-head"><h3 title="${esc(d.nm)}">${esc(r0.제목 || d.nm)}</h3><div class="seg">${seg}</div><button class="btn small" data-act="close">닫기</button></div>`;
  h += '<div class="detail-body">';
  if (mode !== 'org') h += `<div class="pane pane-ext">${extractedHtml(d)}</div>`;
  if (mode !== 'ext') h += `<div class="pane pane-org"><div class="pv-tools"><span class="muted">원본 공문 (${esc(d.nm)})</span><span class="spacer"></span><button class="btn small" data-act="pv-big">새 창으로 크게 보기</button><button class="btn small" data-act="pv-download" title="원본 ODT 파일을 내려받아 한글 등에서 엽니다">원본 파일 열기</button></div><div class="pv" id="pv"><div class="muted pv-msg">원본 불러오는 중…</div></div></div>`;
  h += '</div><div class="detail-foot">';
  if (d.loc === 'done') h += `<button class="btn" data-act="restore">공문 폴더로 되돌리기</button>`;
  else h += `<button class="btn ${isChecked(d) ? '' : 'primary'}" data-act="check-toggle">${isChecked(d) ? '완료 체크 해제' : '완료 체크'}</button>`;
  h += '</div>';
  box.innerHTML = h;
  box.dataset.id = d.id;
  if (same) { const a = box.querySelector('.pane-ext'), b = box.querySelector('.pane-org'); if (a) a.scrollTop = keep.a; if (b) b.scrollTop = keep.b; }
  if (mode !== 'ext') showPreview(d, same ? keep.b : 0);
}
async function getPreview(d) {
  if (state.previewCache.has(d.id)) return state.previewCache.get(d.id);
  const file = await d.handle.getFile();
  const r = await E.renderOdtHtml(new Uint8Array(await file.arrayBuffer()), inflateRaw);
  if (!document.getElementById('odt-css')) { const st = document.createElement('style'); st.id = 'odt-css'; st.textContent = r.css; document.head.appendChild(st); }
  if (state.previewCache.size > 30) state.previewCache.delete(state.previewCache.keys().next().value);
  state.previewCache.set(d.id, r);
  return r;
}
async function showPreview(d, scrollTop) {
  try {
    const r = await getPreview(d);
    const pv = $('#pv');
    if (!pv || state.selected !== d.id) return;
    pv.innerHTML = r.html; fitPreview();
    if (scrollTop) { const b = $('#detail .pane-org'); if (b) b.scrollTop = scrollTop; }
  } catch (e) {
    const pv = $('#pv'); if (pv) pv.innerHTML = `<div class="notice">원본을 표시할 수 없습니다: ${esc(explain(e))}</div>`;
  }
}
function fitPreview() {
  const pv = $('#pv'); if (!pv) return;
  const page = pv.querySelector('.odt-page'); if (!page) return;
  page.style.zoom = '';
  const avail = pv.clientWidth - 24, w = page.offsetWidth;
  if (w > avail && avail > 100) page.style.zoom = (avail / w).toFixed(3);
}
async function openPreviewWindow(d) {
  try {
    const r = await getPreview(d);
    const w = window.open('', '_blank');
    if (!w) { toast('팝업이 차단되었습니다. 주소창 오른쪽의 팝업 차단 아이콘에서 허용해 주세요.', 'err'); return; }
    w.document.write(`<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>${esc(d.nm)}</title><style>body{margin:0;background:#80868f;padding:24px}${r.css}.odt-page{box-shadow:0 2px 12px rgba(0,0,0,.35);padding:1cm 1.5cm}@media print{body{background:#fff;padding:0}.odt-page{box-shadow:none;padding:0}}</style></head><body>${r.html}</body></html>`);
    w.document.close();
  } catch (e) { toast('원본을 열지 못했습니다: ' + explain(e), 'err'); }
}
async function downloadOriginal(d) {
  try {
    const file = await d.handle.getFile();
    const url = URL.createObjectURL(new Blob([await file.arrayBuffer()], { type: 'application/vnd.oasis.opendocument.text' }));
    const a = document.createElement('a'); a.href = url; a.download = d.nm; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast('원본 파일을 내려받았습니다. 브라우저의 다운로드 목록에서 열면 한글(또는 기본 프로그램)로 열립니다.');
  } catch (e) { toast('원본 파일을 열지 못했습니다: ' + explain(e), 'err'); }
}

/* ───── 체크 ───── */
function setChecked(d, on) {
  if (!d || d.loc !== 'root') return;
  if (on) state.status.checked[d.key] = { at: nowIso(), file: d.nm };
  else delete state.status.checked[d.key];
  saveStatusSoon();
}
function findDoc(id) { return [...state.docs, ...state.doneDocs].find(x => x.id === id); }

/* ───── 파일 이동 ───── */
function explain(e) {
  const n = e && e.name;
  if (n === 'NoModificationAllowedError' || n === 'InvalidModificationError' || n === 'InvalidStateError') return '파일이 다른 프로그램(한글·엑셀 등)에서 열려 있어 처리할 수 없습니다. 파일을 닫고 다시 시도하세요.';
  if (n === 'NotFoundError') return '파일이 이미 옮겨졌거나 없습니다. [새로고침] 후 다시 확인하세요.';
  if (n === 'NotAllowedError' || n === 'SecurityError') return '폴더 쓰기 권한이 없습니다. 폴더를 다시 연결해 주세요.';
  if (n === 'QuotaExceededError') return '저장 공간이 부족합니다.';
  return (e && e.message) || String(e);
}
async function exists(dir, name) { try { await dir.getFileHandle(name); return true; } catch (e) { return false; } }
async function uniqueName(dir, name) {
  if (!(await exists(dir, name))) return name;
  const dot = name.lastIndexOf('.'), base = dot > 0 ? name.slice(0, dot) : name, ext = dot > 0 ? name.slice(dot) : '';
  for (let k = 2; k < 1000; k++) { const c = `${base} (${k})${ext}`; if (!(await exists(dir, c))) return c; }
  throw new Error('같은 이름의 파일이 너무 많습니다.');
}
// 복사 → 크기 확인 → 원본 삭제 (실패하면 복사본을 지우고 원본 유지)
async function moveFile(srcDir, name, dstDir) {
  const fh = await srcDir.getFileHandle(name); // 없으면 NotFoundError
  const target = await uniqueName(dstDir, name.normalize('NFC'));
  if (typeof fh.move === 'function') {
    try { await fh.move(dstDir, target); if (await exists(dstDir, target)) return target; } catch (e) { /* 아래 방식으로 다시 시도 */ }
    if (await exists(dstDir, target) && !(await exists(srcDir, name))) return target;
  }
  const file = await fh.getFile();
  const nh = await dstDir.getFileHandle(target, { create: true });
  try {
    const w = await nh.createWritable(); await w.write(file); await w.close();
    const copied = await nh.getFile();
    if (copied.size !== file.size) throw new Error('복사한 파일 크기가 원본과 다릅니다.');
  } catch (e) { await dstDir.removeEntry(target).catch(() => {}); throw e; }
  try { await srcDir.removeEntry(name); }
  catch (e) { await dstDir.removeEntry(target).catch(() => {}); throw e; }
  return target;
}
async function processChecked() {
  const groups = checkedGroups();
  if (!groups.length) return toast('완료 체크한 공문이 없습니다.');
  const files = groups.flatMap(g => g.docs);
  const ok = await modal('처리 완료', `<p>완료 체크한 공문 <b>${groups.length}건</b>(파일 ${files.length}개)을 <b>${DONE_DIR}</b> 폴더로 옮깁니다.</p><ul class="flist">${files.map(d => `<li>${esc(d.nm)}</li>`).join('')}</ul><p class="muted">옮긴 공문은 [성적처리완료 폴더] 보기에서 언제든 되돌릴 수 있습니다.</p>`, '옮기기');
  if (!ok) return;
  busy(true, '공문 옮기는 중…');
  const okList = [], failList = [];
  try {
    const doneDir = await getDoneDir(true);
    if (!doneDir) throw new Error(`${DONE_DIR} 폴더를 만들 수 없습니다.`);
    for (const g of groups) {
      const moved = []; let failed = false;
      for (const d of g.docs) {
        try { const to = await moveFile(state.root, d.name, doneDir); moved.push({ from: d.nm, to }); okList.push({ file: d.nm, to }); }
        catch (e) { failed = true; failList.push({ file: d.nm, msg: explain(e) }); }
      }
      if (moved.length) state.status.history.unshift({ at: nowIso(), action: '처리완료', key: g.key, files: moved });
      if (!failed) delete state.status.checked[g.key];
    }
    await writeStatus();
  } catch (e) { failList.push({ file: '(전체)', msg: explain(e) }); }
  busy(false);
  state.selected = null;
  await scan({ quiet: true });
  let html = `<p class="res-ok">옮긴 파일 <b>${okList.length}</b>개</p>`;
  if (okList.some(x => x.to !== x.file.normalize('NFC'))) html += `<p class="muted">같은 이름이 이미 있어 이름 뒤에 번호를 붙인 파일이 있습니다.</p>`;
  if (failList.length) html += `<h4 class="res-err">옮기지 못한 파일 ${failList.length}개</h4><ul class="flist">${failList.map(f => `<li><b>${esc(f.file)}</b><br>${esc(f.msg)}</li>`).join('')}</ul><p>실패한 공문은 완료 체크가 그대로 남아 있습니다. 원인을 해결한 뒤 다시 [처리 완료]를 누르세요.</p>`;
  await info('처리 완료 결과', html);
}
async function restore(d) {
  if (!d || d.loc !== 'done') return;
  const ok = await modal('되돌리기', `<p><b>${esc(d.nm)}</b><br>이 공문을 <b>${esc(state.root.name)}</b> 폴더로 되돌립니다. 완료 체크는 해제됩니다.</p>`, '되돌리기');
  if (!ok) return;
  busy(true, '되돌리는 중…');
  try {
    const doneDir = await getDoneDir(false);
    const to = await moveFile(doneDir, d.name, state.root);
    delete state.status.checked[d.key];
    state.status.history.unshift({ at: nowIso(), action: '되돌리기', key: d.key, files: [{ from: d.nm, to }] });
    await writeStatus();
    toast(`되돌렸습니다: ${to}`);
  } catch (e) { toast('되돌리지 못했습니다: ' + explain(e), 'err'); }
  busy(false); state.selected = null;
  await scan({ quiet: true });
}

/* ───── 엑셀 저장 ───── */
async function saveBytes(bytes, name) {
  const mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  if (window.showSaveFilePicker) {
    try {
      const h = await window.showSaveFilePicker({ id: 'odt-excel', suggestedName: name, types: [{ description: '엑셀 파일', accept: { [mime]: ['.xlsx'] } }] });
      const w = await h.createWritable(); await w.write(bytes); await w.close();
      toast(`저장했습니다: ${h.name}`); return true;
    } catch (e) {
      if (e.name === 'AbortError') return false;
      if (e.name === 'NoModificationAllowedError' || e.name === 'InvalidModificationError') { toast('같은 이름의 엑셀 파일이 열려 있어 저장할 수 없습니다. 엑셀을 닫거나 다른 이름으로 저장하세요.', 'err'); return false; }
    }
  }
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
  const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  toast(`다운로드 폴더에 저장했습니다: ${name}`); return true;
}
async function exportExcel() {
  const list = visibleDocs();
  if (!list.length) return toast('저장할 공문이 없습니다.');
  const header = ['상태', ...E.COLUMNS];
  const rows = [], meta = [];
  for (const d of list) {
    const st = d.loc === 'done' ? '처리완료' : isChecked(d) ? '완료체크' : '처리대기';
    for (const r of docRows(d)) { rows.push([st, ...E.COLUMNS.map(c => r[c] == null ? '' : r[c])]); meta.push({ dup: !!(d.result && d.result.duplicate), st }); }
  }
  const iWarn = header.indexOf('확인필요'), iDate = header.indexOf('시료채취일');
  const bytes = X.buildXlsx([{
    name: '공문추출', columns: header.map(h => ({ header: h, width: XLSX_W[h] || 12 })), rows,
    styleOf: (ri, k, v) => meta[ri].dup ? 3 : ((k === iWarn && v) || (k === iDate && v === '채취일자 확인 필요')) ? 2 : (k === 0 && meta[ri].st !== '처리대기') ? 4 : 0,
  }]);
  await saveBytes(bytes, `공문추출_${today()}.xlsx`);
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
    <h4>1. 공문 모으기</h4><p>검사의뢰 공문(ODT)을 공문 폴더에 저장합니다. 이 창으로 돌아오면 자동으로 다시 읽습니다.</p>
    <h4>2. 확인하기</h4><p>시료 1개당 1행으로, 최근 접수한 공문이 위에 보입니다. 노란 칸·확인필요 열은 직접 확인이 필요한 값입니다. 행을 누르면 오른쪽에 <b>추출 결과와 원본 공문이 나란히</b> 나옵니다. [추출 결과]·[원본 보기]·[나란히]로 바꿀 수 있고, [새 창으로 크게 보기]·[원본 파일 열기]도 있습니다.</p>
    <h4>3. 완료 체크 → 처리 완료</h4><p>성적 작성이 끝난 공문의 맨 앞 칸을 체크합니다(공문 단위). 체크는 공문 폴더의 <b>${STATUS_FILE}</b>에 저장되어 프로그램을 껐다 켜도 유지됩니다. <b>[처리 완료]</b>를 누르면 체크한 공문이 <b>${DONE_DIR}</b> 폴더로 옮겨집니다.</p>
    <h4>4. 되돌리기</h4><p>필터에서 <b>성적처리완료 폴더</b>를 고르면 옮긴 공문이 보이고, [되돌리기]로 다시 공문 폴더로 옮길 수 있습니다.</p>
    <h4>5. 엑셀 저장</h4><p>현재 화면에 보이는 공문(필터 적용)을 시료 1행 형식으로 저장합니다. 모든 칸은 텍스트로 저장되어 시료번호가 날짜로 바뀌지 않습니다.</p>
    <h4>6. 기준표</h4><p><b>[기준표 양식 만들기]</b>로 기준이 빈 항목 목록을 만들고, 기준값을 채워 <b>기준표.xlsx</b>로 공문 폴더에 두면 빈 기준이 자동으로 채워집니다.</p>
    <h4>표시 설명</h4><p><span class="badge">본문</span> 채취일을 공문 본문 문장에서 찾음 · <span class="badge ok">기준표</span> 기준표에서 채운 값 포함 · 회색 행: 접수번호가 같은 중복 공문</p>`);
}

/* ───── 이벤트 ───── */
function bindUi() {
  $('#btnPick').onclick = pickFolder;
  $('#btnRefresh').onclick = () => scan();
  $('#btnHelp').onclick = showHelp;
  $('#btnDone').onclick = processChecked;
  $('#btnExcel').onclick = exportExcel;
  $('#btnStd').onclick = makeStdTemplate;
  let qt;
  $('#fSearch').oninput = e => { clearTimeout(qt); qt = setTimeout(() => { state.filter.q = e.target.value; render(); }, 150); };
  $('#fOrg').onchange = e => { state.filter.org = e.target.value; render(); };
  $('#fState').onchange = async e => { state.filter.state = e.target.value; state.selected = null; if (e.target.value === 'done') await scan(); else render(); };
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
  document.addEventListener('click', () => { $('#colMenu').hidden = true; });

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
    const act = e.target.dataset.act;
    if (act === 'check') { setChecked(d, e.target.checked); render(); return; }
    if (act === 'restore') { restore(d); return; }
    if (e.target.closest('td.c-chk')) return;
    state.selected = state.selected === d.id ? null : d.id;
    render();
  });
  $('#detail').addEventListener('click', e => {
    const act = e.target.dataset.act; if (!act) return;
    const d = findDoc($('#detail').dataset.id);
    if (act === 'close') { state.selected = null; render(); }
    else if (act.startsWith('mode-')) { state.detailMode = act.slice(5); savePref('odt-detail-mode', state.detailMode); renderDetail(); }
    else if (act === 'pv-big' && d) openPreviewWindow(d);
    else if (act === 'pv-download' && d) downloadOriginal(d);
    else if (act === 'check-toggle' && d) { setChecked(d, !isChecked(d)); render(); }
    else if (act === 'restore' && d) restore(d);
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('#modal').hidden && state.selected) { state.selected = null; render(); } });
  // 창으로 돌아오면 폴더를 다시 읽음 (새로 저장한 공문 자동 반영)
  window.addEventListener('focus', () => { if (state.root && !state.busy && $('#modal').hidden && Date.now() - state.lastScan > 2000) scan({ quiet: true }); });
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(fitPreview, 150); });
  window.addEventListener('beforeunload', () => { if (saveTimer) writeStatus(); });
}

init();
})();
