/* 검사의뢰 공문(ODT) 추출 엔진 v2.0 — 외부 라이브러리 없음 (브라우저·Node 공용) */
(function (global) {
'use strict';

/* ───────── 1. ZIP 읽기 ───────── */
// inflateRaw: (Uint8Array) => Promise<Uint8Array>   브라우저: DecompressionStream('deflate-raw') / Node: zlib
async function unzipEntry(bytes, name, inflateRaw, optional) {
  const b = await unzipBytes(bytes, name, inflateRaw, optional);
  return b == null ? null : new TextDecoder('utf-8').decode(b);
}
function unzipList(bytes) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let eocd = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 66000); i--) if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) return [];
  const n = dv.getUint16(eocd + 10, true), td = new TextDecoder('utf-8'), out = [];
  let p = dv.getUint32(eocd + 16, true);
  for (let i = 0; i < n; i++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break;
    const fl = dv.getUint16(p + 28, true), el = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true);
    out.push(td.decode(bytes.subarray(p + 46, p + 46 + fl))); p += 46 + fl + el + cl;
  }
  return out;
}
async function unzipBytes(bytes, name, inflateRaw, optional) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let eocd = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 66000); i--) {
    if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error('ZIP 구조가 아님(손상되었거나 ODT 파일이 아님)');
  const n = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const td = new TextDecoder('utf-8');
  for (let i = 0; i < n; i++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break;
    const method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true);
    const fl = dv.getUint16(p + 28, true), el = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true);
    const lo = dv.getUint32(p + 42, true);
    const fn = td.decode(bytes.subarray(p + 46, p + 46 + fl));
    if (fn === name) {
      const lfl = dv.getUint16(lo + 26, true), lel = dv.getUint16(lo + 28, true);
      const data = bytes.subarray(lo + 30 + lfl + lel, lo + 30 + lfl + lel + csize);
      return method === 0 ? data : await inflateRaw(data);
    }
    p += 46 + fl + el + cl;
  }
  if (optional) return null;
  throw new Error(name + ' 없음(ODT 파일이 아님)');
}

/* ───────── 2. XML 파서 (경량) ───────── */
const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" };
const dec = t => t.indexOf('&') < 0 ? t : t.replace(/&(#x[0-9a-fA-F]+|#\d+|\w+);/g, (m, e) =>
  e[0] === '#' ? String.fromCodePoint(e[1] === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10)) : (ENT[e] != null ? ENT[e] : m));
const local = q => { const k = q.indexOf(':'); return k < 0 ? q : q.slice(k + 1); };
function parseXML(s) {
  const root = { n: '#root', a: {}, c: [] }, st = [root]; let i = 0; const L = s.length;
  while (i < L) {
    const lt = s.indexOf('<', i); if (lt < 0) break;
    if (lt > i) st[st.length - 1].c.push(dec(s.slice(i, lt)));
    const c1 = s[lt + 1];
    if (c1 === '?') { i = s.indexOf('?>', lt) + 2; continue; }
    if (c1 === '!') {
      if (s.startsWith('<!--', lt)) i = s.indexOf('-->', lt) + 3;
      else if (s.startsWith('<![CDATA[', lt)) { const e = s.indexOf(']]>', lt); st[st.length - 1].c.push(s.slice(lt + 9, e)); i = e + 3; }
      else i = s.indexOf('>', lt) + 1;
      continue;
    }
    let j = lt + 1, q = null;
    for (; j < L; j++) { const ch = s[j]; if (q) { if (ch === q) q = null; } else if (ch === '"' || ch === "'") q = ch; else if (ch === '>') break; }
    let body = s.slice(lt + 1, j); i = j + 1;
    if (body[0] === '/') { if (st.length > 1) st.pop(); continue; }
    let self = false; if (body.endsWith('/')) { self = true; body = body.slice(0, -1); }
    const qn = /^\S+/.exec(body)[0];
    const a = {}, re = /([^\s=]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g; re.lastIndex = qn.length; let m;
    while ((m = re.exec(body))) a[local(m[1])] = dec(m[2] != null ? m[2] : m[3]);
    const node = { n: local(qn), a, c: [] };
    st[st.length - 1].c.push(node); if (!self) st.push(node);
  }
  return root;
}
const kids = (e, n) => e.c.filter(x => typeof x !== 'string' && (!n || x.n === n));
function walk(e, fn) { for (const x of e.c) { if (typeof x === 'string') continue; if (fn(x) === false) continue; walk(x, fn); } }
function findAll(e, n) { const r = []; walk(e, x => { if (x.n === n) r.push(x); }); return r; }
function has(e, n) { let f = false; walk(e, x => { if (x.n === n) f = true; }); return f; }
const textAll = e => e.c.map(x => typeof x === 'string' ? x : textAll(x)).join('');

/* ───────── 3. 텍스트 ───────── */
function inlineText(e) {
  let out = '';
  for (const x of e.c) {
    if (typeof x === 'string') { out += x.replace(/[\t\r\n ]+/g, ' '); continue; }
    switch (x.n) {
      case 's': out += ' '.repeat(+x.a.c || 1); break;
      case 'tab': out += '\t'; break;
      case 'line-break': out += '\n'; break;
      case 'frame': case 'note': case 'annotation': case 'table': break;
      default: out += inlineText(x);
    }
  }
  return out;
}
function blockLines(e) {
  const lines = [];
  for (const x of kids(e)) {
    if (x.n === 'p' || x.n === 'h') inlineText(x).split('\n').forEach(t => lines.push(t));
    else if (x.n === 'list' || x.n === 'list-item' || x.n === 'section') lines.push(...blockLines(x));
  }
  return lines.map(t => t.trim()).filter(Boolean);
}
const squash = t => (t || '').replace(/\s+/g, '');
function spacedName(t) {
  const toks = (t || '').trim().split(/\s+/).filter(Boolean);
  if (!toks.length) return '';
  return toks.every(x => x.length === 1) ? toks.join('') : toks.join(' ');
}

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

/* ───────── 6. 사전 (설정) — 새 표기가 나오면 여기에 한 줄 추가 ───────── */
const ITEM_DICT = {
  'bod': 'BOD', 'toc': 'TOC', 'ss': 'SS', 'cod': 'COD',
  't-n': 'T-N', 'tn': 'T-N', '총질소': 'T-N',
  't-p': 'T-P', 'tp': 'T-P', '총인': 'T-P',
  'n-h(광)': 'n-H(광)', 'n-h(광유류)': 'n-H(광)', '노르말헥산(광유류)': 'n-H(광)', '노르말헥산(광)': 'n-H(광)',
  'n-h(동식)': 'n-H(동식)', 'n-h(동식물유류)': 'n-H(동식)', '노르말헥산(동식물유류)': 'n-H(동식)',
  'abs': 'ABS', '음이온계면활성제': 'ABS',
  '생태독성': '생태독성', '색도': '색도', '철': '철', 'ph': 'pH', '수소이온농도': 'pH',
  '대장균군': '대장균군', '총대장균군': '총대장균군', '페놀류': '페놀류', '시안': '시안', '구리': '구리', '아연': '아연',
  '클로로필a': '클로로필a', '클로로필-a': '클로로필a', 'chl-a': '클로로필a', 'chl.a': '클로로필a', '엽록소a': '클로로필a',
  'do': 'DO', '용존산소': 'DO', '수온': '수온', '온도': '수온', '페놀': '페놀류', '노말헥산추출물질': 'n-H(광)', '노말헥산': 'n-H(광)',
  '납': '납', '카드뮴': '카드뮴', '크롬': '크롬', '6가크롬': '6가크롬', '비소': '비소', '수은': '수은', '망간': '망간', '불소': '불소',
};
const SIDO_TITLE = { '시': '시장', '군': '군수', '도': '도지사' };
const ORG_EXCEPTIONS = {}; // 예: { '○○사업소': { 의뢰기관: '○○시', 의뢰자: '○○시장' } }
const REGION_CODE = /^(가|나|다|라|청정|특례|특정)(지역)?$/;
function normItem(tok) { return ITEM_DICT[String(tok || '').toLowerCase().replace(/\s+/g, '')] || null; }

/* ───────── 7. 헤더 분류 ───────── */
function classify(h) {
  const t = squash(h);
  if (!t) return null;
  if (/^(연번|순번|번호|no\.?)$/i.test(t)) return 'seq';
  if (/(시료|검체|지시|의뢰)번호/.test(t)) return 'sampleNo';
  if (/^(시료|검체)(명|코드|no\.?|명칭)$/i.test(t)) return 'sampleName'; // v1.1: '시료명' 등 — 값이 번호 형태면 시료번호로 사용
  if (/^(소?하천|지점|정점|측정지점|채수지점|하천지점)(명|명칭)$/.test(t)) return 'sampleName'; // v2.0: 하천명 등 (첨부 시료 목록)
  if (/항목/.test(t)) return /기준/.test(t) ? 'itemsStd' : 'items';
  if (/(채취|채수)(일|일자|일시|날짜)/.test(t)) return 'date';
  if (/지역/.test(t)) return 'region';
  if (/기준/.test(t)) return 'std';
  if (/(시료량|채취량|채수량|수량)/.test(t) || t === '시료') return 'qty';
  if (/(업종|배출시설|성상|건물용도)/.test(t)) return 'industry';
  if (/지점/.test(t)) return 'point';
  if (/비고/.test(t)) return 'note';
  return 'other';
}

/* ───────── 8. 상단·하단 ───────── */
function parseHeader(tables) {
  for (const t of tables) {
    const g = buildGrid(t);
    let rRecv = -1, title = '', org = '';
    for (let r = 0; r < g.nrows; r++) {
      const os = rowOrigins(g, r);
      os.forEach((o, k) => {
        if (squash(o.text) === '수신' && rRecv < 0) rRecv = r;
        if (squash(o.text) === '제목' && os[k + 1]) title = os[k + 1].lines.join(' ');
      });
    }
    if (rRecv < 0 || !title) continue;
    for (let r = 0; r < rRecv; r++) for (const o of rowOrigins(g, r)) {
      const s = squash(o.text);
      if (s && /^[가-힣]+$/.test(s) && s.length <= 15) org = s;
    }
    return { org, title: title.trim() };
  }
  return null;
}
function parseFooter(tables) {
  for (const t of tables) {
    const g = buildGrid(t);
    let rSi = -1, rCoop = -1;
    for (let r = 0; r < g.nrows; r++) for (const o of rowOrigins(g, r)) {
      const s = squash(o.text);
      if (s === '시행' && rSi < 0) rSi = r;
      if (s === '협조자' && rCoop < 0) rCoop = r;
    }
    if (rSi < 0) continue;
    const f = {};
    const nextVals = (r, label) => { const os = rowOrigins(g, r).filter(o => o.text); const k = os.findIndex(o => squash(o.text) === label); return k < 0 ? [] : os.slice(k + 1).map(o => o.text.trim()); };
    let v = nextVals(rSi, '시행'); f.siNo = v[0] || ''; f.siDate = v[1] || '';
    v = nextVals(rSi, '접수'); f.rcNo = v[0] || ''; f.rcDate = v[1] || '';
    if (rCoop > 1) {
      const names = rowOrigins(g, rCoop - 1).filter(o => o.r === rCoop - 1 && o.text && !/결|\d/.test(o.text));
      const posRow = rowOrigins(g, rCoop - 2).filter(o => o.r === rCoop - 2 && o.text);
      f.drafter = names[0] ? names[0].text.trim() : '';
      f.drafterPos = posRow[0] ? posRow[0].text.trim() : '';
      for (let r = 0; r < rCoop - 2; r++) for (const o of rowOrigins(g, r)) if (o.text && !o.nested) f.sender = spacedName(o.text);
    }
    for (let r = 0; r < g.nrows; r++) {
      const os = rowOrigins(g, r).filter(o => o.text).map(o => o.text.trim());
      if (os[0] === '우') { f.zip = os[1] || ''; f.addr = os[2] || ''; }
      const k = os.indexOf('전화번호'); if (k >= 0) f.tel = os[k + 1] || '';
      const kf = os.indexOf('팩스번호'); if (kf >= 0) f.fax = os[kf + 1] || '';
      const em = os.find(x => x.includes('@')); if (em) f.email = em;
    }
    return f;
  }
  return null;
}
function senderFallback(body, posFirst) {
  const cells = [];
  walk(body, x => { if (x.n === 'table-cell' && !has(x, 'table')) { const t = blockLines(x).join(' '); if (t) cells.push(t); return false; } });
  const k = cells.findIndex(t => squash(t) === squash(posFirst));
  return k > 0 ? spacedName(cells[k - 1]) : '';
}
function deriveOrg(orgTop, addr) {
  if (ORG_EXCEPTIONS[orgTop]) return ORG_EXCEPTIONS[orgTop];
  let org = '';
  if (/^[가-힣]{1,4}(시|군)$/.test(orgTop) || /^[가-힣]{1,3}도$/.test(orgTop)) org = orgTop;
  else { const m = /(?:^|\s)([가-힣]{1,4}(?:시|군))(?=\s)/.exec(addr || ''); if (m) org = m[1]; }
  if (!org) return { 의뢰기관: orgTop, 의뢰자: '' };
  return { 의뢰기관: org, 의뢰자: org.slice(0, -1) + SIDO_TITLE[org.slice(-1)] };
}

/* ───────── 9. 시료 표 ───────── */
// v1.1: 시료번호처럼 생긴 값인지 (예: 동두천-10-1, 2-10-401~402, TMS 2-10-3 (A~D), 하천수 2-5-9-46)
const looksLikeSampleNo = v => {
  const s = String(v || '').replace(/\s*\n\s*/g, '').trim();
  if (!s || s.length > 40 || DATE_RE.test(s)) return false;
  return /\d+\s*-\s*\d+/.test(s);
};
function dataColumnValues(g, hr, o) {
  const vals = [];
  for (let r = hr + 1; r < g.nrows; r++) { const c = g.G[r] && g.G[r][o.c]; if (c && c.r === r && c.text) vals.push(c.text); }
  return vals;
}
const codeRatio = vals => vals.length ? vals.filter(looksLikeSampleNo).length / vals.length : 0;
// 시료번호 열 결정: ① 제목에 '번호' ② '시료명' 등이면서 값이 번호 형태 ③ 항목 열이 있는 표에서 값이 번호 형태인 열
function pickSampleCol(g, hr) {
  const os = rowOrigins(g, hr);
  const byNo = os.find(o => classify(o.text) === 'sampleNo');
  if (byNo) return { col: byNo, how: 'header' };
  const named = os.find(o => classify(o.text) === 'sampleName' && codeRatio(dataColumnValues(g, hr, o)) >= 0.6);
  if (named) return { col: named, how: 'name' };
  if (!os.some(o => /^items/.test(classify(o.text) || ''))) return null;
  let best = null, bestR = 0;
  for (const o of os) {
    const f = classify(o.text);
    if (/^items/.test(f || '') || f === 'date' || f === 'seq') continue;
    const r = codeRatio(dataColumnValues(g, hr, o));
    if (r > bestR) { best = o; bestR = r; }
  }
  if (best && bestR >= 0.6) return { col: best, how: 'content' };
  // v2.0 ④ 시료번호가 없는 목록(예: 하천명 + 의뢰항목) — 이름 열을 시료번호로 사용
  const nameCol = os.find(o => classify(o.text) === 'sampleName' && dataColumnValues(g, hr, o).length);
  return nameCol ? { col: nameCol, how: 'name-only' } : null;
}
function findSampleTables(tables) {
  const out = [], sigs = new Set();
  for (const t of tables) {
    const g = buildGrid(t);
    for (let r = 0; r < Math.min(3, g.nrows); r++) {
      const pick = pickSampleCol(g, r);
      if (!pick) continue;
      const sig = gridText(g); if (sigs.has(sig)) break; sigs.add(sig);
      out.push({ g, hr: r, sampleCol: pick.col, how: pick.how }); break;
    }
  }
  return out;
}
function joinNo(lines) {
  let s = '';
  for (const l of lines) s += (s && !/[-~]$/.test(s) && !/^[-~]/.test(l) ? ' ' : '') + l;
  return s.trim();
}
function readSampleTable({ g, hr, sampleCol }) {
  const heads = rowOrigins(g, hr).map(o => {
    let f = classify(o.text);
    if (sampleCol) f = o === sampleCol ? 'sampleNo' : (f === 'sampleNo' ? 'other' : f);
    if (f === 'sampleName') f = 'industry'; // 시료번호로 쓰지 않은 '시료명'은 성상 정보로 보관
    return { o, f, name: spacedName(o.text.replace(/\n/g, ' ')) };
  });
  const samples = [];
  const raw = [];
  for (let r = hr; r < g.nrows; r++) raw.push(heads.map(h => {
    const set = []; for (let c = h.o.c; c < h.o.c + h.o.cs; c++) { const o = g.G[r] && g.G[r][c]; if (o && !set.includes(o)) set.push(o); }
    return set.map(o => o.lines.join(' ')).join(' / ');
  }));
  const valOf = (r, h) => {
    const set = []; for (let c = h.o.c; c < h.o.c + h.o.cs; c++) { const o = g.G[r] && g.G[r][c]; if (o && o.r !== hr && !set.includes(o)) set.push(o); }
    return set;
  };
  for (let r = hr + 1; r < g.nrows; r++) {
    const rec = {}; let noCell = null, any = false;
    for (const h of heads) {
      if (!h.f || h.f === 'seq') continue;
      const cells = valOf(r, h);
      const text = cells.map(o => o.text).filter(Boolean).join('\n');
      if (h.f === 'sampleNo') { noCell = cells[0] || null; rec._noLines = noCell ? noCell.lines : []; }
      if (text) any = true;
      if (h.f === 'other') { if (text) (rec.other = rec.other || []).push(h.name + ': ' + text.replace(/\n/g, ' ')); }
      else rec[h.f] = rec[h.f] ? rec[h.f] + '\n' + text : text;
    }
    if (!any) continue;
    const cont = !noCell || !noCell.text || noCell.r < r;
    if (/^[-–—]$/.test((rec.note || '').trim())) rec.note = '';
    if (!rec.region && REGION_CODE.test(squash(rec.note))) { rec.region = rec.note.trim(); rec.note = ''; }
    const group = { items: rec.items || rec.itemsStd || '', std: rec.std || '', region: rec.region || '' };
    if (cont) { if (samples.length) samples[samples.length - 1].groups.push(group); continue; }
    samples.push({ rawNo: joinNo(rec._noLines || []), groups: [group], date: rec.date || '', qty: rec.qty || '',
      industry: rec.industry || '', point: rec.point || '', note: rec.note || '', other: (rec.other || []).join(' / ') });
  }
  return { headers: heads.map(h => h.name), raw, samples };
}
function expandNo(raw) {
  let s = raw.replace(/\s*\n\s*/g, '').trim();
  let subs = null;
  const sm = /\(\s*([A-Za-z])\s*~\s*([A-Za-z])\s*\)\s*$/.exec(s);
  if (sm) {
    s = s.slice(0, sm.index).trim(); subs = [];
    for (let c = sm[1].toUpperCase().charCodeAt(0); c <= sm[2].toUpperCase().charCodeAt(0); c++) subs.push(String.fromCharCode(c));
  }
  let bases = [s];
  const rm = /^(.*?)(\d+)\s*~\s*(?:[0-9A-Za-z가-힣\-]*-)?(\d+)$/.exec(s);
  if (rm) { const a = +rm[2], b = +rm[3]; if (b > a && b - a < 200) { bases = []; for (let k = a; k <= b; k++) bases.push(rm[1] + k); } }
  const out = [];
  for (const b of bases) { if (subs) subs.forEach(x => out.push(`${b}(${x})`)); else out.push(b); }
  return { list: out, baseCount: bases.length };
}
function parseItems(text) {
  let region = '';
  let s = (text || '').replace(/[·•▪◦]/g, ',');
  const ar = /(?:→|->|⇒)\s*([^,\n]+)/.exec(s);
  if (ar) { region = ar[1].trim(); s = s.slice(0, ar.index) + s.slice(ar.index + ar[0].length); }
  s = s.replace(/\n/g, ',');
  const toks = []; let depth = 0, cur = '';
  for (const ch of s) {
    if (ch === '(' || ch === '（') depth++; else if (ch === ')' || ch === '）') depth = Math.max(0, depth - 1);
    if ((ch === ',' || ch === '，' || ch === '、') && depth === 0) { toks.push(cur); cur = ''; } else cur += ch;
  }
  toks.push(cur);
  const items = [];
  for (let t of toks) {
    t = t.replace(/^[\s\-–]+/, '').replace(/^[(\[]?\s*추가\s*[)\]]?\s*[:：]?\s*/, '').trim(); if (!t) continue; // v2.0: '(추가) COD'
    const sp = splitItemStd(t);
    t = sp.name; const std = sp.std;
    const name = normItem(t);
    items.push({ raw: t, name: name || t, known: !!name, std });
  }
  return { items, region };
}
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
/* v1.1: 항목 안의 기준 표기 — BOD(20), BOD(20이하), BOD(20 ㎎/L 이하), BOD(기준 20), BOD(≤20), T-P(0.5미만),
   pH(5.8~8.6), 대장균군(3,000개/mL), BOD 20이하, SS: 20  → 이름과 기준값 분리 */
const STD_UNIT = '(?:mg\\s*/\\s*[lLℓ]|㎎\\s*/\\s*[lLℓ]|㎎/ℓ|mg/ℓ|ppm|ppb|도|TU|개\\s*/\\s*(?:100\\s*)?m[lL]|%)';
const STD_NUM = '(\\d[\\d.,]*(?:\\s*[~∼-]\\s*\\d[\\d.,]*)?)';
const STD_PAREN = new RegExp('^(.*?\\S)\\s*[(（]\\s*(?:기준\\s*[:：]?\\s*)?(≤|<=|<|이하|미만)?\\s*' + STD_NUM + '\\s*' + STD_UNIT + '?\\s*(이하|미만)?\\s*[)）]$');
const STD_PLAIN = new RegExp('^(.*?\\S)\\s*([:：])?\\s*(≤|<=|<)?\\s*' + STD_NUM + '\\s*' + STD_UNIT + '?\\s*(이하|미만)?$');
const fmtStd = (num, q) => num.replace(/\s+/g, '').replace(/∼/g, '~') + (q === '미만' || q === '<' ? ' 미만' : '');
function splitItemStd(t) {
  let m = STD_PAREN.exec(t);
  if (m && !/^[\d.,]+$/.test(m[1])) return { name: m[1].trim(), std: fmtStd(m[3], m[2] || m[4]) };
  m = STD_PLAIN.exec(t);
  if (m && normItem(m[1].trim()) && (m[2] || m[3] || m[5] || /\s/.test(t.slice(m[1].length, m[1].length + 1)))) return { name: m[1].trim(), std: fmtStd(m[4], m[3] || m[5]) };
  return { name: t, std: '' };
}
function applyStdColumn(items, std) {
  if (!std) return;
  const v = std.replace(/\n/g, ' ');
  const each = /각\s*([\d.]+)/.exec(v);
  if (each) { items.forEach(i => { if (!i.std) i.std = each[1]; }); return; }
  let hit = false;
  for (const i of items) {
    for (const key of new Set([i.raw, i.name])) {
      const m = new RegExp(esc(key) + '\\s*[:：]?\\s*([\\d.]+)', 'i').exec(v);
      if (m) { if (!i.std) i.std = m[1]; hit = true; break; }
    }
  }
  if (hit) return;
  const nums = v.match(/\d+(?:\.\d+)?/g) || [];
  if (nums.length === items.length) items.forEach((i, k) => { if (!i.std) i.std = nums[k]; });
}

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

/* ───────── 12. 메인 ───────── */
async function extractOdt(bytes, fileName, inflateRaw) {
  const xml = await unzipEntry(bytes, 'content.xml', inflateRaw);
  const root = parseXML(xml);
  const officeBody = findAll(root, 'body')[0];
  const body = (officeBody && kids(officeBody, 'text')[0]) || root;
  const tables = findAll(body, 'table').filter(t => !findAll(t, 'table').length); // 중첩 없는 표만
  const hdr = parseHeader(tables) || { org: '', title: '' };
  const ftr = parseFooter(tables) || {};
  if (!ftr.sender && ftr.drafterPos) ftr.sender = senderFallback(body, ftr.drafterPos);
  const org = deriveOrg(hdr.org, ftr.addr);
  const paras = bodyParagraphs(body);
  const doc = {
    파일명: (fileName || '').normalize('NFC'), 제목: hdr.title, 상단기관명: hdr.org,
    의뢰기관: org.의뢰기관, 의뢰자: org.의뢰자, 발신명의: ftr.sender || '',
    시행: ftr.siNo || '', 시행일: (parseDate(ftr.siDate) || {}).date || '',
    접수: ftr.rcNo || '', 접수일: (parseDate(ftr.rcDate) || {}).date || '',
    시료채취자: ftr.drafter || '', 기안자직위: ftr.drafterPos || '',
    우편번호: ftr.zip || '', 주소: ftr.addr || '', 전화번호: ftr.tel || '', 이메일: ftr.email || '',
  };
  return buildResult(doc, paras, findSampleTables(tables));
}
// v2.0: 공문 정보 + 시료 표(격자) → 결과. 첨부 HWPX의 시료 목록에도 같은 규칙을 쓴다
function buildResult(doc, paras, sts) {
  const docWarn = [];
  if (!doc.접수) docWarn.push('접수번호 없음');
  if (!doc.의뢰자) docWarn.push('의뢰자 판정 불가');
  if (!sts.length) docWarn.push('시료표 미인식');
  const bodyDates = dateFromBody(paras);
  const bodyDate = bodyDates[0] || null;
  const bset = [...new Set(bodyDates.map(d => d.date))];
  if (bset.length > 1) docWarn.push('본문 채취일 여러 개: ' + bset.join(', '));
  const rows = [], allSamples = [], tableInfo = []; let baseTotal = 0;
  for (const st of sts) {
    const { headers, raw, samples } = readSampleTable(st);
    tableInfo.push({ headers, raw });
    for (const s of samples) {
      const ex = expandNo(s.rawNo); baseTotal += ex.baseCount; allSamples.push(s);
      const warn = [];
      const groups = s.groups.map(gp => {
        const p = parseItems(gp.items);
        let std = gp.std, region = gp.region;
        if (std && !/\d/.test(std)) { region = region || std; std = ''; } // '수질기준' 열에 지역코드가 들어간 경우
        applyStdColumn(p.items, std);
        const rg = (region || p.region || '').replace(/\s*\n\s*/g, ' ').trim();
        p.items.forEach(i => { i.region = rg; });
        return { items: p.items, region: rg };
      });
      const items = [];
      groups.forEach(gp => gp.items.forEach(i => { if (!items.some(x => x.name === i.name)) items.push(i); }));
      if (/기준/.test(s.note)) applyStdColumn(items, s.note);
      const unknown = items.filter(i => !i.known).map(i => i.raw);
      if (unknown.length) warn.push('미등록 항목: ' + unknown.join(', '));
      if (!items.length) warn.push('검사항목 없음');
      const regs = groups.map(gp => gp.region).filter(Boolean);
      const regionText = new Set(regs).size > 1
        ? groups.filter(gp => gp.region).map(gp => `${gp.region}(${gp.items.map(i => i.name).join(', ')})`).join(' / ')
        : (regs[0] || '');
      let date, time = '', src;
      const pd = parseDate(s.date);
      if (pd) { date = pd.date; time = pd.time; src = '표'; }
      else if (bodyDate) { date = bodyDate.date; time = bodyDate.time; src = '본문'; }
      else { date = '채취일자 확인 필요'; src = '확인필요'; warn.push('채취일자 확인 필요'); }
      if (pd && doc.접수일 && pd.date > doc.접수일) warn.push('채취일이 접수일보다 늦음');
      for (const no of ex.list) {
        const row = {
          ...doc, 시료번호: no, 시료번호원문: s.rawNo,
          검사항목: items.map(i => i.name).join(', '),
          기준: '', 기준출처: '',
          지역구분: regionText, 시료채취일: date, 채취시각: time, 채취일출처: src,
          '업종/성상': spacedName(s.industry.replace(/\n/g, ' ')), 시료량: s.qty.replace(/\n/g, ', '),
          채취지점: s.point.replace(/\n/g, ' '), 비고: s.note.replace(/\n/g, ' '), 기타: s.other,
          _items: items.map(i => ({ name: i.name, region: i.region || regionText, stdDoc: i.std || '', std: i.std || '', src: i.std ? '공문' : '' })),
          _warn: warn,
        };
        refreshStdText(row);
        rows.push(row);
      }
    }
  }
  const tc = titleCheck(doc.제목, allSamples, baseTotal); if (tc) docWarn.push(tc);
  if (doc.시행일 && doc.접수일 && doc.접수일 < doc.시행일) docWarn.push('접수일이 시행일보다 빠름');
  if (!rows.length) rows.push({ ...doc, 시료번호: '', _items: [], _warn: [] });
  rows.forEach(r => { r._baseWarn = [...docWarn, ...r._warn]; delete r._warn; r.확인필요 = r._baseWarn.join(' / '); });
  return { doc: { ...doc, 본문: paras }, rows, warnings: docWarn, tables: tableInfo };
}
function rebuildResult(result, sts) {
  const doc = { ...result.doc }; const paras = doc.본문 || []; delete doc.본문;
  return buildResult(doc, paras, sts);
}

// v1.1: 엑셀·화면 기본 순서 — 접수일, 의뢰기관, 의뢰자, 발신명의, 시행, 시료번호, 검사항목, 시료채취일 먼저
const COLUMNS = ['접수일','의뢰기관','의뢰자','발신명의','시행','시료번호','검사항목','시료채취일','기준','기준출처','지역구분',
  '채취시각','채취일출처','시료채취자','접수','시행일','제목','업종/성상','시료량','채취지점','비고','기타','우편번호','주소','전화번호','이메일','확인필요','파일명'];

/* ───────── 13. 중복 공문 ───────── */
function markDuplicates(results) {
  const by = {};
  results.forEach(r => { r.duplicate = false; r.dupWarn = ''; if (r.doc && r.doc.접수) (by[r.doc.접수] = by[r.doc.접수] || []).push(r); });
  for (const k in by) if (by[k].length > 1) by[k].forEach((r, i) => {
    const others = by[k].filter(x => x !== r).map(x => x.doc.파일명).join(', ');
    r.duplicate = i > 0;
    r.dupWarn = (i > 0 ? '중복 공문(집계 제외)' : '중복 공문 있음') + ': ' + others;
  });
  results.forEach(r => r.rows.forEach(x => { x.확인필요 = [...(x._baseWarn || []), ...(r.dupWarn ? [r.dupWarn] : [])].join(' / '); }));
  return results;
}

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

/* ───────── 16. 원본 미리보기 (ODT → HTML, v1.1) ───────── */
const ODT_PREVIEW_CSS = `
.odt-page{font-family:"Malgun Gothic","맑은 고딕","Apple SD Gothic Neo","Noto Sans KR",sans-serif;font-size:10pt;line-height:1.3;color:#000;background:#fff;margin:0 auto;padding:1cm 0;box-sizing:content-box}
.odt-p{margin:0;min-height:1.2em;white-space:pre-wrap;word-break:keep-all;overflow-wrap:anywhere}
.odt-table{border-collapse:collapse;table-layout:fixed;margin:0}
.odt-table td{vertical-align:top;padding:1px 3px;overflow:hidden;overflow-wrap:anywhere}
.odt-frame{display:inline-block;vertical-align:top;max-width:100%}
.odt-img{display:inline-block;vertical-align:middle;object-fit:contain}
.odt-list{margin:0;padding-left:1.2em}`;
const hesc = v => String(v == null ? '' : v).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function b64(bytes) {
  if (typeof btoa === 'function') { let s = ''; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)); return btoa(s); }
  return Buffer.from(bytes).toString('base64');
}
const IMG_MIME = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif', bmp: 'image/bmp', svg: 'image/svg+xml', webp: 'image/webp' };
const CSS_LEN = v => /^-?[\d.]+(cm|mm|in|pt|pc|px|%)$/.test(String(v || '').trim());
async function renderOdtHtml(bytes, inflateRaw) {
  const content = parseXML(await unzipEntry(bytes, 'content.xml', inflateRaw));
  const sx = await unzipEntry(bytes, 'styles.xml', inflateRaw, true);
  const stylesDoc = sx ? parseXML(sx) : { n: '#root', a: {}, c: [] };
  const S = {}, D = {};
  for (const root of [stylesDoc, content]) for (const box of [...findAll(root, 'styles'), ...findAll(root, 'automatic-styles')]) {
    for (const st of kids(box, 'style')) if (st.a.name) S[(st.a.family || '') + ':' + st.a.name] = st;
    for (const st of kids(box, 'default-style')) if (st.a.family) D[st.a.family] = st;
  }
  const cache = {};
  function props(family, name) {
    const key = family + ':' + (name || '');
    if (cache[key]) return cache[key];
    const chain = []; let cur = name ? S[family + ':' + name] : null, guard = 0;
    while (cur && guard++ < 20) { chain.unshift(cur); cur = cur.a['parent-style-name'] ? S[family + ':' + cur.a['parent-style-name']] : null; }
    if (D[family]) chain.unshift(D[family]);
    const out = {};
    for (const st of chain) for (const pe of kids(st)) { const k = pe.n.replace(/-properties$/, ''); out[k] = Object.assign(out[k] || {}, pe.a); }
    return (cache[key] = out);
  }
  const ALIGN = { start: 'left', left: 'left', end: 'right', right: 'right', center: 'center', justify: 'justify' };
  function textCss(t) {
    if (!t) return '';
    const o = [], size = t['font-size-asian'] || t['font-size'], w = t['font-weight-asian'] || t['font-weight'];
    if (CSS_LEN(size) && !/%$/.test(size)) o.push('font-size:' + size);
    if (w && (w === 'bold' || +w >= 600)) o.push('font-weight:bold');
    if ((t['font-style-asian'] || t['font-style']) === 'italic') o.push('font-style:italic');
    if (t.color && /^#[0-9a-f]{6}$/i.test(t.color)) o.push('color:' + t.color);
    if (t['text-underline-style'] && t['text-underline-style'] !== 'none') o.push('text-decoration:underline');
    if (t['background-color'] && t['background-color'] !== 'transparent') o.push('background-color:' + t['background-color']);
    return o.join(';');
  }
  function paraCss(p) {
    if (!p) return '';
    const o = [];
    if (p['text-align']) o.push('text-align:' + (ALIGN[p['text-align']] || 'left'));
    for (const k of ['margin-left', 'margin-right', 'margin-top', 'margin-bottom', 'text-indent']) if (CSS_LEN(p[k])) o.push(k + ':' + p[k]);
    const lh = p['line-height'];
    if (lh && /%$/.test(lh)) o.push('line-height:' + (parseFloat(lh) / 100 * 1.2).toFixed(2));
    else if (CSS_LEN(lh)) o.push('line-height:' + lh);
    return o.join(';');
  }
  function cellCss(c) {
    if (!c) return '';
    const o = [];
    for (const k of ['border', 'border-top', 'border-bottom', 'border-left', 'border-right']) if (c[k]) o.push(k + ':' + c[k]);
    for (const k of ['padding', 'padding-top', 'padding-bottom', 'padding-left', 'padding-right']) if (CSS_LEN(c[k])) o.push(k + ':' + c[k]);
    if (c['background-color'] && c['background-color'] !== 'transparent') o.push('background-color:' + c['background-color']);
    if (c['vertical-align']) o.push('vertical-align:' + ({ middle: 'middle', top: 'top', bottom: 'bottom' }[c['vertical-align']] || 'top'));
    return o.join(';');
  }
  const imgs = {};
  for (const im of findAll(content, 'image')) {
    const href = im.a.href; if (!href || imgs[href] !== undefined || /^https?:/.test(href)) continue;
    try { const b = await unzipBytes(bytes, href.replace(/^\.\//, ''), inflateRaw, true); const ext = (href.split('.').pop() || '').toLowerCase(); imgs[href] = b && IMG_MIME[ext] ? `data:${IMG_MIME[ext]};base64,${b64(b)}` : null; }
    catch (e) { imgs[href] = null; }
  }
  function rInline(e) {
    let out = '';
    for (const x of e.c) {
      if (typeof x === 'string') { out += hesc(x.replace(/[\t\r\n ]+/g, ' ')); continue; }
      switch (x.n) {
        case 's': out += ' '.repeat(+x.a.c || 1); break;
        case 'tab': out += '\t'; break;
        case 'line-break': out += '<br>'; break;
        case 'frame': out += rFrame(x); break;
        case 'span': { const css = textCss(props('text', x.a['style-name']).text); out += css ? `<span style="${css}">${rInline(x)}</span>` : rInline(x); break; }
        case 'note': case 'annotation': case 'bookmark': case 'bookmark-start': case 'bookmark-end': case 'soft-page-break': break;
        default: out += rInline(x);
      }
    }
    return out;
  }
  function rFrame(f) {
    const w = CSS_LEN(f.a.width) ? f.a.width : '', h = CSS_LEN(f.a.height) ? f.a.height : '';
    const im = kids(f, 'image')[0], tb = kids(f, 'text-box')[0];
    if (tb) return `<div class="odt-frame"${w ? ` style="width:${w}"` : ''}>${rBlocks(tb)}</div>`;
    if (im) { const src = imgs[im.a.href]; return src ? `<img class="odt-img" src="${src}" style="${w ? 'width:' + w + ';' : ''}${h ? 'height:' + h : ''}" alt="">` : ''; }
    return '';
  }
  function rTable(t) {
    const tp = props('table', t.a['style-name']).table || {};
    const cols = [];
    (function colsOf(e) { for (const x of kids(e)) {
      if (x.n === 'table-column') { const rep = Math.min(+x.a['number-columns-repeated'] || 1, 64); const cw = (props('table-column', x.a['style-name'])['table-column'] || {})['column-width']; for (let k = 0; k < rep; k++) cols.push(CSS_LEN(cw) ? cw : ''); }
      else if (x.n === 'table-columns' || x.n === 'table-header-columns' || x.n === 'table-column-group') colsOf(x);
    } })(t);
    const tw = CSS_LEN(tp.width) ? tp.width : '';
    let h = `<table class="odt-table"${tw ? ` style="width:${tw}"` : ''}>`;
    if (cols.length && cols.every(Boolean)) h += '<colgroup>' + cols.map(c => `<col style="width:${c}">`).join('') + '</colgroup>';
    for (const row of tableRows(t)) {
      const rp = props('table-row', row.a['style-name'])['table-row'] || {};
      const rh = rp['row-height'] || rp['min-row-height'];
      h += `<tr${CSS_LEN(rh) ? ` style="height:${rh}"` : ''}>`;
      for (const cell of kids(row)) {
        if (cell.n !== 'table-cell') continue;
        const rep = Math.min(+cell.a['number-columns-repeated'] || 1, 64);
        const cs = +cell.a['number-columns-spanned'] || 1, rs = +cell.a['number-rows-spanned'] || 1;
        const css = cellCss(props('table-cell', cell.a['style-name'])['table-cell']);
        const inner = rBlocks(cell);
        for (let k = 0; k < rep; k++) h += `<td${cs > 1 ? ` colspan="${cs}"` : ''}${rs > 1 ? ` rowspan="${rs}"` : ''}${css ? ` style="${css}"` : ''}>${inner}</td>`;
      }
      h += '</tr>';
    }
    return h + '</table>';
  }
  function rBlocks(e) {
    let out = '';
    for (const x of kids(e)) {
      if (x.n === 'p' || x.n === 'h') {
        const pr = props('paragraph', x.a['style-name']);
        const css = [paraCss(pr.paragraph), textCss(pr.text)].filter(Boolean).join(';');
        out += `<div class="odt-p"${css ? ` style="${css}"` : ''}>${rInline(x) || '&#8203;'}</div>`;
      } else if (x.n === 'table') out += rTable(x);
      else if (x.n === 'list') out += `<div class="odt-list">${kids(x, 'list-item').map(rBlocks).join('')}</div>`;
      else if (x.n === 'section' || x.n === 'list-item') out += rBlocks(x);
      else if (x.n === 'frame') out += rFrame(x);
    }
    return out;
  }
  let pageW = '17cm';
  const pl = findAll(stylesDoc, 'page-layout-properties')[0];
  if (pl && /cm$/.test(pl.a['page-width'] || '')) {
    const w = parseFloat(pl.a['page-width']) - (parseFloat(pl.a['margin-left']) || 0) - (parseFloat(pl.a['margin-right']) || 0);
    if (w > 5) pageW = w.toFixed(2) + 'cm';
  }
  const base = textCss((props('paragraph', '').text) || {});
  const officeBody = findAll(content, 'body')[0];
  const body = (officeBody && kids(officeBody, 'text')[0]) || content;
  return { html: `<div class="odt-page" style="width:${pageW}${base ? ';' + base : ''}">${rBlocks(body)}</div>`, css: ODT_PREVIEW_CSS, pageWidth: pageW };
}

const _internal = { parseXML, kids, walk, findAll, has, textAll, inlineText, blockLines, squash, spacedName, buildGrid, rowOrigins, classify,
  pickSampleCol, readSampleTable, findSampleTables, expandNo, parseItems, normItem, parseDate, allDates, dateFromBody, unzipEntry, unzipBytes, unzipList,
  buildResult, rebuildResult, looksLikeSampleNo, refreshStdText, hesc, b64 };
const API = { _internal, rebuildResult, unzipList, extractOdt, unzipBytes, renderOdtHtml, markDuplicates, parseXML, parseDate, expandNo, parseItems, COLUMNS, ITEM_DICT, ORG_EXCEPTIONS,
  parseStdTable, applyStdTable, lookupStd, missingStdPairs, readXlsxRows, decodeText, parseCsv, VERSION: '2.0' };
if (typeof module !== 'undefined' && module.exports) module.exports = API; else global.OdtEngine = API;
})(typeof window !== 'undefined' ? window : globalThis);
