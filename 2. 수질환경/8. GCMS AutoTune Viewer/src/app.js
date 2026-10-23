(() => {
'use strict';

/* =====================================================================
 * GC/MS Autotune 판독기
 *  - PDF/이미지 → (pdf.js) 렌더링 → 영역(ROI)별 전처리 → (Tesseract.js) OCR
 *  - 규칙 기반 값 추출 → 판정 → 원본/재구성 화면 비교, 이력·트렌드, A4 평가서
 * ===================================================================== */

/* ---------------------------------------------------------------- 상수 */
const REF_W = 2481;                       // 모든 페이지를 A4 300dpi 폭으로 정규화
const ROI_KEYS = ['header', 'param', 'actual', 'temp', 'target', 'ramp'];
const ROI_DEF = {                         // 페이지 대비 비율 [x1, y1, x2, y2]
  header: [0.03, 0.000, 0.97, 0.115],
  param:  [0.555, 0.115, 0.935, 0.315],
  actual: [0.05, 0.325, 0.57, 0.405],
  temp:   [0.555, 0.325, 0.935, 0.400],
  target: [0.05, 0.615, 0.935, 0.705],
  ramp:   [0.05, 0.735, 0.935, 0.775],
};
const ROI_LABEL = {
  header: '헤더', param: '파라미터 표', actual: 'Actual m/z 표',
  temp: '온도·압력', target: 'Target m/z 표 + Air/Water', ramp: 'Ramp Criteria',
};
const NOMINAL = [69, 219, 502];
const ISO_MZ = [70, 220, 503];
const ISO_THEORY = [1.08, 4.32, 10.09];

// [왼쪽키, 왼쪽라벨, 왼쪽형식, 오른쪽키, 오른쪽라벨, 오른쪽형식]
const PARAM_ROWS = [
  ['ion_polarity', 'Ion Polarity', 'text', 'pftba', 'PFTBA', 'text'],
  ['emission', 'Emission', 'float', 'mass_gain', 'Mass Gain', 'float'],
  ['electron_energy', 'Electron Energy', 'float', 'mass_offset', 'Mass Offset', 'float'],
  ['filament', 'Filament', 'float', 'amu_gain', 'Amu Gain', 'float'],
  ['repeller', 'Repeller', 'float', 'amu_offset', 'Amu Offset', 'float'],
  ['ion_focus', 'Ion Focus', 'float', 'width219', 'Width219', 'float'],
  ['entrance_lens', 'Entrance Lens', 'float', 'dc_polarity', 'DC Polarity', 'text'],
  ['ent_lens_offset', 'Ent Lens Offset', 'float', 'hed_enable', 'HED Enable', 'text'],
  ['ion_body', 'Ion Body', 'float', 'em_volts', 'EM Volts', 'float'],
  ['post_extractor_1', 'Post Extractor 1', 'float', 'extractor_lens', 'Extractor Lens', 'float'],
  ['post_extractor_2', 'Post Extractor 2', 'float', 'scan_speed', 'Scan Speed', 'float'],
  ['jetclean_flow', 'JetClean Flow', 'float', 'averages', 'Averages', 'float'],
];

const CATEGORIES = { ion_polarity: ['Pos', 'Neg'], dc_polarity: ['Pos', 'Neg'], hed_enable: ['On', 'Off'] };
const V = { OK: '정상', WARN: '주의', FAIL: '경고', UNK: '확인필요' };
const VCLS = { '정상': 'ok', '주의': 'warn', '경고': 'fail', '확인필요': 'unk' };
const RANK = { '정상': 0, '주의': 1, '확인필요': 2, '경고': 3 };
const worst = (a, b) => (RANK[a] >= RANK[b] ? a : b);

const DEFAULT_CRIT = {
  massTol: 0.2, massImplausible: 2.0,
  pwTarget: 0.60, pwTol: 0.05,
  rel219Min: 40, rel502Min: 2,
  isoTolPct: 20, isoAbundMin: 1000,
  abund69Min: 200000, abund69Max: 550000,
  emNormalMax: 1600, emWarnMax: 2800, emLimit: 3000,
  repellerWarnPct: 90, ionFocusWarnPct: 85,
  repellerMaxDefault: 35, ionFocusMaxDefault: 90,
  airWaterMax: 10,
  hiVacMin: 1e-6, hiVacMax: 1.4e-4,
  turboMin: 95,
};
const DEFAULT_OPTS = {
  reocr: true, lowConf: 60, autoSave: false,
  roi: { dx: 0, dy: 0, scale: 1 },
};

/* ---------------------------------------------------------------- 유틸 */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fmtNum = (v, d = 2) => (v == null || !isFinite(v) ? '-' : Number(v).toFixed(d));
const fmtInt = (v) => (v == null || !isFinite(v) ? '-' : Math.round(v).toLocaleString('en-US'));
const fmtSci = (v) => {
  if (v == null || !isFinite(v) || v <= 0) return '-';
  const e = Math.floor(Math.log10(v)); const m = v / Math.pow(10, e);
  return `${m.toFixed(2)}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`;
};
const pad2 = (n) => String(n).padStart(2, '0');

const store = {
  mem: {},
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return k in this.mem ? this.mem[k] : d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { this.mem[k] = v; } },
};

let crit = Object.assign({}, DEFAULT_CRIT, store.get('gcmsAT.crit', {}));
let opts = Object.assign({}, DEFAULT_OPTS, store.get('gcmsAT.opts', {}));
opts.roi = Object.assign({}, DEFAULT_OPTS.roi, opts.roi || {});

function toast(msg, ms = 3200) {
  const t = document.createElement('div');
  t.className = 'toast'; t.textContent = msg; t.setAttribute('role', 'status');
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

/* ---------------------------------------------------- 라이브러리 준비 */
let pdfReady = false;
function ensurePdfJs() {
  if (pdfReady) return;
  const src = document.getElementById('lib-pdfworker').textContent;
  const url = URL.createObjectURL(new Blob([src], { type: 'text/javascript' }));
  window.pdfjsLib.GlobalWorkerOptions.workerSrc = url;
  pdfReady = true;
}

let ocrPromise = null;
let ocrListener = null;
function getOcr() {
  if (ocrPromise) return ocrPromise;
  ocrPromise = (async () => {
    const coreSrc = document.getElementById('lib-core').textContent;
    const workerSrc = document.getElementById('lib-tworker').textContent;
    const engB64 = document.getElementById('data-eng').textContent.replace(/\s+/g, '');
    // 워커 안에서: (1) 코어를 미리 정의 → CDN 호출 불필요, (2) 언어데이터 fetch를 내장본으로 대체
    const prelude = `
;self.__ENG_GZ_B64="${engB64}";
(function(){
  var origFetch = self.fetch ? self.fetch.bind(self) : null;
  self.fetch = function(url, o){
    var u = String(url);
    if (/eng\\.traineddata(\\.gz)?$/.test(u)) {
      var bin = atob(self.__ENG_GZ_B64), n = bin.length, bytes = new Uint8Array(n);
      for (var i = 0; i < n; i++) bytes[i] = bin.charCodeAt(i);
      return Promise.resolve(new Response(bytes, { status: 200, headers: { 'Content-Type': 'application/octet-stream' } }));
    }
    return origFetch ? origFetch(url, o) : Promise.reject(new Error('offline'));
  };
})();
;`;
    const blob = new Blob([coreSrc, '\n', prelude, '\n', workerSrc], { type: 'text/javascript' });
    const workerUrl = URL.createObjectURL(blob);
    const worker = await window.Tesseract.createWorker('eng', 1, {
      workerPath: workerUrl, workerBlobURL: false,
      corePath: 'https://offline.invalid/tesseract-core-simd-lstm.wasm.js',
      langPath: 'https://offline.invalid/tessdata',
      cacheMethod: 'none', gzip: true,
      logger: (m) => { if (ocrListener) ocrListener(m); },
    });
    await worker.setParameters({
      tessedit_pageseg_mode: '6', preserve_interword_spaces: '1', user_defined_dpi: '300',
    });
    return worker;
  })();
  ocrPromise.catch(() => { ocrPromise = null; });
  return ocrPromise;
}

/* ------------------------------------------------- 페이지 렌더링/전처리 */
async function renderPage(src, pageNo) {
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d');
  if (src.kind === 'pdf') {
    const page = await src.pdfDoc.getPage(pageNo);
    const v1 = page.getViewport({ scale: 1 });
    const vp = page.getViewport({ scale: REF_W / v1.width });
    c.width = Math.round(vp.width); c.height = Math.round(vp.height);
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height);
    await page.render({ canvasContext: ctx, viewport: vp }).promise;
  } else {
    const bmp = await createImageBitmap(src.file);
    const sc = REF_W / bmp.width;
    c.width = REF_W; c.height = Math.round(bmp.height * sc);
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height);
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(bmp, 0, 0, c.width, c.height);
    if (bmp.close) bmp.close();
  }
  return c;
}

const canvasToBlob = (c, type = 'image/png', q) => new Promise((res) => c.toBlob(res, type, q));

function roiRect(key, W, H, nud) {
  const [x1, y1, x2, y2] = ROI_DEF[key];
  const f = (v, d) => 0.5 + (v - 0.5) * nud.scale + d;
  const X1 = Math.max(0, Math.round(f(x1, nud.dx) * W));
  const Y1 = Math.max(0, Math.round(f(y1, nud.dy) * H));
  const X2 = Math.min(W, Math.round(f(x2, nud.dx) * W));
  const Y2 = Math.min(H, Math.round(f(y2, nud.dy) * H));
  return { x: X1, y: Y1, w: Math.max(20, X2 - X1), h: Math.max(20, Y2 - Y1) };
}

function cropToCanvas(src, rect, pad = 20) {
  const c = document.createElement('canvas');
  c.width = rect.w + pad * 2; c.height = rect.h + pad * 2;
  const x = c.getContext('2d', { willReadFrequently: true });
  x.fillStyle = '#fff'; x.fillRect(0, 0, c.width, c.height);
  x.drawImage(src, rect.x, rect.y, rect.w, rect.h, pad, pad, rect.w, rect.h);
  return { canvas: c, ox: rect.x - pad, oy: rect.y - pad };
}

function otsu(gray) {
  const hist = new Uint32Array(256);
  for (let i = 0; i < gray.length; i++) hist[gray[i]]++;
  const total = gray.length; let sum = 0;
  for (let i = 0; i < 256; i++) sum += i * hist[i];
  let sumB = 0, wB = 0, max = -1, thr = 127;
  for (let t = 0; t < 256; t++) {
    wB += hist[t]; if (!wB) continue;
    const wF = total - wB; if (!wF) break;
    sumB += t * hist[t];
    const mB = sumB / wB, mF = (sum - sumB) / wF;
    const v = wB * wF * (mB - mF) * (mB - mF);
    if (v > max) { max = v; thr = t; }
  }
  return thr;
}

/* 표 격자선 제거: 가로/세로로 길게 이어진 선(런) 제거 (OpenCV MORPH_OPEN과 동일 원리) */
function removeGridlines(src, hLen = 25, vLen = 25) {
  const w = src.width, h = src.height;
  const d = src.getContext('2d').getImageData(0, 0, w, h).data;
  const n = w * h, gray = new Uint8Array(n);
  for (let i = 0, p = 0; i < n; i++, p += 4) gray[i] = (d[p] * 299 + d[p + 1] * 587 + d[p + 2] * 114) / 1000 | 0;
  const thr = otsu(gray);
  const fg = new Uint8Array(n);
  for (let i = 0; i < n; i++) fg[i] = gray[i] <= thr ? 1 : 0;
  const line = new Uint8Array(n);
  for (let y = 0; y < h; y++) {
    let x = 0;
    while (x < w) {
      if (fg[y * w + x]) {
        const s = x; while (x < w && fg[y * w + x]) x++;
        if (x - s >= hLen) for (let k = s; k < x; k++) line[y * w + k] = 1;
      } else x++;
    }
  }
  for (let x = 0; x < w; x++) {
    let y = 0;
    while (y < h) {
      if (fg[y * w + x]) {
        const s = y; while (y < h && fg[y * w + x]) y++;
        if (y - s >= vLen) for (let k = s; k < y; k++) line[k * w + x] = 1;
      } else y++;
    }
  }
  const out = document.createElement('canvas'); out.width = w; out.height = h;
  const octx = out.getContext('2d', { willReadFrequently: true });
  const od = octx.createImageData(w, h);
  for (let i = 0, p = 0; i < n; i++, p += 4) {
    const v = (fg[i] && !line[i]) ? 0 : 255;
    od.data[p] = od.data[p + 1] = od.data[p + 2] = v; od.data[p + 3] = 255;
  }
  octx.putImageData(od, 0, 0);
  return out;
}

/* ------------------------------------------------------------ OCR 호출 */
function flatten(data, ox, oy, sc = 1) {
  const tb = (bb) => ({ x0: bb.x0 / sc + ox, y0: bb.y0 / sc + oy, x1: bb.x1 / sc + ox, y1: bb.y1 / sc + oy });
  const lines = [];
  (data.blocks || []).forEach((b) => b.paragraphs.forEach((p) => p.lines.forEach((l) => {
    const words = (l.words || []).map((w) => ({ text: (w.text || '').trim(), conf: w.confidence, bbox: tb(w.bbox) })).filter((w) => w.text);
    if (!words.length) return;
    lines.push({ text: words.map((w) => w.text).join(' '), conf: l.confidence, bbox: tb(l.bbox), words });
  })));
  lines.sort((a, b) => (a.bbox.y0 + a.bbox.y1) / 2 - (b.bbox.y0 + b.bbox.y1) / 2 || a.bbox.x0 - b.bbox.x0);
  return lines;
}

async function ocrCanvas(worker, canvas, { psm = 6, whitelist = '' } = {}) {
  await worker.setParameters({ tessedit_pageseg_mode: String(psm), tessedit_char_whitelist: whitelist });
  const blob = await canvasToBlob(canvas, 'image/png');
  const { data } = await worker.recognize(blob, {}, { blocks: true, text: true });
  return data;
}

/* ------------------------------------------------------ 값 파싱 도구들 */
function sanitizeNum(s) {
  return String(s == null ? '' : s)
    .replace(/[−–—]/g, '-').replace(/[|\[\]()'"`“”‘’:;_~!*]/g, '').replace(/\s+/g, '')
    .replace(/[OoQDGC¢]/g, '0').replace(/[Il]/g, '1')
    .replace(/(\d)-(\d)/, '$1.$2').replace(/,(?=\d{1,2}$)/, '.').replace(/^[,.]+|[,.]+$/g, '');
}
function pFloat(s) {
  const t = sanitizeNum(s);
  return /^[+-]?\d*\.?\d+$/.test(t) ? parseFloat(t) : null;
}
function pInt(s) {
  const t = sanitizeNum(s).replace(/[,.](?=\d{3}(?:\D|$))/g, '');
  return /^\d+$/.test(t) ? parseInt(t, 10) : null;
}
function pPct(s) {
  const t = sanitizeNum(String(s == null ? '' : s).replace(/%/g, ''));
  const m = t.match(/^(\d+)\.(\d)\d+$/);          // 5.29 → 5.2 (표 형식은 항상 소수 1자리)
  return pFloat(m ? m[1] + '.' + m[2] : t);
}
function pMz(s) { const t = sanitizeNum(s); return /^\d{1,3}\.\d{1,2}$/.test(t) ? parseFloat(t) : null; }
function pSci(s) {
  const t = String(s == null ? '' : s).replace(/[−–—]/g, '-').replace(/\s+/g, '').replace(/[Oo]/g, '0');
  const m = t.match(/^(\d+(?:\.\d+)?)[eE]([+-]?\d+)$/);
  if (m) return parseFloat(m[1] + 'e' + m[2]);
  const v = parseFloat(t); return isFinite(v) ? v : null;
}
const PARSERS = { mz: pMz, int: pInt, pct: pPct, float: pFloat, sci: pSci, text: () => null };
const FORMATTERS = {
  mz: (v) => v.toFixed(2), int: (v) => v.toLocaleString('en-US'), pct: (v) => v.toFixed(1) + '%',
};

function lev(a, b) {
  const m = a.length, n = b.length;
  if (!m) return n; if (!n) return m;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = cur;
  }
  return prev[n];
}
function sim(a, b) {
  a = a.toLowerCase().replace(/[^a-z]/g, ''); b = b.toLowerCase().replace(/[^a-z]/g, '');
  if (!a || !b) return 0;
  return 1 - lev(a, b) / Math.max(a.length, b.length);
}

const normTok = (t) => String(t || '').toLowerCase().replace(/[^a-z0-9.%\-+:/\\]/g, '');
function unionBox(ws) {
  if (!ws.length) return null;
  return { x0: Math.min(...ws.map((w) => w.bbox.x0)), y0: Math.min(...ws.map((w) => w.bbox.y0)), x1: Math.max(...ws.map((w) => w.bbox.x1)), y1: Math.max(...ws.map((w) => w.bbox.y1)) };
}
function meanConf(ws) {
  const c = ws.map((w) => w.conf).filter((v) => v != null && isFinite(v));
  return c.length ? c.reduce((a, b) => a + b, 0) / c.length : null;
}
/* 문자열(공백 구분 토큰)에 대응하는 단어들을 라인에서 순서대로 찾는다 */
function wordsForStr(line, str) {
  const toks = String(str).split(/\s+/).filter(Boolean);
  const out = []; let j = 0;
  for (const tk of toks) {
    const nt = normTok(tk); if (!nt) continue;
    for (let k = j; k < line.words.length; k++) {
      const nw = normTok(line.words[k].text);
      if (nw && (nw.includes(nt) || (nw.length >= 2 && nt.includes(nw)))) { out.push(line.words[k]); j = k + 1; break; }
    }
  }
  return out;
}

function addField(F, id, o) {
  F[id] = Object.assign({ id, label: '', text: '', num: null, conf: null, bbox: null, type: 'float', roi: '', edited: false, refined: false }, o);
  return F[id];
}
/* 라인 + 매칭 문자열 → 필드 */
function fieldFromMatch(F, id, label, type, roi, line, str) {
  const ws = wordsForStr(line, str);
  const num = PARSERS[type](str);
  const fmt = FORMATTERS[type];
  return addField(F, id, {
    label, type, roi,
    text: (fmt && num != null) ? fmt(num) : String(str).trim(),
    num,
    conf: ws.length ? meanConf(ws) : line.conf,
    bbox: ws.length ? unionBox(ws) : line.bbox,
  });
}

/* 숫자 표 행: 숫자 사이에 섞인 C/O/D/G 등을 0으로 바로잡는다 */
function fixLine(line) {
  const f = (t) => (/\d/.test(t) && /^[\d.,%CcOoDGgQ¢Il]+$/.test(t) ? t.replace(/[CcOoDGgQ¢]/g, '0').replace(/[Il]/g, '1') : t);
  const words = line.words.map((w) => Object.assign({}, w, { text: f(w.text) }));
  return Object.assign({}, line, { words, text: words.map((w) => w.text).join(' ') });
}

/* ------------------------------------------------------------- 파싱 */
function parseHeader(F, o) {
  for (const l of o.lines) {
    let m;
    if (!F['h.title'] && (m = l.text.match(/(Auto\s*tune\s*[-–—]?\s*\w+)/i))) {
      addField(F, 'h.title', { label: '리포트 제목', type: 'text', roi: 'header', text: m[1].replace(/\s+/g, ' '), conf: meanConf(wordsForStr(l, m[1])) ?? l.conf, bbox: unionBox(wordsForStr(l, m[1])) || l.bbox });
    }
    if (!F['h.time'] && (m = l.text.match(/(\d{1,2}\/\d{1,2}\/\d{4}\s+\d{1,2}:\d{2}\s*[AaPp][Mm])(\s*\(UTC[^)]*\))?/))) {
      const str = (m[1] + (m[2] || '')).replace(/\s+/g, ' ');
      const ws = wordsForStr(l, str);
      addField(F, 'h.time', { label: '튠 일시', type: 'text', roi: 'header', text: str, conf: meanConf(ws) ?? l.conf, bbox: unionBox(ws) || l.bbox });
    }
    if (!F['h.method'] && (m = l.text.match(/([A-Za-z]:\\.*?\.u)\b/))) {
      const mp = m[1].replace(/\s+/g, '');
      let k = l.words.findIndex((w) => /\.u$/i.test(w.text)); if (k < 0) k = l.words.length - 1;
      const ws = l.words.slice(0, k + 1);
      addField(F, 'h.method', { label: '메소드 경로', type: 'text', roi: 'header', text: mp, conf: meanConf(ws) ?? l.conf, bbox: unionBox(ws) || l.bbox });
    }
    if (!F['h.serial'] && (m = l.text.match(/\b([A-Z]{2}\d{3,}[A-Z0-9]{3,})\b/))) {
      const ws = wordsForStr(l, m[1]);
      addField(F, 'h.serial', { label: '장비 S/N', type: 'text', roi: 'header', text: m[1], conf: meanConf(ws) ?? l.conf, bbox: unionBox(ws) || l.bbox });
    }
    if (!F['h.inst'] && (m = l.text.match(/\b(GCMSD)\b/i))) {
      const ws = wordsForStr(l, m[1]);
      addField(F, 'h.inst', { label: '장비명', type: 'text', roi: 'header', text: m[1].toUpperCase(), conf: meanConf(ws) ?? l.conf, bbox: unionBox(ws) || l.bbox });
    }
  }
}

function parseParam(F, o) {
  const rect = o.rect, W = rect.w, Hh = rect.h;
  const used = new Set();
  for (const line of o.lines) {
    const zones = { l1: [], v1: [], l2: [], v2: [] };
    for (const w of line.words) {
      const cx = (w.bbox.x0 + w.bbox.x1) / 2; const rel = (cx - rect.x) / W;
      zones[rel < 0.30 ? 'l1' : rel < 0.485 ? 'v1' : rel < 0.74 ? 'l2' : 'v2'].push(w);
    }
    const t1 = zones.l1.map((w) => w.text).join(' '), t2 = zones.l2.map((w) => w.text).join(' ');
    const yc = ((line.bbox.y0 + line.bbox.y1) / 2 - rect.y) / Hh;
    let best = -1, bs = 0;
    PARAM_ROWS.forEach((r, i) => {
      if (used.has(i)) return;
      const a = t1 ? sim(t1, r[1]) : 0, b = t2 ? sim(t2, r[4]) : 0;
      let s = (t1 && t2) ? (a + b) / 2 : Math.max(a, b);
      if (s < 0.5) return;
      s -= Math.abs(yc - (38 + 56.5 * i) / 702) * 0.8;
      if (s > bs) { bs = s; best = i; }
    });
    if (best < 0) continue;
    used.add(best);
    const r = PARAM_ROWS[best];
    [[zones.v1, r[0], r[1], r[2]], [zones.v2, r[3], r[4], r[5]]].forEach(([ws, key, label, type]) => {
      if (!ws.length) return;
      const raw = ws.map((w) => w.text).join('');
      let text, num = null;
      if (type === 'text') {
        text = raw.replace(/[^A-Za-z]/g, ''); if (!text) return;
        const ch = CATEGORIES[key];
        if (ch) { let bs = 0, bc = null; ch.forEach((c) => { const sc = sim(text, c); if (sc > bs) { bs = sc; bc = c; } }); if (bc && bs >= 0.5) text = bc; }
      }
      else { text = sanitizeNum(raw); num = pFloat(raw); if (!text) return; }
      addField(F, 'p.' + key, { label, type, roi: 'param', text, num, conf: meanConf(ws), bbox: unionBox(ws) });
    });
  }
  // 핵심 3개는 라벨 매칭 실패 시 정규식으로 한 번 더 시도
  const fb = [['repeller', 'Repeller', /Repel\w*\D+(\d+\.?\d*)/i], ['ion_focus', 'Ion Focus', /[IJil1][oc0]n\s*Focus\D+(\d+\.?\d*)/i], ['em_volts', 'EM Volts', /EM\s*Vo[l1]ts?\D+(\d+\.?\d*)/i]];
  for (const [key, label, re] of fb) {
    if (F['p.' + key]) continue;
    for (const l of o.lines) {
      const m = l.text.match(re);
      if (m) { fieldFromMatch(F, 'p.' + key, label, 'float', 'param', l, m[1]); break; }
    }
  }
}

function nearestRow(mz) {
  let bi = -1, bd = 1e9;
  NOMINAL.forEach((n, i) => { const d = Math.abs(n - mz); if (d < bd) { bd = d; bi = i; } });
  return bd <= 30 ? bi : -1;
}

function parseActual(F, o) {
  const re = /(\d{2,3}[.,]\d{1,2})\s+([\d,.]+)\s+(\d{1,3}[.,]\d{1,2})\s*%?\s+(\d[.,]\d{2})/;
  let order = 0;
  for (const l0 of o.lines) {
    const l = fixLine(l0);
    const m = l.text.match(re); if (!m) continue;
    let ri = nearestRow(pMz(m[1]) ?? 0); if (ri < 0) ri = order;
    order++;
    if (F[`am.r${ri}.mz`]) continue;
    const ws = wordsForStr(l, [m[1], m[2], m[3], m[4]].join(' '));
    const mk = (k, label, type, str, idx) => {
      const w = wordsForStr(l, str)[0];
      const num = PARSERS[type](str);
      addField(F, `am.r${ri}.${k}`, { label, type, roi: 'actual', text: (FORMATTERS[type] && num != null) ? FORMATTERS[type](num) : str, num, conf: w ? w.conf : l.conf, bbox: w ? w.bbox : l.bbox });
    };
    // 단어 매핑은 라인 안에서 순서대로 진행
    const toks = [m[1], m[2], m[3], m[4]]; const types = ['mz', 'int', 'pct', 'float']; const keys = ['mz', 'abund', 'rel', 'pw50'];
    const labels = ['Actual m/z', 'Abund', 'Rel Abund', 'PW50'];
    let j = 0;
    toks.forEach((tk, idx) => {
      const nt = normTok(tk); let w = null;
      for (let k = j; k < l.words.length; k++) { const nw = normTok(l.words[k].text); if (nw && (nw.includes(nt) || nt.includes(nw))) { w = l.words[k]; j = k + 1; break; } }
      const num = PARSERS[types[idx]](tk);
      addField(F, `am.r${ri}.${keys[idx]}`, { label: labels[idx], type: types[idx], roi: 'actual', text: (FORMATTERS[types[idx]] && num != null) ? FORMATTERS[types[idx]](num) : sanitizeNum(tk), num, conf: w ? w.conf : l.conf, bbox: w ? w.bbox : l.bbox });
    });
    void ws; void mk;
  }
}

function parseTemp(F, o) {
  for (const l of o.lines) {
    let m;
    if ((m = l.text.match(/Source\D*(\d{2,3})/i)) && !F['tp.source']) fieldFromMatch(F, 'tp.source', 'MS Source (℃)', 'float', 'temp', l, m[1]);
    if ((m = l.text.match(/Quad\D*(\d{2,3})/i)) && !F['tp.quad']) fieldFromMatch(F, 'tp.quad', 'MS Quad (℃)', 'float', 'temp', l, m[1]);
    if ((m = l.text.match(/Turbo\s*Speed\D*(\d+\.?\d*)/i)) && !F['tp.turbo']) fieldFromMatch(F, 'tp.turbo', 'Turbo Speed (%)', 'float', 'temp', l, m[1]);
    if ((m = l.text.match(/Vac\W*(\d+(?:\.\d+)?\s*[eE]\s*[-+−]?\s*\d+|\d+\.\d+)/i)) && !F['tp.hivac']) {
      const str = m[1].replace(/\s+/g, '');
      const ws = wordsForStr(l, str);
      addField(F, 'tp.hivac', { label: 'Hi Vac (Torr)', type: 'sci', roi: 'temp', text: str, num: pSci(str), conf: ws.length ? meanConf(ws) : l.conf, bbox: ws.length ? unionBox(ws) : l.bbox });
    }
  }
}

function parseTarget(F, o) {
  const re = /(\d{2,3}[.,]\d{2})\s+(\d{2,3}[.,]\d{2})\s+([\d,.]+)\s+(\d{1,3}[.,]\d{1,2})\s*%?\s+(\d{2,3}[.,]\d{2})\s+([\d,.]+)\s+(\d{1,3}[.,]\d{1,2})\s*%?/;
  const keys = ['target', 'actual', 'abund', 'rel', 'isomz', 'isoabund', 'isoratio'];
  const types = ['mz', 'mz', 'int', 'pct', 'mz', 'int', 'pct'];
  const labels = ['Target m/z', 'Actual m/z', 'Abund', 'Rel Abund', 'Iso m/z', 'Iso Abund', 'Iso Ratio'];
  let order = 0;
  for (const l0 of o.lines) {
    const l = /^\s*[\dCcOoQ¢]{2,3}[.,]/.test(l0.text) ? fixLine(l0) : l0;
    const m = l.text.match(re);
    if (m) {
      let ri = nearestRow(pMz(m[1]) ?? 0); if (ri < 0) ri = order;
      order++;
      if (F[`tt.r${ri}.target`]) continue;
      let j = 0;
      for (let idx = 0; idx < 7; idx++) {
        const tk = m[idx + 1]; const nt = normTok(tk); let w = null;
        for (let k = j; k < l.words.length; k++) { const nw = normTok(l.words[k].text); if (nw && (nw.includes(nt) || nt.includes(nw))) { w = l.words[k]; j = k + 1; break; } }
        const num = PARSERS[types[idx]](tk);
        addField(F, `tt.r${ri}.${keys[idx]}`, { label: labels[idx], type: types[idx], roi: 'target', text: (FORMATTERS[types[idx]] && num != null) ? FORMATTERS[types[idx]](num) : sanitizeNum(tk), num, conf: w ? w.conf : l.conf, bbox: w ? w.bbox : l.bbox });
      }
      continue;
    }
    // Air/Water
    if (/H2|H20|Water|N2/i.test(l.text) && /%/.test(l.text) && !F['aw.h2o']) {
      const re2 = /([A-Za-z0-9\/]{2,6})\s*~?\s*(\d+(?:\.\d+)?)\s*%/g; let mm;
      while ((mm = re2.exec(l.text))) {
        const lab = mm[1].toUpperCase().replace(/[^A-Z0-9\/]/g, '');
        let id = null, label = '';
        if (lab.includes('/')) { id = 'aw.n2h2o'; label = 'N2/H2O'; }
        else if (/^C/.test(lab)) { id = 'aw.co2'; label = 'CO2'; }
        else if (/^H/.test(lab)) { id = 'aw.h2o'; label = 'H2O'; }
        else if (/^N/.test(lab)) { id = 'aw.n2'; label = 'N2'; }
        else if (/^[O0]/.test(lab)) { id = 'aw.o2'; label = 'O2'; }
        if (!id || F[id]) continue;
        const ws = wordsForStr(l, mm[2] + '%'); const w = ws[ws.length - 1];
        addField(F, id, { label, type: 'pct', roi: 'target', text: mm[2] + '%', num: parseFloat(mm[2]), conf: w ? w.conf : l.conf, bbox: w ? w.bbox : l.bbox });
      }
    }
  }
}

function parseRamp(F, o) {
  let idxLine = 0;
  for (const l of o.lines) {
    if (!/volts?/i.test(l.text)) continue;
    const isFocus = /Focus/i.test(l.text) || (!/Repe/i.test(l.text) && idxLine === 0);
    const pre = isFocus ? 'rc.ionfocus' : 'rc.repeller';
    idxLine++;
    let m;
    if ((m = l.text.match(/(\d+(?:\.\d+)?)\s*volts?/i))) fieldFromMatch(F, pre + '_max', isFocus ? 'Ion Focus 상한(V)' : 'Repeller 상한(V)', 'float', 'ramp', l, m[1]);
    if ((m = l.text.match(/ion\s*([A-Za-z0-9]{3})\b/i))) {
      const fixed = m[1].replace(/[Ss]/g, '5').replace(/[Oo]/g, '0');
      const ws = wordsForStr(l, m[1]);
      addField(F, pre + '_ion', { label: '기준 이온', type: 'float', roi: 'ramp', text: fixed, num: pFloat(fixed), conf: ws.length ? meanConf(ws) : l.conf, bbox: ws.length ? unionBox(ws) : l.bbox });
    }
    if (isFocus && (m = l.text.match(/Gain\s*([\d.]+)/i))) fieldFromMatch(F, 'rc.em_gain', 'EM Gain', 'float', 'ramp', l, m[1]);
    if (!isFocus && (m = l.text.match(/Factor\s*([\d.]+)/i))) fieldFromMatch(F, 'rc.gain_factor', 'Gain Factor', 'float', 'ramp', l, m[1]);
  }
}

function parseAll(ocr) {
  const F = {};
  parseHeader(F, ocr.header);
  parseParam(F, ocr.param);
  if (ocr.param2) {                       // 보조(격자선 제거본) 결과로 빈 칸 채우기
    const F2 = {}; parseParam(F2, ocr.param2);
    Object.keys(F2).forEach((k) => { if (!F[k]) F[k] = F2[k]; });
  }
  parseActual(F, ocr.actual);
  parseTemp(F, ocr.temp);
  parseTarget(F, ocr.target);
  parseRamp(F, ocr.ramp);
  // 타깃 m/z 열은 항상 공칭값(69/219/502)이므로 인식이 어긋나면 공칭값으로 보정
  NOMINAL.forEach((n, i) => {
    const f = F[`tt.r${i}.target`];
    if (f && (f.num == null || Math.abs(f.num - n) > 0.01)) { f.text = n.toFixed(2); f.num = n; f.refined = true; }
  });
  return F;
}

/* ------------------------------------------------ 타당성 검사·재인식 */
function validField(f) {
  if (f.num == null || !isFinite(f.num)) return false;
  let m;
  if ((m = f.id.match(/^(tt|am)\.r(\d)\.(actual|mz)$/))) return Math.abs(f.num - NOMINAL[+m[2]]) < 0.5;
  if (/\.rel$/.test(f.id)) return f.num >= 0 && f.num <= 100.5;
  if (/isoratio$/.test(f.id)) return f.num >= 0 && f.num <= 30;
  if (/isomz$/.test(f.id)) { m = f.id.match(/r(\d)/); return Math.abs(f.num - ISO_MZ[+m[1]]) < 1; }
  if (/pw50$/.test(f.id)) return f.num >= 0.3 && f.num <= 1.2;
  if (/abund$|isoabund$/.test(f.id)) return f.num > 0;
  switch (f.id) {
    case 'p.repeller': return f.num >= 0 && f.num <= 60;
    case 'p.ion_focus': return f.num >= 0 && f.num <= 150;
    case 'p.em_volts': return f.num >= 300 && f.num <= 3500;
    case 'tp.hivac': return f.num >= 1e-9 && f.num <= 1e-2;
    case 'tp.turbo': return f.num >= 0 && f.num <= 120;
    case 'rc.gain_factor': return f.num > 0 && f.num <= 1;
    case 'rc.ionfocus_max': case 'rc.repeller_max': return f.num >= 1 && f.num <= 200;
    default: return true;
  }
}
const REFINE_RE = /^(tt|am)\.r\d\.(actual|mz|abund|rel|pw50|isoabund|isoratio)$|^p\.(repeller|ion_focus|em_volts)$|^tp\.(hivac|turbo)$|^rc\.(ionfocus|repeller)_max$|^rc\.(em_gain|gain_factor)$|^aw\.(h2o|n2|o2)$/;
const WL = { mz: '0123456789.,', int: '0123456789,.', pct: '0123456789.%', float: '0123456789.-', sci: '0123456789.e+-' };

/* 확대·재인식 + 다중 판독 투표: 같은 칸을 배율/모드를 바꿔 여러 번 읽고 다수결로 정한다.
 * 판독끼리 의견이 갈리면(예: 9와 5) 값은 유지하되 "읽기 불일치"로 표시해 사람 확인을 요청한다. */
function cleanRead(raw, type) {
  let t = String(raw || '').replace(/[|\[\]{}()'"`“”‘’]/g, '').replace(/\s+/g, '');
  if (type !== 'sci') t = t.replace(/[GOoDQC¢]/g, '0').replace(/[Il]/g, '1').replace(/S/g, '5').replace(/B/g, '8').replace(/Z/g, '2');
  return t;
}
const VOTE_READS = [[1, 7], [3, 7], [4, 7], [3, 8], [4, 8]];   // [배율, psm]

async function refineFields(worker, rec, page) {
  const F = rec.report;
  for (const f of Object.values(F)) {
    if (!REFINE_RE.test(f.id) || !f.bbox) continue;
    const initValid = validField(f);
    if (initValid && f.conf != null && f.conf >= 96) continue;
    const pad = 10;
    const bx = { x: Math.max(0, Math.floor(f.bbox.x0 - pad)), y: Math.max(0, Math.floor(f.bbox.y0 - pad)) };
    bx.w = Math.min(page.width - bx.x, Math.ceil(f.bbox.x1 - f.bbox.x0 + pad * 2));
    bx.h = Math.min(page.height - bx.y, Math.ceil(f.bbox.y1 - f.bbox.y0 + pad * 2));
    if (bx.w < 6 || bx.h < 6) continue;
    const votes = [];                                   // {num, conf}
    if (f.num != null) votes.push({ num: f.num, conf: f.conf || 50, init: true });
    for (const [scale, psm] of VOTE_READS) {
      const c = document.createElement('canvas'); const b = 24;
      c.width = bx.w * scale + b * 2; c.height = bx.h * scale + b * 2;
      const cx = c.getContext('2d'); cx.fillStyle = '#fff'; cx.fillRect(0, 0, c.width, c.height);
      cx.imageSmoothingQuality = 'high';
      cx.drawImage(page, bx.x, bx.y, bx.w, bx.h, b, b, bx.w * scale, bx.h * scale);
      let data;
      try { data = await ocrCanvas(worker, c, { psm, whitelist: '' }); } catch (e) { continue; }   // 화이트리스트 없이 읽고 G→0 등은 사후 보정
      const text = (data.text || '').trim(); if (!text) continue;
      const cl = cleanRead(text, f.type);
      let num = PARSERS[f.type](cl);
      const okv = (n) => n != null && validField(Object.assign({}, f, { num: n }));
      if (!okv(num)) {                                   // 가장자리 잡음(|, 1 등) 제거 후 재시도
        const alt = [cl.slice(1), cl.slice(0, -1)].map((x) => PARSERS[f.type](x)).find(okv);
        num = alt != null ? alt : null;
      }
      if (num == null) continue;
      votes.push({ num, conf: data.confidence || 0 });
    }
    if (!votes.length) continue;
    // 같은 숫자열의 앞/뒤가 잘린 판독("8800" ← "18800", "2" ← "0.2")은 더 긴 쪽의 표로 합산
    const dig = (n) => String(n).replace(/[^0-9]/g, '');
    const keys = Array.from(new Set(votes.map((v) => String(v.num))));
    const target = (k) => {
      const d = dig(k); let best = k;
      keys.forEach((o) => {
        const od = dig(o);
        if (od.length <= dig(best).length || od.length <= d.length || !od.endsWith(d)) return;   // 앞자리가 잘린 경우만
        if (o === String(f.num) || /^0*$/.test(od.slice(0, od.length - d.length))) best = o;      // 긴 쪽이 최초 판독이거나 앞이 0뿐일 때만
      });
      return best;
    };
    const groups = new Map();
    votes.forEach((v) => {
      const k = target(String(v.num)); const g = groups.get(k) || { num: parseFloat(k), n: 0, w: 0, c: 0 };
      g.n++; g.w += 20 + v.conf; g.c += v.conf; groups.set(k, g);
    });
    f.votes = votes.map((v) => v.num + '@' + Math.round(v.conf));
    const ranked = Array.from(groups.values()).sort((a, b) => b.w - a.w);
    const initG = ranked.findIndex((g) => g.num === f.num);
    if (initG > 0 && ranked[initG].w >= 0.9 * ranked[0].w) ranked.unshift(ranked.splice(initG, 1)[0]);   // 근소한 차이면 최초 판독 유지
    const top = ranked[0];
    const agree = top.n / votes.length;
    if (top.num !== f.num && (!initValid || agree >= 0.5)) {
      f.prevText = f.prevText || f.text;
      f.num = top.num; f.refined = true;
      if (FORMATTERS[f.type]) f.text = FORMATTERS[f.type](top.num);
      else if (f.type === 'sci') f.text = fmtSci(top.num);
      else {                                         // 원본 표기의 소수 자릿수 유지 (예: 100.0, 0.2980)
        const dec = Math.max(((f.prevText || '').split('.')[1] || '').replace(/\D/g, '').length, (String(top.num).split('.')[1] || '').length);
        f.text = top.num.toFixed(dec);
      }
    }
    const avg = top.c / top.n;
    const second = ranked[1];
    const split = agree < 0.6 || (second && second.n >= 2 && second.c >= 0.4 * top.c);
    if (split && votes.length >= 4) {
      f.disputed = true; f.alts = ranked.slice(1, 3).map((g) => (FORMATTERS[f.type] ? FORMATTERS[f.type](g.num) : String(g.num)));
      f.conf = Math.min(f.conf || 100, 55);
    } else if (agree >= 0.8 && votes.length >= 4) f.conf = Math.max(f.conf || 0, 92);
    else if (agree >= 0.6 && top.n >= 3) f.conf = Math.max(f.conf || 0, 82);
    else if (top.num !== f.num) f.conf = Math.min(f.conf || 100, avg);
  }
}

/* ------------------------------------------------------------ 판정 */
const EXPLAIN = {
  mass: ['튠 기준 이온(69·219·502)이 정해진 질량 위치에 정확히 찍혔는지 보는 가장 기본 항목입니다. 질량 눈금(m/z 축)이 맞는지 알려줍니다.',
    'Autotune을 다시 실행해 보세요. 반복해서 벗어나면 엔지니어 점검이 필요합니다. "확인필요"는 원본의 숫자를 직접 확인해 값을 고쳐 주세요.'],
  pw50: ['피크의 반치폭(분해능)입니다. 0.60 근처여야 이웃한 질량(예: 69와 70)이 서로 섞이지 않고 구분됩니다.',
    'Autotune을 다시 실행하고, 반복되면 이온원 오염과 진공 상태를 점검하세요.'],
  rel219: ['69 신호 대비 219 신호의 비율입니다. 높은 질량 쪽 감도의 균형(스펙트럼 기울기)을 보여줍니다.',
    '소스 오염이나 누설이 있으면 낮아집니다. 누설 점검과 소스 청소 후 다시 튠하세요.'],
  rel502: ['502는 오염의 "조기 경보" 이온입니다. 소스가 더러워지면 다른 이온보다 먼저 줄어듭니다.',
    '값이 계속 내려가면 소스 청소 일정을 잡으세요. 이력 탭에서 추세를 함께 확인하세요.'],
  iso: ['PFTBA의 탄소 동위원소 비율(이론값 1.08 / 4.32 / 10.09%)과 비교합니다. 이론값에서 크게 벗어나면 검출기나 튠 파라미터 이상을 의심합니다.',
    'Autotune을 다시 실행하세요. 계속 벗어나면 EM 상태와 튠 파일을 점검합니다.'],
  abund69: ['기준 이온 69의 절대 신호 크기입니다. 감도의 척도이며, 장기간 서서히 낮아지면 필라멘트 노화나 소스 오염 신호입니다.',
    '낮으면 소스 청소·필라멘트 점검, 높으면 튠 타깃 설정이 다른지 확인하세요.'],
  em: ['전자증배관(EM, 검출기)의 증폭 전압입니다. 소스가 오염되거나 EM이 노화될수록 같은 신호를 얻기 위해 전압이 올라갑니다. 한계는 3,000V입니다.',
    '아직 쓸 수 있어도 상승 추세인지 이력으로 확인하세요. 소스 청소 후에도 높으면 EM(Horn) 교체를 검토합니다.'],
  repeller: ['이온을 소스 밖으로 밀어내는 전극 전압입니다. 소스가 더러워지면 튠이 이 값을 올려 보상하며, 상한(Ramp Criteria)에 붙으면 더 보상할 여지가 없다는 뜻입니다.',
    '지금 당장 문제는 아니어도 소스 청소 시점을 계획하세요. 다음 튠에서 더 올랐는지 이력으로 확인합니다.'],
  ionfocus: ['이온을 모아 분석부로 보내는 렌즈 전압입니다. Repeller와 마찬가지로 소스 오염을 보상하느라 올라가며, 상한에 가까울수록 소스 상태가 나쁘다는 신호입니다.',
    '소스 청소 시점을 계획하고, 이력에서 상승 추세인지 확인하세요.'],
  air: ['진공 속의 공기(N₂·O₂)와 수분(H₂O)을 m/z 69 대비 %로 봅니다. 높으면 누설 또는 수분 오염이며, N₂:O₂가 약 4:1이면 실제 공기 유입입니다.',
    '셉텀·페룰·컬럼 연결부·벤트 밸브를 점검하고, 가열 후 2시간 이상 안정화한 뒤 다시 측정하세요.'],
  hivac: ['분석기(진공 챔버) 압력입니다. 같은 컬럼 유량에서 점점 올라가면 누설이나 터보펌프 성능 저하를 의심합니다. 0에 가깝게 비정상적으로 낮으면 진공 게이지 꺼짐/고장일 수 있습니다.',
    '누설 점검 후에도 높으면 터보·전치 펌프 점검을 요청하세요.'],
  turbo: ['터보분자펌프 회전 속도입니다. 100%가 정상이며 낮으면 진공이 충분히 만들어지지 않습니다.',
    '펌프 상태와 전원/냉각을 확인하고, 반복되면 서비스 요청을 하세요.'],
};

function evaluate(F) {
  const C = crit;
  const num = (id) => (F[id] && F[id].num != null && isFinite(F[id].num) ? F[id].num : null);
  const txt = (id, d = '?') => (F[id] ? F[id].text : d);
  const rows = [];
  const lbl = (id) => (F[id] ? `${F[id].label}(${F[id].text})` : id);
  const guard = (v, refs) => {
    if (v === V.UNK) return { v, note: '' };
    const low = refs.filter((id) => { const f = F[id]; return f && !f.edited && f.conf != null && f.conf < opts.lowConf; });
    if (low.length) return { v: V.UNK, note: `OCR 신뢰도가 낮은 값(${low.map(lbl).join(', ')})이 포함되어 원본 대조가 필요합니다.` };
    return { v, note: '' };
  };
  const push = (id, name, value, criterion, v, refs, note = '') => {
    const g = guard(v, refs);
    rows.push({ id, name, value, criterion, verdict: g.v, refs, note: [note, g.note].filter(Boolean).join(' '), explain: EXPLAIN[id] });
  };

  // 1) Mass 배정
  {
    const dev = [], unc = [], refs = [];
    for (let i = 0; i < 3; i++) {
      for (const fid of [`tt.r${i}.actual`, `am.r${i}.mz`]) {
        const f = F[fid]; if (!f) continue; refs.push(fid);
        if (f.num == null) { unc.push(fid); continue; }
        const d = Math.abs(f.num - NOMINAL[i]);
        if (d > C.massImplausible) unc.push(fid); else dev.push(d);
      }
    }
    const shown = [0, 1, 2].map((i) => (F[`tt.r${i}.actual`] || F[`am.r${i}.mz`] || {}).text || '?').join(' · ');
    let v, note = '';
    if (!refs.length) v = V.UNK;
    else if (unc.length) { v = V.UNK; note = `판독이 의심스러운 값: ${unc.map(lbl).join(', ')} (기준 이온과 2 이상 차이 → OCR 오독 가능성)`; }
    else { const mx = Math.max(...dev); v = mx <= C.massTol + 1e-9 ? V.OK : mx <= C.massTol * 2 ? V.WARN : V.FAIL; }
    push('mass', 'Mass 배정 정확도', refs.length ? `${shown} (최대편차 ${dev.length ? fmtNum(Math.max(...dev)) : '-'})` : '판독불가',
      `Actual m/z가 69 / 219 / 502 대비 ±${C.massTol} 이내`, v, refs, note);
  }
  // 2) PW50
  {
    const refs = [0, 1, 2].map((i) => `am.r${i}.pw50`).filter((id) => F[id]);
    const vals = refs.map(num).filter((x) => x != null);
    let v = V.UNK;
    if (vals.length) {
      const dmax = Math.max(...vals.map((x) => Math.abs(x - C.pwTarget)));
      v = dmax <= C.pwTol + 1e-9 ? V.OK : dmax <= C.pwTol * 2 ? V.WARN : V.FAIL;
    }
    push('pw50', 'Peak Width (PW50)', vals.length ? vals.map((x) => x.toFixed(2)).join(' · ') : '판독불가',
      `${C.pwTarget.toFixed(2)} ± ${C.pwTol}`, v, refs);
  }
  // 3,4) Rel Abund
  for (const [id, i, nm, min] of [['rel219', 1, 'Rel Abund (m/z 219)', C.rel219Min], ['rel502', 2, 'Rel Abund (m/z 502)', C.rel502Min]]) {
    const fid = F[`tt.r${i}.rel`] ? `tt.r${i}.rel` : `am.r${i}.rel`;
    const val = num(fid);
    push(id, nm, val == null ? '판독불가' : `${val.toFixed(1)}%`, `${min}% 이상`, val == null ? V.UNK : (val >= min ? V.OK : V.FAIL), F[fid] ? [fid] : []);
  }
  // 5) Isotope
  {
    const refs = [], devs = []; let abundLow = false;
    for (let i = 0; i < 3; i++) {
      const r = `tt.r${i}.isoratio`, a = `tt.r${i}.isoabund`;
      if (F[r]) refs.push(r);
      if (F[a]) refs.push(a);
      const v = num(r); if (v != null) devs.push(Math.abs(v - ISO_THEORY[i]) / ISO_THEORY[i] * 100);
      const ab = num(a); if (ab != null && ab < C.isoAbundMin) abundLow = true;
    }
    const shown = [0, 1, 2].map((i) => txt(`tt.r${i}.isoratio`)).join(' · ');
    let v = V.UNK;
    if (devs.length) v = (Math.max(...devs) <= C.isoTolPct && !abundLow) ? V.OK : V.WARN;
    push('iso', 'Isotope Ratio (70/220/503)', devs.length ? shown : '판독불가',
      `이론값(${ISO_THEORY.join(' / ')}%) 대비 ±${C.isoTolPct}% 이내, Iso Abund ${fmtInt(C.isoAbundMin)} 이상`, v, refs,
      abundLow ? 'Iso Abund가 기준보다 작은 항목이 있습니다.' : '');
  }
  // 6) m/z 69 Abund
  {
    const fid = F['tt.r0.abund'] ? 'tt.r0.abund' : 'am.r0.abund'; const val = num(fid);
    let v = V.UNK;
    if (val != null) v = (val >= C.abund69Min && val <= C.abund69Max) ? V.OK : (val < C.abund69Min ? (val >= C.abund69Min * 0.5 ? V.WARN : V.FAIL) : V.WARN);
    push('abund69', 'm/z 69 절대 Abundance', val == null ? '판독불가' : `${fmtInt(val)} counts`,
      `${fmtInt(C.abund69Min)} ~ ${fmtInt(C.abund69Max)} counts`, v, F[fid] ? [fid] : []);
  }
  // 7) EM
  {
    const val = num('p.em_volts'); let v = V.UNK;
    if (val != null) v = val <= C.emNormalMax ? V.OK : val <= C.emWarnMax ? V.WARN : V.FAIL;
    push('em', 'EM Volts', val == null ? '판독불가' : `${fmtNum(val, 1)} V`,
      `${fmtInt(C.emNormalMax)}V 이하 정상 · ${fmtInt(C.emNormalMax)}~${fmtInt(C.emWarnMax)}V 주의 · 초과 경고 (한계 ${fmtInt(C.emLimit)}V)`, v, F['p.em_volts'] ? ['p.em_volts'] : []);
  }
  // 8,9) Repeller / Ion Focus
  for (const [id, key, mk, nm, def, warn] of [['repeller', 'p.repeller', 'rc.repeller_max', 'Repeller', C.repellerMaxDefault, C.repellerWarnPct], ['ionfocus', 'p.ion_focus', 'rc.ionfocus_max', 'Ion Focus', C.ionFocusMaxDefault, C.ionFocusWarnPct]]) {
    const val = num(key); let mx = num(mk); let note = '';
    if (mx == null || !validField(F[mk])) { mx = def; note = `Ramp Criteria 상한을 읽지 못해 기본값 ${def}V를 사용했습니다.`; }
    let v = V.UNK, pct = null;
    if (val != null) { pct = val / mx * 100; v = pct < warn ? V.OK : V.WARN; }
    push(id, nm, val == null ? '판독불가' : `${val}V (상한 ${mx}V 대비 ${pct.toFixed(0)}%)`,
      `Ramp Criteria 상한 대비 ${warn}% 미만`, v, [key, ...(F[mk] ? [mk] : [])], note);
  }
  // 10) Air/Water
  {
    const refs = ['aw.h2o', 'aw.n2', 'aw.o2'].filter((id) => F[id]);
    const [h, n, o] = ['aw.h2o', 'aw.n2', 'aw.o2'].map(num);
    let v = V.UNK;
    if (h != null && n != null && o != null) v = Math.max(h, n, o) < C.airWaterMax ? V.OK : V.WARN;
    push('air', 'Air/Water Check', (h != null && n != null && o != null) ? `H₂O ${h}% · N₂ ${n}% · O₂ ${o}%` : '판독불가',
      `H₂O·N₂·O₂ 모두 m/z 69 대비 ${C.airWaterMax}% 미만`, v, refs);
  }
  // 11) Hi Vac
  {
    const val = num('tp.hivac'); let v = V.UNK;
    if (val != null) v = (val >= C.hiVacMin && val <= C.hiVacMax) ? V.OK : (val < C.hiVacMin ? V.WARN : V.FAIL);
    push('hivac', 'Hi Vac (분석기 압력)', val == null ? '판독불가' : `${fmtSci(val)} Torr`,
      `${fmtSci(C.hiVacMin)} ~ ${fmtSci(C.hiVacMax)} Torr`, v, F['tp.hivac'] ? ['tp.hivac'] : []);
  }
  // 12) Turbo
  {
    const val = num('tp.turbo'); let v = V.UNK;
    if (val != null) v = val >= C.turboMin ? V.OK : V.FAIL;
    push('turbo', 'Turbo Speed', val == null ? '판독불가' : `${val}%`, `${C.turboMin}% 이상 (정상 100%)`, v, F['tp.turbo'] ? ['tp.turbo'] : []);
  }

  const counts = { ok: 0, warn: 0, fail: 0, unk: 0 };
  const fv = {};
  rows.forEach((r) => {
    counts[VCLS[r.verdict]]++;
    r.refs.forEach((id) => { fv[id] = fv[id] ? worst(fv[id], r.verdict) : r.verdict; });
  });
  const overall = counts.fail ? V.FAIL : counts.unk >= 6 ? V.UNK : (counts.warn || counts.unk) ? V.WARN : V.OK;
  return { rows, counts, overall, fv, summary: composeSummary(rows, F) };
}

function composeSummary(rows, F) {
  const R = Object.fromEntries(rows.map((r) => [r.id, r]));
  const c = { ok: 0, warn: 0, fail: 0, unk: 0 }; rows.forEach((r) => c[VCLS[r.verdict]]++);
  const L = [];
  const overall = c.fail ? '경고' : c.unk >= 6 ? '확인필요' : (c.warn || c.unk) ? '주의' : '정상';
  L.push(`종합 판정은 「${overall}」입니다. (정상 ${c.ok} · 주의 ${c.warn} · 경고 ${c.fail} · 확인필요 ${c.unk} / 총 ${rows.length}항목)`);
  L.push(`검출기·감도: EM Volts ${R.em.value} → ${R.em.verdict}, m/z 69 신호 ${R.abund69.value} → ${R.abund69.verdict}.`);
  L.push(`이온원 상태: Repeller ${R.repeller.value.split(' (')[0]} / Ion Focus ${R.ionfocus.value.split(' (')[0]} → ${worst(R.repeller.verdict, R.ionfocus.verdict)}, m/z 502 Rel Abund ${R.rel502.value} → ${R.rel502.verdict}.`);
  L.push(`진공·누설: Air/Water ${R.air.verdict}, Hi Vac ${R.hivac.value} → ${R.hivac.verdict}, Turbo ${R.turbo.value} → ${R.turbo.verdict}.`);
  const unk = rows.filter((r) => r.verdict === V.UNK).map((r) => r.name);
  const warn = rows.filter((r) => r.verdict === V.WARN || r.verdict === V.FAIL).map((r) => r.name);
  if (unk.length) L.push(`원본 확인 필요: ${unk.join(', ')} — 인식 화면에서 값을 눌러 원본과 대조하고 필요하면 직접 고치세요.`);
  else if (warn.length) L.push(`주의 항목(${warn.join(', ')})은 이력 탭에서 상승/하락 추세를 확인하고 소스 청소 시점을 계획하세요.`);
  else L.push('모든 항목이 기준 이내입니다. 이력에 저장해 다음 튠과의 변화를 비교하세요.');
  return L;
}

/* ------------------------------------------------------ 상태 / 큐 처리 */
const sources = new Map();
const recs = [];
let active = null;
let seq = 0, busy = false;
const ui = { tab: 'replica', zoom: 1, ov: 'none', split: false, sel: null, roi: false, openRows: new Set() };

function newRec(src, pageNo) {
  return { id: 'r' + (++seq), src, pageNo, name: src.file.name, status: 'queued', progress: 0, msg: '대기 중', imgUrl: null, imgW: 0, imgH: 0, ocr: null, proc: null, report: null, eval: null, savedKey: null, error: null };
}
const recLabel = (r) => `${r.name}${r.src.numPages > 1 ? ` (p.${r.pageNo})` : ''}`;

async function addFiles(fileList) {
  const files = Array.from(fileList || []).filter((f) => /\.pdf$/i.test(f.name) || f.type === 'application/pdf' || /^image\//.test(f.type));
  if (!files.length) { toast('PDF 또는 이미지 파일만 열 수 있습니다.'); return; }
  showWorkspace();
  const fresh = [];
  for (const file of files) {
    const isPdf = /\.pdf$/i.test(file.name) || file.type === 'application/pdf';
    const src = { id: 's' + (++seq), file, kind: isPdf ? 'pdf' : 'img', blobUrl: URL.createObjectURL(file), numPages: 1 };
    try {
      if (isPdf) {
        ensurePdfJs();
        const buf = new Uint8Array(await file.arrayBuffer());
        src.pdfDoc = await window.pdfjsLib.getDocument({ data: buf }).promise;
        src.numPages = Math.min(src.pdfDoc.numPages, 40);
        if (src.pdfDoc.numPages > 40) toast(`${file.name}: 처음 40쪽만 처리합니다.`);
      }
    } catch (e) { toast(`${file.name}: 파일을 열 수 없습니다 (${e.message || e})`); continue; }
    sources.set(src.id, src);
    for (let p = 1; p <= src.numPages; p++) { const r = newRec(src, p); recs.push(r); fresh.push(r); }
  }
  if (!fresh.length) return;
  renderQueue();
  if (!active || active.status === 'error') setActive(fresh[0]);
  pump();
}

async function pump() {
  if (busy) return;
  busy = true;
  try {
    for (;;) {
      const r = recs.find((x) => x.status === 'queued');
      if (!r) break;
      try { await processRec(r); } catch (e) {
        console.error(e);
        r.status = 'error'; r.error = String(e && e.message || e); r.msg = '오류: ' + r.error;
        refreshStatus(r);
      }
    }
  } finally { busy = false; }
}

function setProgress(r, p, msg) { r.progress = p; r.msg = msg; if (active === r) renderBanner(r); }
function refreshStatus(r) { renderQueue(); if (active === r) { renderBanner(r); renderAll(); } updateTopButtons(); }

async function processRec(rec) {
  rec.status = 'rendering'; rec.error = null; renderQueue();
  setProgress(rec, 0.02, '원본 페이지를 렌더링하는 중…');
  const canvas = await renderPage(rec.src, rec.pageNo);
  rec.imgW = canvas.width; rec.imgH = canvas.height;
  if (rec.imgUrl) URL.revokeObjectURL(rec.imgUrl);
  rec.imgUrl = URL.createObjectURL(await canvasToBlob(canvas, 'image/jpeg', 0.88));
  if (active === rec) renderOriginal();

  rec.status = 'ocr';
  setProgress(rec, 0.06, 'OCR 엔진을 준비하는 중… (처음 한 번만 몇 초 걸립니다)');
  ocrListener = (m) => {
    if (m && m.status === 'recognizing text' && rec.status === 'ocr' && rec._stepBase != null) {
      setProgress(rec, rec._stepBase + (m.progress || 0) * rec._stepSpan, rec.msg);
    }
  };
  const worker = await getOcr();

  const W = canvas.width, H = canvas.height;
  rec.ocr = {}; rec.proc = {};
  const steps = ROI_KEYS.length;
  for (let i = 0; i < steps; i++) {
    const key = ROI_KEYS[i];
    rec._stepBase = 0.12 + (i / steps) * 0.7; rec._stepSpan = 0.7 / steps;
    setProgress(rec, rec._stepBase, `OCR ${i + 1}/${steps}: ${ROI_LABEL[key]}`);
    const rect = roiRect(key, W, H, opts.roi);
    const crop = cropToCanvas(canvas, rect, 20);
    const proc = crop.canvas;                       // 파라미터 표는 격자선이 점선이라 원본 그대로 읽는 쪽이 더 정확함
    const data = await ocrCanvas(worker, proc, { psm: key === 'param' ? 4 : 6 });
    const lines = flatten(data, crop.ox, crop.oy);
    rec.proc[key] = { canvas: proc, ox: crop.ox, oy: crop.oy };
    rec.ocr[key] = { key, rect, lines, text: lines.map((l) => l.text).join('\n'), conf: data.confidence, cropUrl: URL.createObjectURL(await canvasToBlob(proc, 'image/png')) };
    if (key === 'param') {                          // 보조 판독: 격자선 제거 + psm 6
      const alt = removeGridlines(crop.canvas);
      const d2 = await ocrCanvas(worker, alt, { psm: 6 });
      rec.ocr.param2 = { key: 'param2', rect, lines: flatten(d2, crop.ox, crop.oy) };
    }
    await sleep(0);
  }
  rec._stepBase = null;
  setProgress(rec, 0.84, '값을 추출하는 중…');
  rec.report = parseAll(rec.ocr);
  if (opts.reocr) {
    setProgress(rec, 0.88, '신뢰도가 낮은 값을 확대해 다시 읽는 중…');
    await refineFields(worker, rec, canvas);
  }
  rec.proc = null; // 메모리 해제
  setProgress(rec, 0.97, '판정하는 중…');
  rec.eval = evaluate(rec.report);
  rec.status = 'done'; rec.progress = 1; rec.msg = '완료';
  const header = rec.report['h.title'];
  rec.notAutotune = !header || !/auto\s*tune\s*[-–—]/i.test(header.text) || rec.eval.counts.unk >= 8;
  if (opts.autoSave && !rec.notAutotune) saveHistory(rec, true);
  refreshStatus(rec);
}

/* ===================================================================== */
/*  UI                                                                    */
/* ===================================================================== */
function showWorkspace() {
  $('#emptyState').hidden = true; $('#workspace').hidden = false;
}

function updateTopButtons() {
  const ok = !!(active && active.status === 'done');
  $('#btnCsv').disabled = !ok; $('#btnPrint').disabled = !ok;
}

function renderQueue() {
  const q = $('#queue'); q.innerHTML = '';
  recs.forEach((r) => {
    const cls = r.status === 'done' ? VCLS[r.eval.overall] : (r.status === 'error' ? 'fail' : 'busy');
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'chip'; b.setAttribute('aria-current', r === active ? 'true' : 'false');
    b.innerHTML = `<i class="dot ${cls}"></i>${esc(recLabel(r))}${r.status === 'done' ? ` <small>${esc(r.eval.overall)}</small>` : ''}`;
    b.addEventListener('click', () => setActive(r));
    q.appendChild(b);
  });
}

function setActive(r) {
  active = r; ui.sel = null; ui.openRows = new Set();
  renderQueue(); renderOriginal(); renderBanner(r); renderAll(); updateTopButtons();
}

/* -------- 원본 */
function stageW() { return Math.max(240, ($('#origScroll').clientWidth - 22) * ui.zoom); }
function applyZoom() {
  const st = $('#origStage');
  if (!active || !active.imgW) return;
  const w = stageW();
  st.style.width = w + 'px'; st.style.setProperty('--s', (w / active.imgW).toFixed(5));
}
function renderOriginal() {
  const st = $('#origStage'), img = $('#origImg'), ov = $('#overlay');
  let hint = $('#origHint');
  if (!hint) { hint = document.createElement('div'); hint.id = 'origHint'; hint.style.cssText = 'color:#e5e9ef;text-align:center;padding:40px 10px'; $('#origScroll').appendChild(hint); }
  if (!active || !active.imgUrl) {
    st.hidden = true; hint.hidden = false; hint.textContent = active ? '원본을 렌더링하는 중…' : 'PDF나 이미지를 열면 원본이 여기에 표시됩니다.';
    return;
  }
  hint.hidden = true; st.hidden = false;
  if (img.getAttribute('src') !== active.imgUrl) img.src = active.imgUrl;
  applyZoom();
  ov.innerHTML = '';
  ov.classList.toggle('values', ui.ov === 'values');
  if (active.report && (ui.ov !== 'none')) {
    const frag = document.createDocumentFragment();
    Object.values(active.report).forEach((f) => {
      if (!f.bbox) return;
      const b = document.createElement('div');
      const cc = f.conf == null ? '' : f.conf < opts.lowConf ? 'low' : f.conf < 80 ? 'mid' : '';
      b.className = 'bx ' + cc + (f.edited ? ' edited' : ''); b.dataset.f = f.id;
      const pad = 3;
      b.style.left = ((f.bbox.x0 - pad) / active.imgW * 100) + '%'; b.style.top = ((f.bbox.y0 - pad) / active.imgH * 100) + '%';
      b.style.width = ((f.bbox.x1 - f.bbox.x0 + pad * 2) / active.imgW * 100) + '%'; b.style.height = ((f.bbox.y1 - f.bbox.y0 + pad * 2) / active.imgH * 100) + '%';
      b.style.setProperty('--h', String(f.bbox.y1 - f.bbox.y0 + pad * 2));
      b.title = `${f.label}: ${f.text}  (신뢰도 ${f.conf == null ? '-' : Math.round(f.conf)}%)`;
      const t = document.createElement('span'); t.className = 't'; t.textContent = f.text; b.appendChild(t);
      frag.appendChild(b);
    });
    ov.appendChild(frag);
  }
  if (ui.roi && active.ocr) {
    Object.values(active.ocr).filter((o) => o.key !== 'param2').forEach((o) => {
      const d = document.createElement('div'); d.className = 'roi';
      d.style.left = (o.rect.x / active.imgW * 100) + '%'; d.style.top = (o.rect.y / active.imgH * 100) + '%';
      d.style.width = (o.rect.w / active.imgW * 100) + '%'; d.style.height = (o.rect.h / active.imgH * 100) + '%';
      d.innerHTML = `<span>${esc(ROI_LABEL[o.key])}</span>`; ov.appendChild(d);
    });
  }
  highlight(ui.sel, true);
}

/* -------- 배너 */
function renderBanner(r) {
  const b = $('#banner');
  if (!r) { b.innerHTML = ''; return; }
  const F = r.report || {};
  const meta = [F['h.title'] && F['h.title'].text, F['h.time'] && ('튠 ' + F['h.time'].text), F['h.serial'] && ('S/N ' + F['h.serial'].text)].filter(Boolean).join('  |  ');
  if (r.status === 'done') {
    const ev = r.eval, c = ev.counts;
    const saved = r.savedKey && historyHas(r);
    b.innerHTML = `
      <div class="row1">
        <span class="verdict-pill v-${VCLS[ev.overall]}">종합 판정 · ${esc(ev.overall)}</span>
        <div class="counts"><span class="v-ok">정상 ${c.ok}</span><span class="v-warn">주의 ${c.warn}</span><span class="v-fail">경고 ${c.fail}</span><span class="v-unk">확인필요 ${c.unk}</span></div>
        <span style="flex:1"></span>
        <button class="btn sm" id="btnSaveHist" type="button">${saved ? '이력 갱신' : '이력에 저장'}</button>
      </div>
      <div class="meta">${esc(recLabel(r))}${meta ? '  ·  ' + esc(meta) : ''}</div>
      ${r.notAutotune ? '<div class="meta" style="color:var(--warn);font-weight:700">⚠ Autotune 리포트로 보기 어렵거나 영역 위치가 크게 어긋났습니다(인식된 값이 거의 없음). 표준 Autotune 인쇄 양식(A4 세로)인지 확인하고, 스캔 여백이 다르면 설정 → 영역 위치 보정을 사용하세요.</div>' : ''}
      <ol id="summary5">${ev.summary.map((s) => `<li>${esc(s)}</li>`).join('')}</ol>`;
    $('#btnSaveHist').addEventListener('click', () => { saveHistory(r, false); });
  } else if (r.status === 'error') {
    b.innerHTML = `<div class="row1"><span class="verdict-pill v-fail">처리 오류</span></div><div class="meta">${esc(r.error)}</div>`;
  } else {
    b.innerHTML = `<div class="row1"><span class="verdict-pill v-unk">${r.status === 'queued' ? '대기 중' : '인식 중'}</span><span>${esc(recLabel(r))}</span></div>
      <div class="progress"><div class="bar"><i style="width:${Math.round(r.progress * 100)}%"></i></div><div class="msg">${esc(r.msg)}</div></div>`;
  }
}

/* -------- 오른쪽 패널들 */
function renderAll() {
  renderReplica(); renderJudge(); renderOcrLog(); renderTrend();
  $$('.tab').forEach((t) => t.setAttribute('aria-selected', String(t.dataset.tab === ui.tab)));
  $$('.panel').forEach((p) => p.classList.toggle('on', p.id === 'panel' + ui.tab[0].toUpperCase() + ui.tab.slice(1)));
  $('#panels').classList.toggle('split', ui.split);
  $('#btnSplit').setAttribute('aria-pressed', String(ui.split));
  $('#btnReocr').disabled = !active || active.status === 'rendering' || active.status === 'ocr';
}

function pendingHtml(msg) { return `<p class="hint">${esc(msg)}</p>`; }

function fld(F, fv, id) {
  const f = F[id];
  if (!f) return `<span class="fld miss" title="인식되지 않음">—</span>`;
  const cc = f.conf == null ? '' : f.conf < opts.lowConf ? 'c-low' : f.conf < 80 ? 'c-mid' : '';
  const v = fv[id] ? 'fv-' + VCLS[fv[id]] : '';
  const tip = `${f.label} · 신뢰도 ${f.conf == null ? '-' : Math.round(f.conf)}%${f.refined ? ' · 확대 재인식 보정' : ''}${f.disputed ? ' · 읽기 불일치(다른 후보: ' + f.alts.join(', ') + ')' : ''}${f.edited ? ' · 직접 수정' : ''}${f.prevText ? ` (최초 인식: ${f.prevText})` : ''}`;
  return `<span class="fld ${cc} ${v} ${f.edited ? 'edited' : ''} ${f.refined && !f.edited ? 'refined' : ''}" data-f="${esc(id)}" tabindex="0" title="${esc(tip)}">${esc(f.text)}</span>`;
}

function renderReplica() {
  const p = $('#panelReplica');
  if (!active) { p.innerHTML = pendingHtml('파일을 열면 OCR로 인식한 내용을 원본과 같은 구성으로 다시 정리해서 보여줍니다.'); return; }
  if (!active.report) { p.innerHTML = pendingHtml(active.status === 'error' ? '처리 중 오류가 발생했습니다.' : '인식이 끝나면 이곳에 정제된 화면이 나타납니다.'); return; }
  const F = active.report, fv = active.eval ? active.eval.fv : {};
  const f = (id) => fld(F, fv, id);
  const prow = PARAM_ROWS.map((r) => `<tr><td class="lab">${esc(r[1])}</td><td class="val">${f('p.' + r[0])}</td><td class="lab">${esc(r[4])}</td><td class="val">${f('p.' + r[3])}</td></tr>`).join('');
  const arow = [0, 1, 2].map((i) => `<tr><td>${f(`am.r${i}.mz`)}</td><td>${f(`am.r${i}.abund`)}</td><td>${f(`am.r${i}.rel`)}</td><td>${f(`am.r${i}.pw50`)}</td></tr>`).join('');
  const trow = [0, 1, 2].map((i) => `<tr>${['target', 'actual', 'abund', 'rel', 'isomz', 'isoabund', 'isoratio'].map((k) => `<td>${f(`tt.r${i}.${k}`)}</td>`).join('')}</tr>`).join('');
  p.innerHTML = `
    <p class="hint">OCR이 읽은 값을 원본 리포트와 같은 구성으로 정리한 화면입니다. 값을 <b>클릭</b>하면 왼쪽 원본의 위치가 강조되고, <b>더블클릭</b>하면 값을 고칠 수 있습니다(고치면 즉시 다시 판정). 밑줄 색은 OCR 신뢰도, 배경색은 판정 결과입니다.</p>
    <div class="replica">
      <div class="rp-title">${f('h.title')}</div>
      <div class="rp-meta"><span>Tune timestamp: ${f('h.time')}</span><span>${f('h.inst')}</span></div>
      <div class="rp-meta"><span>${f('h.method')}</span><span>${f('h.serial')}</span></div>
      <table class="rp-grid"><tbody>${prow}</tbody></table>
      <div class="rp-two">
        <div><div class="rp-sec">Actual m/z</div><table class="rp-tbl"><thead><tr><th>Actual m/z</th><th>Abund</th><th>Rel Abund</th><th>PW50</th></tr></thead><tbody>${arow}</tbody></table></div>
        <div><div class="rp-sec">Temperatures and Pressures</div>
          <div class="rp-line"><span class="lbl">MS Source</span> ${f('tp.source')} <span class="lbl" style="margin-left:10px">Turbo Speed</span> ${f('tp.turbo')}</div>
          <div class="rp-line"><span class="lbl">MS Quad</span> ${f('tp.quad')} <span class="lbl" style="margin-left:10px">Hi Vac</span> ${f('tp.hivac')}</div></div>
      </div>
      <div class="rp-sec">Target m/z</div>
      <table class="rp-tbl"><thead><tr><th>Target m/z</th><th>Actual m/z</th><th>Abund</th><th>Rel Abund</th><th>Iso m/z</th><th>Iso Abund</th><th>Iso Ratio</th></tr></thead><tbody>${trow}</tbody></table>
      <div class="rp-line" style="margin-top:8px"><span class="lbl">Air/Water Check:</span> H₂O ${f('aw.h2o')} N₂ ${f('aw.n2')} O₂ ${f('aw.o2')} CO₂ ${f('aw.co2')} N₂/H₂O ${f('aw.n2h2o')}</div>
      <div class="rp-line"><span class="lbl">Ramp Criteria:</span></div>
      <div class="rp-line">Ion Focus maximum ${f('rc.ionfocus_max')} volts using ion ${f('rc.ionfocus_ion')}; Electron Multiplier Gain ${f('rc.em_gain')}</div>
      <div class="rp-line">Repeller maximum ${f('rc.repeller_max')} volts using ion ${f('rc.repeller_ion')}; Gain Factor ${f('rc.gain_factor')}</div>
      <div class="legend"><span>밑줄·신뢰도</span><span><i class="a"></i>높음</span><span><i class="b"></i>보통</span><span><i class="c"></i>낮음(확인 권장)</span><span>↻ 확대 재인식 보정</span><span>✎ 직접 수정</span></div>
      <p class="hint" style="margin-top:8px">※ 값을 고친 뒤 <b>Enter</b>를 누르면, 같은 값이어도 "사람이 확인함"으로 확정되어 판정의 확인필요가 해소됩니다. 차트(피크 형상, 스펙트럼)와 일부 보조 항목은 판정에 쓰이지 않아 생략했습니다. 원본은 왼쪽에서 확인하세요.</p>
    </div>`;
  highlight(ui.sel, false);
}

function renderJudge() {
  const p = $('#panelJudge');
  if (!active || !active.eval) { p.innerHTML = pendingHtml(active && active.status !== 'done' ? '인식이 끝나면 판정 결과가 표시됩니다.' : '파일을 열면 항목별 판정이 표시됩니다.'); return; }
  const rows = active.eval.rows;
  const trs = rows.map((r) => {
    const open = ui.openRows.has(r.id);
    const act = (r.verdict !== V.OK) ? `<p class="act">▶ 조치: ${esc(r.explain[1])}</p>` : '';
    const edited = r.refs.some((id) => active.report[id] && active.report[id].edited) ? '<span class="note-edit">✎ 수정값 반영</span>' : '';
    return `<tr class="item ${open ? 'open' : ''}" data-row="${r.id}" tabindex="0"><td class="name"><span class="caret">▸</span>${esc(r.name)}</td><td>${esc(r.value)}${edited}</td><td class="crit">${esc(r.criterion)}</td><td><span class="badge v-${VCLS[r.verdict]}">${esc(r.verdict)}</span></td></tr>
      <tr class="detail" data-detail="${r.id}" ${open ? '' : 'hidden'}><td colspan="4"><p>${esc(r.explain[0])}</p>${r.note ? `<p><b>참고:</b> ${esc(r.note)}</p>` : ''}${act}<p><button class="btn sm" type="button" data-goto="${r.id}">원본에서 위치 보기</button></p></td></tr>`;
  }).join('');
  p.innerHTML = `
    <div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;align-items:center">
      <p class="hint" style="margin:0;flex:1">항목을 누르면 쉬운 설명과 조치 방법이 펼쳐집니다. 판정 기준은 [설정]에서 바꿀 수 있습니다.</p>
      <button class="btn sm" type="button" id="btnOpenAll">모두 펼치기</button><button class="btn sm" type="button" id="btnCloseAll">모두 접기</button>
    </div>
    <table class="judge"><thead><tr><th>항목</th><th>측정값</th><th>판정 기준</th><th>판정</th></tr></thead><tbody>${trs}</tbody></table>
    <p class="small-note">※ "확인필요"는 OCR 신뢰도가 낮거나 물리적으로 불가능한 값이 검출되어 자동 판정을 보류한 항목입니다. 원본과 반드시 대조하세요. 판정 기준은 Agilent 5977 시리즈 권장값을 기본으로 하며 사내 기준으로 바꿀 수 있습니다.</p>`;
}

function renderOcrLog() {
  const p = $('#panelOcr');
  if (!active || !active.ocr) { p.innerHTML = pendingHtml('인식이 끝나면 영역별 OCR 입력 이미지와 원문이 표시됩니다.'); return; }
  p.innerHTML = `<p class="hint">영역별로 잘라 전처리한 이미지(파라미터 표는 격자선 제거본)와 Tesseract가 읽은 원문입니다. 인식이 이상할 때 어느 단계가 문제인지 확인하는 용도입니다.</p>` +
    ROI_KEYS.filter((k) => active.ocr[k]).map((k) => {
      const o = active.ocr[k];
      return `<div class="ocr-item"><header>${esc(ROI_LABEL[k])} <span>평균 신뢰도 ${o.conf == null ? '-' : Math.round(o.conf)}% · ${o.lines.length}줄</span></header><img src="${o.cropUrl}" alt="${esc(ROI_LABEL[k])} 입력 이미지"><pre>${esc(o.text)}</pre></div>`;
    }).join('');
}

/* -------- 선택 / 강조 / 편집 */
function highlight(id, scrollOrig) {
  $$('.fld.sel,.bx.sel').forEach((e) => e.classList.remove('sel'));
  if (!id) return;
  $$(`.fld[data-f="${CSS.escape(id)}"]`).forEach((e) => e.classList.add('sel'));
  const bx = $(`#overlay .bx[data-f="${CSS.escape(id)}"]`);
  if (bx) { bx.classList.add('sel'); if (scrollOrig) bx.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' }); }
}
function selectField(id, scrollOrig = true) {
  ui.sel = id;
  if (scrollOrig && ui.ov === 'none') { setOverlay('boxes'); }
  highlight(id, scrollOrig);
}

function startEdit(id) {
  const f = active && active.report && active.report[id]; if (!f) return;
  const span = $(`#panelReplica .fld[data-f="${CSS.escape(id)}"]`); if (!span) return;
  const input = document.createElement('input');
  input.className = 'fld-input'; input.value = f.text; input.setAttribute('aria-label', f.label + ' 값 수정');
  span.replaceWith(input); input.focus(); input.select();
  let done = false;
  const finish = (commit, confirm) => {
    if (done) return; done = true;
    if (commit && (confirm || input.value.trim() !== f.text)) setFieldValue(id, input.value.trim());
    else renderReplica();
  };
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') finish(true, true); else if (e.key === 'Escape') finish(false); });   // Enter = 값 확인(같은 값이어도 확정)
  input.addEventListener('blur', () => finish(true, false));
}

function setFieldValue(id, val) {
  const f = active.report[id]; if (!f) return;
  const num = PARSERS[f.type](val);
  f.prevText = f.prevText || f.text;
  f.text = (FORMATTERS[f.type] && num != null) ? FORMATTERS[f.type](num) : (f.type === 'text' ? val : sanitizeNum(val) || val);
  f.num = num; f.edited = true; f.refined = false; f.disputed = false;
  if (f.type === 'float' || f.type === 'sci') f.text = val.replace(/\s+/g, '');
  if (num == null && f.type !== 'text') toast('숫자로 읽을 수 없는 값입니다. 다시 확인하세요.');
  active.eval = evaluate(active.report);
  renderQueue(); renderBanner(active); renderAll(); renderOriginal();
  if (active.savedKey && historyHas(active)) toast('이력에 저장된 항목입니다. 배너의 [이력 갱신]을 누르면 수정값이 반영됩니다.');
}

/* ===================================================================== */
/*  이력 · 트렌드                                                         */
/* ===================================================================== */
const HKEY = 'gcmsAT.history';
const getHist = () => store.get(HKEY, []);
function parseTs(text) {
  const m = String(text || '').match(/(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})\s*([AaPp])[Mm]/);
  if (!m) return null;
  let h = +m[4] % 12; if (/p/i.test(m[6])) h += 12;
  return Date.UTC(+m[3], +m[1] - 1, +m[2], h, +m[5]);
}
function recordKey(r) {
  const F = r.report;
  return `${F['h.serial'] ? F['h.serial'].text : ''}|${F['h.time'] ? F['h.time'].text : r.name}`;
}
function historyHas(r) { return getHist().some((h) => h.key === r.savedKey); }
function makeRecord(r) {
  const F = r.report, n = (id) => (F[id] && F[id].num != null ? F[id].num : null);
  const c = r.eval.counts;
  return {
    key: recordKey(r), ts: parseTs(F['h.time'] && F['h.time'].text), label: F['h.time'] ? F['h.time'].text : '',
    file: recLabel(r), serial: F['h.serial'] ? F['h.serial'].text : '',
    em: n('p.em_volts'), repeller: n('p.repeller'), repellerMax: n('rc.repeller_max') || crit.repellerMaxDefault,
    ionFocus: n('p.ion_focus'), ionFocusMax: n('rc.ionfocus_max') || crit.ionFocusMaxDefault,
    rel219: n('tt.r1.rel'), rel502: n('tt.r2.rel'), abund69: n('tt.r0.abund'), hivac: n('tp.hivac'),
    h2o: n('aw.h2o'), n2: n('aw.n2'), o2: n('aw.o2'), turbo: n('tp.turbo'),
    overall: r.eval.overall, nWarn: c.warn, nFail: c.fail, nUnk: c.unk, saved: Date.now(),
  };
}
function saveHistory(r, silent) {
  if (!r.report || !r.eval) return;
  const rec = makeRecord(r); const h = getHist();
  const i = h.findIndex((x) => x.key === rec.key);
  if (i >= 0) h[i] = rec; else h.push(rec);
  store.set(HKEY, h);
  r.savedKey = rec.key;
  if (!silent) toast(i >= 0 ? '이력을 갱신했습니다.' : '이력에 저장했습니다.');
  if (active === r) renderBanner(r);
  renderTrend();
}

const METRICS = [
  { id: 'em', title: 'EM Volts (V)', get: (r) => r.em, fmt: (v) => v.toFixed(0), refs: () => [crit.emNormalMax, crit.emWarnMax], bad: (l, p) => l - p >= 50 },
  { id: 'rep', title: 'Repeller (상한 대비 %)', get: (r) => (r.repeller != null ? r.repeller / r.repellerMax * 100 : null), fmt: (v) => v.toFixed(1), refs: () => [crit.repellerWarnPct, 100], bad: (l, p) => l - p >= 3 },
  { id: 'ion', title: 'Ion Focus (상한 대비 %)', get: (r) => (r.ionFocus != null ? r.ionFocus / r.ionFocusMax * 100 : null), fmt: (v) => v.toFixed(1), refs: () => [crit.ionFocusWarnPct, 100], bad: (l, p) => l - p >= 3 },
  { id: 'rel502', title: 'm/z 502 Rel Abund (%)', get: (r) => r.rel502, fmt: (v) => v.toFixed(1), refs: () => [crit.rel502Min], bad: (l, p) => p > 0 && (p - l) / p >= 0.10 },
  { id: 'abund69', title: 'm/z 69 Abundance', get: (r) => r.abund69, fmt: (v) => fmtInt(v), refs: () => [crit.abund69Min, crit.abund69Max], bad: (l, p) => p > 0 && (p - l) / p >= 0.20 },
  { id: 'hivac', title: 'Hi Vac (Torr, 로그 눈금)', get: (r) => r.hivac, fmt: (v) => fmtSci(v), refs: () => [crit.hiVacMin, crit.hiVacMax], log: true, bad: (l, p) => p > 0 && l / p >= 2 },
  { id: 'air', title: 'Air/Water (%)', multi: [['H₂O', (r) => r.h2o], ['N₂', (r) => r.n2], ['O₂', (r) => r.o2]], refs: () => [crit.airWaterMax], fmt: (v) => v.toFixed(1) },
];

function dateLabel(r) {
  if (r.ts == null) return '?';
  const d = new Date(r.ts); return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
}
function chartSvg(m, hist) {
  const W = 340, H = 168, ml = 46, mr = 10, mt = 10, mb = 24;
  const series = m.multi ? m.multi.map(([name, g]) => ({ name, vals: hist.map(g) })) : [{ name: m.title, vals: hist.map(m.get) }];
  const tf = (v) => (m.log ? Math.log10(Math.max(v, 1e-12)) : v);
  const all = series.flatMap((s) => s.vals).filter((v) => v != null && isFinite(v)).map(tf);
  if (!all.length) return '<p class="hint">데이터 없음</p>';
  let lo = Math.min(...all), hi = Math.max(...all);
  if (hi - lo < Math.max(Math.abs(hi) * 0.02, m.log ? 0.3 : 1e-9)) { const c = (hi + lo) / 2, h = Math.max(Math.abs(c) * 0.02, m.log ? 0.3 : 0.5); lo = c - h; hi = c + h; }   // 점이 하나뿐일 때 축 확장
  const R0 = hi - lo || Math.abs(hi) * 0.04 || 1;
  const refs = (m.refs ? m.refs() : []).map(tf).filter((v) => v >= lo - 1.2 * R0 && v <= hi + 1.2 * R0);
  const lo2 = Math.min(lo, ...refs), hi2 = Math.max(hi, ...refs);
  const pad = (hi2 - lo2 || 1) * 0.14; lo = lo2 - pad; hi = hi2 + pad;
  const pw = W - ml - mr, ph = H - mt - mb;
  const X = (i) => ml + (hist.length === 1 ? pw / 2 : (i * pw) / (hist.length - 1));
  const Y = (v) => mt + ph - ((tf(v) - lo) / (hi - lo)) * ph;
  let g = '';
  for (let t = 0; t <= 3; t++) {
    const val = lo + ((hi - lo) * t) / 3; const y = mt + ph - (ph * t) / 3;
    const raw = m.log ? Math.pow(10, val) : val;
    g += `<line class="grid" x1="${ml}" x2="${W - mr}" y1="${y}" y2="${y}"/><text class="ax" x="${ml - 4}" y="${y + 3}" text-anchor="end">${m.fmt ? m.fmt(raw) : raw.toFixed(1)}</text>`;
  }
  (m.refs ? m.refs() : []).forEach((rv) => {
    const t = tf(rv); if (t < lo || t > hi) return;
    const y = mt + ph - ((t - lo) / (hi - lo)) * ph;
    g += `<line class="ref" x1="${ml}" x2="${W - mr}" y1="${y}" y2="${y}"/>`;
  });
  const cls = ['ln', 'ln2', 'ln3'];
  series.forEach((s, si) => {
    const pts = s.vals.map((v, i) => (v == null || !isFinite(v) ? null : [X(i), Y(v), v, i])).filter(Boolean);
    if (pts.length > 1) g += `<polyline class="${cls[si]}" points="${pts.map((p) => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ')}"/>`;
    pts.forEach((p, k) => {
      const last = k === pts.length - 1;
      g += `<circle class="pt${last ? ' last' : ''}" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3" ${si ? `style="fill:${si === 1 ? '#c2410c' : '#0f766e'}"` : ''}><title>${esc(hist[p[3]].label || '')} · ${esc(s.name)} ${m.fmt ? m.fmt(p[2]) : p[2]}</title></circle>`;
    });
  });
  g += `<text class="ax" x="${ml}" y="${H - 6}">${esc(dateLabel(hist[0]))}</text>`;
  if (hist.length > 1) g += `<text class="ax" x="${W - mr}" y="${H - 6}" text-anchor="end">${esc(dateLabel(hist[hist.length - 1]))}</text>`;
  if (m.multi) g += `<text class="ax" x="${W - mr}" y="${mt + 8}" text-anchor="end">${series.map((s, i) => `${s.name}`).join(' / ')}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(m.title)} 추이">${g}</svg>`;
}

function renderTrend() {
  const p = $('#panelTrend');
  const hist = getHist().slice().sort((a, b) => (a.ts ?? a.saved) - (b.ts ?? b.saved));
  const tools = `<div class="hist-tools">
    <button class="btn sm" type="button" id="btnHistCsv" ${hist.length ? '' : 'disabled'}>이력 CSV</button>
    <button class="btn sm" type="button" id="btnHistExport" ${hist.length ? '' : 'disabled'}>이력 백업(JSON)</button>
    <button class="btn sm" type="button" id="btnHistImport">백업 불러오기</button>
    <button class="btn sm" type="button" id="btnHistClear" ${hist.length ? '' : 'disabled'}>이력 모두 삭제</button>
    <span class="hint" style="margin:0">이력은 이 브라우저에만 저장됩니다. 브라우저 데이터를 지우면 사라지니 가끔 백업하세요.</span></div>`;
  if (!hist.length) {
    p.innerHTML = tools + `<p class="hint">저장된 이력이 없습니다. 판독 결과 상단의 [이력에 저장]을 누르면 튠 일시별로 쌓이고, 여기서 EM Volts·Repeller·Ion Focus 등의 변화를 한눈에 볼 수 있습니다. (설정에서 '인식 완료 시 자동 저장'도 켤 수 있습니다.)</p>`;
    bindHistTools(); return;
  }
  const cards = METRICS.map((m) => {
    const vals = m.multi ? null : hist.map(m.get);
    let sub = '';
    if (vals) {
      const nn = vals.map((v, i) => [v, i]).filter(([v]) => v != null && isFinite(v));
      if (nn.length) {
        const last = nn[nn.length - 1][0];
        sub = `최근 <b>${m.fmt(last)}</b>`;
        if (nn.length > 1) {
          const prevVals = nn.slice(Math.max(0, nn.length - 4), nn.length - 1).map(([v]) => v);
          const prev = prevVals.reduce((a, b) => a + b, 0) / prevVals.length;
          const d = last - nn[nn.length - 2][0];
          const bad = m.bad && m.bad(last, prev);
          const arrow = d > 0 ? '▲' : d < 0 ? '▼' : '■';
          sub += ` · 직전 대비 <span class="delta ${d > 0 ? 'up' : 'down'}">${arrow} ${m.log ? '×' + (nn[nn.length - 2][0] ? (last / nn[nn.length - 2][0]).toFixed(2) : '-') : (d > 0 ? '+' : '') + (Math.abs(d) < 10 ? d.toFixed(2) : d.toFixed(0))}</span>${bad ? ' · <b style="color:var(--warn)">추세 주의</b>' : ''}`;
        }
      }
    } else sub = '점선: 기준선';
    return `<div class="card"><h3>${esc(m.title)}</h3><div class="sub">${sub}</div>${chartSvg(m, hist)}</div>`;
  }).join('');
  const rowsH = hist.slice().reverse().map((h, i) => `<tr><td>${esc(h.label || '-')}</td><td>${h.em != null ? h.em.toFixed(1) : '-'}</td><td>${h.repeller != null ? h.repeller : '-'}</td><td>${h.ionFocus != null ? h.ionFocus : '-'}</td><td>${h.rel502 != null ? h.rel502.toFixed(1) : '-'}</td><td>${h.abund69 != null ? fmtInt(h.abund69) : '-'}</td><td>${h.hivac != null ? fmtSci(h.hivac) : '-'}</td><td><span class="badge v-${VCLS[h.overall] || 'unk'}">${esc(h.overall)}</span></td><td><button class="btn sm" type="button" data-hdel="${esc(h.key)}" aria-label="삭제">삭제</button></td></tr>`).join('');
  p.innerHTML = tools + `<div class="trend-grid">${cards}</div>
    <div class="hist-wrap"><table class="hist"><thead><tr><th>튠 일시</th><th>EM(V)</th><th>Repeller</th><th>Ion Focus</th><th>502 Rel(%)</th><th>69 Abund</th><th>Hi Vac</th><th>종합</th><th></th></tr></thead><tbody>${rowsH}</tbody></table></div>`;
  bindHistTools();
}

function download(name, blob) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}
const csvCell = (s) => { s = String(s == null ? '' : s); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };

function bindHistTools() {
  const on = (id, fn) => { const e = document.getElementById(id); if (e) e.addEventListener('click', fn); };
  on('btnHistCsv', () => {
    const h = getHist().slice().sort((a, b) => (a.ts ?? a.saved) - (b.ts ?? b.saved));
    const head = ['튠일시', '파일', 'S/N', 'EM Volts', 'Repeller', 'Repeller상한', 'Ion Focus', 'Ion Focus상한', '219 Rel', '502 Rel', '69 Abund', 'Hi Vac', 'H2O%', 'N2%', 'O2%', 'Turbo', '종합', '주의수', '경고수', '확인필요수'];
    const lines = [head.join(',')].concat(h.map((r) => [r.label, r.file, r.serial, r.em, r.repeller, r.repellerMax, r.ionFocus, r.ionFocusMax, r.rel219, r.rel502, r.abund69, r.hivac, r.h2o, r.n2, r.o2, r.turbo, r.overall, r.nWarn, r.nFail, r.nUnk].map(csvCell).join(',')));
    download('autotune_history.csv', new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' }));
  });
  on('btnHistExport', () => download('autotune_history_backup.json', new Blob([JSON.stringify(getHist(), null, 1)], { type: 'application/json' })));
  on('btnHistImport', () => {
    const i = document.createElement('input'); i.type = 'file'; i.accept = '.json,application/json';
    i.addEventListener('change', async () => {
      try {
        const arr = JSON.parse(await i.files[0].text()); if (!Array.isArray(arr)) throw new Error('형식 오류');
        const h = getHist(); arr.forEach((r) => { if (!r || !r.key) return; const k = h.findIndex((x) => x.key === r.key); if (k >= 0) h[k] = r; else h.push(r); });
        store.set(HKEY, h); renderTrend(); toast(`${arr.length}건을 불러왔습니다.`);
      } catch (e) { toast('백업 파일을 읽을 수 없습니다: ' + e.message); }
    });
    i.click();
  });
  on('btnHistClear', () => { if (confirm('저장된 이력을 모두 삭제할까요? 되돌릴 수 없습니다.')) { store.set(HKEY, []); renderTrend(); if (active) renderBanner(active); } });
  $$('[data-hdel]').forEach((b) => b.addEventListener('click', () => { store.set(HKEY, getHist().filter((x) => x.key !== b.dataset.hdel)); renderTrend(); if (active) renderBanner(active); }));
}

/* ===================================================================== */
/*  내보내기 · 인쇄                                                       */
/* ===================================================================== */
function exportCsv() {
  if (!active || !active.eval) return;
  const F = active.report;
  const lines = [['파일', recLabel(active)], ['튠 일시', F['h.time'] ? F['h.time'].text : ''], ['종합 판정', active.eval.overall], [], ['항목', '측정값', '판정 기준', '판정', '참고']]
    .map((r) => r.map(csvCell).join(','));
  active.eval.rows.forEach((r) => lines.push([r.name, r.value, r.criterion, r.verdict, r.note].map(csvCell).join(',')));
  lines.push('', ['필드ID', '라벨', '값', '신뢰도', '수정여부'].join(','));
  Object.values(F).forEach((f) => lines.push([f.id, f.label, f.text, f.conf == null ? '' : Math.round(f.conf), f.edited ? '수정' : ''].map(csvCell).join(',')));
  download(`autotune_${(active.name || 'report').replace(/\.[^.]+$/, '')}_평가.csv`, new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' }));
}

function printSheet() {
  if (!active || !active.eval) return;
  const F = active.report, ev = active.eval;
  const meta = [F['h.title'] && F['h.title'].text, F['h.time'] && ('튠 일시 ' + F['h.time'].text), F['h.serial'] && ('S/N ' + F['h.serial'].text), F['h.method'] && F['h.method'].text].filter(Boolean).join('  |  ');
  const now = new Date();
  const stamp = `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())} ${pad2(now.getHours())}:${pad2(now.getMinutes())}`;
  const c = ev.counts;
  $('#printSheet').innerHTML = `
    <h1>GC/MS Autotune 자동 판독 평가서</h1>
    <div class="pmeta">${esc(meta)}<br>원본 파일: ${esc(recLabel(active))}  |  평가 처리: ${esc(stamp)}</div>
    <div class="pbanner pv-${VCLS[ev.overall]}"><b>종합 판정: ${esc(ev.overall)}</b>  (정상 ${c.ok} · 주의 ${c.warn} · 경고 ${c.fail} · 확인필요 ${c.unk} / 총 ${ev.rows.length}항목)</div>
    <ol>${ev.summary.map((s) => `<li>${esc(s)}</li>`).join('')}</ol>
    <table><thead><tr><th style="width:24%">항목</th><th style="width:26%">측정값</th><th>판정 기준</th><th style="width:12%;text-align:center">판정</th></tr></thead><tbody>
    ${ev.rows.map((r) => `<tr><td>${esc(r.name)}</td><td>${esc(r.value)}</td><td>${esc(r.criterion)}</td><td class="vd pv-${VCLS[r.verdict]}">${esc(r.verdict)}</td></tr>`).join('')}
    </tbody></table>
    <div class="foot">※ OCR 자동 판독 결과이며, '확인필요' 항목과 수정값(✎)은 원본 리포트와 대조 확인이 필요합니다. 판정 기준은 Agilent 5977 시리즈 권장값을 기본으로 하며 사내 기준으로 변경할 수 있습니다.</div>`;
  const prevTitle = document.title;
  document.title = `Autotune_평가서_${(F['h.time'] ? F['h.time'].text.split(' ')[0].replace(/\//g, '-') : 'report')}`;
  window.print();
  setTimeout(() => { document.title = prevTitle; }, 800);
}

/* ===================================================================== */
/*  설정                                                                  */
/* ===================================================================== */
const CRIT_FIELDS = [
  ['질량·피크', [['massTol', 'Mass 배정 허용 편차(±)', '0.01'], ['pwTarget', 'PW50 목표값', '0.01'], ['pwTol', 'PW50 허용 편차(±)', '0.01']]],
  ['신호 균형', [['rel219Min', 'Rel Abund 219 최소(%)', '1'], ['rel502Min', 'Rel Abund 502 최소(%)', '0.1'], ['isoTolPct', '동위원소 비 허용 편차(%)', '1'], ['abund69Min', 'm/z 69 Abundance 최소', '1000'], ['abund69Max', 'm/z 69 Abundance 최대', '1000']]],
  ['검출기·이온원', [['emNormalMax', 'EM Volts 정상 상한(V)', '10'], ['emWarnMax', 'EM Volts 주의 상한(V)', '10'], ['repellerWarnPct', 'Repeller 주의 시작(상한 대비 %)', '1'], ['ionFocusWarnPct', 'Ion Focus 주의 시작(상한 대비 %)', '1']]],
  ['진공·누설', [['airWaterMax', 'Air/Water 허용 상한(%)', '1'], ['hiVacMin', 'Hi Vac 최소(Torr)', 'any'], ['hiVacMax', 'Hi Vac 최대(Torr)', 'any'], ['turboMin', 'Turbo Speed 최소(%)', '1']]],
];

function openSettings() {
  const body = $('#settingsBody');
  body.innerHTML = CRIT_FIELDS.map(([g, fs]) => `<fieldset><legend>판정 기준 · ${g}</legend><div class="form-grid">${fs.map(([k, l, st]) => `<label>${l}<input type="${st === 'any' ? 'text' : 'number'}" step="${st === 'any' ? '' : st}" data-crit="${k}" value="${crit[k]}"></label>`).join('')}</div></fieldset>`).join('') + `
    <fieldset><legend>인식 옵션</legend>
      <label class="chk"><input type="checkbox" id="optReocr" ${opts.reocr ? 'checked' : ''}><span>신뢰도가 낮거나 이상한 숫자는 확대해서 숫자 전용으로 다시 읽기 <small style="color:var(--muted)">(권장)</small></span></label>
      <div class="form-grid"><label>저신뢰 기준(%) — 이보다 낮으면 해당 판정을 "확인필요"로 보류<input type="number" id="optLow" min="0" max="100" value="${opts.lowConf}"></label></div>
      <label class="chk"><input type="checkbox" id="optAuto" ${opts.autoSave ? 'checked' : ''}><span>인식이 끝나면 이력에 자동 저장 <small style="color:var(--muted)">(잘못 읽힌 값이 섞일 수 있어 기본은 끔)</small></span></label>
    </fieldset>
    <fieldset><legend>영역 위치 보정 (스캔 여백이 다를 때)</legend>
      <p class="hint">표준 Autotune 인쇄 양식(A4)을 기준으로 영역을 잡습니다. 인식이 어긋나면 원본 위의 [영역 구획]을 켜서 위치를 보며 조정한 뒤 [저장하고 다시 판정] → [다시 인식]을 누르세요.</p>
      <div class="form-grid">
        <label>가로 이동(%)<input type="number" step="0.2" id="roiDx" value="${(opts.roi.dx * 100).toFixed(1)}"></label>
        <label>세로 이동(%)<input type="number" step="0.2" id="roiDy" value="${(opts.roi.dy * 100).toFixed(1)}"></label>
        <label>크기 배율(%)<input type="number" step="0.5" id="roiSc" value="${(opts.roi.scale * 100).toFixed(1)}"></label>
      </div>
    </fieldset>`;
  $('#dlgSettings').showModal();
}

function saveSettings() {
  const next = Object.assign({}, crit);
  let bad = null;
  $$('[data-crit]').forEach((i) => { const v = parseFloat(i.value); if (!isFinite(v)) bad = i.dataset.crit; else next[i.dataset.crit] = v; });
  if (bad) { toast('숫자가 아닌 값이 있습니다: ' + bad); return; }
  crit = next; store.set('gcmsAT.crit', crit);
  const old = JSON.stringify(opts.roi);
  opts.reocr = $('#optReocr').checked; opts.autoSave = $('#optAuto').checked;
  opts.lowConf = Math.min(100, Math.max(0, parseFloat($('#optLow').value) || 60));
  opts.roi = { dx: (parseFloat($('#roiDx').value) || 0) / 100, dy: (parseFloat($('#roiDy').value) || 0) / 100, scale: Math.max(0.8, Math.min(1.2, (parseFloat($('#roiSc').value) || 100) / 100)) };
  store.set('gcmsAT.opts', opts);
  $('#dlgSettings').close();
  recs.forEach((r) => { if (r.status === 'done') r.eval = evaluate(r.report); });
  renderQueue(); if (active) { renderBanner(active); renderAll(); renderOriginal(); }
  if (JSON.stringify(opts.roi) !== old && active && active.status === 'done') toast('영역 위치가 바뀌었습니다. [다시 인식]을 눌러 적용하세요.', 4500);
  else toast('설정을 저장하고 다시 판정했습니다.');
}

/* ===================================================================== */
/*  이벤트 연결                                                           */
/* ===================================================================== */
function setOverlay(mode) {
  ui.ov = mode;
  $$('[data-ov]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.ov === mode)));
  renderOriginal();
}

function init() {
  const fi = $('#fileInput');
  $('#btnOpen').addEventListener('click', () => fi.click());
  fi.addEventListener('change', () => { addFiles(fi.files); fi.value = ''; });
  const dc = $('#dropcard');
  dc.addEventListener('click', () => fi.click());
  dc.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fi.click(); } });

  let depth = 0; const ovl = $('#dropOverlay');
  window.addEventListener('dragenter', (e) => { if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files')) { depth++; ovl.classList.add('on'); dc.classList.add('over'); } });
  window.addEventListener('dragleave', () => { depth = Math.max(0, depth - 1); if (!depth) { ovl.classList.remove('on'); dc.classList.remove('over'); } });
  window.addEventListener('dragover', (e) => { e.preventDefault(); });
  window.addEventListener('drop', (e) => { e.preventDefault(); depth = 0; ovl.classList.remove('on'); dc.classList.remove('over'); if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files); });

  $$('[data-zoom]').forEach((b) => b.addEventListener('click', () => {
    ui.zoom = parseFloat(b.dataset.zoom);
    $$('[data-zoom]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    applyZoom();
  }));
  $$('[data-ov]').forEach((b) => b.addEventListener('click', () => setOverlay(b.dataset.ov)));
  $('#chkRoi').addEventListener('change', (e) => { ui.roi = e.target.checked; renderOriginal(); });
  new ResizeObserver(() => applyZoom()).observe($('#origScroll'));
  $('#btnOpenPdf').addEventListener('click', () => { if (active) window.open(active.src.blobUrl, '_blank'); });

  $$('.tab').forEach((t) => t.addEventListener('click', () => { ui.tab = t.dataset.tab; renderAll(); }));
  $('#btnTrend').addEventListener('click', () => { showWorkspace(); ui.tab = 'trend'; renderAll(); renderOriginal(); });
  $('#btnSplit').addEventListener('click', () => { ui.split = !ui.split; if (ui.split && (ui.tab === 'trend' || ui.tab === 'ocr')) ui.tab = 'replica'; renderAll(); });
  $('#btnReocr').addEventListener('click', () => {
    if (!active) return;
    active.status = 'queued'; active.report = null; active.eval = null; active.ocr = null; active.error = null; active.msg = '대기 중';
    renderQueue(); renderBanner(active); renderAll(); updateTopButtons(); pump();
  });
  $('#btnCsv').addEventListener('click', exportCsv);
  $('#btnPrint').addEventListener('click', printSheet);
  $('#btnSettings').addEventListener('click', openSettings);
  $('#btnSaveSettings').addEventListener('click', saveSettings);
  $('#btnResetCrit').addEventListener('click', () => { crit = Object.assign({}, DEFAULT_CRIT); store.set('gcmsAT.crit', crit); openSettings(); toast('판정 기준을 기본값으로 되돌렸습니다. [저장하고 다시 판정]을 누르면 반영됩니다.'); });
  $$('[data-close]').forEach((b) => b.addEventListener('click', () => b.closest('dialog').close()));

  // 위임 이벤트: 재구성 화면 / 판정표 / 원본 오버레이
  document.addEventListener('click', (e) => {
    const fe = e.target.closest('.fld[data-f]');
    if (fe) { selectField(fe.dataset.f, true); return; }
    const bx = e.target.closest('#overlay .bx');
    if (bx) { selectField(bx.dataset.f, false); const t = $(`#panelReplica .fld[data-f="${CSS.escape(bx.dataset.f)}"]`); if (t) { if (!$('#panelReplica').classList.contains('on') && !ui.split) { ui.tab = 'replica'; renderAll(); highlight(bx.dataset.f, false); } const tt = $(`#panelReplica .fld[data-f="${CSS.escape(bx.dataset.f)}"]`); if (tt) tt.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } return; }
    const gt = e.target.closest('[data-goto]');
    if (gt) { const r = active.eval.rows.find((x) => x.id === gt.dataset.goto); if (r && r.refs[0]) { ui.sel = r.refs[0]; setOverlay('boxes'); highlight(r.refs[0], true); } return; }
    const it = e.target.closest('tr.item');
    if (it) { const id = it.dataset.row; if (ui.openRows.has(id)) ui.openRows.delete(id); else ui.openRows.add(id); it.classList.toggle('open'); const d = $(`tr[data-detail="${id}"]`); if (d) d.hidden = !ui.openRows.has(id); return; }
    if (e.target.id === 'btnOpenAll') { active.eval.rows.forEach((r) => ui.openRows.add(r.id)); renderJudge(); }
    if (e.target.id === 'btnCloseAll') { ui.openRows.clear(); renderJudge(); }
  });
  document.addEventListener('dblclick', (e) => { const fe = e.target.closest('#panelReplica .fld[data-f]'); if (fe) startEdit(fe.dataset.f); });
  document.addEventListener('keydown', (e) => {
    const fe = e.target.closest && e.target.closest('.fld[data-f]');
    if (fe && e.key === 'Enter') { e.preventDefault(); startEdit(fe.dataset.f); }
    const it = e.target.closest && e.target.closest('tr.item');
    if (it && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); it.click(); }
  });
  document.addEventListener('mouseover', (e) => {
    const t = e.target.closest('.fld[data-f],#overlay .bx'); if (!t) return;
    const id = t.dataset.f; $$(`[data-f="${CSS.escape(id)}"]`).forEach((x) => { if (x.classList.contains('fld') || x.classList.contains('bx')) x.classList.add('hl'); });
  });
  document.addEventListener('mouseout', (e) => {
    const t = e.target.closest('.fld[data-f],#overlay .bx'); if (!t) return;
    $$('.hl').forEach((x) => x.classList.remove('hl'));
  });

  window.addEventListener('error', (e) => toast('오류: ' + (e.message || e)));
  window.addEventListener('unhandledrejection', (e) => toast('오류: ' + ((e.reason && e.reason.message) || e.reason)));

  renderAll();
}

window.__app = { getOcr, ocrCanvas, removeGridlines, cropToCanvas, renderPage, roiRect, flatten, get recs() { return recs; }, get active() { return active; }, crit: () => crit, opts: () => opts, evaluate, parseAll, addFiles };
init();
})();
