/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/51_처리기한.js] 처리기한([별표 2])
   하는 일 : 항목별 표준처리기간 표, 근무일 계산, 남은 기간, 시료 기한(긴/짧은 항목)
   주요 이름: STD_DAYS, stdDaysTable, deadline, remaining, sampleDeadline
   이럴 때 고침: 처리기간 기본값·계산 규칙
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───────── 6. 표준처리기간 ([별표 2]) ───────── */
const STD_DAYS = [
  // [항목명(정규화), 일수, 근거]
  ['pH', 2, '별표2 수소이온농도(현장측정)'], ['수온', 2, '별표2 온도(현장측정)'], ['DO', 2, '별표2 용존산소(현장측정)'],
  ['SS', 5, '별표2 부유물질'], ['COD', 5, '별표2 화학적산소요구량'], ['색도', 5, '별표2 색도'], ['총대장균군', 5, '별표2 총대장균군'],
  ['T-P', 7, '별표2 총인'], ['T-N', 7, '별표2 총질소'], ['페놀류', 7, '별표2 페놀'], ['시안', 7, '별표2 시안'], ['불소', 7, '별표2 불소'],
  ['n-H(광)', 7, '별표2 노말헥산추출물질'], ['n-H(동식)', 7, '별표2 노말헥산추출물질'], ['ABS', 7, '별표2 음이온계면활성제'],
  ['철', 8, '별표2 철'], ['아연', 8, '별표2 아연'], ['구리', 8, '별표2 구리'], ['카드뮴', 8, '별표2 카드뮴'], ['납', 8, '별표2 납'], ['망간', 8, '별표2 망간'],
  ['크롬', 8, '별표2 크롬'], ['6가크롬', 8, '별표2 6가크롬'],
  ['BOD', 9, '별표2 생물화학적산소요구량'], ['수은', 11, '별표2 수은'], ['비소', 11, '별표2 비소'],
  // 비고 5 (규정되지 않은 항목은 유사 항목 준용) — 기관 확인 후 [처리기간 설정]에서 고칠 것
  ['TOC', 5, '준용(COD와 유사) — 확인 필요', true], ['대장균군', 5, '준용(총대장균군) — 확인 필요', true],
  ['생태독성', null, '별표2에 없음 — 설정 필요', true], ['클로로필a', null, '별표2에 없음 — 설정 필요', true],
];
function stdDaysTable(overrides) {
  const t = {};
  for (const [k, d, why, flag] of STD_DAYS) t[k] = { days: d, why, flag: !!flag };
  for (const [k, v] of Object.entries(overrides || {})) if (v != null && v !== '') t[k] = { days: +v, why: '사용자 설정', flag: false };
  return t;
}
/* 영업일 달력: holidays = Set('YYYY-MM-DD') (공휴일 + 사용자 지정 휴일) */
const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const toDate = s => { const [y, m, d] = String(s).split('-').map(Number); return new Date(y, m - 1, d, 12); };
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const isWorkday = (d, hol, workdays) => (workdays && workdays.has(ymd(d))) || (d.getDay() !== 0 && d.getDay() !== 6 && !hol.has(ymd(d)));
/* 처리기한: 접수일(13시 이후 접수 → 접수일 불산입, 13시 이전 → 접수일이 근무일이면 1일째)부터 근무일 n일째 날 */
function deadline(receivedYmd, days, hol, opt = {}) {
  if (!receivedYmd || !days) return '';
  let d = toDate(receivedYmd), n = 0;
  if (opt.countReceiptDay && isWorkday(d, hol, opt.workdays)) { n = 1; if (n >= days) return ymd(d); }
  for (let guard = 0; guard < 400; guard++) { d = addDays(d, 1); if (isWorkday(d, hol, opt.workdays)) { n++; if (n >= days) return ymd(d); } }
  return '';
}
/* 남은 기간: 오늘 이후 ~ 기한까지 근무일 수 (기한 당일 = 0, 지나면 음수: 초과된 일수는 공휴일 포함 달력일 — 별표2 2.나) */
function remaining(todayYmd, dueYmd, hol, opt = {}) {
  if (!dueYmd) return null;
  const t = toDate(todayYmd), due = toDate(dueYmd);
  if (t > due) return { days: -Math.round((t - due) / 86400000), overdue: true };
  let n = 0, d = t;
  while (ymd(d) < dueYmd) { d = addDays(d, 1); if (isWorkday(d, hol, opt.workdays)) n++; }
  return { days: n, overdue: false };
}
/* 시료 하나의 처리기한: opt.basis — 'max'(기본, 가장 긴 항목 기준) | 'min'(가장 짧은 항목 기준) */
function sampleDeadline(items, receivedYmd, hol, table, opt = {}) {
  let best = null; const unknown = [], flagged = [], useMin = opt.basis === 'min';
  for (const it of items) {
    const name = typeof it === 'string' ? it : it.name;
    const e = table[name];
    if (!e || !e.days) { unknown.push(name); continue; }
    if (e.flag) flagged.push(name);
    if (!best || (useMin ? e.days < best.days : e.days > best.days)) best = { item: name, days: e.days, why: e.why };
  }
  if (!best) return { due: '', days: null, item: '', unknown, flagged };
  return { due: deadline(receivedYmd, best.days, hol, opt), days: best.days, item: best.item, why: best.why, unknown, flagged, basis: useMin ? 'min' : 'max' };
}
