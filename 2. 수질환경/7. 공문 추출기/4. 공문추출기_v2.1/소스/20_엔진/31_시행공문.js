/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/31_시행공문.js] 시행공문(결과 알림) 해석
   하는 일 : 결과 알림 공문 판별, 본문의 "○○과-번호(날짜)호"로 의뢰 공문번호 읽기
   주요 이름: isReply, parseReply, REL_RE
   이럴 때 고침: 시행공문이 의뢰공문과 연결되지 않을 때
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───────── 3. 시행 공문(결과 알림) ───────── */
const OUR_ORG = /보건환경연구원/;
const REL_RE = /^\s*(?:\d+\.\s*)?(.*?)\s*([^\s]+-\d+)\s*\(\s*(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?\s*\)\s*호/;
function isReply(result) {
  const d = result.doc || {};
  return OUR_ORG.test(d.상단기관명 || '') || /^경기도보건환경연구원/.test(d.시행 || '') || /결과\s*(알림|통보|회신)/.test(d.제목 || '');
}
function parseReply(result) {
  const d = result.doc || {}, paras = d.본문 || [];
  let rel = null;
  for (const p of paras) { const m = REL_RE.exec(p); if (m) { rel = { org: m[1].trim(), no: m[2].trim(), date: `${m[3]}-${pad(m[4])}-${pad(m[5])}` }; break; } }
  const code = (/[\[(]([^\[\]()]+)[\])]\s*$/.exec(d.제목 || '') || [])[1] || '';
  return { 파일명: d.파일명, 제목: d.제목, 시행: d.시행, 시행일: d.시행일, 관련기관: rel ? rel.org : '', 관련공문번호: rel ? rel.no : '', 관련공문일: rel ? rel.date : '',
    제목코드: code, 부적합: /부적합/.test(d.제목 || ''), 단계: (/(1차|2차|중간|최종)/.exec(d.제목 || '') || [])[1] || '' };
}
