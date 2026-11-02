// (v1.1) [문서 보기] 탭 — 원본 문서 모양 그대로 그리고 바뀐 곳 표시
//   그리기(HTML 만들기)는 파이썬(hwpxdiff/render/)이 하고, 여기서는 보기 방식·확대·변경 사이 이동만 맡는다.
//   보기 방식: merged(한 화면에 추가·삭제 함께) | pair(이전 A | 새 B 나란히) | plain(새 버전 원본만, 표시 없음)
//   (v2.0) 고치기 모드: 한 문서를 그대로 그리고 문단·표 칸을 눌러 글자를 고친 뒤 [수정본으로 저장] → 새 HWPX
//          (원본 서식 이어받기, 고친 글자 색 표시 선택). 저장은 파이썬(hwpxdiff/merge/edit.py)이 한다.
import { api } from '../api.js';
import { emit, ensurePair, nameOf, readyItems, state, versionNo } from '../store.js';
import { $, dialog, esc, KIND_CLASS, toast } from '../util.js';

const VIEWS = [['merged', '한 화면에 표시'], ['pair', '나란히 (A | B)'], ['plain', '원본만 (B)']];
const ZOOMS = [['fit', '폭 맞춤'], ['0.5', '50%'], ['0.75', '75%'], ['1', '100%'], ['1.25', '125%']];
let loadingKey = '';
let syncing = false;
let pauseSync = 0;      // 변경으로 이동하는 동안 '함께 스크롤'을 잠시 멈춤 (설정값은 그대로)

const docKey = () => state.doc.editing ? `edit|${state.doc.editDoc}`
  : [state.pair.a, state.pair.b, state.doc.view, JSON.stringify(state.options)].join('|');
const COLORS = [['#FF0000', '빨강'], ['#0000FF', '파랑'], ['', '표시 안 함(원래 색)']];

/** (v2.0) 고치기 시작 */
export function startEdit(id) {
  const d = state.doc;
  if (d.editing && Object.keys(d.edits).length && d.editDoc !== id &&
      !confirm('저장하지 않은 고친 내용이 있습니다. 버리고 다른 문서를 고칠까요?')) return;
  d.editing = true; d.editDoc = id; d.edits = {}; d.data = null;
  loadDoc();
}

/** 서버에서 문서 HTML 받아 오기 (같은 조건이면 다시 받지 않음). cid 를 주면 그 변경으로 이동 */
export async function loadDoc(cid = null) {
  const d = state.doc;
  if (cid != null) d.goto = cid;
  ensurePair();
  if (readyItems().length < 1) return renderDoc();
  const key = docKey();
  if (d.data && d.key === key) return renderDoc();
  if (loadingKey === key) return;              // 이미 받는 중
  loadingKey = key;
  d.data = null;
  renderDoc();
  try {
    let data;
    if (d.editing) {
      data = await api.render(d.editDoc, null, 'merged');           // 고치기: 그 문서만 표시 없이
    } else {
      const one = readyItems().length < 2 || d.view === 'plain';
      data = await api.render(one ? (state.pair.b || readyItems()[0].id) : state.pair.a,
                              one ? null : state.pair.b, d.view === 'pair' ? 'pair' : 'merged');
    }
    if (key === docKey()) {                                         // 받는 사이 조건이 바뀌지 않았을 때만
      d.data = data;
      d.key = key;
      d.cur = null;
    }
  } catch (err) {
    toast(err.message);
  } finally {
    if (loadingKey === key) loadingKey = '';
  }
  renderDoc();
}

export function renderDoc() {
  const box = $('#tab-doc');
  const ready = readyItems();
  if (!ready.length) {
    box.innerHTML = `<div class="card hero"><b>볼 HWPX 파일을 넣어 주세요</b>
      한글 문서 모양(표·글꼴·정렬)을 그대로 그리고, 2개 이상이면 바뀐 곳을 문서 위에 표시합니다.</div>`;
    return;
  }
  ensurePair();
  const d = state.doc;
  if (d.editing) return renderEdit(box);
  const single = ready.length < 2;
  const opt = sel => ready.map(i => `<option value="${i.id}" ${i.id === sel ? 'selected' : ''}>v${versionNo(i.id)} · ${esc(i.name)}</option>`).join('');
  const changes = d.data?.changes || [];
  const pos = d.cur == null ? 0 : changes.findIndex(c => c.id === d.cur) + 1;

  box.innerHTML = `
    <div class="card dv-toolbar">
      <div class="toolbar">
        ${single ? '' : `<label>이전(A) <select id="dvA">${opt(state.pair.a)}</select></label>
        <button class="btn btn-sm" id="dvSwap" title="A·B 바꾸기">⇄</button>`}
        <label>${single ? '문서' : '새(B)'} <select id="dvB">${opt(state.pair.b || ready[0].id)}</select></label>
        ${single ? '' : `<div class="seg">${VIEWS.map(([k, t]) => `<button data-view="${k}" class="${d.view === k ? 'on' : ''}">${t}</button>`).join('')}</div>`}
        <select id="dvZoom" title="확대">${ZOOMS.map(([k, t]) => `<option value="${k}" ${d.zoom === k ? 'selected' : ''}>${t}</option>`).join('')}</select>
        ${d.view === 'pair' && !single ? `<label class="check"><input type="checkbox" id="dvSync" ${d.sync ? 'checked' : ''}> 함께 스크롤</label>` : ''}
        <span style="flex:1"></span>
        <button class="btn btn-sm" id="dvEdit" title="지금 보는 새(B) 문서를 직접 고칩니다">✎ 이 문서 고치기</button>
      </div>
      ${changes.length ? `<div class="toolbar dv-navbar">
        <button class="btn btn-sm" id="dvPrev">◀ 이전 변경</button>
        <span class="mono">${pos} / ${changes.length}</span>
        <button class="btn btn-sm" id="dvNext">다음 변경 ▶</button>
        <span class="muted">${esc(d.data.headline || '')}</span>
        <span class="dv-legend"><span class="dv-ins">새 글자</span> <span class="dv-gdel">지운 글자</span>
          <span class="lg-mod">바뀐 문단·칸</span> <span class="dv-fmtc">서식 바뀜</span></span>
      </div>` : ''}
    </div>
    <div class="dv-layout ${changes.length ? '' : 'no-nav'}">
      ${body(d, single)}
      ${changes.length ? `<aside class="dv-nav card"><b>바뀐 곳 ${changes.length}건</b><ol>${changes.map(c => `
        <li data-cid="${c.id}" class="${c.id === d.cur ? 'on' : ''}"><span class="kind ${KIND_CLASS[c.type]}">${esc(c.label)}</span>
          <span class="loc">${esc(c.location)}</span><span class="sum">${esc(c.summary)}</span></li>`).join('')}</ol></aside>` : ''}
    </div>`;

  bind(single, changes);
  if (!d.data) {
    if (!loadingKey) loadDoc();
    return;
  }
  requestAnimationFrame(() => {
    applyZoom();
    if (d.goto != null) { const g = d.goto; d.goto = null; goTo(g); }
  });
}

function body(d, single) {
  if (!d.data) return `<div class="dv-scroll"><div class="hero">문서를 그리는 중…</div></div>`;
  if (d.data.view === 'pair') {
    return `<div class="dv-pair">
      <div class="dv-pane"><div class="dv-cap">이전 (v${versionNo(state.pair.a)}) — <span class="dv-del">지운 글자</span></div><div class="dv-scroll" data-pane="a"><div class="dv-zoom">${d.data.html_a}</div></div></div>
      <div class="dv-pane"><div class="dv-cap">새 (v${versionNo(state.pair.b)}) — <span class="dv-ins">넣은 글자</span></div><div class="dv-scroll" data-pane="b"><div class="dv-zoom">${d.data.html_b}</div></div></div>
    </div>`;
  }
  return `<div class="dv-scroll"><div class="dv-zoom">${d.data.html}</div></div>`;
}

function bind(single, changes) {
  const d = state.doc;
  const reload = () => { d.data = null; loadDoc(); };
  if (!single) {
    $('#dvA').onchange = e => { state.pair.a = e.target.value; reload(); };
    $('#dvSwap').onclick = () => { state.pair = { a: state.pair.b, b: state.pair.a }; reload(); };
    document.querySelectorAll('#tab-doc [data-view]').forEach(b => b.onclick = () => { d.view = b.dataset.view; reload(); });
  }
  $('#dvB').onchange = e => { state.pair.b = e.target.value; reload(); };
  $('#dvEdit').onclick = () => startEdit(single ? (state.pair.b || readyItems()[0].id) : state.pair.b);
  $('#dvZoom').onchange = e => { d.zoom = e.target.value; applyZoom(); };
  if ($('#dvSync')) $('#dvSync').onchange = e => { d.sync = e.target.checked; };
  if (changes.length) {
    $('#dvPrev').onclick = () => step(-1);
    $('#dvNext').onclick = () => step(1);
    document.querySelectorAll('.dv-nav li').forEach(li => li.onclick = () => goTo(Number(li.dataset.cid)));
  }
  // 문서 위 표시를 누르면 목록에서도 선택
  document.querySelectorAll('#tab-doc .dv-sheet').forEach(sheet => sheet.addEventListener('click', e => {
    const el = e.target.closest('[data-cid]');
    if (el) goTo(Number(el.dataset.cid), false);
  }));
  // 나란히 보기: 한쪽을 스크롤하면 다른 쪽도 같은 비율로
  const panes = [...document.querySelectorAll('#tab-doc .dv-pair .dv-scroll')];
  panes.forEach((p, k) => p.addEventListener('scroll', () => {
    if (!d.sync || syncing || Date.now() < pauseSync) return;
    const o = panes[1 - k];
    syncing = true;
    o.scrollTop = (p.scrollTop / Math.max(1, p.scrollHeight - p.clientHeight)) * (o.scrollHeight - o.clientHeight);
    requestAnimationFrame(() => (syncing = false));
  }));
  window.onresize = () => state.tab === 'doc' && applyZoom();
}

function applyZoom() {
  document.querySelectorAll('#tab-doc .dv-scroll').forEach(sc => {
    const z = sc.querySelector('.dv-zoom');
    const sheet = sc.querySelector('.dv-sheet');
    if (!z || !sheet) return;
    let k = Number(state.doc.zoom);
    if (state.doc.zoom === 'fit') {
      z.style.zoom = 1;
      k = Math.min(1, (sc.clientWidth - 28) / sheet.offsetWidth);
    }
    z.style.zoom = k;
  });
}

function step(dir) {
  const list = state.doc.data?.changes || [];
  if (!list.length) return;
  const k = list.findIndex(c => c.id === state.doc.cur);
  const n = k < 0 ? (dir > 0 ? 0 : list.length - 1) : (k + dir + list.length) % list.length;
  goTo(list[n].id);
}

/** 변경 번호로 이동: 문서 안 표시로 스크롤 + 깜빡임, 목록·번호 갱신 */
function goTo(cid, scroll = true) {
  const d = state.doc;
  d.cur = cid;
  const list = d.data?.changes || [];
  const pos = list.findIndex(c => c.id === cid) + 1;
  const counter = document.querySelector('#tab-doc .dv-navbar .mono');
  if (counter) counter.textContent = `${pos} / ${list.length}`;
  document.querySelectorAll('.dv-nav li').forEach(li => li.classList.toggle('on', Number(li.dataset.cid) === cid));
  const li = document.querySelector(`.dv-nav li[data-cid="${cid}"]`);
  if (li) li.scrollIntoView({ block: 'nearest' });
  pauseSync = Date.now() + 900;                     // 각 쪽을 따로 정확히 맞춤
  document.querySelectorAll(`#tab-doc .dv-sheet [data-cid="${cid}"]`).forEach(el => {
    if (scroll) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    el.classList.remove('dv-focus');
    void el.offsetWidth;                            // 애니메이션 다시 시작
    el.classList.add('dv-focus');
  });
}

// ════════════════════════════════════════════════════════════════
// (v2.0) 고치기 모드
// ════════════════════════════════════════════════════════════════
function renderEdit(box) {
  const d = state.doc;
  const ready = readyItems();
  if (!ready.find(i => i.id === d.editDoc)) { d.editing = false; return renderDoc(); }
  const edits = Object.entries(d.edits);
  box.innerHTML = `
    <div class="card dv-toolbar">
      <div class="toolbar">
        <b>✎ 고치기</b>
        <label>문서 <select id="edDoc">${ready.map(i => `<option value="${i.id}" ${i.id === d.editDoc ? 'selected' : ''}>${esc(i.name)}</option>`).join('')}</select></label>
        <label>고친 글자 색 <select id="edColor">${COLORS.map(([v, t]) => `<option value="${v}" ${d.markColor === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
        <select id="dvZoom" title="확대">${ZOOMS.map(([k, t]) => `<option value="${k}" ${d.zoom === k ? 'selected' : ''}>${t}</option>`).join('')}</select>
        <span style="flex:1"></span>
        <input class="mg-name" id="edName" placeholder="저장 이름 (비우면 자동)">
        <button class="btn btn-sm btn-primary" id="edSave" ${edits.length ? '' : 'disabled'}>수정본으로 저장 (${edits.length})</button>
        <button class="btn btn-sm btn-ghost" id="edCancel">고치기 끝내기</button>
      </div>
      <div class="hint">문단이나 표 칸을 누르면 글자를 고칠 수 있습니다. 새 글자는 앞 글자의 글꼴·크기·굵기를 그대로 이어받고, 원본 파일은 바뀌지 않습니다 — 저장하면 새 문서가 생깁니다 — 최종본을 고치면 새 최종본이 되고 이전 최종본은 보관으로${state.project ? ' (프로젝트 3_최종본 ↔ 4_보관 교체)' : ''}, 그 밖에는 수정본${state.project ? '(2_수정본 폴더)' : ''}.
        표·글상자를 품은 문단은 한글에서 고쳐 주세요.</div>
    </div>
    <div class="dv-layout dv-edit-on">
      <div class="dv-scroll" id="edScroll"><div class="dv-zoom">${d.data ? d.data.html : '<div class="hero">문서를 그리는 중…</div>'}</div></div>
      <aside class="dv-nav card"><b>고친 곳 ${edits.length}</b>
        ${edits.length ? `<ol class="edit-list" style="list-style:none;padding:0">${edits.map(([bi, t]) => `
          <li><span><span class="o">${esc(d.origText?.[bi] ?? '')}</span><br>${esc(t)}</span><button class="icon-btn" data-undo="${bi}" title="되돌리기">↺</button></li>`).join('')}</ol>`
          : '<div class="hint" style="margin-top:6px">아직 없습니다</div>'}</aside>
    </div>`;
  $('#edDoc').onchange = e => startEdit(e.target.value);
  $('#edColor').onchange = e => { d.markColor = e.target.value; };
  $('#dvZoom').onchange = e => { d.zoom = e.target.value; applyZoom(); };
  $('#edCancel').onclick = () => {
    if (edits.length && !confirm('저장하지 않은 고친 내용을 버릴까요?')) return;
    d.editing = false; d.edits = {}; d.data = null; loadDoc();
  };
  $('#edSave').onclick = saveEdits;
  box.querySelectorAll('[data-undo]').forEach(b => b.onclick = () => { delete d.edits[b.dataset.undo]; renderDoc(); });
  const sc = $('#edScroll');
  sc.addEventListener('click', e => {
    const el = e.target.closest('.dv-sheet [data-bi]');
    if (el) editBlock(Number(el.dataset.bi));
  });
  if (!d.data) { if (!loadingKey) loadDoc(); return; }
  requestAnimationFrame(() => {
    applyZoom();
    Object.entries(d.edits).forEach(([bi, t]) => paintEdit(bi, t));
  });
}

function paintEdit(bi, text) {
  const el = document.querySelector(`#edScroll .dv-sheet [data-bi="${bi}"]`);
  if (!el) return;
  const target = el.tagName === 'TD' ? el.querySelector('.dv-p') || el : el;
  target.textContent = text;
  el.classList.add('dv-edited');
}

async function editBlock(bi) {
  const d = state.doc;
  let info;
  try { info = await api.editCheck(d.editDoc, bi); } catch (err) { return toast(err.message); }
  if (!info.ok) return toast(`${info.location}: ${info.reason}`, 5000);
  d.origText = d.origText || {};
  d.origText[bi] = info.text;
  const cur = d.edits[bi] ?? info.text;
  const v = await dialog({
    title: `고치기 — ${info.location}`,
    body: `<textarea id="edText">${esc(cur)}</textarea>
      <div class="hint">${info.location.startsWith('표') ? '줄바꿈(Enter) = 칸 안에서 문단 나누기' : '줄바꿈(Enter) = 줄 바꿈(Shift+Enter 와 같음)'} · 새 글자 색: ${esc(COLORS.find(c => c[0] === d.markColor)?.[1] || '')}</div>`,
    buttons: [{ label: '적용', primary: true, value: box => box.querySelector('#edText').value }],
    onOpen: box => { const t = box.querySelector('#edText'); t.focus(); t.setSelectionRange(t.value.length, t.value.length); },
  });
  if (v == null) return;
  if (v === info.text) delete d.edits[bi]; else d.edits[bi] = v;
  const keep = $('#edScroll')?.scrollTop;
  renderDoc();
  if ($('#edScroll')) $('#edScroll').scrollTop = keep;
}

async function saveEdits() {
  const d = state.doc;
  try {
    toast('수정본을 만드는 중…');
    const r = await api.editSave(d.editDoc, d.edits, d.markColor || null, $('#edName').value);
    const failed = r.report.check_failed;
    toast(`저장했습니다: ${r.name}${r.path ? ' → ' + r.path : ''}${failed.length ? ' (확인 필요: ' + failed.join(', ') + ')' : ''}`, 6000);
    const from = d.editDoc;
    d.editing = false; d.edits = {}; d.data = null;
    emit('poke'); emit('relations');
    emit('saved-doc', { id: r.id, base: from });
  } catch (err) { toast(err.message, 6000); }
}
