/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/02_설정_열_기본값_상태.js] 설정: 표 열·엑셀 열·기본 설정값·화면 상태
   하는 일 : 목록 표 열(기본 표시·순서), 엑셀 추가 열·너비, 설정 기본값(임박 일수·처리기한 기준 등), 화면 상태 state
   주요 이름: COLS, XLSX_EXTRA, XLSX_W, DEFAULT_SETTINGS, state
   이럴 때 고침: 열 순서·기본 표시 열, 설정 기본값
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 열 정의 ───── */
const COLS = [
  { k: '접수일', doc: 1, def: 1 },
  { k: '의뢰기관', doc: 1, def: 1 },
  { k: '의뢰자', doc: 1, def: 1 },
  { k: '발신명의', doc: 1, def: 1 },
  { k: '시행', doc: 1, def: 1 },
  { k: '시료번호', def: 1 },
  { k: '검사항목', def: 1, wrap: 1 },
  { k: '시료채취일', def: 1 },
  { k: '시료접수일', doc: 1, def: 1, v2: 1 },
  { k: '처리기한', def: 1, v2: 1 },
  { k: '진행', doc: 1, def: 1, v2: 1, label: '시행공문·성적서' },
  { k: '결과', v2: 1, wrap: 1 },
  { k: '메모', doc: 1, v2: 1 },
  { k: '기준', wrap: 1 },
  { k: '지역구분', wrap: 1 },
  { k: '시료채취자', doc: 1 },
  { k: '접수', label: '접수번호', doc: 1, fmt: shortNo },
  { k: '시행일', doc: 1 }, { k: '제목', doc: 1, wrap: 1 },
  { k: '기준출처' }, { k: '채취시각' }, { k: '채취일출처' }, { k: '업종/성상', wrap: 1 }, { k: '시료량', wrap: 1 },
  { k: '채취지점', wrap: 1 }, { k: '비고', wrap: 1 }, { k: '기타', wrap: 1 },
  { k: '우편번호', doc: 1 }, { k: '주소', doc: 1 }, { k: '전화번호', doc: 1 }, { k: '이메일', doc: 1 }, { k: '폴더', doc: 1 }, { k: '파일명', doc: 1 },
];
const XLSX_EXTRA = ['시료접수일', '처리기한', '남은기간', '기한결정항목', '시행공문', '성적서', '성적서접수번호', '판정', '결과', '메모', '폴더'];
const XLSX_W = { 상태: 9, 접수: 30, 접수일: 11, 의뢰기관: 10, 의뢰자: 12, 발신명의: 18, 시행: 22, 시행일: 11, 제목: 40, 시료번호: 18, 검사항목: 34, 기준: 30, 기준출처: 10, 지역구분: 28, 시료채취일: 16, 채취시각: 8, 채취일출처: 9, 시료채취자: 9, '업종/성상': 22, 시료량: 22, 채취지점: 24, 비고: 18, 기타: 24, 우편번호: 8, 주소: 36, 전화번호: 14, 이메일: 22, 확인필요: 40, 파일명: 44,
  시료접수일: 11, 처리기한: 11, 남은기간: 10, 기한결정항목: 12, 시행공문: 30, 성적서: 30, 성적서접수번호: 16, 판정: 8, 결과: 40, 메모: 40, 폴더: 40 };

function loadPref(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } }
function savePref(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* 무시 */ } }
function loadCols() {
  try { const v = JSON.parse(loadPref('odt-cols-v20', 'null')); if (Array.isArray(v) && v.length) return v; } catch (e) { /* 무시 */ }
  return COLS.filter(c => c.def).map(c => c.k);
}
function saveCols() { savePref('odt-cols-v20', JSON.stringify(state.cols)); }

const DEFAULT_SETTINGS = () => ({
  version: 1,
  holidays: { api: {}, fetched: {}, custom: {}, work: {} }, // api: 인터넷 공휴일, custom: 사용자 지정 휴일, work: 근무일로 지정
  stdDays: {},           // 처리기간 사용자 설정 {항목: 일수}
  dueBasis: 'max',       // 처리기한 기준: 'max' 가장 긴 항목 | 'min' 가장 짧은 항목
  imminent: 1,           // 남은 근무일 n일 이하 → 빨간색
  soon: 3,               // n일 이하 → 주황색
  organize: { auto: false, asked: false }, // 공문별 폴더 자동 정리
  nestDone: true,        // 처리 완료 시 공문 폴더를 성적처리완료로 옮김
  watermark: true,       // 의뢰공문 우측 상단에 시료접수일 표시
});
const state = {
  root: null, savedHandle: null,
  docs: [], doneDocs: [], doneCount: 0,
  inbox: { replies: [], reports: [], attach: [], requests: [], groups: [] },
  cache: new Map(), fileCache: new Map(),
  status: { version: 1, checked: {}, history: [] },
  notes: { version: 1, cases: {} },
  settings: DEFAULT_SETTINGS(),
  hol: new Set(), holName: new Map(), work: new Set(), stdDays: E2.stdDaysTable(),
  stdTable: [], stdFile: '', stdFilled: 0,
  excluded: [], busy: false, lastScan: 0,
  sort: { key: '접수일', dir: -1 },
  detailMode: loadPref('odt-detail-mode', 'side'), viewer: 'req', previewCache: new Map(),
  filter: { q: '', org: '', state: 'pending', warn: false },
  cols: loadCols(), selected: null,
};
