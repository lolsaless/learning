// 공통 도구: 글자 이스케이프, 날짜·크기 표시, 변경 조각 그리기, 알림
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/** 줄바꿈·탭을 눈에 보이게 */
function vis(s) {
  return esc(s).replace(/\n/g, '<span class="muted">⏎</span>\n').replace(/\t/g, '→\t');
}

/** 변경 조각 → HTML.  side: 'both'(삭제+추가) | 'a'(이전: 삭제만) | 'b'(새: 추가만) */
export function segHTML(segs, side = 'both') {
  return (segs || []).map(s => {
    if (s.op === 'equal') return vis(s.text);
    if (s.op === 'delete') return side === 'b' ? '' : `<del class="d">${vis(s.text)}</del>`;
    if (s.op === 'insert') return side === 'a' ? '' : `<ins class="i">${vis(s.text)}</ins>`;
    return '';
  }).join('');
}
export const plain = s => (s == null ? '' : vis(s));

/** '2026-11-02T04:43:18Z' → '2026-11-02 13:43' (내 컴퓨터 시간대) */
export function fmtDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
export function fmtSize(n) {
  if (n == null) return '';
  return n > 1048576 ? (n / 1048576).toFixed(1) + 'MB' : Math.max(1, Math.round(n / 1024)) + 'KB';
}

let toastTimer;
export function toast(msg, ms = 2600) {
  const el = $('#toast');
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), ms);
}

export const KIND_CLASS = { modified: 'k-modified', added: 'k-added', deleted: 'k-deleted', format: 'k-format' };
export function tagHTML(tags) {
  return (tags || []).map(t => `<span class="tag ${t === '숫자' ? 't-num' : ''}">${esc(t)}</span>`).join('');
}
