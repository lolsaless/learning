// (v2.0) [관계도] 탭 — 문서 사이 관계를 나무 그림으로. 노드(문서)는 마우스로 끌어 옮기고(위치는 프로젝트에 저장),
//   빈 곳을 끌면 화면 이동, 휠로 확대·축소. 노드를 누르면 오른쪽에서 원본/최종본 지정·부모 바꾸기·문서 보기·병합.
//   선(화살표)을 누르면 그 두 문서 비교, 노드를 두 번 누르면 문서 보기.
import { api } from '../api.js';
import { emit, nameOf, readyItems, ROLE_LABEL, state } from '../store.js';
import { $, esc, fmtDate, ROLE_CLASS, toast } from '../util.js';

const W = 220, H = 78, GX = 300, GY = 112;
const ROLE_COLOR = { original: 'var(--orig)', final: 'var(--final)', revision: 'var(--rev)', archived: 'var(--arch)' };
let pos = {};             // id → [x, y] (화면 좌표가 아닌 그림 좌표)
let saveTimer;

export async function loadGraph() {
  if (readyItems().length < 1) { state.lineage = null; return renderGraph(); }
  try { state.lineage = await api.lineage(); } catch (err) { toast(err.message); }
  renderGraph();
}

function autoLayout(lin, force = false) {
  const byDepth = {};
  lin.nodes.forEach(n => (byDepth[n.depth] ||= []).push(n));
  Object.entries(byDepth).forEach(([d, ns]) => {
    ns.sort((a, b) => (a.modified || '').localeCompare(b.modified || ''));
    ns.forEach((n, k) => {
      if (force || !pos[n.id]) pos[n.id] = [Number(d) * GX, (k - (ns.length - 1) / 2) * GY + 200];
    });
  });
}

export function renderGraph() {
  const box = $('#tab-graph');
  const lin = state.lineage;
  if (!lin || !lin.nodes.length) {
    box.innerHTML = `<div class="card hero"><b>문서를 넣으면 관계도가 그려집니다</b>
      원본에서 어떤 수정본이 나왔는지, 어떤 문서끼리 병합됐는지를 나무 모양으로 보여 줍니다.</div>`;
    return;
  }
  pos = { ...(lin.positions || {}), ...pos };
  Object.keys(pos).forEach(k => { if (!lin.nodes.find(n => n.id === k)) delete pos[k]; });
  autoLayout(lin);
  const orig = lin.nodes.find(n => n.id === lin.original);
  const fin = lin.nodes.find(n => n.id === lin.final);
  const latest = lin.nodes.find(n => n.id === lin.latest);
  box.innerHTML = `
    <div class="card">
      <div class="card-head"><h3>문서 관계도</h3>
        <div class="row gap"><button class="btn btn-sm" id="grAuto">자동 정렬</button><button class="btn btn-sm" id="grFit">화면 맞춤</button></div></div>
      <div class="stats" style="margin-bottom:8px">
        <div class="stat"><div class="l">원본 (${esc(lin.original_by)})</div><div style="font-weight:700">${orig ? esc(orig.name) : '-'}</div></div>
        <div class="stat"><div class="l">최종본 (${esc(lin.final_by)})</div><div style="font-weight:700">${fin ? esc(fin.name) : '<span class="hint">아직 없음 — 병합하거나 직접 지정</span>'}</div></div>
        <div class="stat"><div class="l">가장 늦게 저장</div><div style="font-weight:700">${latest ? esc(latest.name) : '-'}</div></div>
      </div>
      ${lin.notes.map(n => `<div class="notice" style="margin-top:6px">${esc(n)}</div>`).join('')}
      <div class="legend-row" style="margin-top:8px">
        <span class="role r-orig">원본</span><span class="role r-rev">수정본</span><span class="role r-final">최종본</span><span class="role r-arch">보관</span>
        <span><i class="ln"></i> 고쳐서 나옴(추정·지정)</span><span><i class="ln m"></i> 병합으로 만듦</span><span><i class="ln e"></i> 직접 고침</span>
        <span>· 선의 숫자 = 바뀐 곳 수</span></div>
    </div>
    <div class="gr-layout">
      <div class="gr-wrap" id="grWrap">
        <svg id="grSvg"><defs>
          <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--rev)"/></marker>
          <marker id="arrM" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--mergec)"/></marker>
        </defs><g id="grView"><g id="grEdges"></g><g id="grNodes"></g></g></svg>
        <div class="gr-zoom"><button id="grIn" title="확대">＋</button><button id="grOut" title="축소">－</button></div>
        <div class="gr-help">노드 끌기 = 옮기기 · 빈 곳 끌기 = 화면 이동 · 휠 = 확대/축소 · 선 누르기 = 두 문서 비교 · 노드 두 번 누르기 = 문서 보기</div>
      </div>
      <aside class="card gr-panel" id="grPanel"></aside>
    </div>`;
  drawEdges(); drawNodes(); applyView(); renderPanel();
  bindGraph();
  const sig = lin.nodes.map(n => n.id).sort().join(',');
  if (state.graph.sig !== sig) { fit(); state.graph.sig = sig; }   // 문서가 늘거나 줄면 다시 화면 맞춤
}

function edgeKind(e) {
  const n = state.lineage.nodes.find(x => x.id === e.to);
  return n?.origin === 'merge' ? 'merge' : n?.origin === 'edit' ? 'edit' : '';
}

function drawEdges() {
  const g = $('#grEdges');
  g.innerHTML = state.lineage.edges.map((e, k) => {
    const [x1, y1] = pos[e.from], [x2, y2] = pos[e.to];
    const sx = x1 + W, sy = y1 + H / 2, tx = x2, ty = y2 + H / 2, mx = (sx + tx) / 2;
    const c = e.counts || {};
    const label = c.total ? `${c.total}곳` : '같음';
    const kind = edgeKind(e);
    return `<g class="gr-edge ${kind}" data-k="${k}"><title>${esc(nameOf(e.from))} → ${esc(nameOf(e.to))}\n${esc(e.headline)}\n근거: ${esc(e.basis || (kind === 'merge' ? '병합 기록' : '기록'))}</title>
      <path d="M${sx},${sy} C${mx},${sy} ${mx},${ty} ${tx - 2},${ty}" marker-end="url(#${kind === 'merge' ? 'arrM' : 'arr'})"/>
      <path d="M${sx},${sy} C${mx},${sy} ${mx},${ty} ${tx},${ty}" stroke="transparent" stroke-width="14"/>
      <g class="lbl" transform="translate(${mx},${(sy + ty) / 2})"><rect x="-24" y="-10" width="48" height="20" rx="10"/><text text-anchor="middle" dy="4">${label}</text></g></g>`;
  }).join('');
}

function drawNodes() {
  const g = $('#grNodes');
  g.innerHTML = state.lineage.nodes.map(n => {
    const [x, y] = pos[n.id];
    const name = n.name.length > 24 ? n.name.slice(0, 11) + '…' + n.name.slice(-11) : n.name;
    const tags = [n.latest ? '최근 저장' : '', n.leaf && n.role !== 'final' ? '끝 문서' : '', n.origin === 'merge' ? '병합' : n.origin === 'edit' ? '고침' : ''].filter(Boolean).join(' · ');
    const roleTxt = ROLE_LABEL[n.role] + (n.role_by === '추정' && n.role !== 'revision' ? '(추정)' : '');
    return `<g class="gr-node ${state.graph.sel === n.id ? 'sel' : ''}" data-id="${n.id}" transform="translate(${x},${y})">
      <title>${esc(n.name)}\n${n.reasons.map(esc).join('\n')}</title>
      <rect class="box" width="${W}" height="${H}" rx="10"/>
      <rect class="bar" width="8" height="${H}" rx="4" fill="${ROLE_COLOR[n.role]}"/>
      <rect x="16" y="8" width="${roleTxt.length * 11 + 10}" height="17" rx="6" fill="${ROLE_COLOR[n.role]}"/>
      <text class="t-role" x="21" y="21">${esc(roleTxt)}</text>
      <text class="t-name" x="16" y="43">${esc(name)}</text>
      <text class="t-sub" x="16" y="62">${esc(fmtDate(n.modified).slice(0, 16))}${n.author ? ' · ' + esc(n.author) : ''}</text>
      ${tags ? `<text class="t-sub" x="${W - 8}" y="21" text-anchor="end">${esc(tags)}</text>` : ''}
    </g>`;
  }).join('');
}

function applyView() {
  const v = state.graph;
  $('#grView').setAttribute('transform', `translate(${v.pan[0]},${v.pan[1]}) scale(${v.zoom})`);
}

function fit() {
  const wrap = $('#grWrap');
  if (!wrap) return;
  const xs = Object.values(pos).map(p => p[0]), ys = Object.values(pos).map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs) + W, minY = Math.min(...ys), maxY = Math.max(...ys) + H;
  const z = Math.min(1.3, Math.max(0.3, Math.min((wrap.clientWidth - 60) / (maxX - minX || 1), (wrap.clientHeight - 60) / (maxY - minY || 1))));
  state.graph.zoom = z;
  state.graph.pan = [(wrap.clientWidth - (maxX - minX) * z) / 2 - minX * z, (wrap.clientHeight - (maxY - minY) * z) / 2 - minY * z];
  applyView();
}

function bindGraph() {
  const svg = $('#grSvg');
  let drag = null;           // {type:'node'|'pan', id, start:[x,y], orig:[x,y], moved}
  const pt = e => [e.clientX, e.clientY];
  svg.addEventListener('pointerdown', e => {
    const node = e.target.closest('.gr-node');
    const edge = e.target.closest('.gr-edge');
    if (edge && !node) return;
    svg.setPointerCapture(e.pointerId);
    if (node) {
      drag = { type: 'node', id: node.dataset.id, start: pt(e), orig: [...pos[node.dataset.id]], moved: false, el: node };
      node.classList.add('dragging');
    } else {
      drag = { type: 'pan', start: pt(e), orig: [...state.graph.pan], moved: false };
      svg.classList.add('panning');
    }
  });
  svg.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.start[0], dy = e.clientY - drag.start[1];
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    if (drag.type === 'node') {
      pos[drag.id] = [drag.orig[0] + dx / state.graph.zoom, drag.orig[1] + dy / state.graph.zoom];
      drag.el.setAttribute('transform', `translate(${pos[drag.id][0]},${pos[drag.id][1]})`);
      drawEdges();
    } else {
      state.graph.pan = [drag.orig[0] + dx, drag.orig[1] + dy];
      applyView();
    }
  });
  const end = () => {
    if (!drag) return;
    svg.classList.remove('panning');
    if (drag.type === 'node') {
      drag.el.classList.remove('dragging');
      if (drag.moved) savePositions({ [drag.id]: pos[drag.id] });
      else select(drag.id);
    }
    drag = null;
  };
  svg.addEventListener('pointerup', end);
  svg.addEventListener('pointercancel', end);
  svg.addEventListener('dblclick', e => {
    const node = e.target.closest('.gr-node');
    if (node) openDoc(node.dataset.id);
  });
  svg.addEventListener('click', e => {
    const edge = e.target.closest('.gr-edge');
    if (edge) {
      const ed = state.lineage.edges[Number(edge.dataset.k)];
      emit('open-compare', { a: ed.from, b: ed.to, cid: null });
    }
  });
  svg.addEventListener('wheel', e => {
    e.preventDefault();
    const r = svg.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    zoomAt(e.deltaY < 0 ? 1.12 : 1 / 1.12, mx, my);
  }, { passive: false });
  $('#grIn').onclick = () => zoomAt(1.2, svg.clientWidth / 2, svg.clientHeight / 2);
  $('#grOut').onclick = () => zoomAt(1 / 1.2, svg.clientWidth / 2, svg.clientHeight / 2);
  $('#grAuto').onclick = () => { autoLayout(state.lineage, true); drawNodes(); drawEdges(); fit(); savePositions(pos); };
  $('#grFit').onclick = fit;
}

function zoomAt(f, mx, my) {
  const v = state.graph;
  const z = Math.min(2.5, Math.max(0.25, v.zoom * f));
  v.pan = [mx - (mx - v.pan[0]) * (z / v.zoom), my - (my - v.pan[1]) * (z / v.zoom)];
  v.zoom = z;
  applyView();
}

function savePositions(p) {
  clearTimeout(saveTimer);
  const snapshot = Object.fromEntries(Object.entries(p).map(([k, v]) => [k, [Math.round(v[0]), Math.round(v[1])]]));
  saveTimer = setTimeout(() => api.positions(snapshot).catch(() => {}), 300);
}

function select(id) {
  state.graph.sel = id;
  document.querySelectorAll('.gr-node').forEach(n => n.classList.toggle('sel', n.dataset.id === id));
  renderPanel();
}

function openDoc(id) {
  const n = state.lineage.nodes.find(x => x.id === id);
  const parent = n?.parents?.[0];
  emit('open-doc', parent ? { a: parent, b: id, cid: null } : { a: id, b: id, cid: null, plain: true });
}

function renderPanel() {
  const p = $('#grPanel');
  const lin = state.lineage;
  const n = lin.nodes.find(x => x.id === state.graph.sel);
  if (!n) {
    p.innerHTML = `<h3>문서를 누르세요</h3><div class="hint">문서 정보와 원본·최종본 지정, 부모 바꾸기, 병합 시작 버튼이 여기에 나옵니다.</div>
      <div class="notice info">원본·최종본 추정 근거<br>· 글자모양 목록이 이어지는지(한글은 고칠 때 새 모양을 목록 끝에 붙임)<br>· 저장 시각 · 내용이 얼마나 가까운지</div>`;
    return;
  }
  const others = lin.nodes.filter(x => x.id !== n.id);
  const hasHangul = state.hangul.ok;
  p.innerHTML = `
    <div><span class="role ${ROLE_CLASS[n.role]}">${ROLE_LABEL[n.role]}${n.role_by === '추정' ? ' (추정)' : ''}</span></div>
    <h3>${esc(n.name)}</h3>
    <dl><dt>마지막 수정</dt><dd>${esc(fmtDate(n.modified))}</dd><dt>처음 만든 날</dt><dd>${esc(fmtDate(n.created))}</dd>
      <dt>저장한 사람</dt><dd>${esc(n.author || '-')}</dd><dt>한글 버전</dt><dd>${esc(n.app || '-')}</dd>
      <dt>글자모양</dt><dd>${n.styles}개</dd><dt>만든 방법</dt><dd>${{ import: '가져옴', merge: '병합', edit: '직접 고침' }[n.origin] || '-'}</dd></dl>
    ${n.reasons.length ? `<b>원본 판정 근거 <span class="hint">(점수 ${n.score}/6${n.id === lin.original ? ' · 원본으로 판정' : ''})</span></b><ul>${n.reasons.map(r => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}
    <b>역할 지정</b>
    <div class="btns">${['original', 'revision', 'final', 'archived'].map(r => `<button class="btn btn-sm ${n.role === r ? 'btn-primary' : ''}" data-role="${r}">${ROLE_LABEL[r]}</button>`).join('')}</div>
    <b>부모 문서 (어느 문서를 고쳐 만들었나)</b>
    <select id="grParent" multiple size="${Math.min(4, Math.max(2, others.length))}" style="width:100%">
      ${others.map(o => `<option value="${o.id}" ${n.parents.includes(o.id) ? 'selected' : ''}>${esc(o.name)}</option>`).join('')}</select>
    <div class="btns"><button class="btn btn-sm" id="grSetParent">부모 지정</button><span class="hint">Ctrl 로 여러 개(병합본)</span></div>
    <b>작업</b>
    <div class="btns">
      <button class="btn btn-sm" data-go="doc">문서 보기</button>
      <button class="btn btn-sm" data-go="edit">고치기</button>
      <button class="btn btn-sm" data-go="merge">이 문서 기준으로 병합</button>
      <button class="btn btn-sm" data-go="hangul">한글에서 열기</button>
      <a class="btn btn-sm" href="${api.downloadUrl(n.id)}">내려받기</a>
      ${hasHangul ? `<button class="btn btn-sm" data-go="resave">한글로 다시 저장</button><button class="btn btn-sm" data-go="pdf">PDF</button>` : ''}
    </div>`;
  p.querySelectorAll('[data-role]').forEach(b => b.onclick = async () => {
    try { const r = await api.setRole(n.id, b.dataset.role); toast(r.messages.join(' / '), 4000); emit('poke'); emit('relations'); }
    catch (err) { toast(err.message); }
  });
  $('#grSetParent').onclick = async () => {
    const ps = [...$('#grParent').selectedOptions].map(o => o.value);
    try { await api.setParents(n.id, ps); toast('부모 문서를 지정했습니다'); emit('relations'); } catch (err) { toast(err.message); }
  };
  p.querySelectorAll('[data-go]').forEach(b => b.onclick = async () => {
    const go = b.dataset.go;
    try {
      if (go === 'doc') openDoc(n.id);
      else if (go === 'edit') emit('open-edit', { id: n.id });
      else if (go === 'merge') emit('open-merge', { base: n.id });
      else if (go === 'hangul') { const r = await api.hangulOpen(n.id); toast('한글에서 엽니다: ' + r.path, 4000); }
      else if (go === 'resave') { toast('한글로 다시 저장하는 중…'); const r = await api.hangulResave(n.id); toast('새 문서: ' + r.name, 4000); emit('poke'); }
      else if (go === 'pdf') { toast('PDF 저장 중…'); const r = await api.hangulPdf(n.id); toast('PDF: ' + r.path, 5000); }
    } catch (err) { toast(err.message, 5000); }
  });
}
