// 화면 상태 한곳 보관 + 간단한 알림(on/emit). 화면 부품끼리는 직접 부르지 않고 이벤트로 주고받는다.
//   'status'   서버 상태(파일 목록·진행·로그)가 새로 옴
//   'docs'     해석 완료된 문서 목록/순서가 바뀜 → 결과 다시 계산
//   'options'  비교 옵션이 바뀜 → 결과 다시 계산
//   'open-compare' {a, b, cid}  두 버전 비교 탭 열기
export const state = {
  items: [],            // 서버의 파일 목록 (순서 = 버전 순서)
  orderMode: 'modified',
  options: {},
  progress: { total: 0, done: 0, busy: false },
  logSince: 0,
  tab: 'summary',
  history: null,        // /api/history 결과
  compare: null,        // /api/compare 결과
  pair: { a: null, b: null },
  view: { type: 'all', q: '', mode: 'list', onlyChanged: true },
  histFilter: 'all',
};

const handlers = {};
export function on(evt, fn) { (handlers[evt] ||= []).push(fn); }
export function emit(evt, data) { (handlers[evt] || []).forEach(fn => fn(data)); }

export const readyItems = () => state.items.filter(i => i.status === 'ready');
export const itemById = id => state.items.find(i => i.id === id);
export function versionNo(id) {
  const k = readyItems().findIndex(i => i.id === id);
  return k < 0 ? '?' : k + 1;
}
