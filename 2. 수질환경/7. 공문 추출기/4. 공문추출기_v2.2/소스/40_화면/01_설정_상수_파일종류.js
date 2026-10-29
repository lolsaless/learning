/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/01_설정_상수_파일종류.js] 설정: 저장 파일 이름·파일 종류
   하는 일 : _처리상태.json 등 파일 이름, 성적처리완료 폴더 이름, 읽지 않을 파일, 파일 종류 판정, 날짜 표기 도우미
   주요 이름: STATUS_FILE, NOTES_FILE, SETTINGS_FILE, DONE_DIR, IGNORE, kindOf, fmtDay, fmtFull
   이럴 때 고침: 저장 파일·폴더 이름, 읽지 않을 파일 규칙
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
const E = window.OdtEngine, E2 = window.OdtEngine2, X = window.MiniXlsx, DG = window.DocGen;
const STATUS_FILE = '_처리상태.json';   // 완료 체크·처리 기록 (v1.x와 같은 파일)
const NOTES_FILE = '_시료이력.json';    // v2.0: 시료접수일·메모·이력·직접 입력 시료
const SETTINGS_FILE = '_설정.json';     // v2.0: 휴일·처리기간·폴더 정리 설정
const DONE_DIR = '성적처리완료';
const STD_RE = /^기준표\.(xlsx|csv)$/i;
const HISTORY_MAX = 2000;
const WEEK = ['일', '월', '화', '수', '목', '금', '토'];

const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const today = () => E2.ymd(new Date());
const nowIso = () => new Date().toISOString();
const shortNo = v => { const m = /-(\d+)$/.exec(v || ''); return m ? m[1] : (v || ''); };
const fmtDay = s => { if (!s) return ''; const d = E2.toDate(s); return `${s.slice(5).replace('-', '.')}(${WEEK[d.getDay()]})`; };
const fmtFull = s => { if (!s) return ''; const d = E2.toDate(s); return `${s.slice(0, 4)}. ${+s.slice(5, 7)}. ${+s.slice(8, 10)}.(${WEEK[d.getDay()]})`; };
const uid = () => Math.random().toString(36).slice(2, 10);

/* ───── 파일 종류 ───── */
const IGNORE = nm => /^(~\$|\.|_)/.test(nm) || STD_RE.test(nm) || /^기준표/.test(nm) || /^공문추출/.test(nm) || /\.(html?|py|json|md|zip|ini|db|lnk|tmp|exe|bat)$/i.test(nm);
const kindOf = nm => /\.odt$/i.test(nm) ? 'odt' : /\.pdf$/i.test(nm) ? 'pdf' : /\.hwpx$/i.test(nm) ? 'hwpx' : /\.(xlsx|xlsm)$/i.test(nm) ? 'xlsx' : /\.(jpe?g|png|gif|bmp|webp)$/i.test(nm) ? 'img' : /\.(tiff?)$/i.test(nm) ? 'tif' : 'doc';
const isHistoryDoc = nm => /^이력_/.test(nm);
const SKIP_DIR = nm => nm === DONE_DIR || /^[_.]/.test(nm) || /^공문추출기/.test(nm);
