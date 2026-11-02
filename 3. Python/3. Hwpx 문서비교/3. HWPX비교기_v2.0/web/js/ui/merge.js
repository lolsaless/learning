// (v2.0) [병합] 탭 — 원본(기준)에 여러 버전의 변경을 골라 넣어 최종본 만들기.
//   · 왼쪽: 원본 문서 모양 위에 병합 항목 표시 (빨강 = 충돌, 노랑 = 한 버전만 고침, 초록 상자 = 끼워 넣을 글)
//   · 표시 위에 마우스를 올리면 그 자리에서 각 버전이 무엇을 바꿨는지 말풍선 → 바로 고르기
//   · 오른쪽: 항목 목록 (같은 고르기). [결과 미리보기] → 합친 결과를 문서 모양으로. [최종본으로 저장] → 새 HWPX
import { api } from '../api.js';
import { emit, readyItems, state } from '../store.js';
import { $, esc, segHTML, toast } from '../util.js';

let hideTimer;
let loading = '';

function defaults() {
  const m = state.merge;
  const ids = readyItems().map(i => i.id);
  const lin = state.lineage;
  if (!ids.includes(m.base)) m.base = (lin && ids.includes(lin.original)) ? lin.original : ids[0];
  if (!m.versions || m.versions.some(v => !ids.includes(v))) {
    const arch = new Set((lin?.nodes || []).filter(n => n.role === 'archived').map(n => n.id));
    const leaves = (lin?.leaves || []).filter(v => v !== m.base && !arch.has(v));
    m.versions = leaves.length ? leaves : ids.filter(v => v !== m.base && !arch.has(v));
  }
  m.versions = m.versions.filter(v => v !== m.base);
}

export async function loadMerge(force = false) {
  const m = state.merge;
  if (readyItems().length < 2) { m.plan = null; return renderMerge(); }
  defaults();
  const key = [m.base, ...m.versions, JSON.stringify(state.options)].join('|');
  if (!force && m.plan && m.key === key) return renderMerge();
  if (!m.versions.length) { m.plan = null; return renderMerge(); }
  if (loading === key) return;
  loading = key;
  m.plan = null; m.preview = null; m.mode = 'plan';
  renderMerge();
  try {
    const plan = await api.mergePlan(m.base, m.versions);
    if (loading !== key) return;
    m.plan = plan; m.key = key; m.choices = {};
  } catch (err) { toast(err.message, 5000); }
  loading = '';
  renderMerge();
}

const choiceOf = it => state.merge.choices[it.key] ?? it.default;

export function renderMerge() {
  const box = $('#tab-merge');
  const ready = readyItems();
  if (ready.length < 2) {
    box.innerHTML = `<div class="card hero"><b>병합하려면 HWPX 파일이 2개 이상 필요합니다</b>원본 하나와 수정본들을 넣으세요.</div>`;
    return;
  }
  defaults();
  const m = state.merge, p = m.plan;
  const items = p?.items || [];
  const unresolved = items.filter(it => it.conflict && choiceOf(it) === 'base').length;
  const chosen = items.filter(it => choiceOf(it) !== 'base').length;
  box.innerHTML = `
    <div class="card dv-toolbar">
      <div class="toolbar">
        <label>기준(원본) <select id="mgBase">${ready.map(i => `<option value="${i.id}" ${i.id === m.base ? 'selected' : ''}>${esc(i.name)}</option>`).join('')}</select></label>
        <span class="hint">에 합칠 버전:</span>
        <div class="ver-checks">${ready.filter(i => i.id !== m.base).map(i => `<label class="${m.versions.includes(i.id) ? 'on' : ''}"><input type="checkbox" data-ver="${i.id}" ${m.versions.includes(i.id) ? 'checked' : ''}> ${esc(i.name)}</label>`).join('')}</div>
      </div>
      ${p ? `<div class="toolbar dv-navbar">
        <div class="mg-stats">
          <span class="kind k-modified">항목 ${p.counts.items}</span>
          ${p.counts.conflicts ? `<span class="kind k-deleted">충돌 ${p.counts.conflicts}${unresolved ? ` (미결정 ${unresolved})` : ''}</span>` : '<span class="kind k-added">충돌 없음</span>'}
          ${p.counts.same ? `<span class="kind k-format">같은 변경 ${p.counts.same}</span>` : ''}
          ${p.counts.unsupported ? `<span class="kind k-flip" title="한글에서 직접 해야 하는 변경">자동 불가 ${p.counts.unsupported}</span>` : ''}
          <span class="muted">적용 ${chosen} / ${items.length}</span>
        </div>
        <button class="btn btn-sm" id="mgAll">모두 적용</button>
        <button class="btn btn-sm" id="mgNone">모두 원본 유지</button>
        <div class="seg"><button data-mmode="plan" class="${m.mode === 'plan' ? 'on' : ''}">고르기</button><button data-mmode="preview" class="${m.mode === 'preview' ? 'on' : ''}">결과 미리보기</button></div>
        <span style="flex:1"></span>
        <input class="mg-name" id="mgName" placeholder="저장 이름 (비우면 자동)">
        <button class="btn btn-sm btn-primary" id="mgSaveFinal" ${chosen ? '' : 'disabled'}>최종본으로 저장</button>
        <button class="btn btn-sm" id="mgSaveRev" ${chosen ? '' : 'disabled'}>수정본으로 저장</button>
      </div>
      <div class="hint">문서의 표시 위에 마우스를 올리면 버전별 변경이 나타나고 바로 고를 수 있습니다. 충돌(빨강)은 직접 골라야 적용됩니다.
        ${state.project ? '저장하면 프로젝트 3_최종본(또는 2_수정본) 폴더에 들어가고, 이전 최종본은 4_보관 으로 옮겨집니다.' : '프로젝트가 없으면 목록에만 추가됩니다 — [내려받기] 또는 위쪽 [새 프로젝트로 저장].'}</div>` : ''}
    </div>
    ${!m.versions.length ? `<div class="card hero">합칠 버전을 하나 이상 고르세요</div>` : !p ? `<div class="card hero">병합 계획을 계산하는 중…</div>` : `
    <div class="mg-layout">
      <div class="dv-scroll" id="mgDoc"><div class="dv-zoom">${m.mode === 'preview' ? (m.preview ? m.preview.html : '<div class="hero">결과를 만드는 중…</div>') : p.html}</div></div>
      <aside class="card mg-list" id="mgList">${m.mode === 'preview' ? previewSide() : items.length ? items.map(itemHTML).join('') : '<div class="hero">원본과 다른 곳이 없습니다</div>'}</aside>
    </div>`}`;
  bind();
  if (p) requestAnimationFrame(() => { fitZoom(); paintChoices(); });
}

function itemHTML(it, k) {
  const ch = choiceOf(it);
  const cls = [it.conflict ? 'conflict' : '', it.same ? 'same' : '', it.conflict && ch === 'base' ? 'unresolved' : ''].join(' ');
  const badge = it.conflict ? '<span class="kind k-deleted">충돌</span>' : it.same ? '<span class="kind k-format">같은 변경</span>' : '';
  return `<div class="mg-item ${cls}" data-item="${k + 1}">
    <div class="hd" data-goto="${k + 1}"><span class="num mono">#${k + 1}</span>${badge}<span class="loc">${esc(it.location)}</span>
      ${it.context ? `<span class="hint">${esc(it.context)}</span>` : ''}</div>
    ${optionsHTML(it)}</div>`;
}

function optionsHTML(it) {
  const ch = choiceOf(it);
  const name = 'c_' + it.key.replace(/[^a-zA-Z0-9]/g, '_');
  return `<label class="mg-opt"><input type="radio" name="${name}" data-key="${esc(it.key)}" value="base" ${ch === 'base' ? 'checked' : ''}>
      <span><span class="vn">원본 유지</span>${it.base_text ? ` <span class="hint">${esc(it.base_text.slice(0, 60))}</span>` : ''}</span></label>` +
    it.options.map(o => `<label class="mg-opt ${o.unsupported ? 'dis' : ''}" title="${esc(o.unsupported)}">
      <input type="radio" name="${name}" data-key="${esc(it.key)}" value="${esc(o.op_id)}" ${ch === o.op_id ? 'checked' : ''} ${o.unsupported ? 'disabled' : ''}>
      <span><span class="vn">${esc(o.vname)}</span> <span class="kind ${o.type === 'added' ? 'k-added' : o.type === 'deleted' ? 'k-deleted' : o.type === 'format' ? 'k-format' : 'k-modified'}">${esc(o.label)}</span>
      ${o.unsupported ? `<span class="why">${esc(o.unsupported)}</span>` : `<span class="seg ws">${o.type === 'added' && o.mode === 'insert' ? `<ins class="i">${esc(o.new_text)}</ins>` : segHTML(o.segments, 'both')}</span>`}</span></label>`).join('');
}

function previewSide() {
  const pv = state.merge.preview;
  if (!pv) return '<div class="hero">결과를 만드는 중…</div>';
  const r = pv.report;
  return `<b>${esc(pv.headline)}</b> <span class="hint">(원본 대비)</span>
    <div class="hint">적용 ${r.applied.length}건 · 건너뜀 ${r.skipped.length}건 · 모양 정의 ${r.header_added}개 추가</div>
    ${r.skipped.map(s => `<div class="notice">${esc(s.location)}: ${esc(s.reason)}</div>`).join('')}
    <ol class="edit-list" style="padding-left:18px">${r.applied.map(a => `<li><span><b>${esc(a.version)}</b> ${esc(a.location)} — ${esc(a.summary)}</span></li>`).join('')}</ol>`;
}

function setChoice(key, value) {
  state.merge.choices[key] = value;
  state.merge.preview = null;
  const scroll = $('#mgList')?.scrollTop;
  const docScroll = $('#mgDoc')?.scrollTop;
  renderMerge();
  if ($('#mgList')) $('#mgList').scrollTop = scroll;
  if ($('#mgDoc')) $('#mgDoc').scrollTop = docScroll;
}

function paintChoices() {
  const items = state.merge.plan?.items || [];
  if (state.merge.mode !== 'plan') return;
  document.querySelectorAll('#mgDoc [data-cid]').forEach(el => {
    const it = items[Number(el.dataset.cid) - 1];
    if (!it) return;
    const on = choiceOf(it) !== 'base';
    el.classList.toggle('mg-on', on);
    el.classList.toggle('mg-off', !on && !it.conflict);
  });
}

function fitZoom() {
  const sc = $('#mgDoc'); const sheet = sc?.querySelector('.dv-sheet'); const z = sc?.querySelector('.dv-zoom');
  if (!sheet || !z) return;
  z.style.zoom = 1;
  z.style.zoom = Math.min(1, (sc.clientWidth - 28) / sheet.offsetWidth);
}

function goto(n) {
  document.querySelectorAll('#mgDoc [data-cid="' + n + '"]').forEach(el => {
    el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    el.classList.remove('dv-focus'); void el.offsetWidth; el.classList.add('dv-focus');
  });
  document.querySelectorAll('.mg-item').forEach(x => x.classList.toggle('on', x.dataset.item === String(n)));
  const li = document.querySelector(`.mg-item[data-item="${n}"]`);
  if (li) li.scrollIntoView({ block: 'nearest' });
}

async function save(role) {
  const m = state.merge;
  const items = m.plan.items;
  const unresolved = items.filter(it => it.conflict && choiceOf(it) === 'base').length;
  if (unresolved && !confirm(`충돌 ${unresolved}곳을 고르지 않았습니다 (원본 유지로 저장). 계속할까요?`)) return;
  try {
    toast('병합 파일을 만드는 중…');
    const r = await api.mergeSave(m.base, m.versions, m.choices, $('#mgName').value, role);
    toast(`저장했습니다: ${r.name}${r.path ? ' → ' + r.path : ''}`, 6000);
    m.plan = null; m.key = '';
    emit('poke'); emit('relations');
    emit('saved-doc', { id: r.id, base: m.base });
  } catch (err) { toast(err.message, 6000); }
}

function bind() {
  const m = state.merge;
  if ($('#mgBase')) $('#mgBase').onchange = e => { m.base = e.target.value; m.versions = null; loadMerge(); };
  document.querySelectorAll('#tab-merge [data-ver]').forEach(c => c.onchange = () => {
    m.versions = [...document.querySelectorAll('#tab-merge [data-ver]:checked')].map(x => x.dataset.ver);
    loadMerge();
  });
  if (!m.plan) return;
  $('#mgAll').onclick = () => {
    m.plan.items.forEach(it => { const o = it.options.find(x => !x.unsupported); if (o) m.choices[it.key] = o.op_id; });
    m.preview = null; renderMerge();
  };
  $('#mgNone').onclick = () => { m.plan.items.forEach(it => { m.choices[it.key] = 'base'; }); m.preview = null; renderMerge(); };
  document.querySelectorAll('[data-mmode]').forEach(b => b.onclick = async () => {
    m.mode = b.dataset.mmode;
    renderMerge();
    if (m.mode === 'preview' && !m.preview) {
      try { m.preview = await api.mergePreview(m.base, m.versions, m.choices); } catch (err) { toast(err.message, 6000); m.mode = 'plan'; }
      renderMerge();
    }
  });
  $('#mgSaveFinal').onclick = () => save('final');
  $('#mgSaveRev').onclick = () => save('revision');
  document.querySelectorAll('#mgList input[type=radio]').forEach(r => r.onchange = () => setChoice(r.dataset.key, r.value));
  document.querySelectorAll('#mgList [data-goto]').forEach(h => h.onclick = () => goto(h.dataset.goto));
  // 말풍선: 문서 표시 위에 마우스
  const doc = $('#mgDoc');
  if (m.mode === 'plan' && doc) {
    doc.addEventListener('mouseover', e => {
      const el = e.target.closest('[data-cid]');
      if (el) showPop(el);
    });
    doc.addEventListener('mouseout', e => { if (e.target.closest('[data-cid]')) hideSoon(); });
    doc.addEventListener('click', e => { const el = e.target.closest('[data-cid]'); if (el) goto(el.dataset.cid); });
  }
}

function showPop(el) {
  clearTimeout(hideTimer);
  const n = Number(el.dataset.cid);
  const it = state.merge.plan.items[n - 1];
  if (!it) return;
  const pop = $('#popover');
  pop.innerHTML = `<h4>#${n} ${esc(it.location)} ${it.conflict ? '<span class="kind k-deleted">충돌</span>' : ''}</h4>
    ${it.base_text ? `<div class="base">원본: ${esc(it.base_text.slice(0, 160))}</div>` : ''}
    <div>${optionsHTML(it)}</div>`;
  pop.hidden = false;
  const r = el.getBoundingClientRect();
  const left = Math.min(window.innerWidth - 400, Math.max(8, r.right + 12));
  const top = Math.min(window.innerHeight - pop.offsetHeight - 8, Math.max(8, r.top - 10));
  pop.style.left = left + 'px';
  pop.style.top = top + 'px';
  pop.onmouseenter = () => clearTimeout(hideTimer);
  pop.onmouseleave = hideSoon;
  pop.querySelectorAll('input[type=radio]').forEach(x => x.onchange = () => {
    pop.hidden = true;
    setChoice(x.dataset.key, x.value);
    toast(x.value === 'base' ? '원본 유지' : '적용으로 골랐습니다');
  });
}

function hideSoon() {
  clearTimeout(hideTimer);
  hideTimer = setTimeout(() => { $('#popover').hidden = true; }, 350);
}
