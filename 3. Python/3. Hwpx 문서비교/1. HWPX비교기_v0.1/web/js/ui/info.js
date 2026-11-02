// [문서 정보] 탭 — 각 파일의 메타정보(작성자·수정일 등)와 구성(문단·표·셀 수)
import { readyItems, state } from '../store.js';
import { $, esc, fmtDate, fmtSize } from '../util.js';

const ROWS = [
  ['파일 이름', i => esc(i.name)],
  ['원래 위치', i => esc(i.label || '')],
  ['문서 만든 날', i => esc(fmtDate(i.meta?.CreatedDate))],
  ['마지막 수정일', i => esc(fmtDate(i.meta?.ModifiedDate))],
  ['작성자', i => esc(i.meta?.creator || '-')],
  ['마지막 저장자', i => esc(i.meta?.lastsaveby || '-')],
  ['프로그램', i => esc(i.meta?.application || '-')],
  ['파일 크기', i => fmtSize(i.size)],
  ['문단 / 표 / 셀', i => `${i.stats?.paragraphs ?? 0} / ${i.stats?.tables ?? 0} / ${i.stats?.cells ?? 0}`],
  ['글자 수', i => (i.stats?.chars ?? 0).toLocaleString()],
  ['추정 쪽수', i => i.stats?.pages_est ?? '-'],
  ['지문(SHA-1)', i => `<span class="mono" title="${esc(i.sha1)}">${esc((i.sha1 || '').slice(0, 12))}</span>`],
  ['알림', i => esc([...(i.warnings || []), i.duplicate_of ? `${i.duplicate_of} 와 같은 파일` : ''].filter(Boolean).join(' · ') || '-')],
];

export function renderInfo() {
  const box = $('#tab-info');
  const items = readyItems();
  const errors = state.items.filter(i => i.status === 'error');
  if (!items.length && !errors.length) {
    box.innerHTML = `<div class="card hero"><b>넣은 파일이 없습니다</b></div>`;
    return;
  }
  box.innerHTML = `
    ${items.length ? `<div class="tbl-wrap"><table class="grid">
      <tr><th>항목</th>${items.map((i, k) => `<th>v${k + 1}</th>`).join('')}</tr>
      ${ROWS.map(([label, f]) => `<tr><th>${label}</th>${items.map(i => `<td>${f(i)}</td>`).join('')}</tr>`).join('')}
    </table></div>` : ''}
    ${errors.length ? `<div class="card"><h3>읽지 못한 파일</h3><ul>${errors.map(e => `<li><b>${esc(e.name)}</b> — ${esc(e.error)}</li>`).join('')}</ul></div>` : ''}
    <div class="muted">추정 쪽수·쪽 번호는 HWPX 안의 줄 배치 정보로 계산한 참고값입니다. 한글 화면의 쪽과 다를 수 있습니다.</div>`;
}
