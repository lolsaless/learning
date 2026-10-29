/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/41_시험성적서.js] 시험성적서 PDF 해석
   하는 일 : PDF 글자 좌표 → 줄·칸, 접수번호·시료명·공문번호·결과표·판정 읽기, 파일 단위 묶기
   주요 이름: pdfLines, parseReportPage, parseReportPdf, splitSampleType, REPORT_ITEM
   이럴 때 고침: 성적서 양식이 바뀌거나 항목명이 안 맞을 때, 검체유형 나누는 기호(SAMPLE_TYPE_SEP)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
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
    검체대분류: '', 검체중분류: '', 검체소분류: '',
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
  Object.assign(r, splitSampleType(r.검체유형));
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
  samples.forEach(s => { s.결과.forEach(x => { x.항목명 = normItem(x.항목) || normReportItem(x.항목); }); });
  return { 파일명: NFC(fileName), 공문번호: [...new Set(samples.map(s => s.공문번호))].join(', '), 의뢰기관: samples[0] ? samples[0].의뢰기관 : '',
    samples, 중간: /중간/.test(NFC(fileName)), 부적합: samples.some(s => /부적합/.test(s.판정)) };
}
// v2.2: 검체유형 "폐수/폐수/폐수" → 대·중·소분류 ('/' 기준, 4개 이상이면 나머지는 소분류에 '/'로 이어 붙임, 모자라면 빈칸)
const SAMPLE_TYPE_SEP = /\s*[\/／]\s*/;
function splitSampleType(s) {
  const p = String(s || '').split(SAMPLE_TYPE_SEP).map(x => x.trim()).filter(Boolean);
  return { 검체대분류: p[0] || '', 검체중분류: p[1] || '', 검체소분류: p.length > 3 ? p.slice(2).join('/') : (p[2] || '') };
}
const REPORT_ITEM = { '총질소': 'T-N', '총인': 'T-P', '노말헥산추출물질(광유류)': 'n-H(광)', '노말헥산추출물질(동식물유지류)': 'n-H(동식)', '노말헥산추출물질(동식물유류)': 'n-H(동식)',
  '생물화학적산소요구량': 'BOD', '화학적산소요구량': 'COD', '부유물질': 'SS', '총유기탄소': 'TOC', '수소이온농도': 'pH', '음이온계면활성제': 'ABS', '클로로필-a': '클로로필a', '클로로필a': '클로로필a' };
function normReportItem(t) { const k = squash(t); return REPORT_ITEM[k] || normItem(k.replace(/\(.*\)$/, '')) || t; }
