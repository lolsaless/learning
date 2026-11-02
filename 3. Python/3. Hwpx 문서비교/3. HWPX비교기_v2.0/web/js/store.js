// 화면 상태 한곳 보관 + 간단한 알림(on/emit). 화면 부품끼리는 직접 부르지 않고 이벤트로 주고받는다.
//   'status'   서버 상태(파일 목록·진행·로그)가 새로 옴
//   'docs'     해석 완료된 문서 목록/순서가 바뀜 → 결과 다시 계산
//   'options'  비교 옵션이 바뀜 → 결과 다시 계산
//   'open-compare' {a, b, cid}  두 버전 비교 탭 열기
//   'open-doc'     {a, b, cid}  (v1.1) 문서 보기 탭 열기
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
  doc: { view: 'merged', zoom: 'fit', sync: true, data: null, key: '', cur: null,   // (v1.1) 문서 보기
         editing: false, edits: {}, editDoc: null, markColor: '#FF0000' },          // (v2.0) 고치기
  // ── v2.0 ──
  lineage: null,          // /api/lineage 결과 (관계도·원본/최종본 추정)
  project: null,          // {name, folder} | null
  hangul: { ok: false },  // 한글 자동화 가능 여부
  graph: { sel: null, zoom: 1, pan: [40, 40] },
  merge: { base: null, versions: null, plan: null, choices: {}, preview: null, mode: 'plan', key: '' },
};

export const ROLE_LABEL = { original: '원본', revision: '수정본', final: '최종본', archived: '보관' };
export const nameOf = id => (state.items.find(i => i.id === id) || {}).name || id;

const handlers = {};
export function on(evt, fn) { (handlers[evt] ||= []).push(fn); }
export function emit(evt, data) { (handlers[evt] || []).forEach(fn => fn(data)); }

export const readyItems = () => state.items.filter(i => i.status === 'ready');
export const itemById = id => state.items.find(i => i.id === id);
/** 고른 두 버전(state.pair)이 유효한지 확인하고, 아니면 기본값(처음 → 최신)으로. 비교·문서 보기 탭이 함께 씀 */
export function ensurePair() {
  const ids = readyItems().map(i => i.id);
  const { a, b } = state.pair;
  if (!ids.includes(a) || !ids.includes(b) || a === b) {
    state.pair = { a: ids[0] || null, b: ids[ids.length - 1] || null };
  }
}

export function versionNo(id) {
  const k = readyItems().findIndex(i => i.id === id);
  return k < 0 ? '?' : k + 1;
}
