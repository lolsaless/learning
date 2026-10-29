/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/12_접수공문_시료표.js] 접수공문 시료 표 찾기·읽기
   하는 일 : 표 머리글 분류, 시료번호 열 판정, 시료 표 찾기, 행 읽기, 범위·하위 시료번호 펼치기
   주요 이름: classify, pickSampleCol, findSampleTables, readSampleTable, expandNo, looksLikeSampleNo
   이럴 때 고침: "시료표 미인식"·새 열 이름(예: 채수지점명)·시료번호 모양
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
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
