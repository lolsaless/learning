/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/03_표격자_날짜.js] 표 격자·날짜
   하는 일 : 병합 칸을 펼친 표 격자, 날짜 글자 해석
   주요 이름: buildGrid, rowOrigins, parseDate, allDates
   이럴 때 고침: 날짜 표기 형식 추가
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───────── 4. 표 → 격자 (병합 처리) ───────── */
function tableRows(tbl) {
  const rows = [];
  (function collect(e) {
    for (const x of kids(e)) {
      if (x.n === 'table-row') { const rep = Math.min(+x.a['number-rows-repeated'] || 1, 3); for (let k = 0; k < rep; k++) rows.push(x); }
      else if (x.n === 'table-header-rows' || x.n === 'table-rows' || x.n === 'table-row-group') collect(x);
    }
  })(tbl);
  return rows;
}
function buildGrid(tbl) {
  const rows = tableRows(tbl), G = [];
  let ncols = 0;
  rows.forEach((row, r) => {
    G[r] = G[r] || []; let c = 0;
    for (const cell of kids(row)) {
      if (cell.n !== 'table-cell' && cell.n !== 'covered-table-cell') continue;
      const rep = Math.min(+cell.a['number-columns-repeated'] || 1, 64);
      for (let k = 0; k < rep; k++, c++) {
        if (cell.n !== 'table-cell') continue;
        if (G[r][c]) continue;
        const o = { r, c, rs: +cell.a['number-rows-spanned'] || 1, cs: +cell.a['number-columns-spanned'] || 1,
          lines: blockLines(cell), nested: has(cell, 'table') };
        o.text = o.lines.join('\n');
        for (let dr = 0; dr < o.rs; dr++) for (let dc = 0; dc < o.cs; dc++) {
          G[r + dr] = G[r + dr] || []; if (!G[r + dr][c + dc]) G[r + dr][c + dc] = o;
        }
      }
      ncols = Math.max(ncols, c);
    }
  });
  return { G, nrows: rows.length, ncols };
}
function rowOrigins(grid, r) {
  const out = [], seen = new Set();
  for (const o of grid.G[r] || []) if (o && !seen.has(o)) { seen.add(o); out.push(o); }
  return out;
}
const gridText = grid => grid.G.map((_, r) => rowOrigins(grid, r).map(o => o.text).join('|')).join('\n');

/* ───────── 5. 날짜 ───────── */
const DATE_RE = /(?:(\d{4})|'(\d{2}))\s*(?:[.\-\/]|년)\s*(\d{1,2})\s*(?:[.\-\/]|월)\s*(\d{1,2})(?!\d)\s*(?:\.|일)?/;
const pad = n => String(n).padStart(2, '0');
function parseDate(s) {
  if (!s) return null;
  const m = DATE_RE.exec(s); if (!m) return null;
  const y = m[1] || ('20' + m[2]), mo = +m[3], d = +m[4];
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
  const rest = s.slice(m.index + m[0].length);
  const t = /(\d{1,2})\s*:\s*(\d{2})/.exec(rest);
  return { date: `${y}-${pad(mo)}-${pad(d)}`, time: t ? `${pad(t[1])}:${t[2]}` : '' };
}
function allDates(s) {
  const re = new RegExp(DATE_RE.source, 'g'), out = []; let m;
  while ((m = re.exec(s))) { const p = parseDate(m[0]); if (p) out.push({ ...p, index: m.index, end: m.index + m[0].length }); }
  return out;
}
