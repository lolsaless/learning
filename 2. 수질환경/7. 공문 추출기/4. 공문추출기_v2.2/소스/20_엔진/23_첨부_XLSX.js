/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/23_첨부_XLSX.js] 첨부 XLSX(엑셀) 보기
   하는 일 : 엑셀 파일의 시트·칸 값·병합·열 너비·글꼴·채우기·테두리·표시 형식을 읽어 화면·이력 문서용 HTML로 그림 (읽기 전용)
   주요 이름: parseXlsxView, xlsxHtml, xlsxFormat, XLSX_VIEW_LIMIT
   이럴 때 고침: 엑셀 첨부 보기 모양이 원본과 다를 때, 날짜·숫자 표시 형식, 보여 줄 최대 행·열 수
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───────── 1. 설정 ───────── */
const XLSX_VIEW_LIMIT = { rows: 1000, cols: 80 };   // 이보다 큰 시트는 앞부분만 보여 주고 안내
const XLSX_DATE_IDS = new Set([14, 15, 16, 17, 18, 19, 20, 21, 22, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 45, 46, 47, 50, 51, 52, 53, 54, 55, 56, 57, 58]);
const XLSX_BUILTIN_FMT = { 0: 'General', 1: '0', 2: '0.00', 3: '#,##0', 4: '#,##0.00', 9: '0%', 10: '0.00%', 11: '0.00E+00', 12: '# ?/?', 13: '# ??/??',
  14: 'yyyy-mm-dd', 15: 'd-mmm-yy', 16: 'd-mmm', 17: 'mmm-yy', 18: 'h:mm AM/PM', 19: 'h:mm:ss AM/PM', 20: 'h:mm', 21: 'h:mm:ss', 22: 'yyyy-mm-dd h:mm',
  27: 'yyyy"년" mm"월"', 28: 'mm-dd', 29: 'mm-dd', 30: 'mm-dd-yy', 31: 'yyyy"년" mm"월" dd"일"', 32: 'h"시" mm"분"', 33: 'h"시" mm"분" ss"초"', 34: 'yyyy"년" mm"월"', 35: 'mm-dd', 36: 'yyyy"년" mm"월"',
  37: '#,##0 ;(#,##0)', 38: '#,##0 ;[Red](#,##0)', 39: '#,##0.00;(#,##0.00)', 40: '#,##0.00;[Red](#,##0.00)', 45: 'mm:ss', 46: '[h]:mm:ss', 47: 'mm:ss.0', 48: '##0.0E+0', 49: '@',
  50: 'yyyy"년" mm"월"', 51: 'mm-dd', 52: 'yyyy"년" mm"월"', 53: 'mm-dd', 54: 'mm-dd', 55: 'yyyy"년" mm"월"', 56: 'mm-dd', 57: 'yyyy"년" mm"월"', 58: 'mm-dd' };
// 엑셀 기본 색 번호(indexed) 0~63
const XLSX_INDEXED = ['000000', 'FFFFFF', 'FF0000', '00FF00', '0000FF', 'FFFF00', 'FF00FF', '00FFFF', '000000', 'FFFFFF', 'FF0000', '00FF00', '0000FF', 'FFFF00', 'FF00FF', '00FFFF',
  '800000', '008000', '000080', '808000', '800080', '008080', 'C0C0C0', '808080', '9999FF', '993366', 'FFFFCC', 'CCFFFF', '660066', 'FF8080', '0066CC', 'CCCCFF',
  '000080', 'FF00FF', 'FFFF00', '00FFFF', '800080', '800000', '008080', '0000FF', '00CCFF', 'CCFFFF', 'CCFFCC', 'FFFF99', '99CCFF', 'FF99CC', 'CC99FF', 'FFCC99',
  '3366FF', '33CCCC', '99CC00', 'FFCC00', 'FF9900', 'FF6600', '666699', '969696', '003366', '339966', '003300', '333300', '993300', '993366', '333399', '333333'];

/* ───────── 2. 읽기 ───────── */
const xColIdx = ref => { const m = /^([A-Z]+)(\d+)$/.exec(ref || ''); if (!m) return null; let c = 0; for (const ch of m[1]) c = c * 26 + ch.charCodeAt(0) - 64; return { r: +m[2] - 1, c: c - 1 }; };
const xKid = (e, n) => e && e.c.find(x => typeof x !== 'string' && x.n === n);
// 공유 문자열 하나 (읽는 법 표시 rPh 는 뺀다)
function xRichText(si) {
  let out = '';
  for (const x of si.c) { if (typeof x === 'string') continue; if (x.n === 't') out += textAll(x); else if (x.n === 'r') { const t = xKid(x, 't'); if (t) out += textAll(t); } }
  return out;
}
function xThemeColors(xml) {
  if (!xml) return [];
  const sch = findAll(parseXML(xml), 'clrScheme')[0]; if (!sch) return [];
  const pick = n => { const e = kids(sch).find(x => x.n === n); if (!e) return null; const v = kids(e)[0]; return v ? (v.a.lastClr || v.a.val || null) : null; };
  // 엑셀 theme 번호 순서: lt1, dk1, lt2, dk2, accent1~6, hlink, folHlink
  return ['lt1', 'dk1', 'lt2', 'dk2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink'].map(pick);
}
function xColor(e, theme) {
  if (!e || e.a.auto === '1') return null;
  let hex = null;
  if (e.a.rgb) hex = e.a.rgb.slice(-6);
  else if (e.a.theme != null) hex = theme[+e.a.theme] || null;
  else if (e.a.indexed != null) { const k = +e.a.indexed; if (k === 64 || k === 65) return null; hex = XLSX_INDEXED[k] || null; }
  if (!hex || !/^[0-9a-f]{6}$/i.test(hex)) return null;
  const tint = +(e.a.tint || 0);
  let rgb = [0, 2, 4].map(i => parseInt(hex.slice(i, i + 2), 16));
  if (tint) rgb = rgb.map(v => Math.round(tint < 0 ? v * (1 + tint) : v + (255 - v) * tint));
  return '#' + rgb.map(v => Math.max(0, Math.min(255, v)).toString(16).padStart(2, '0')).join('');
}
function xStyles(xml, theme) {
  const S = { xf: [{}], fmt: {} };
  if (!xml) return S;
  const root = parseXML(xml);
  for (const f of findAll(root, 'numFmt')) S.fmt[+f.a.numFmtId] = f.a.formatCode;
  const fontsEl = findAll(root, 'fonts')[0], fillsEl = findAll(root, 'fills')[0], bordersEl = findAll(root, 'borders')[0], xfsEl = findAll(root, 'cellXfs')[0];
  const fonts = fontsEl ? kids(fontsEl, 'font').map(f => {
    const v = n => xKid(f, n);
    return { b: !!v('b') && v('b').a.val !== '0', i: !!v('i') && v('i').a.val !== '0', u: !!v('u') && v('u').a.val !== 'none', strike: !!v('strike'), sz: v('sz') ? +v('sz').a.val : 11, color: xColor(v('color'), theme), name: v('name') ? v('name').a.val : '' };
  }) : [];
  const fills = fillsEl ? kids(fillsEl, 'fill').map(f => { const p = xKid(f, 'patternFill'); if (!p || !p.a.patternType || p.a.patternType === 'none') return null; return xColor(xKid(p, 'fgColor'), theme) || (p.a.patternType === 'solid' ? null : xColor(xKid(p, 'bgColor'), theme)); }) : [];
  const borders = bordersEl ? kids(bordersEl, 'border').map(b => {
    const o = {};
    for (const side of ['left', 'right', 'top', 'bottom']) { const e = xKid(b, side); if (e && e.a.style && e.a.style !== 'none') o[side] = { style: e.a.style, color: xColor(xKid(e, 'color'), theme) || '#000' }; }
    return o;
  }) : [];
  S.font0 = fonts[0] || { sz: 11, name: '' };
  if (xfsEl) S.xf = kids(xfsEl, 'xf').map(x => {
    const al = xKid(x, 'alignment');
    return { fmt: +(x.a.numFmtId || 0), font: fonts[+(x.a.fontId || 0)] || null, fill: fills[+(x.a.fillId || 0)] || null, border: borders[+(x.a.borderId || 0)] || null,
      h: al ? al.a.horizontal || '' : '', v: al ? al.a.vertical || '' : '', wrap: !!(al && al.a.wrapText === '1'), indent: al ? +(al.a.indent || 0) : 0 };
  });
  return S;
}
async function parseXlsxView(bytes, inflateRaw) {
  const names = unzipList(bytes);
  const wbXml = await unzipEntry(bytes, 'xl/workbook.xml', inflateRaw, true);
  if (!wbXml) throw new Error('엑셀(xlsx) 형식이 아닙니다(xl/workbook.xml 없음)');
  const wb = parseXML(wbXml);
  const wbPr = findAll(wb, 'workbookPr')[0], date1904 = !!(wbPr && (wbPr.a.date1904 === '1' || wbPr.a.date1904 === 'true'));
  const relXml = await unzipEntry(bytes, 'xl/_rels/workbook.xml.rels', inflateRaw, true);
  const rels = {}; if (relXml) for (const r of findAll(parseXML(relXml), 'Relationship')) rels[r.a.Id] = r.a.Target;
  const theme = xThemeColors(await unzipEntry(bytes, 'xl/theme/theme1.xml', inflateRaw, true));
  const styles = xStyles(await unzipEntry(bytes, 'xl/styles.xml', inflateRaw, true), theme);
  const ssXml = await unzipEntry(bytes, 'xl/sharedStrings.xml', inflateRaw, true);
  const shared = ssXml ? findAll(parseXML(ssXml), 'si').map(xRichText) : [];
  const sheets = [];
  const list = findAll(wb, 'sheet');
  for (let k = 0; k < list.length; k++) {
    const sh = list[k];
    let target = rels[sh.a.id] || `worksheets/sheet${k + 1}.xml`;
    target = target.replace(/^\/?xl\//, '').replace(/^\//, '');
    const path = 'xl/' + target;
    const S = { name: sh.a.name || `시트${k + 1}`, hidden: sh.a.state === 'hidden' || sh.a.state === 'veryHidden', cells: new Map(), merges: [], cols: {}, rows: {}, nrows: 0, ncols: 0, drawing: false, truncated: false, error: '' };
    sheets.push(S);
    try {
      const xml = await unzipEntry(bytes, path, inflateRaw, true);
      if (!xml) { S.error = '시트 내용 없음'; continue; }
      const root = parseXML(xml);
      S.drawing = findAll(root, 'drawing').length > 0;
      const fmtPr = findAll(root, 'sheetFormatPr')[0];
      S.defW = fmtPr && fmtPr.a.defaultColWidth ? +fmtPr.a.defaultColWidth : (fmtPr && fmtPr.a.baseColWidth ? +fmtPr.a.baseColWidth + 0.71 : 8.43);
      S.defH = fmtPr && fmtPr.a.defaultRowHeight ? +fmtPr.a.defaultRowHeight : 15;
      for (const c of findAll(root, 'col')) for (let i = +c.a.min - 1; i <= +c.a.max - 1 && i < 16384; i++) S.cols[i] = { w: c.a.width ? +c.a.width : null, hidden: c.a.hidden === '1', style: c.a.style != null ? +c.a.style : null };
      for (const m of findAll(root, 'mergeCell')) { const [a, b] = (m.a.ref || '').split(':').map(xColIdx); if (a && b) S.merges.push({ r: a.r, c: a.c, rs: b.r - a.r + 1, cs: b.c - a.c + 1 }); }
      let maxR = -1, maxC = -1;
      for (const row of findAll(root, 'row')) {
        const ri = +row.a.r - 1;
        if (row.a.ht || row.a.hidden === '1') S.rows[ri] = { h: row.a.ht ? +row.a.ht : null, hidden: row.a.hidden === '1' };
        let ci = -1;
        for (const c of kids(row, 'c')) {
          const p = xColIdx(c.a.r); ci = p ? p.c : ci + 1;
          const t = c.a.t || 'n', s = +(c.a.s || 0);
          const ve = xKid(c, 'v'); let raw = ve ? textAll(ve) : '';
          let v;
          if (t === 's') v = shared[+raw] != null ? shared[+raw] : '';
          else if (t === 'inlineStr') { const is = xKid(c, 'is'); v = is ? xRichText(is) : ''; }
          else if (t === 'b') v = raw === '1' ? 'TRUE' : raw === '0' ? 'FALSE' : '';
          else if (t === 'str' || t === 'e' || t === 'd') v = raw;
          else v = raw === '' ? '' : Number(raw);
          if (typeof v === 'string') v = v.replace(/\r\n?/g, '\n');
          const cell = { v, t, s };
          S.cells.set(ri + ',' + ci, cell);
          if (v !== '' && v != null) { if (ri > maxR) maxR = ri; if (ci > maxC) maxC = ci; }
        }
      }
      for (const m of S.merges) { maxR = Math.max(maxR, m.r + m.rs - 1); maxC = Math.max(maxC, m.c + m.cs - 1); }
      S.nrows = maxR + 1; S.ncols = maxC + 1;
      if (S.nrows > XLSX_VIEW_LIMIT.rows) { S.nrows = XLSX_VIEW_LIMIT.rows; S.truncated = true; }
      if (S.ncols > XLSX_VIEW_LIMIT.cols) { S.ncols = XLSX_VIEW_LIMIT.cols; S.truncated = true; }
    } catch (e) { S.error = String(e && e.message || e); }
  }
  return { sheets, styles, date1904, hasMacro: names.some(n => /vbaProject\.bin$/i.test(n)) };
}

/* ───────── 3. 표시 형식 (날짜·시각·숫자) ───────── */
const WEEK_KO = ['일', '월', '화', '수', '목', '금', '토'];
const WEEK_KO_LONG = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];
const xPad = (n, k) => String(n).padStart(k, '0');
function xSerialDate(v, date1904) {
  // 엑셀 날짜 일련번호 → {y,m,d,H,M,S,dow}
  let days = Math.floor(v), frac = v - days;
  if (!date1904 && days < 60) days += 1;          // 1900년 2월 29일(없는 날) 보정
  const base = date1904 ? Date.UTC(1904, 0, 1) : Date.UTC(1899, 11, 31);
  const ms = base + (date1904 ? days : days - 1) * 86400000;
  let secs = Math.round(frac * 86400); if (secs >= 86400) secs = 86399;
  const dt = new Date(ms);
  return { y: dt.getUTCFullYear(), m: dt.getUTCMonth() + 1, d: dt.getUTCDate(), H: Math.floor(secs / 3600), M: Math.floor(secs / 60) % 60, S: secs % 60, dow: dt.getUTCDay(), total: v };
}
function xIsDateFmt(code) {
  const c = String(code || '').replace(/"[^"]*"/g, '').replace(/\\./g, '').replace(/\[(?![hms]+\])[^\]]*\]/gi, '');
  return /[ymdhs]/i.test(c) && !/[0#?]/.test(c.replace(/[ymdhs]/gi, ''));
}
function xFmtDate(v, code, date1904) {
  const D = xSerialDate(v, date1904);
  const sec = String(code).split(';')[0];
  const toks = []; let i = 0;
  const hasAmPm = /AM\/PM|A\/P|오전\/오후/i.test(sec);
  while (i < sec.length) {
    const ch = sec[i], rest = sec.slice(i);
    if (ch === '"') { const e = sec.indexOf('"', i + 1); toks.push({ lit: sec.slice(i + 1, e < 0 ? undefined : e) }); i = e < 0 ? sec.length : e + 1; continue; }
    if (ch === '\\') { toks.push({ lit: sec[i + 1] || '' }); i += 2; continue; }
    if (ch === '_' ) { toks.push({ lit: ' ' }); i += 2; continue; }
    if (ch === '*') { i += 2; continue; }
    if (ch === '[') { const e = sec.indexOf(']', i); const inner = sec.slice(i + 1, e); if (/^h+$/i.test(inner)) toks.push({ k: 'H*', n: inner.length }); else if (/^m+$/i.test(inner)) toks.push({ k: 'M*', n: inner.length }); else if (/^s+$/i.test(inner)) toks.push({ k: 'S*', n: inner.length }); i = e < 0 ? sec.length : e + 1; continue; }
    let m;
    if ((m = /^(AM\/PM|A\/P|오전\/오후)/i.exec(rest))) { toks.push({ k: 'ap', s: m[1] }); i += m[1].length; continue; }
    if ((m = /^(y+|m+|d+|h+|s+|a{3,4})/i.exec(rest))) { toks.push({ k: m[1][0].toLowerCase(), n: m[1].length }); i += m[1].length; continue; }
    if (ch === '.' && /^\.0+/.test(rest)) { const z = /^\.0+/.exec(rest)[0]; toks.push({ k: 'frac', n: z.length - 1 }); i += z.length; continue; }
    toks.push({ lit: ch }); i++;
  }
  // m 이 분인지 월인지: 앞에 h 또는 뒤에 s 가 있으면 분
  toks.forEach((t, k) => {
    if (t.k !== 'm') return;
    const prev = toks.slice(0, k).reverse().find(x => x.k), next = toks.slice(k + 1).find(x => x.k);
    if ((prev && (prev.k === 'h' || prev.k === 'H*')) || (next && next.k === 's')) t.k = 'min';
  });
  return toks.map(t => {
    if (t.lit != null) return t.lit;
    switch (t.k) {
      case 'y': return t.n <= 2 ? xPad(D.y % 100, 2) : String(D.y);
      case 'm': return t.n === 1 ? String(D.m) : t.n === 2 ? xPad(D.m, 2) : t.n === 3 ? D.m + '월' : D.m + '월';
      case 'd': return t.n === 1 ? String(D.d) : t.n === 2 ? xPad(D.d, 2) : t.n === 3 ? WEEK_KO[D.dow] : WEEK_KO_LONG[D.dow];
      case 'a': return t.n === 3 ? WEEK_KO[D.dow] : WEEK_KO_LONG[D.dow];
      case 'h': { const h = hasAmPm ? ((D.H % 12) || 12) : D.H; return t.n >= 2 ? xPad(h, 2) : String(h); }
      case 'min': return t.n >= 2 ? xPad(D.M, 2) : String(D.M);
      case 's': return t.n >= 2 ? xPad(D.S, 2) : String(D.S);
      case 'H*': return xPad(Math.floor(D.total * 24), t.n);
      case 'M*': return xPad(Math.floor(D.total * 1440), t.n);
      case 'S*': return xPad(Math.round(D.total * 86400), t.n);
      case 'frac': return t.n ? '.' + xPad(0, t.n) : '';
      case 'ap': return /오전/.test(t.s) ? (D.H < 12 ? '오전' : '오후') : /^A\/P$/i.test(t.s) ? (D.H < 12 ? 'A' : 'P') : (D.H < 12 ? 'AM' : 'PM');
      default: return '';
    }
  }).join('');
}
function xGeneral(v) {
  if (!isFinite(v)) return String(v);
  if (Number.isInteger(v) && Math.abs(v) < 1e11) return String(v);
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-9 || a >= 1e11)) return v.toExponential(5).replace(/\.?0+e/, 'E').replace('E+', 'E+').replace(/e/, 'E');
  return String(Number(v.toPrecision(11)));
}
function xFmtNumber(v, code) {
  const secs = String(code).split(';');
  let sec = secs[0], val = v;
  if (v < 0 && secs.length > 1) { sec = secs[1]; val = -v; }
  else if (v === 0 && secs.length > 2) sec = secs[2];
  if (/^\s*General\s*$/i.test(sec) || !/[0#?]/.test(sec.replace(/"[^"]*"/g, '').replace(/\\./g, ''))) {
    // 숫자 자리가 없는 구역(예: "-") → 글자 그대로
    const lit = sec.replace(/\[[^\]]*\]/g, '').replace(/_./g, ' ').replace(/\*./g, '').replace(/"([^"]*)"/g, '$1').replace(/\\(.)/g, '$1');
    return /General/i.test(lit) ? lit.replace(/General/i, xGeneral(val)) : lit.trim() ? lit : xGeneral(v);
  }
  sec = sec.replace(/\[[^\]]*\]/g, '');
  if (/E[+-]/i.test(sec)) { const dm = /\.([0#]+)E/i.exec(sec); return val.toExponential(dm ? dm[1].length : 0).toUpperCase().replace(/E\+?(-?)(\d)$/, 'E+$10$2').replace('E+-', 'E-'); }
  if (/%/.test(sec.replace(/"[^"]*"/g, ''))) val *= 100;
  // 숫자 자리 부분과 앞뒤 글자 나누기
  let pre = '', num = '', post = '', i = 0, stage = 0;
  while (i < sec.length) {
    const ch = sec[i];
    let piece = ch, isNum = /[0#?.,]/.test(ch);
    if (ch === '"') { const e = sec.indexOf('"', i + 1); piece = sec.slice(i + 1, e < 0 ? undefined : e); i = e < 0 ? sec.length : e + 1; isNum = false; }
    else if (ch === '\\') { piece = sec[i + 1] || ''; i += 2; isNum = false; }
    else if (ch === '_') { piece = ' '; i += 2; isNum = false; }
    else if (ch === '*') { piece = ''; i += 2; isNum = false; }
    else i++;
    if (isNum && stage < 2) { stage = 1; num += piece; }
    else if (stage === 0) pre += piece; else { stage = 2; post += piece; }
  }
  const dot = num.indexOf('.');
  const intPart = dot < 0 ? num : num.slice(0, dot), decPart = dot < 0 ? '' : num.slice(dot + 1).replace(/,/g, '');
  const scaleCommas = (/(,+)$/.exec(intPart) || ['', ''])[1].length;   // 끝 쉼표 = 1000 단위 나눔
  if (scaleCommas) val /= Math.pow(1000, scaleCommas);
  const group = /[0#?],[0#?]/.test(intPart);
  const minInt = (intPart.replace(/,/g, '').match(/0/g) || []).length;
  const decMin = (decPart.match(/0/g) || []).length, decMax = decPart.length;
  let s = val.toFixed(decMax);
  if (decMax > decMin) s = s.replace(new RegExp(`(\\.\\d{${decMin}}\\d*?)0+$`), '$1').replace(/\.$/, '');
  let [ip, dp] = s.split('.');
  if (+ip === 0 && minInt === 0) ip = '';
  ip = ip.padStart(minInt, '0');
  if (group) ip = ip.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const neg = v < 0 && secs.length < 2 ? '-' : '';
  return pre + neg + ip + (dp != null && dp !== '' ? '.' + dp : '') + post;
}
// 칸 하나의 보이는 글자
function xlsxFormat(cell, styles, date1904) {
  if (!cell) return '';
  const v = cell.v;
  if (typeof v !== 'number') {
    const xf = styles.xf[cell.s] || {}; const code = xf.fmt ? (styles.fmt[xf.fmt] || XLSX_BUILTIN_FMT[xf.fmt] || '') : '';
    if (code && code.includes('@') && v !== '') { const secs = code.split(';'); const t = secs[3] || (secs.length === 1 ? secs[0] : ''); if (t && t.includes('@')) return t.replace(/"([^"]*)"/g, '$1').replace(/_./g, ' ').replace(/\\(.)/g, '$1').replace('@', v); }
    return v == null ? '' : String(v);
  }
  const xf = styles.xf[cell.s] || {}, id = xf.fmt || 0;
  const code = styles.fmt[id] || XLSX_BUILTIN_FMT[id] || 'General';
  try {
    if (XLSX_DATE_IDS.has(id) || xIsDateFmt(code)) return v < 0 ? xGeneral(v) : xFmtDate(v, code, date1904);
    if (/^General$/i.test(code)) return xGeneral(v);
    return xFmtNumber(v, code);
  } catch (e) { return xGeneral(v); }
}

/* ───────── 4. HTML 그리기 ───────── */
const xEsc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const xColPx = w => Math.round((w == null ? 8.43 : w) * 7 + 5);
const X_BORDER = { thin: '1px solid', hair: '1px solid', medium: '2px solid', thick: '3px solid', dashed: '1px dashed', mediumDashed: '2px dashed', dotted: '1px dotted', double: '3px double',
  dashDot: '1px dashed', mediumDashDot: '2px dashed', dashDotDot: '1px dotted', mediumDashDotDot: '2px dotted', slantDashDot: '2px dashed' };
// 글자 폭 대략(px): 한글·전각 1em, 그 밖 0.55em
const xTextPx = (s, pt) => { const px = pt * 4 / 3; let w = 0; for (const ch of String(s).split('\n').reduce((a, b) => (b.length > a.length ? b : a), '')) w += /[ᄀ-ᇿ　-鿿가-힯＀-￯]/.test(ch) ? px : px * 0.55; return w + 6; };
function xlsxSheetHtml(S, view) {
  const st = view.styles;
  if (S.error) return `<div style="color:#b00;margin:6px 0">이 시트를 읽지 못했습니다: ${xEsc(S.error)}</div>`;
  if (!S.nrows || !S.ncols) return '<div style="color:#666;margin:6px 0">(빈 시트)</div>';
  const colShown = [], rowShown = [];
  for (let c = 0; c < S.ncols; c++) if (!(S.cols[c] && S.cols[c].hidden)) colShown.push(c);
  for (let r = 0; r < S.nrows; r++) if (!(S.rows[r] && S.rows[r].hidden)) rowShown.push(r);
  const colW = c => xColPx(S.cols[c] && S.cols[c].w != null ? S.cols[c].w : S.defW);
  const cover = new Map();                       // 병합 칸 → 대표 칸
  for (const m of S.merges) for (let r = m.r; r < m.r + m.rs; r++) for (let c = m.c; c < m.c + m.cs; c++) cover.set(r + ',' + c, m);
  const used = new Set();
  const f0 = st.font0 || { sz: 11 };
  let totalW = 0; colShown.forEach(c => { totalW += colW(c); });
  let h = `<table style="border-collapse:collapse;table-layout:fixed;width:${totalW}px;font-family:'Malgun Gothic','맑은 고딕',sans-serif;font-size:${f0.sz}pt;color:#000;background:#fff">`;
  h += '<colgroup>' + colShown.map(c => `<col style="width:${colW(c)}px">`).join('') + '</colgroup>';
  for (const r of rowShown) {
    const rh = S.rows[r] && S.rows[r].h ? S.rows[r].h : S.defH;
    h += `<tr style="height:${(rh * 4 / 3).toFixed(1)}px">`;
    for (let k = 0; k < colShown.length; k++) {
      const c = colShown[k], key = r + ',' + c;
      if (used.has(key)) continue;
      const m = cover.get(key);
      if (m && (m.r !== r || m.c !== c)) continue;   // 병합 칸의 나머지
      const cell = S.cells.get(key);
      const sIdx = cell ? cell.s : (S.cols[c] && S.cols[c].style != null ? S.cols[c].style : 0);
      const xf = st.xf[sIdx] || {};
      const text = xlsxFormat(cell, st, view.date1904);
      let rs = 1, cs = 1;
      if (m) {
        rs = rowShown.filter(x => x >= m.r && x < m.r + m.rs).length || 1;
        cs = colShown.filter(x => x >= m.c && x < m.c + m.cs).length || 1;
        for (let rr = m.r; rr < m.r + m.rs; rr++) for (let cc = m.c; cc < m.c + m.cs; cc++) used.add(rr + ',' + cc);
      } else if (text && !xf.wrap && !/\n/.test(text) && (!xf.h || xf.h === 'left' || xf.h === 'general') && typeof (cell && cell.v) !== 'number') {
        // 줄바꿈 없는 글자가 칸보다 길면 오른쪽 빈 칸으로 넘쳐 보이게(엑셀과 같게)
        const need = xTextPx(text, xf.font ? xf.font.sz : f0.sz); let w = colW(c), j = k + 1;
        while (w < need && j < colShown.length) {
          const nk = r + ',' + colShown[j], nc = S.cells.get(nk);
          if (cover.has(nk) || (nc && nc.v !== '' && nc.v != null)) break;
          w += colW(colShown[j]); used.add(nk); cs++; j++;
        }
      }
      const css = ['padding:1px 3px', 'overflow:hidden'];
      const f = xf.font;
      if (f) { if (f.b) css.push('font-weight:bold'); if (f.i) css.push('font-style:italic'); if (f.u || f.strike) css.push(`text-decoration:${f.u ? 'underline' : ''}${f.strike ? ' line-through' : ''}`); if (f.sz && f.sz !== f0.sz) css.push(`font-size:${f.sz}pt`); if (f.color) css.push(`color:${f.color}`); }
      if (xf.fill) css.push(`background:${xf.fill}`);
      const isNum = cell && typeof cell.v === 'number';
      const ha = xf.h === 'center' || xf.h === 'centerContinuous' ? 'center' : xf.h === 'right' ? 'right' : xf.h === 'justify' || xf.h === 'distributed' ? 'justify' : xf.h === 'left' ? 'left' : isNum ? 'right' : (cell && cell.t === 'b' ? 'center' : 'left');
      css.push(`text-align:${ha}`);
      css.push(`vertical-align:${xf.v === 'center' ? 'middle' : xf.v === 'top' ? 'top' : 'bottom'}`);
      css.push(xf.wrap || /\n/.test(text) ? 'white-space:pre-wrap;word-break:break-all' : 'white-space:nowrap');
      if (xf.indent) css.push(`padding-left:${3 + xf.indent * 9}px`);
      // 테두리: 병합 칸이면 오른쪽·아래쪽은 끝 칸의 테두리도 살핌
      let bd = xf.border || {};
      if (m) {
        const endR = st.xf[(S.cells.get((m.r + m.rs - 1) + ',' + m.c) || {}).s] || {}, endC = st.xf[(S.cells.get(m.r + ',' + (m.c + m.cs - 1)) || {}).s] || {};
        bd = { ...bd, ...(endR.border && endR.border.bottom ? { bottom: endR.border.bottom } : {}), ...(endC.border && endC.border.right ? { right: endC.border.right } : {}) };
      }
      for (const side of ['left', 'right', 'top', 'bottom']) if (bd[side]) css.push(`border-${side}:${X_BORDER[bd[side].style] || '1px solid'} ${bd[side].color}`);
      h += `<td${rs > 1 ? ` rowspan="${rs}"` : ''}${cs > 1 ? ` colspan="${cs}"` : ''} style="${css.join(';')}">${xEsc(text)}</td>`;
    }
    h += '</tr>';
  }
  return h + '</table>';
}
// 엑셀 전체 → HTML (시트마다 이름 + 표). 원본 보기·이력 문서 그림용
function xlsxHtml(view, title) {
  let out = `<div class="odt-page xlsx-page" style="width:max-content;min-width:18cm;background:#fff;color:#000;padding:0.8cm 1cm;font-family:'Malgun Gothic',sans-serif;font-size:10pt">`;
  if (title) out += `<div style="font-size:9pt;color:#666;margin-bottom:6px">${xEsc(title)}</div>`;
  const shown = view.sheets.filter(s => !s.hidden);
  const hidden = view.sheets.length - shown.length;
  shown.forEach((S, i) => {
    out += `<div style="margin:${i ? 18 : 4}px 0 6px;font-weight:bold;font-size:10.5pt;border-bottom:2px solid #1f6e43;color:#1f6e43;padding-bottom:2px">▦ 시트 ${i + 1}/${shown.length} · ${xEsc(S.name)}</div>`;
    out += xlsxSheetHtml(S, view);
    const notes = [];
    if (S.truncated) notes.push(`행·열이 많아 앞부분(최대 ${XLSX_VIEW_LIMIT.rows}행 × ${XLSX_VIEW_LIMIT.cols}열)만 표시`);
    if (S.drawing) notes.push('그림·도형·차트는 표시하지 않음');
    if (notes.length) out += `<div style="font-size:8.5pt;color:#8a6d00;margin-top:3px">※ ${notes.join(' · ')} — 전체는 [원본 파일 열기]로 확인</div>`;
  });
  if (!shown.length) out += '<div style="color:#666">표시할 시트가 없습니다.</div>';
  if (hidden) out += `<div style="font-size:8.5pt;color:#666;margin-top:8px">숨긴 시트 ${hidden}개는 표시하지 않았습니다.</div>`;
  return out + '</div>';
}
