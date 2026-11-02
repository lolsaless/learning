// [요약] 탭 — 버전 흐름, 단계별 변경 건수, 주요 변경 (누르면 두 버전 비교로 이동)
import { emit, readyItems, state } from '../store.js';
import { $, esc, fmtDate, KIND_CLASS } from '../util.js';

const CHAIN_ORDER = ['changed', 'reverted', 'added', 'deleted', 'format', 'flip'];

export function renderSummary() {
  const box = $('#tab-summary');
  const ready = readyItems();
  if (ready.length < 2) {
    box.innerHTML = `<div class="card hero"><b>${ready.length ? 'HWPX 파일을 하나 더 넣어 주세요' : '비교할 HWPX 파일을 넣어 주세요'}</b>
      같은 문서의 여러 버전을 2개 이상 넣으면, 문서 속 수정일 순으로 줄을 세워 무엇이 바뀌었는지 보여 줍니다.<br>
      왼쪽 칸에 파일이나 폴더를 끌어 놓거나 [파일 선택]·[폴더 선택]을 누르세요.</div>`;
    return;
  }
  const h = state.history;
  if (!h) { box.innerHTML = `<div class="card hero">결과 계산 중…</div>`; return; }

  const totalChanges = h.steps.reduce((s, x) => s + x.counts.total, 0);
  const kinds = CHAIN_ORDER.filter(k => h.counts[k]).map(k =>
    `<div class="stat s-${k === 'changed' ? 'modified' : k}"><div class="n">${h.counts[k]}</div><div class="l">${esc(h.kind_labels[k])}</div></div>`).join('');

  box.innerHTML = `
    <div class="stats">
      <div class="stat"><div class="n">${h.versions.length}</div><div class="l">버전 수</div></div>
      <div class="stat"><div class="n">${totalChanges}</div><div class="l">단계별 변경 합계</div></div>
      <div class="stat"><div class="n">${h.counts.total || 0}</div><div class="l">바뀐 위치 (전체 이력)</div></div>
      ${kinds}
    </div>
    <div class="card">
      <div class="card-head"><h3>버전 흐름</h3><span class="muted">문서 속 '마지막 수정일' 기준 · 왼쪽 목록에서 순서를 바꿀 수 있습니다</span></div>
      <div class="row wrap gap">${h.versions.map((v, k) => `${k ? '<span class="arrow">→</span>' : ''}
        <span class="vchip" title="${esc(v.name)}"><b>v${v.no}</b> ${esc(short(v.name))} <span class="muted">${esc(fmtDate(v.modified))}</span></span>`).join('')}</div>
      ${reverted(h)}
    </div>
    <div class="timeline">${h.steps.map(stepCard).join('')}</div>`;

  box.querySelectorAll('[data-open]').forEach(el => el.onclick = () => {
    const [a, b, cid] = el.dataset.open.split('|');
    emit('open-compare', { a, b, cid: cid ? Number(cid) : null });
  });
  box.querySelectorAll('[data-doc]').forEach(el => el.onclick = () => {
    const [a, b] = el.dataset.doc.split('|');
    emit('open-doc', { a, b, cid: null });
  });
}

function short(name) { return name.length > 28 ? name.slice(0, 12) + '…' + name.slice(-14) : name; }

function reverted(h) {
  const r = h.chains.filter(c => c.kind === 'reverted');
  if (!r.length) return '';
  return `<div class="muted" style="margin-top:10px">↺ 중간에 바뀌었다가 <b>원래대로 되돌아간 곳 ${r.length}곳</b>이 있습니다 — [이력 추적표]에서 확인하세요.
    (처음 버전과 마지막 버전만 비교하면 보이지 않는 변화입니다)</div>`;
}

function stepCard(s) {
  const c = s.counts;
  const badges = ['modified', 'added', 'deleted', 'format'].filter(k => c[k]).map(k =>
    `<span class="kind ${KIND_CLASS[k]}">${{ modified: '수정', added: '추가', deleted: '삭제', format: '서식' }[k]} ${c[k]}</span>`).join(' ');
  const more = c.total > s.highlights.length ? `<li class="muted" data-open="${s.a}|${s.b}|">… 외 ${c.total - s.highlights.length}건 더 보기</li>` : '';
  return `<div class="card">
    <div class="card-head">
      <h3>v${s.from} <span class="arrow">→</span> v${s.to}</h3>
      <div class="row gap">${badges || '<span class="muted">변경 없음</span>'}
        <button class="btn btn-sm" data-open="${s.a}|${s.b}|">자세히</button>
        <button class="btn btn-sm" data-doc="${s.a}|${s.b}">문서로 보기</button></div>
    </div>
    <div class="muted">${esc(s.headline)}${s.identical_file ? ' · 두 파일이 완전히 같습니다' : ''}
      ${s.meta_changes.length ? ' · 문서 정보: ' + s.meta_changes.map(m => esc(m.field)).join(', ') + ' 바뀜' : ''}</div>
    ${s.highlights.length ? `<ul class="hl">${s.highlights.map(x => `
      <li data-open="${s.a}|${s.b}|${x.id}"><span class="kind ${KIND_CLASS[x.type]}">${esc(x.label)}</span>
        <span class="loc">${esc(x.location)}</span><span>${esc(x.summary)}</span></li>`).join('')}${more}</ul>` : ''}
  </div>`;
}
