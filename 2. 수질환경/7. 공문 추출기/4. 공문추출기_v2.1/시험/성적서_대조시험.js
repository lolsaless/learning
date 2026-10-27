// 특이 공문·시행공문·시험성적서·대조 시험 (실제 자료 필요)
// 사용: node 시험/성적서_대조시험.js <의뢰공문폴더> <시행공문·성적서폴더> [특이공문폴더]
const { E, list, odt, pdfPages, check, summary } = require('./공통.js');
(async () => {
  const [qd, rd, sd] = process.argv.slice(2);
  if (!qd || !rd) { console.log('사용: node 시험/성적서_대조시험.js <의뢰공문폴더> <시행공문·성적서폴더> [특이공문폴더]'); process.exit(2); }
  if (sd) {
    console.log('[특이 공문 — 첨부 HWPX 시료 목록]');
    for (const f of list(sd, /\.odt$/i)) {
      const r = await odt(f), names = E.attachmentNames(r.doc.본문);
      const hw = []; for (const h of list(sd, /\.hwpx$/i)) if (E.attachScore(h.name, names) >= 0.6) hw.push({ name: h.name, parsed: await E.parseHwpx(require('fs').readFileSync(h.path), require('./공통.js').inflate) });
      const r2 = E.samplesFromAttachments(r, hw);
      check(!!r2 && r2.rows.length > 0, `${f.name}: 첨부 ${hw.length}개 → 시료 ${r2 ? r2.rows.length : 0}행`);
    }
  }
  console.log('\n[시행공문]');
  const replies = [];
  for (const f of list(rd, /\.odt$/i)) { const r = await odt(f); if (E.isReply(r)) replies.push(E.parseReply(r)); }
  check(replies.length && replies.every(x => x.관련공문번호), `시행공문 ${replies.length}건 모두 관련 공문번호 읽음`, replies.filter(x => !x.관련공문번호).map(x => x.파일명).join(', '));
  console.log('\n[시험성적서]');
  const reps = [];
  for (const f of list(rd, /\.pdf$/i)) {
    const R = E.parseReportPdf(await pdfPages(f.path), f.name); if (!R.samples.length) continue; reps.push(R);
    const n = +((/등\s*(\d+)\s*건/.exec(f.name) || [0, 1])[1]);
    if (!/중간/.test(f.name)) check(R.samples.length === n, `${f.name}: 시료 ${R.samples.length} (파일 이름 ${n}건)`);
  }
  console.log('\n[대조]');
  let full = 0, part = 0;
  for (const f of list(qd, /\.odt$/i)) {
    const r = await odt(f), nos = r.rows.map(x => x.시료번호).filter(Boolean);
    const mm = reps.map(p => E.matchReport(r.doc, nos, p)).filter(m => m.level !== 'none');
    if (!mm.length) continue;
    const got = new Set(); mm.forEach(m => m.matched.forEach(n => got.add(n)));
    const ok = got.size === nos.length && !mm.some(m => m.extra.length);
    ok ? full++ : part++;
    console.log(`  ${ok ? '일치' : '일부'}  ${r.doc.시행}  시료 ${got.size}/${nos.length}  시행공문 ${replies.filter(x => E.matchReply(r.doc, x) > 0).length}`);
  }
  console.log(`  → 완전 일치 ${full} · 일부 ${part}`);
  summary();
})();
