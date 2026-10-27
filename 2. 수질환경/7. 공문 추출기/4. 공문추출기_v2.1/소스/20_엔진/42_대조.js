/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/42_대조.js] 대조(의뢰 ↔ 시행공문 ↔ 성적서)
   하는 일 : 공문번호·시료명·의뢰기관 비교 → 일치/일부/없음
   주요 이름: matchReply, matchReport, noKey, orgOk
   이럴 때 고침: 짝짓기 조건을 바꿀 때
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───────── 5. 대조 (의뢰 ↔ 시행공문 ↔ 성적서) ───────── */
const orgOk = (a, b) => { a = squash(a); b = squash(b); return !a || !b || a.includes(b) || b.includes(a); };
const noKey = s => squash(s).replace(/[()（）]/g, '').toLowerCase();
function matchReply(caseDoc, reply) {
  if (!reply.관련공문번호 || squash(reply.관련공문번호) !== squash(caseDoc.시행)) return 0;
  return orgOk(reply.관련기관, caseDoc.의뢰기관) ? 1 : 0.5;
}
// 반환 {level:'full'|'partial'|'none', matched:[시료], missing:[시료], extra:[시료]}
function matchReport(caseDoc, sampleNos, report) {
  const rs = report.samples.filter(s => squash(s.공문번호) === squash(caseDoc.시행));
  if (!rs.length) return { level: 'none', matched: [], missing: sampleNos.slice(), extra: [] };
  const want = new Map(sampleNos.map(n => [noKey(n), n]));
  const matched = [], extra = [];
  for (const s of rs) { if (want.has(noKey(s.시료명))) matched.push(want.get(noKey(s.시료명))); else extra.push(s.시료명); }
  const orgGood = rs.every(s => orgOk(s.의뢰기관, caseDoc.의뢰기관));
  const missing = sampleNos.filter(n => !matched.includes(n));
  const level = matched.length && orgGood && !extra.length ? 'full' : 'partial';
  return { level, matched, missing, extra, orgGood };
}
