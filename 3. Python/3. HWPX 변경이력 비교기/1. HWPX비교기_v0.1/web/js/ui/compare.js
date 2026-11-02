// [두 버전 비교] 탭 — A/B 고르기, 종류 거르기·검색, 변경 목록 / 나란히 보기
import { api } from '../api.js';
import { readyItems, state, versionNo } from '../store.js';
import { $, esc, fmtDate, KIND_CLASS, plain, segHTML, tagHTML, toast } from '../util.js';

const FILTERS = [
  ['all', '전체', () => true],
  ['modified', '수정', c => c.type === 'modified'],
  ['added', '추가', c => c.type === 'added'],
  ['deleted', '삭제', c => c.type === 'deleted'],
  ['format', '서식', c => c.type === 'format' || c.tags.includes('서식')],
  ['numeric', '숫자', c => c.tags.includes('숫자')],
  ['table', '표', c => c.tags.includes('표')],
];
let pendingFlash = null;
const metaVal = v => (/^\d{4}-\d\d-\d\dT/.test(v || '') ? fmtDate(v) : v || '-');

/** 고른 두 버전이 유효한지 확인하고, 아니면 기본값(처음 → 최신)으로 */
function ensurePair() {
  const ids = readyItems().map(i => i.id);
  const { a, b } = state.pair;
  if (!ids.includes(a) || !ids.includes(b) || a === b) {
    state.pair = { a: ids[0] || null, b: ids[ids.length - 1] || null };
  }
}

export async function loadCompare(flashCid = null) {
  ensurePair();
  const { a, b } = state.pair;
  if (flashCid != null) pendingFlash = flashCid;
  if (!a || !b || a === b) { state.compare = null; return renderCompare(); }
  try {
    state.compare = await api.compare(a, b);
  } catch (err) {
    state.compare = null;
    toast(err.message);
  }
  renderCompare();
}

export function renderCompare() {
  const box = $('#tab-compare');
  const ready = readyItems();
  if (ready.length < 2) {
    box.innerHTML = `<div class="card hero"><b>비교하려면 HWPX 파일이 2개 이상 필요합니다</b></div>`;
    return;
  }
  ensurePair();
  const opt = sel => ready.map(i => `<option value="${i.id}" ${i.id === sel ? 'selected' : ''}>v${versionNo(i.id)} · ${esc(i.name)}</option>`).join('');
  const r = state.compare;
  const v = state.view;
  const counts = r ? Object.fromEntries(FILTERS.map(([k, , f]) => [k, r.changes.filter(f).length])) : {};

  box.innerHTML = `
    <div class="card">
      <div class="toolbar">
        <label>이전(A) <select id="selA">${opt(state.pair.a)}</select></label>
        <button class="btn btn-sm" id="btnSwap" title="A·B 바꾸기">⇄</button>
        <label>새(B) <select id="selB">${opt(state.pair.b)}</select></label>
        <button class="btn btn-sm" id="btnFirstLast">처음 ↔ 최신</button>
        <button class="btn btn-sm" id="btnPrevLast">직전 ↔ 최신</button>
      </div>
      ${r ? `<div style="margin-top:10px"><b>${esc(r.headline)}</b>
        <span class="muted"> · ${r.elapsed ?? ''}초${r.identical_file ? ' · 두 파일이 완전히 같습니다' : ''}</span></div>
        ${r.meta_changes.length ? `<div class="muted">문서 정보 변경: ${r.meta_changes.map(m => `${esc(m.field)} <s>${esc(metaVal(m.a))}</s> → ${esc(metaVal(m.b))}`).join(' · ')}</div>` : ''}` : ''}
    </div>
    ${r ? `
    <div class="toolbar">
      <div class="chips">${FILTERS.map(([k, t]) => `<button class="chip ${v.type === k ? 'on' : ''}" data-type="${k}">${t}<span class="c">${counts[k]}</span></button>`).join('')}</div>
      <input type="search" id="inpSearch" placeholder="위치·내용 검색" value="${esc(v.q)}">
      <div class="seg"><button data-mode="list" class="${v.mode === 'list' ? 'on' : ''}">변경 목록</button><button data-mode="side" class="${v.mode === 'side' ? 'on' : ''}">나란히 보기</button></div>
      ${v.mode === 'side' ? `<label class="check"><input type="checkbox" id="chkOnly" ${v.onlyChanged ? 'checked' : ''}> 바뀐 곳만</label>` : ''}
    </div>
    <div id="cmpBody"></div>` : `<div class="card hero">결과 계산 중…</div>`}`;

  $('#selA').onchange = e => { state.pair.a = e.target.value; loadCompare(); };
  $('#selB').onchange = e => { state.pair.b = e.target.value; loadCompare(); };
  $('#btnSwap').onclick = () => { state.pair = { a: state.pair.b, b: state.pair.a }; loadCompare(); };
  $('#btnFirstLast').onclick = () => { state.pair = { a: ready[0].id, b: ready[ready.length - 1].id }; loadCompare(); };
  $('#btnPrevLast').onclick = () => { state.pair = { a: ready[ready.length - 2].id, b: ready[ready.length - 1].id }; loadCompare(); };
  if (!r) return;
  box.querySelectorAll('[data-type]').forEach(b => b.onclick = () => { v.type = b.dataset.type; renderCompare(); });
  box.querySelectorAll('[data-mode]').forEach(b => b.onclick = () => { v.mode = b.dataset.mode; renderCompare(); });
  $('#inpSearch').oninput = e => { v.q = e.target.value; renderBody(); };
  if ($('#chkOnly')) $('#chkOnly').onchange = e => { v.onlyChanged = e.target.checked; renderBody(); };
  renderBody();
}

function visibleChanges() {
  const r = state.compare;
  const f = FILTERS.find(x => x[0] === state.view.type)[2];
  const q = state.view.q.trim().toLowerCase();
  return r.changes.filter(c => f(c) && (!q || [c.location, c.context, c.old_text, c.new_text, c.summary]
    .some(s => (s || '').toLowerCase().includes(q))));
}

function renderBody() {
  const body = $('#cmpBody');
  if (!body) return;
  const list = visibleChanges();
  body.innerHTML = state.view.mode === 'side' ? sideHTML(new Set(list.map(c => c.id))) : listHTML(list);
  body.querySelectorAll('[data-goto]').forEach(b => b.onclick = () => {
    state.view.mode = 'side';
    state.view.onlyChanged = true;
    pendingFlash = Number(b.dataset.goto);
    renderCompare();
  });
  if (pendingFlash != null) {
    const el = body.querySelector(`[data-cid="${pendingFlash}"]`);
    pendingFlash = null;
    if (el) {
      el.scrollIntoView({ block: 'center', behavior: 'smooth' });
      el.classList.add('flash');
      setTimeout(() => el.classList.remove('flash'), 2400);
    }
  }
}

function listHTML(list) {
  if (!list.length) return `<div class="card hero">${state.compare.changes.length ? '조건에 맞는 변경이 없습니다' : '두 문서의 내용이 같습니다'}</div>`;
  return `<div class="changes">${list.map(c => {
    const notes = c.format.map(f => `‘${esc(f.text)}’ ${esc(f.details.join(', '))}`).concat(c.notes.map(esc));
    const page = c.page_b || c.page_a;
    return `<div class="change c-${c.type}" data-cid="${c.id}">
      <div class="change-head">
        <span class="num">#${c.id}</span><span class="kind ${KIND_CLASS[c.type]}">${esc(c.label)}</span>
        <span class="loc">${esc(c.location)}</span>
        ${c.context ? `<span class="ctx">· ${esc(c.context)}</span>` : ''}
        ${page ? `<span class="ctx">· 약 ${page}쪽</span>` : ''}${tagHTML(c.tags)}
        <button class="btn btn-sm go" data-goto="${c.id}">나란히 보기</button>
      </div>
      <div class="summary">${esc(c.summary)}</div>
      <div class="text ws">${segHTML(c.segments, 'both')}</div>
      ${notes.length ? `<ul class="fmt-notes">${notes.map(n => `<li>${n}</li>`).join('')}</ul>` : ''}
    </div>`;
  }).join('')}</div>`;
}

function sideHTML(show) {
  const r = state.compare;
  const byId = Object.fromEntries(r.changes.map(c => [c.id, c]));
  const rows = r.rows;
  const keep = rows.map((row, k) => !state.view.onlyChanged || near(rows, k, show));
  const out = [];
  let skipped = 0;
  rows.forEach((row, k) => {
    if (!keep[k]) { skipped++; return; }
    if (skipped) { out.push(`<tr class="gap"><td colspan="3">… 같은 내용 ${skipped}곳 생략 …</td></tr>`); skipped = 0; }
    const c = row.cid ? byId[row.cid] : null;
    const dim = c && !show.has(c.id) ? ' style="opacity:.45"' : '';
    let a, b;
    if (c && c.type === 'modified') { a = segHTML(c.segments, 'a'); b = segHTML(c.segments, 'b'); }
    else { a = plain(row.a); b = plain(row.b); }
    out.push(`<tr class="r-${row.status}" ${c ? `data-cid="${c.id}"` : ''}${dim}>
      <td class="loc">${esc(row.location)}${c ? `<br><span class="kind ${KIND_CLASS[c.type]}">${esc(c.label)}</span>` : ''}</td>
      <td class="txt a ws">${row.a == null ? '<span class="muted">(없음)</span>' : a}</td>
      <td class="txt b ws">${row.b == null ? '<span class="muted">(없음)</span>' : b}</td></tr>`);
  });
  if (skipped) out.push(`<tr class="gap"><td colspan="3">… 같은 내용 ${skipped}곳 생략 …</td></tr>`);
  const va = versionNo(state.pair.a), vb = versionNo(state.pair.b);
  return `<div class="tbl-wrap"><table class="grid side-by-side">
    <tr><th class="loc">위치</th><th>이전 (v${va})</th><th>새 (v${vb})</th></tr>${out.join('')}</table></div>`;
}

/** 바뀐 줄과 그 앞뒤 1줄은 보여 준다 */
function near(rows, k, show) {
  for (let d = -1; d <= 1; d++) {
    const r = rows[k + d];
    if (r && r.cid && show.has(r.cid)) return true;
  }
  return false;
}
