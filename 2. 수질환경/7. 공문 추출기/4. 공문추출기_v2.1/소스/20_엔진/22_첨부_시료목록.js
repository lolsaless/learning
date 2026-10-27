/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/22_첨부_시료목록.js] 특이 공문: 첨부 시료 목록·직접 입력
   하는 일 : 본문 붙임 목록 ↔ 첨부 파일 이름 대조, HWPX 표 → 시료 행, 직접 입력·붙여넣기 해석
   주요 이름: attachmentNames, attachScore, samplesFromAttachments, samplesFromManual, parsePastedSamples
   이럴 때 고침: 첨부를 못 찾거나 붙여넣기 열 인식
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
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
    for (let r = 0; r < Math.min(3, t.g.nrows); r++) { const os = rowOrigins(t.g, r); if (!os.some(o => /^items/.test(classify(o.text) || ''))) continue; pick = pickSampleCol(t.g, r); if (pick) { hr = r; break; } }
    if (pick) sts.push({ g: t.g, hr, sampleCol: pick.col, how: 'hwpx-' + pick.how, file: t.file }); else others.push(t);
  }
  if (!sts.length) return null;
  const res = rebuildResult(result, sts);
  // 보충 정보: 이름 → {시군, 위치}
  const extra = new Map();
  for (const t of others) {
    for (let hr = 0; hr < Math.min(3, t.g.nrows); hr++) {
      const heads = rowOrigins(t.g, hr), nameH = heads.find(o => classify(o.text) === 'sampleName');
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
  const res = rebuildResult(result, [{ g, hr: 0, sampleCol: G[0][0], how: 'manual' }]);
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
  const h = rows[0].map(c => classify(c));
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
