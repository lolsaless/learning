/* 검사의뢰 공문 추출기 v2.0 — 확장 엔진
   HWPX 첨부 시료 목록 · 시행(결과 알림) 공문 · 시험성적서 PDF 해석 · 표준처리기한 · 사건 폴더 이름
   engine.js(OdtEngine) 다음에 읽는다. 브라우저·Node 공용. */
(function (root, factory) {
  const E = typeof module === 'object' && module.exports ? require('./engine.js') : root.OdtEngine;
  const api = factory(E);
  if (typeof module === 'object' && module.exports) module.exports = api; else root.OdtEngine2 = api;
})(typeof self !== 'undefined' ? self : this, function (E) {
'use strict';
const I = E._internal;
const { parseXML, kids, walk, findAll, squash, spacedName, rowOrigins, parseDate, unzipBytes, unzipList, expandNo, parseItems } = I;
const pad = n => String(n).padStart(2, '0');
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

/* ───────── 2. 첨부 시료 목록 → 행 ───────── */
// 공문 본문의 '붙임' 목록 (첨부 파일 이름 대조용)
function attachmentNames(paras) {
  const out = []; let on = false;
  for (const p of paras || []) {
    let t = p;
    const m = /^붙\s*임\s*(.*)$/.exec(t);
    if (m) { on = true; t = m[1]; } else if (!on) continue;
    const it = /^\s*(?:\d+\s*[.)]\s*)?(.+?)\s*(?:\d+\s*(?:부|매|개|건|식)\s*)?[.。]?\s*(?:끝\s*\.?)?\s*$/.exec(t);
    if (it && it[1]) out.push(it[1].replace(/\s*\(\s*별송\s*\)\s*/, '').trim());
    if (/끝\s*\.?\s*$/.test(p)) break;
  }
  return out.filter(Boolean);
}
const nameKey = s => squash(NFC(s)).replace(/\.[a-z0-9]+$/i, '').replace(/[^0-9a-z가-힣]/gi, '').toLowerCase();
// 첨부 파일이 공문 붙임 목록과 맞는지 (0~1)
function attachScore(fileName, names) {
  const k = nameKey(fileName); if (!k) return 0;
  let best = 0;
  for (const n of names) {
    const nk = nameKey(n); if (!nk) continue;
    if (nk === k || nk.includes(k) || k.includes(nk)) return 1;
    // 글자 2-gram 겹침
    const g = x => { const a = new Set(); for (let i = 0; i < x.length - 1; i++) a.add(x.slice(i, i + 2)); return a; };
    const A = g(k), B = g(nk); let hit = 0; A.forEach(x => { if (B.has(x)) hit++; });
    best = Math.max(best, hit / Math.max(1, Math.min(A.size, B.size)));
  }
  return best;
}
/* 공문 결과(result)에 첨부 HWPX 표를 붙여 시료 행을 만든다.
   - 의뢰항목 열이 있는 표 = 주 시료표 (engine.js와 같은 규칙으로 읽음)
   - 나머지 표에서 같은 이름의 행을 찾아 시군·지점 위치를 보충 */
function samplesFromAttachments(result, hwpxList) {
  const tables = [];
  for (const h of hwpxList) for (const g of h.parsed.grids) tables.push({ g, file: h.name });
  const sts = [], others = [];
  for (const t of tables) {
    let pick = null, hr = -1;
    for (let r = 0; r < Math.min(3, t.g.nrows); r++) { const os = rowOrigins(t.g, r); if (!os.some(o => /^items/.test(I.classify(o.text) || ''))) continue; pick = I.pickSampleCol(t.g, r); if (pick) { hr = r; break; } }
    if (pick) sts.push({ g: t.g, hr, sampleCol: pick.col, how: 'hwpx-' + pick.how, file: t.file }); else others.push(t);
  }
  if (!sts.length) return null;
  const res = I.rebuildResult(result, sts);
  // 보충 정보: 이름 → {시군, 위치}
  const extra = new Map();
  for (const t of others) {
    for (let hr = 0; hr < Math.min(3, t.g.nrows); hr++) {
      const heads = rowOrigins(t.g, hr), nameH = heads.find(o => I.classify(o.text) === 'sampleName');
      if (!nameH) continue;
      for (let r = hr + 1; r < t.g.nrows; r++) {
        const os = rowOrigins(t.g, r).filter(o => o.r === r || o.rs > 1);
        const nm = (t.g.G[r][nameH.c] || {}).text; if (!nm) continue;
        const info = [];
        for (const h of heads) { if (h === nameH || /^(연번|순번|번호)$/.test(squash(h.text))) continue; const v = (t.g.G[r][h.c] || {}).text; if (v) info.push(spacedName(h.text) + ': ' + v.replace(/\n/g, ' ')); }
        extra.set(squash(nm), info.join(' / '));
      }
      break;
    }
  }
  for (const row of res.rows) {
    // 줄바꿈된 이름 '용암교 (구 세월교)' → '용암교(구 세월교)'
    row.시료번호 = row.시료번호.replace(/\s+\(/g, '(');
    const ex = extra.get(squash(row.시료번호)) || extra.get(squash(row.시료번호원문 || ''));
    if (ex) { row.채취지점 = row.채취지점 || ex; }
    if (!row.시료채취일 || /확인/.test(row.시료채취일)) {/* 공문 본문 규칙 유지 */}
  }
  res.warnings = res.warnings.filter(w => w !== '시료표 미인식');
  res.source = { type: 'hwpx', files: [...new Set(sts.map(s => s.file))], how: sts.map(s => s.how) };
  res.rows.forEach(r => { r.시료출처 = '첨부(HWPX)'; });
  return res;
}
// 사용자가 직접 입력(붙여넣기)한 시료 목록 → 행.  lines: [{no, items, std, date, note}]
function samplesFromManual(result, list) {
  const G = [], head = ['시료번호', '검사항목', '기준', '시료채취일', '비고'];
  const mk = (r, c, t) => ({ r, c, rs: 1, cs: 1, lines: String(t || '').split('\n').map(x => x.trim()).filter(Boolean), text: String(t || '').trim(), nested: false });
  G[0] = head.map((h, c) => mk(0, c, h));
  list.forEach((x, k) => { G[k + 1] = [x.no, x.items, x.std, x.date, x.note].map((v, c) => mk(k + 1, c, v)); });
  const g = { G, nrows: G.length, ncols: head.length };
  const res = I.rebuildResult(result, [{ g, hr: 0, sampleCol: G[0][0], how: 'manual' }]);
  res.warnings = res.warnings.filter(w => w !== '시료표 미인식' && !/^제목 시료/.test(w));
  res.rows.forEach(r => { r.시료출처 = '직접 입력'; r.확인필요 = (r.확인필요 || '').split(' / ').filter(w => w && w !== '시료표 미인식' && !/^제목 시료/.test(w)).join(' / '); });
  res.source = { type: 'manual' };
  return res;
}
// 붙여넣기 텍스트(엑셀 복사: 탭 구분) → 목록. 첫 줄이 머리글이면 열 이름으로 맞춤
function parsePastedSamples(text) {
  const rows = String(text || '').replace(/\r/g, '').split('\n').map(l => l.split('\t')).filter(r => r.some(c => c.trim()));
  if (!rows.length) return [];
  let map = { no: 0, items: 1, std: 2, date: 3, note: 4 }, start = 0;
  const h = rows[0].map(c => I.classify(c));
  if (h.some(f => f === 'sampleNo' || f === 'sampleName' || /^items/.test(f || ''))) {
    map = { no: -1, items: -1, std: -1, date: -1, note: -1 };
    h.forEach((f, i) => { if ((f === 'sampleNo' || f === 'sampleName') && map.no < 0) map.no = i; else if (/^items/.test(f || '') && map.items < 0) map.items = i; else if (f === 'std' && map.std < 0) map.std = i; else if (f === 'date' && map.date < 0) map.date = i; else if (f === 'note' && map.note < 0) map.note = i; });
    start = 1;
  }
  const out = []; let last = null;
  for (const r of rows.slice(start)) {
    const g = k => map[k] >= 0 ? (r[map[k]] || '').trim() : '';
    const x = { no: g('no'), items: g('items'), std: g('std'), date: g('date'), note: g('note') };
    if (!x.no && last) { if (x.items) last.items = x.items; continue; } // 병합 칸 복사 시 빈 칸
    if (!x.items && last) x.items = last.items;                          // 항목 칸이 병합된 경우 위 값 사용
    if (x.no) { out.push(x); last = x; }
  }
  return out;
}

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

/* ───────── 4. 시험성적서 PDF ───────── */
// pdf.js 텍스트 항목 [{s,x,y,w,h}] → 줄 [{y, cells:[{s,x0,x1}], text}]
function pdfLines(items) {
  const its = items.filter(t => t.s !== '').slice().sort((a, b) => a.y - b.y || a.x - b.x);
  const L = [];
  for (const t of its) {
    let l = null; for (let k = L.length - 1; k >= 0 && k >= L.length - 3; k--) if (Math.abs(L[k].y - t.y) <= Math.max(2.2, t.h * 0.3)) { l = L[k]; break; }
    if (!l) { l = { y: t.y, it: [] }; L.push(l); } l.it.push(t);
  }
  L.sort((a, b) => a.y - b.y);
  return L.map(l => {
    l.it.sort((a, b) => a.x - b.x);
    const cells = []; let cur = null, end = null;
    for (const t of l.it) {
      const h = t.h || 10, blank = t.s.trim() === '';
      const gap = end == null ? 0 : t.x - end;
      if (!cur || (blank && t.w > h * 2.5) || gap > h * 2.5) { if (cur && cur.s.trim()) cells.push(cur); cur = { s: '', x0: blank ? t.x + t.w : t.x, x1: t.x }; if (blank) { end = t.x + t.w; continue; } }
      else if (gap > h * 0.25 && !blank) cur.s += ' ';
      cur.s += t.s; cur.x1 = t.x + t.w; end = t.x + t.w;
    }
    if (cur && cur.s.trim()) cells.push(cur);
    cells.forEach(c => { c.s = c.s.replace(/\s+/g, ' ').trim(); });
    return { y: l.y, cells, text: cells.map(c => c.s).join(' ⎮ ') };
  });
}
const spaced = w => w.split('').map(ch => ch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s*');
function field(text, label, until) {
  const re = new RegExp(spaced(label) + '\\s*[:：]?\\s*(.*?)\\s*(?:⎮|$' + (until ? '|' + until.map(spaced).join('|') : '') + ')');
  const m = re.exec(text); return m ? m[1].trim() : '';
}
const kDate = s => { const m = /(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일/.exec(s || ''); return m ? `${m[1]}-${pad(m[2])}-${pad(m[3])}` : ''; };
function parseReportPage(lines) {
  const all = lines.map(l => l.text).join('\n');
  const fl = label => { const l = lines.find(x => new RegExp('^' + spaced(label)).test(x.text) || x.text.includes('⎮ ' + label) || new RegExp('⎮\\s*' + spaced(label)).test(x.text)); return l ? l.text : ''; };
  const no = (/접\s*수\s*번\s*호\s*([0-9]{6,}-[0-9]+)/.exec(all) || [])[1] || '';
  if (!no) return null;
  const L1 = fl('접수번호'), L2 = fl('시료명'), L3 = fl('공문번호'), L4 = fl('시험기간'), L5 = fl('시료채취자');
  const r = {
    접수번호: no,
    의뢰기관: field(L1, '의뢰기관', ['성적서페이지']),
    시료명: field(L2, '시료명', ['검체유형']),
    검체유형: field(L2, '검체유형'),
    공문번호: field(L3, '공문번호', ['시료접수일']),
    시료접수일: kDate(field(L3, '시료접수일', ['성적서용도'])),
    성적서용도: field(L3, '성적서용도'),
    시험기간: (() => { const m = /시\s*험\s*기\s*간\s*(\d{4}\s*년[^~]*?일)\s*~\s*(\d{4}\s*년.*?일)/.exec(L4); return m ? kDate(m[1]) + '~' + kDate(m[2]) : ''; })(),
    시험방법: field(L4, '시험방법'),
    시료채취자: field(L5, '시료채취자'),
    결과: [], 판정: '',
  };
  const page = /페이지\s*\(\s*(\d+)\s*\)\s*\/\s*총\s*\(\s*(\d+)\s*\)/.exec(all); if (page) { r.페이지 = +page[1]; r.총페이지 = +page[2]; }
  const hi = lines.findIndex(l => l.cells.length >= 3 && /^검사\s*항목$/.test(l.cells[0].s) && l.cells.some(c => /^결\s*과$/.test(c.s)));
  if (hi >= 0) {
    const H = lines[hi].cells.map(c => ({ name: c.s.replace(/\s+/g, ''), xc: (c.x0 + c.x1) / 2, x0: c.x0 }));
    for (let k = hi + 1; k < lines.length; k++) {
      const l = lines[k];
      if (/^판\s*정$/.test(l.cells[0] ? l.cells[0].s : '')) { r.판정 = l.cells.slice(1).map(c => c.s).join(' '); break; }
      if (!l.cells.length) continue;
      const rec = {};
      for (const c of l.cells) {
        // 줄의 첫 칸은 항목명(왼쪽 정렬), 나머지는 가장 가까운 열 중심
        let best = H[0], bd = Infinity; const xc = (c.x0 + c.x1) / 2;
        if (!(c === l.cells[0] && c.x0 < (H[0].xc + H[1].xc) / 2)) for (const h of H.slice(1)) { const d = Math.abs(h.xc - xc); if (d < bd) { bd = d; best = h; } }
        rec[best.name] = rec[best.name] ? rec[best.name] + ' ' + c.s : c.s;
      }
      if (!rec['검사항목']) { const prev = r.결과[r.결과.length - 1]; if (prev) Object.keys(rec).forEach(key => { prev[key] = (prev[key] ? prev[key] + ' ' : '') + rec[key]; }); continue; }
      r.결과.push({ 항목: rec['검사항목'], 기준: rec['기준'] && rec['기준'] !== '-' ? rec['기준'] : '', 결과: rec['결과'] || '', 단위: rec['단위'] || '' });
    }
  }
  r.판정 = r.판정.replace(/\s*[:：]?\s*『.*$/, '').trim() || r.판정;
  return r;
}
// 한 PDF의 모든 쪽 → 시료(접수번호) 단위로 묶음
function parseReportPdf(pages, fileName) {
  const map = new Map(), order = [];
  pages.forEach((pg, i) => {
    const r = parseReportPage(pdfLines(pg.items)); if (!r) return;
    const key = r.접수번호 + '|' + r.시료명;
    if (!map.has(key)) { map.set(key, { ...r, 쪽: [i + 1] }); order.push(key); }
    else { const a = map.get(key); a.결과.push(...r.결과); a.쪽.push(i + 1); if (r.판정) a.판정 = a.판정 && a.판정 !== r.판정 ? a.판정 + ' / ' + r.판정 : r.판정; }
  });
  const samples = order.map(k => map.get(k));
  samples.forEach(s => { s.결과.forEach(x => { x.항목명 = I.normItem(x.항목) || normReportItem(x.항목); }); });
  return { 파일명: NFC(fileName), 공문번호: [...new Set(samples.map(s => s.공문번호))].join(', '), 의뢰기관: samples[0] ? samples[0].의뢰기관 : '',
    samples, 중간: /중간/.test(NFC(fileName)), 부적합: samples.some(s => /부적합/.test(s.판정)) };
}
const REPORT_ITEM = { '총질소': 'T-N', '총인': 'T-P', '노말헥산추출물질(광유류)': 'n-H(광)', '노말헥산추출물질(동식물유지류)': 'n-H(동식)', '노말헥산추출물질(동식물유류)': 'n-H(동식)',
  '생물화학적산소요구량': 'BOD', '화학적산소요구량': 'COD', '부유물질': 'SS', '총유기탄소': 'TOC', '수소이온농도': 'pH', '음이온계면활성제': 'ABS', '클로로필-a': '클로로필a', '클로로필a': '클로로필a' };
function normReportItem(t) { const k = squash(t); return REPORT_ITEM[k] || I.normItem(k.replace(/\(.*\)$/, '')) || t; }

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

/* ───────── 7. 공휴일 ───────── */
// 내장 목록 (인터넷에서 못 가져올 때 사용). 출처: 우주항공청 특일정보 기반 공개 목록(holidays.hyunbin.page), 2026-10 확인
const HOLIDAYS_BUILTIN = {
  2026: { '2026-01-01': '신정', '2026-02-16': '설날 연휴', '2026-02-17': '설날', '2026-02-18': '설날 연휴', '2026-03-01': '삼일절', '2026-03-02': '대체공휴일(삼일절)',
    '2026-05-01': '노동절', '2026-05-05': '어린이날', '2026-05-24': '부처님오신날', '2026-05-25': '대체공휴일(부처님오신날)', '2026-06-03': '전국동시지방선거',
    '2026-06-06': '현충일', '2026-07-17': '제헌절', '2026-08-15': '광복절', '2026-08-17': '대체공휴일(광복절)', '2026-09-24': '추석 연휴', '2026-09-25': '추석',
    '2026-09-26': '추석 연휴', '2026-10-03': '개천절', '2026-10-05': '대체공휴일(개천절)', '2026-10-09': '한글날', '2026-12-25': '기독탄신일' },
  2027: { '2027-01-01': '신정', '2027-02-06': '설날 연휴', '2027-02-07': '설날', '2027-02-08': '설날 연휴', '2027-02-09': '대체공휴일(설날)', '2027-03-01': '삼일절',
    '2027-05-01': '노동절', '2027-05-03': '대체공휴일(노동절)', '2027-05-05': '어린이날', '2027-05-13': '부처님오신날', '2027-06-06': '현충일',
    '2027-07-17': '제헌절', '2027-07-19': '대체공휴일(제헌절)', '2027-08-15': '광복절', '2027-08-16': '대체공휴일(광복절)', '2027-09-14': '추석 연휴',
    '2027-09-15': '추석', '2027-09-16': '추석 연휴', '2027-10-03': '개천절', '2027-10-04': '대체공휴일(개천절)', '2027-10-09': '한글날',
    '2027-10-11': '대체공휴일(한글날)', '2027-12-25': '기독탄신일', '2027-12-27': '대체공휴일(기독탄신일)' },
};
// 인터넷 응답 → {date: name}.  지원: holidays.hyunbin.page ({"2026-01-01":["신정"]}), date.nager.at ([{date, localName}])
function parseHolidayJson(j) {
  const out = {};
  if (Array.isArray(j)) { for (const x of j) if (x && x.date) out[x.date] = x.localName || x.name || '공휴일'; }
  else if (j && typeof j === 'object') { for (const [k, v] of Object.entries(j)) if (/^\d{4}-\d{2}-\d{2}$/.test(k)) out[k] = Array.isArray(v) ? v.join(', ') : String(v || '공휴일'); }
  return out;
}

/* ───────── 8. 폴더 이름 ───────── */
function safeName(s, max) {
  let t = NFC(s).replace(/[\\/:*?"<>|\u0000-\u001f]/g, ' ').replace(/\s+/g, ' ').trim();
  if (max && t.length > max) t = t.slice(0, max).trim();
  return t.replace(/[. ]+$/, '');
}
// "의뢰기관_의뢰공문 제목_시행(공문번호)"
function caseFolderName(doc) {
  const org = safeName(doc.의뢰기관 || doc.상단기관명 || '기관미상', 20);
  const no = safeName(doc.시행 || '번호없음', 40);
  const title = safeName(doc.제목 || String(doc.파일명 || '').replace(/\.odt$/i, ''), 80);
  return `${org}_${title}_${no}`;
}

return { parseHwpx, hwpGrid, hwpxHtml, attachmentNames, attachScore, samplesFromAttachments, samplesFromManual, parsePastedSamples,
  isReply, parseReply, pdfLines, parseReportPage, parseReportPdf, normReportItem, matchReply, matchReport, noKey, orgOk,
  STD_DAYS, stdDaysTable, deadline, remaining, sampleDeadline, isWorkday, ymd, toDate, addDays,
  HOLIDAYS_BUILTIN, parseHolidayJson, safeName, caseFolderName, VERSION: '2.0' };
});
