/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/06_대조_처리기한_화면.js] 화면용 대조·처리기한
   하는 일 : 공문마다 시행공문·성적서 짝 붙이기(성적서의 검체유형 대·중·소분류를 시료 행에 넣음), 시료접수일·처리기한·색 계산
   주요 이름: matchDoc, readyToFinish, caseRecv, rowDue, dueClass, remText, docDueMin
   이럴 때 고침: 진행 표시·기한 색 규칙
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 대조: 의뢰공문 ↔ 시행공문 ↔ 성적서 ───── */
function matchDoc(d, inbox) {
  d.match = { replies: [], reports: [], got: 0, total: 0, extra: [], replyOk: false, reportState: 'none' };
  if (!d.result) return;
  const doc = d.result.doc, nos = d.result.rows.map(r => r.시료번호).filter(Boolean);
  const replies = [], reports = [];
  if (!d.C.shared) for (const x of d.C.replies) replies.push({ ...x, inCase: true, score: 1 });
  for (const x of inbox.replies || []) { const s = E2.matchReply(doc, x.info); if (s > 0) { replies.push({ ...x, score: s }); (x.usedBy = x.usedBy || new Set()).add(d.key); } }
  if (!d.C.shared) for (const x of d.C.reports) reports.push({ ...x, inCase: true, m: E2.matchReport(doc, nos, x.rep) });
  for (const x of inbox.reports || []) { const m = E2.matchReport(doc, nos, x.rep); if (m.level !== 'none') { reports.push({ ...x, m }); (x.usedBy = x.usedBy || new Set()).add(d.key); } }
  const got = new Set(); reports.forEach(x => x.m.matched.forEach(n => got.add(n)));
  const extra = [...new Set(reports.flatMap(x => x.m.extra))], orgBad = reports.some(x => x.m.orgGood === false && x.m.level !== 'none');
  d.match = { replies, reports, got: got.size, total: nos.length, extra, orgBad,
    replyOk: replies.some(x => x.score === 1),
    reportState: !reports.length ? 'none' : (nos.length && got.size === nos.length && !extra.length && !orgBad ? 'full' : 'partial') };
  for (const r of d.result.rows) {
    r._rep = null;
    for (const k of SAMPLE_TYPE_KEYS) r[k] = '';
    for (const x of reports) {
      const s = x.rep.samples.find(s => E2.noKey(s.시료명) === E2.noKey(r.시료번호) && (x.inCase || E2.noKey(s.공문번호) === E2.noKey(doc.시행)));
      if (s) { r._rep = { s, f: x.f }; for (const k of SAMPLE_TYPE_KEYS) r[k] = s[k] || ''; break; }
    }
  }
}
const readyToFinish = d => d.match && d.match.replyOk && d.match.reportState === 'full';

/* ───── 처리기한 ───── */
function caseRecv(d) {
  const n = peekNotes(d.key);
  if (n.recv) return { date: n.recv, est: false, before13: !!n.before13 };
  const dd = d.result && d.result.doc.접수일;
  return dd ? { date: dd, est: true, before13: !!n.before13 } : null;
}
function rowDue(d, r) {
  if (!d.result || !r.시료번호) return null;
  const rc = caseRecv(d); if (!rc) return null;
  const items = (r._items || []).map(i => i.name);
  if (!items.length) return null;
  const sd = E2.sampleDeadline(items, rc.date, state.hol, state.stdDays, { countReceiptDay: rc.before13, basis: state.settings.dueBasis, ...dayOpt() });
  sd.est = rc.est;
  sd.rem = sd.due ? E2.remaining(today(), sd.due, state.hol, dayOpt()) : null;
  return sd;
}
function dueClass(sd, finished) {
  if (!sd || !sd.rem || finished) return '';
  if (sd.rem.overdue) return 'due-over';
  if (sd.rem.days <= state.settings.imminent) return 'due-imm';
  if (sd.rem.days <= state.settings.soon) return 'due-soon';
  return '';
}
const remText = rem => !rem ? '' : rem.overdue ? `${-rem.days}일 초과` : rem.days === 0 ? '오늘 마감' : `D-${rem.days}`;
function docDueMin(d) {
  let best = null;
  if (d.result) for (const r of d.result.rows) { const sd = rowDue(d, r); if (sd && sd.due && (!best || sd.due < best.due)) best = sd; }
  return best;
}
