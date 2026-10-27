/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/14_접수공문_본문_제목.js] 본문 채취일·제목 대조
   하는 일 : 본문 문장에서 채취일 찾기, 제목의 시료 수·번호와 표 대조 경고
   주요 이름: bodyParagraphs, dateFromBody, titleCheck
   이럴 때 고침: 채취일을 못 찾거나 제목 경고가 잘못 날 때
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───────── 10. 본문 채취일 ───────── */
function bodyParagraphs(body) {
  const out = [];
  for (const x of kids(body)) {
    if (x.n === 'p' || x.n === 'h') { const t = inlineText(x).replace(/\s+/g, ' ').trim(); if (t) out.push(t); }
    else if (x.n === 'list' || x.n === 'list-item' || x.n === 'section') out.push(...bodyParagraphs(x));
  }
  return out;
}
function dateFromBody(paras) {
  const found = [];
  for (const p of paras) for (const d of allDates(p)) {
    const before = p.slice(Math.max(0, d.index - 25), d.index), after = p.slice(d.end, d.end + 45);
    if (/의뢰\s*(일|일자)/.test(before)) continue;
    if (/(채수|채취|채집)/.test(after) || /(채수|채취)[^.。]{0,15}$/.test(before)) found.push(d);
  }
  return found;
}

/* ───────── 11. 제목 대조 ───────── */
function titleCheck(title, samples, baseTotal) {
  const m = /[(\[]([^()\[\]]*\d[^()\[\]]*)[)\]]\s*$/.exec(title || '');
  if (!m || !samples.length) return '';
  const code = m[1];
  if (/^\s*(\d{4}\s*년\s*)?\d{1,2}\s*월(분)?\s*$|^\s*\d{4}\s*년(도)?\s*$|^\s*\d+\s*차\s*$/.test(code)) return ''; // v2.0: '(10월)'·'(2026년)'·'(3차)'는 시료번호가 아님
  let exp = null;
  const n = /등\s*(\d+)\s*건/.exec(code);
  if (n) exp = +n[1];
  else {
    const r = /(\d+)\s*~\s*(?:[0-9A-Za-z가-힣\-]*-)?(\d+)/.exec(code);
    if (r) exp = +r[2] - +r[1] + 1;
    else {
      const S = squash(samples[0].rawNo).replace(/\([A-Z]~[A-Z]\)/i, ''), C = squash(code);
      const x = new RegExp('^' + esc(S) + '-(\\d+)$').exec(C);
      if (x) exp = +x[1] - +(/(\d+)$/.exec(S) || [0, 0])[1] + 1;
      else if (C.replace(/-/g, '').includes(S.replace(/-/g, ''))) exp = 1;
      else return `제목 시료번호(${code})와 표 시료번호 다름`;
    }
  }
  return exp != null && exp !== baseTotal ? `제목 시료 수(${exp})와 표(${baseTotal}) 다름` : '';
}
