/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/21_첨부_HWPX.js] 첨부 HWPX(한글) 읽기
   하는 일 : HWPX 표·문단 읽기(병합 칸), 화면·이력 문서용 HTML 그리기
   주요 이름: parseHwpx, hwpGrid, hwpxHtml
   이럴 때 고침: HWPX 표를 못 읽거나 보기 모양
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
const NFC = s => String(s || '').normalize('NFC');

/* ───────── 1. HWPX (한글 문서) ───────── */
function hwpParaText(p) {
  let out = '';
  walk(p, x => {
    if (x.n === 'tbl') return false;            // 문단 안 표는 따로
    if (x.n === 't') { out += x.c.map(y => typeof y === 'string' ? y : (y.n === 'tab' ? '\t' : y.n === 'lineBreak' ? '\n' : '')).join(''); return false; }
    if (x.n === 'lineBreak') out += '\n';
  });
  return out;
}
function hwpCellLines(tc) {
  const lines = [];
  const sub = kids(tc).find(x => x.n === 'subList') || tc;
  for (const p of kids(sub)) if (p.n === 'p') hwpParaText(p).split('\n').forEach(t => lines.push(t));
  return lines.map(t => t.replace(/\s+/g, ' ').trim()).filter(Boolean);
}
function hwpGrid(tbl) {
  const G = []; let nrows = +tbl.a.rowCnt || 0, ncols = +tbl.a.colCnt || 0;
  for (const tr of kids(tbl)) {
    if (tr.n !== 'tr') continue;
    for (const tc of kids(tr)) {
      if (tc.n !== 'tc') continue;
      const addr = kids(tc).find(x => x.n === 'cellAddr'), span = kids(tc).find(x => x.n === 'cellSpan');
      const r = addr ? +addr.a.rowAddr : 0, c = addr ? +addr.a.colAddr : 0;
      const o = { r, c, rs: span ? +span.a.rowSpan || 1 : 1, cs: span ? +span.a.colSpan || 1 : 1, lines: hwpCellLines(tc), nested: findAll(tc, 'tbl').length > 0 };
      o.text = o.lines.join('\n');
      for (let dr = 0; dr < o.rs; dr++) for (let dc = 0; dc < o.cs; dc++) { G[r + dr] = G[r + dr] || []; if (!G[r + dr][c + dc]) G[r + dr][c + dc] = o; }
      nrows = Math.max(nrows, r + o.rs); ncols = Math.max(ncols, c + o.cs);
    }
  }
  for (let r = 0; r < nrows; r++) G[r] = G[r] || [];
  return { G, nrows, ncols };
}
async function parseHwpx(bytes, inflateRaw) {
  const names = unzipList(bytes).filter(n => /^Contents\/section\d+\.xml$/i.test(n)).sort((a, b) => +a.match(/\d+/)[0] - +b.match(/\d+/)[0]);
  const grids = [], paras = [];
  for (const n of names) {
    const xml = new TextDecoder('utf-8').decode(await unzipBytes(bytes, n, inflateRaw));
    const root = parseXML(xml);
    for (const t of findAll(root, 'tbl')) if (!findAll(t, 'tbl').length) grids.push(hwpGrid(t));
    walk(root, x => { if (x.n === 'tbl') return false; if (x.n === 'p') { const t = hwpParaText(x).replace(/\s+/g, ' ').trim(); if (t) paras.push(t); return false; } });
  }
  let preview = null;
  try { preview = await unzipBytes(bytes, 'Preview/PrvImage.png', inflateRaw, true); } catch (e) { preview = null; }
  return { grids, paras, preview };
}
// HWPX 문단·표를 간단한 HTML로 (원본 보기·이력 문서 이미지용)
function hwpxHtml(h, title) {
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  let out = `<div class="odt-page hwpx-page" style="width:21cm;background:#fff;color:#000;padding:1.2cm 1.4cm;font-family:'Malgun Gothic',sans-serif;font-size:10.5pt">`;
  if (title) out += `<div style="font-size:9pt;color:#666;margin-bottom:8px">${esc(title)}</div>`;
  const used = new Set();
  for (const p of h.paras) { if (used.has(p)) continue; used.add(p); }
  // 표 밖 문단 (표 안 텍스트와 중복 제외)
  const inTables = new Set(); h.grids.forEach(g => g.G.forEach(row => row.forEach(o => o && o.lines.forEach(l => inTables.add(squash(l))))));
  h.paras.filter(p => !inTables.has(squash(p))).forEach(p => { out += `<p style="margin:4px 0">${esc(p)}</p>`; });
  for (const g of h.grids) {
    out += '<table style="border-collapse:collapse;width:100%;margin:8px 0;font-size:9.5pt">';
    for (let r = 0; r < g.nrows; r++) {
      out += '<tr>';
      for (let c = 0; c < g.ncols; c++) {
        const o = g.G[r][c]; if (!o || o.r !== r || o.c !== c) continue;
        out += `<td${o.rs > 1 ? ` rowspan="${o.rs}"` : ''}${o.cs > 1 ? ` colspan="${o.cs}"` : ''} style="border:1px solid #444;padding:3px 5px;vertical-align:middle;text-align:center${r === 0 ? ';background:#eee;font-weight:bold' : ''}">${o.lines.map(esc).join('<br>')}</td>`;
      }
      out += '</tr>';
    }
    out += '</table>';
  }
  return out + '</div>';
}
