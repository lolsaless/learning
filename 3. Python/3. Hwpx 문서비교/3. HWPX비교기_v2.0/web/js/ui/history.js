// [이력 추적표] 탭 — 행 = 바뀐 위치, 열 = 버전. 그 버전에서 바뀐 칸은 주황색, 바뀐 글자는 강조.
import { emit, readyItems, state } from '../store.js';
import { $, esc, fmtDate, plain, segHTML } from '../util.js';

const KIND_CLS = { changed: 'k-changed', reverted: 'k-reverted', added: 'k-added', deleted: 'k-deleted', format: 'k-format', flip: 'k-flip' };

export function renderHistory() {
  const box = $('#tab-history');
  const h = state.history;
  if (readyItems().length < 2 || !h) {
    box.innerHTML = `<div class="card hero"><b>이력을 보려면 HWPX 파일이 2개 이상 필요합니다</b>
      3개 이상이면 '바뀌었다가 되돌아간 곳'까지 찾아 줍니다.</div>`;
    return;
  }
  const f = state.histFilter;
  const chains = h.chains.filter(c => f === 'all' || c.kind === f);
  const chips = [['all', '전체', h.counts.total || 0]].concat(
    Object.keys(h.kind_labels).filter(k => h.counts[k]).map(k => [k, h.kind_labels[k], h.counts[k]]));

  box.innerHTML = `
    <div class="card">
      <div class="card-head"><h3>이력 추적표</h3>
        <span class="muted">주황 칸 = 그 버전에서 바뀜 · 칸을 누르면 해당 단계의 비교로 이동</span></div>
      <div class="chips">${chips.map(([k, t, n]) => `<button class="chip ${f === k ? 'on' : ''}" data-hf="${k}">${esc(t)}<span class="c">${n}</span></button>`).join('')}</div>
    </div>
    ${chains.length ? `<div class="tbl-wrap"><table class="grid hist">
      <tr><th>#</th><th>구분</th><th>위치</th>${h.versions.map(v => `<th><span class="vn">v${v.no}</span>
        <span class="vd" title="${esc(v.name)}">${esc(fmtDate(v.modified))}</span></th>`).join('')}</tr>
      ${chains.map((c, n) => row(c, n, h)).join('')}
    </table></div>` : `<div class="card hero">${h.chains.length ? '조건에 맞는 항목이 없습니다' : '모든 버전의 내용이 같습니다'}</div>`}`;

  box.querySelectorAll('[data-hf]').forEach(b => b.onclick = () => { state.histFilter = b.dataset.hf; renderHistory(); });
  box.querySelectorAll('td[data-step]').forEach(td => td.onclick = () => {
    const [k, cid] = td.dataset.step.split('|').map(Number);
    const s = h.steps[k];
    emit('open-compare', { a: s.a, b: s.b, cid });
  });
}

function row(c, n, h) {
  const cells = c.texts.map((t, k) => {
    const step = k - 1;                                   // 이 칸으로 들어온 단계
    const changed = k > 0 && c.steps[step] && c.steps[step] !== 'same';
    const segs = k > 0 ? c.diffs[step] : null;
    let html;
    if (t == null) html = '(없음)';
    else if (changed && segs && c.steps[step] === 'modified') html = segHTML(segs, 'b');
    else html = plain(t);
    const click = changed && c.cids[step] ? ` data-step="${step}|${c.cids[step]}" style="cursor:pointer" title="${esc(c.summaries[step] || '')}"` : '';
    return `<td class="v ws ${changed ? 'changed' : ''} ${t == null ? 'none' : ''}"${click}>${html}</td>`;
  }).join('');
  return `<tr><td class="muted">${n + 1}</td><td><span class="kind ${KIND_CLS[c.kind]}">${esc(c.kind_label)}</span></td>
    <td>${esc(c.location)}<div class="muted">${c.n_changes}번 바뀜</div></td>${cells}</tr>`;
}
