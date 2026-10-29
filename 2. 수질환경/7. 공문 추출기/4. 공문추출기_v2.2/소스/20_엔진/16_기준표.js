/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/16_기준표.js] 기준표(지역구분×항목)
   하는 일 : 기준표.xlsx/csv 읽기, 빈 기준 채우기, 양식용 빈칸 목록
   주요 이름: parseStdTable, lookupStd, applyStdTable, missingStdPairs, readXlsxRows, parseCsv
   이럴 때 고침: 기준표 해석 규칙
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───────── 14. 기준표 (지역구분 × 항목 → 기준값) ───────── */
function refreshStdText(row) {
  const its = row._items || [];
  const withStd = its.filter(i => i.std);
  row.기준 = withStd.map(i => `${i.name} ${i.std}`).join(', ');
  const srcs = new Set(withStd.map(i => i.src));
  row.기준출처 = !withStd.length ? '' : (srcs.size > 1 ? '공문+기준표' : [...srcs][0]) + (withStd.length < its.length ? '(일부)' : '');
}
const normRegionTok = t => squash(t).replace(/지역$/, '');
function regionTokens(region) { return String(region || '').split(/[,\/()（）·]+/).map(normRegionTok).filter(Boolean); }
// rows2d: 첫 행 머리글(지역구분·항목·기준값·단위)
function parseStdTable(rows2d) {
  if (!rows2d || !rows2d.length) return [];
  let hr = rows2d.findIndex(r => r.some(c => squash(c) === '항목'));
  if (hr < 0) return [];
  const H = rows2d[hr].map(squash);
  const ci = k => H.findIndex(h => h.includes(k));
  const iR = ci('지역'), iI = H.findIndex(h => h === '항목' || h.includes('항목')), iV = ci('기준'), iU = ci('단위');
  const out = [];
  for (const r of rows2d.slice(hr + 1)) {
    const item = (r[iI] || '').trim(), val = (r[iV] || '').toString().trim();
    if (!item || !val) continue;
    const region = iR >= 0 ? (r[iR] || '').trim() : '';
    out.push({ region, key: normRegionTok(region), item: normItem(item) || item, value: val, unit: iU >= 0 ? (r[iU] || '').trim() : '' });
  }
  return out;
}
function lookupStd(table, itemName, region) {
  const toks = regionTokens(region), whole = squash(region).replace(/지역/g, '');
  let best = null, bestScore = -1;
  for (const e of table) {
    if (e.item !== itemName) continue;
    let score = -1;
    if (!e.key || e.key === '*' || e.key === '전체') score = 0;
    else if (toks.includes(e.key)) score = 10 + e.key.length;
    else if (e.key.length > 2 && whole.includes(e.key.replace(/지역/g, ''))) score = 5 + e.key.length;
    if (score > bestScore) { best = e; bestScore = score; }
  }
  return best;
}
function applyStdTable(results, table) {
  let filled = 0;
  for (const r of results) for (const row of r.rows) {
    for (const it of row._items || []) {
      it.std = it.stdDoc; it.src = it.stdDoc ? '공문' : '';
      if (!it.stdDoc && table && table.length) {
        const e = lookupStd(table, it.name, it.region || row.지역구분);
        if (e) { it.std = e.value; it.src = '기준표'; filled++; }
      }
    }
    refreshStdText(row);
  }
  return filled;
}
function missingStdPairs(results) {
  const map = new Map();
  for (const r of results) if (!r.duplicate) for (const row of r.rows) for (const it of row._items || []) {
    if (it.std) continue;
    const region = it.region || row.지역구분 || '';
    const k = region + '\u0001' + it.name;
    if (!map.has(k)) map.set(k, { 지역구분: region, 항목: it.name, 예시: row.시료번호, 건수: 0 });
    map.get(k).건수++;
  }
  return [...map.values()].sort((a, b) => (a.지역구분 + a.항목).localeCompare(b.지역구분 + b.항목, 'ko'));
}

/* ───────── 15. 기준표 파일 읽기 (xlsx / csv) ───────── */
async function readXlsxRows(bytes, inflateRaw) {
  const ss = await unzipEntry(bytes, 'xl/sharedStrings.xml', inflateRaw, true);
  const shared = ss ? findAll(parseXML(ss), 'si').map(si => findAll(si, 't').map(textAll).join('')) : [];
  let sheet = await unzipEntry(bytes, 'xl/worksheets/sheet1.xml', inflateRaw, true);
  if (!sheet) throw new Error('첫 번째 시트를 찾을 수 없음');
  const rows = [];
  for (const row of findAll(parseXML(sheet), 'row')) {
    const arr = [];
    for (const c of kids(row, 'c')) {
      const ref = c.a.r || ''; const letters = (/^[A-Z]+/.exec(ref) || ['A'])[0];
      let ci = 0; for (const ch of letters) ci = ci * 26 + (ch.charCodeAt(0) - 64); ci--;
      let v = '';
      const t = c.a.t;
      if (t === 'inlineStr') v = findAll(c, 't').map(textAll).join('');
      else { const ve = kids(c, 'v')[0]; v = ve ? textAll(ve) : ''; if (t === 's') v = shared[+v] || ''; }
      arr[ci < 0 ? arr.length : ci] = v;
    }
    rows.push(Array.from(arr, x => x == null ? '' : String(x)));
  }
  return rows;
}
function decodeText(bytes) {
  try { return new TextDecoder('utf-8', { fatal: true }).decode(bytes).replace(/^﻿/, ''); }
  catch (e) { return new TextDecoder('euc-kr').decode(bytes); } // 엑셀 기본 CSV(한글 Windows)
}
function parseCsv(text) {
  const rows = []; let row = [], cur = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) { if (ch === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += ch; }
    else if (ch === '"') q = true;
    else if (ch === ',') { row.push(cur); cur = ''; }
    else if (ch === '\n' || ch === '\r') { if (ch === '\r' && text[i + 1] === '\n') i++; row.push(cur); rows.push(row); row = []; cur = ''; }
    else cur += ch;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  return rows;
}
