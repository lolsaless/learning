/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/03_공통_시작_연결.js] 공통 도구·시작·폴더 연결
   하는 일 : 압축 해제, 폴더 기억(IndexedDB), 알림·확인 창, 시작 화면, 폴더 선택·다시 연결
   주요 이름: inflateRaw, toast, modal, info, init, showWelcome, pickFolder, connect
   이럴 때 고침: 첫 화면 안내 글, 확인 창 동작
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
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
