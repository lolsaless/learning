/* 검사의뢰 공문 추출기 v2.0 — 이력 문서(Word·PDF) 생성 · 문서 → 그림 변환 (브라우저 전용, 외부 라이브러리 없음)
   - HTML(원본 공문 미리보기) → SVG foreignObject → canvas
   - PDF 쪽 → pdf.js → canvas
   - 그림 파일 → canvas
   - Word(.docx): 직접 작성한 OOXML + 저장(Store) ZIP
   - PDF: A4 쪽을 canvas로 그려 JPEG(DCTDecode)로 묶음 */
(function (global) {
'use strict';
const X = global.MiniXlsx;
const enc = new TextEncoder();

/* ───────── 1. 그림 만들기 ───────── */
// HTML 조각 → canvas (widthPx: CSS 픽셀 폭, scale: 해상도 배율)
async function htmlToCanvas(html, css, widthPx, scale) {
  scale = scale || 2;
  const holder = document.createElement('div');
  holder.style.cssText = `position:fixed;left:-20000px;top:0;width:${widthPx}px;background:#fff`;
  holder.innerHTML = `<style>${css || ''}</style><div class="dg-root" style="width:${widthPx}px;background:#fff">${html}</div>`;
  document.body.appendChild(holder);
  try {
    await new Promise(r => requestAnimationFrame(() => r()));
    const root = holder.querySelector('.dg-root');
    const H = Math.ceil(root.scrollHeight) + 2;
    const ser = new XMLSerializer();
    const body = ser.serializeToString(holder.querySelector('style')) + ser.serializeToString(root);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${widthPx}" height="${H}"><foreignObject x="0" y="0" width="${widthPx}" height="${H}"><div xmlns="http://www.w3.org/1999/xhtml" style="width:${widthPx}px">${body}</div></foreignObject></svg>`;
    const img = new Image();
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    await img.decode();
    const c = document.createElement('canvas');
    c.width = Math.round(widthPx * scale); c.height = Math.round(H * scale);
    const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.scale(scale, scale); g.drawImage(img, 0, 0);
    return c;
  } finally { holder.remove(); }
}
// PDF → 쪽별 canvas (pages: 1부터 시작하는 쪽 번호 배열, 비우면 전체)
async function pdfToCanvases(bytes, pages, scale) {
  const lib = global.pdfjsLib; if (!lib) throw new Error('PDF 읽기 기능(pdf.js)이 없습니다.');
  const doc = await lib.getDocument({ data: bytes.slice ? bytes.slice(0) : bytes, isEvalSupported: false }).promise;
  const list = pages && pages.length ? pages : Array.from({ length: doc.numPages }, (_, i) => i + 1);
  const out = [];
  for (const n of list) {
    if (n < 1 || n > doc.numPages) continue;
    const p = await doc.getPage(n), vp = p.getViewport({ scale: scale || 2 });
    const c = document.createElement('canvas'); c.width = Math.ceil(vp.width); c.height = Math.ceil(vp.height);
    const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    await p.render({ canvasContext: g, viewport: vp }).promise;
    out.push(c);
  }
  doc.destroy && doc.destroy();
  return out;
}
const IMG_MIME = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif', bmp: 'image/bmp', webp: 'image/webp', tif: 'image/tiff', tiff: 'image/tiff' };
async function imageToCanvas(bytes, name) {
  const ext = String(name || '').split('.').pop().toLowerCase();
  const blob = new Blob([bytes], { type: IMG_MIME[ext] || 'application/octet-stream' });
  const bmp = await createImageBitmap(blob);
  const max = 2400, k = Math.min(1, max / Math.max(bmp.width, bmp.height));
  const c = document.createElement('canvas'); c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
  const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(bmp, 0, 0, c.width, c.height);
  return c;
}
async function canvasJpeg(c, q) {
  const blob = await new Promise(res => c.toBlob(res, 'image/jpeg', q || 0.86));
  return new Uint8Array(await blob.arrayBuffer());
}
// 세로로 긴 그림을 쪽 비율(ratio = 높이/폭)에 맞게 자름
function sliceCanvas(c, ratio) {
  const maxH = Math.round(c.width * ratio);
  if (c.height <= maxH * 1.04) return [c];
  const out = [];
  for (let y = 0; y < c.height; y += maxH) {
    const h = Math.min(maxH, c.height - y); if (h < 20) break;
    const s = document.createElement('canvas'); s.width = c.width; s.height = h;
    s.getContext('2d').drawImage(c, 0, y, c.width, h, 0, 0, c.width, h);
    out.push(s);
  }
  return out;
}

/* ───────── 2. 문서 구성 (공통 블록) ─────────
   blocks: [{t:'title', text}, {t:'h', text}, {t:'p', text, muted?}, {t:'kv', rows:[[k,v]]}, {t:'table', head:[], rows:[[]]},
            {t:'img', canvas, caption}, {t:'pagebreak'}] */

/* ───────── 3. Word (.docx) ───────── */
const xe = s => String(s == null ? '' : s).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const run = (text, o = {}) => {
  const pr = `<w:rPr><w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="맑은 고딕"/>${o.b ? '<w:b/>' : ''}${o.color ? `<w:color w:val="${o.color}"/>` : ''}<w:sz w:val="${o.sz || 20}"/></w:rPr>`;
  return String(text).split('\n').map((ln, i) => `${i ? '<w:r><w:br/></w:r>' : ''}<w:r>${pr}<w:t xml:space="preserve">${xe(ln)}</w:t></w:r>`).join('');
};
const para = (inner, o = {}) => `<w:p><w:pPr>${o.keep ? '<w:keepNext/>' : ''}<w:spacing w:before="${o.before || 0}" w:after="${o.after == null ? 80 : o.after}"/>${o.center ? '<w:jc w:val="center"/>' : ''}</w:pPr>${inner}</w:p>`;
const PAGE_W_TW = 11906, PAGE_H_TW = 16838, MARGIN_TW = 1134; // A4, 여백 2cm
const CONTENT_W_EMU = Math.round((PAGE_W_TW - 2 * MARGIN_TW) / 1440 * 914400);
const CONTENT_H_EMU = Math.round((PAGE_H_TW - 2 * MARGIN_TW - 900) / 1440 * 914400);
async function buildDocx(blocks, title) {
  const media = []; let body = '';
  const tbl = (head, rows, widths) => {
    const n = (head || rows[0] || []).length, total = PAGE_W_TW - 2 * MARGIN_TW, sum = widths ? widths.reduce((x, y) => x + y, 0) : 0;
    const w = widths ? widths.map(v => Math.floor(v / sum * total)) : Array(n).fill(Math.floor(total / n));
    const cell = (v, k, isHead) => `<w:tc><w:tcPr><w:tcW w:w="${w[k]}" w:type="dxa"/>${isHead ? '<w:shd w:val="clear" w:color="auto" w:fill="E8EDF4"/>' : ''}</w:tcPr>${para(run(v, { b: isHead, sz: 18 }), { after: 0 })}</w:tc>`;
    let x = `<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>${['top', 'left', 'bottom', 'right', 'insideH', 'insideV'].map(s => `<w:${s} w:val="single" w:sz="4" w:space="0" w:color="999999"/>`).join('')}</w:tblBorders><w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>${w.map(v => `<w:gridCol w:w="${v}"/>`).join('')}</w:tblGrid>`;
    if (head) x += '<w:tr>' + head.map((v, k) => cell(v, k, true)).join('') + '</w:tr>';
    for (const r of rows) x += '<w:tr>' + r.map((v, k) => cell(v, k, false)).join('') + '</w:tr>';
    return x + '</w:tbl>' + para('', { after: 60 });
  };
  for (const b of blocks) {
    if (b.t === 'title') body += para(run(b.text, { b: 1, sz: 32 }), { after: 120 });
    else if (b.t === 'h') body += para(run(b.text, { b: 1, sz: 24, color: '1F4E79' }), { before: 200, after: 80, keep: 1 });
    else if (b.t === 'p') body += para(run(b.text, { sz: 20, color: b.muted ? '666666' : null }));
    else if (b.t === 'kv') body += tbl(null, b.rows, [1, 4]);
    else if (b.t === 'table') body += tbl(b.head, b.rows, b.widths);
    else if (b.t === 'pagebreak') body += '<w:p><w:r><w:br w:type="page"/></w:r></w:p>';
    else if (b.t === 'img') {
      const parts = sliceCanvas(b.canvas, CONTENT_H_EMU / CONTENT_W_EMU);
      for (let i = 0; i < parts.length; i++) {
        const c = parts[i], id = media.length + 1;
        media.push({ name: `word/media/image${id}.jpeg`, data: await canvasJpeg(c) });
        const cx = CONTENT_W_EMU, cy = Math.round(CONTENT_W_EMU * c.height / c.width);
        body += `<w:p><w:pPr><w:spacing w:before="0" w:after="60"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="${cx}" cy="${cy}"/><wp:docPr id="${id}" name="그림 ${id}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="${id}" name="image${id}.jpeg"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rImg${id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:ln w="6350"><a:solidFill><a:srgbClr val="BFBFBF"/></a:solidFill></a:ln></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>`;
      }
      if (b.caption) body += para(run(b.caption, { sz: 16, color: '666666' }), { center: 1, after: 160 });
    }
  }
  const ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"';
  const doc = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${ns}><w:body>${body}<w:sectPr><w:pgSz w:w="${PAGE_W_TW}" w:h="${PAGE_H_TW}"/><w:pgMar w:top="${MARGIN_TW}" w:right="${MARGIN_TW}" w:bottom="${MARGIN_TW}" w:left="${MARGIN_TW}" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>`;
  const rels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>${media.map((m, i) => `<Relationship Id="rImg${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image${i + 1}.jpeg"/>`).join('')}</Relationships>`;
  const styles = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="맑은 고딕" w:cs="Malgun Gothic"/><w:sz w:val="20"/><w:lang w:val="en-US" w:eastAsia="ko-KR"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>`;
  const now = new Date().toISOString().replace(/\.\d+Z$/, 'Z');
  const core = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>${xe(title || '시료 처리 이력')}</dc:title><dc:creator>검사의뢰 공문 추출기</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">${now}</dcterms:created></cp:coreProperties>`;
  const files = [
    { name: '[Content_Types].xml', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="jpeg" ContentType="image/jpeg"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>' },
    { name: '_rels/.rels', data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>' },
    { name: 'docProps/core.xml', data: core },
    { name: 'word/document.xml', data: doc },
    { name: 'word/styles.xml', data: styles },
    { name: 'word/_rels/document.xml.rels', data: rels },
    ...media,
  ];
  return X.zipStore(files);
}

/* ───────── 4. PDF ───────── */
// 블록을 A4 canvas 쪽으로 배치 (150dpi: 1240 × 1754)
const PW = 1240, PH = 1754, PM = 94; // 여백 약 1.6cm
function layoutPages(blocks, footer) {
  const pages = []; let c, g, y;
  const FONT = '"Malgun Gothic","맑은 고딕","Apple SD Gothic Neo","Noto Sans KR",sans-serif';
  const newPage = () => { c = document.createElement('canvas'); c.width = PW; c.height = PH; g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, PW, PH); g.textBaseline = 'top'; y = PM; pages.push(c); };
  const W = PW - 2 * PM, bottom = PH - PM - 30;
  const wrap = (text, font, maxW) => {
    g.font = font; const out = [];
    for (const para of String(text).split('\n')) {
      let line = '';
      for (const ch of para) { if (g.measureText(line + ch).width > maxW && line) { out.push(line); line = ch; } else line += ch; }
      out.push(line);
    }
    return out;
  };
  const textBlock = (text, size, opt = {}) => {
    const font = `${opt.b ? 'bold ' : ''}${size}px ${FONT}`, lh = Math.round(size * 1.5);
    for (const ln of wrap(text, font, W - (opt.indent || 0))) {
      if (y + lh > bottom) newPage();
      g.font = font; g.fillStyle = opt.color || '#111'; g.fillText(ln, PM + (opt.indent || 0), y); y += lh;
    }
    y += opt.after == null ? 6 : opt.after;
  };
  const table = (head, rows, widths) => {
    const n = (head || rows[0] || []).length, ws = widths ? widths.map(v => v / widths.reduce((a, b) => a + b, 0) * W) : Array(n).fill(W / n);
    const size = 19, font = `${size}px ${FONT}`, bfont = `bold ${size}px ${FONT}`, lh = Math.round(size * 1.45), pad = 8;
    const drawRow = (r, isHead) => {
      const cells = r.map((v, k) => wrap(v == null ? '' : v, isHead ? bfont : font, ws[k] - 2 * pad));
      const h = Math.max(...cells.map(x => x.length)) * lh + 2 * pad;
      if (y + h > bottom) { newPage(); if (head && !isHead) drawRow(head, true); }
      let x = PM;
      cells.forEach((lines, k) => {
        if (isHead) { g.fillStyle = '#e8edf4'; g.fillRect(x, y, ws[k], h); }
        g.strokeStyle = '#999'; g.lineWidth = 1; g.strokeRect(x + 0.5, y + 0.5, ws[k], h);
        g.font = isHead ? bfont : font; g.fillStyle = '#111';
        lines.forEach((ln, i) => g.fillText(ln, x + pad, y + pad + i * lh));
        x += ws[k];
      });
      y += h;
    };
    if (head) drawRow(head, true);
    rows.forEach(r => drawRow(r, false));
    y += 14;
  };
  newPage();
  // 제목 다음 그림의 첫 조각 높이 (제목만 쪽 끝에 남지 않게)
  const firstImgH = b => { if (!b || b.t !== 'img') return 0; const fullH = bottom - PM - (b.caption ? 36 : 0); const part = sliceCanvas(b.canvas, fullH / W)[0]; return Math.min(fullH, Math.round(W * part.height / part.width)); };
  blocks.forEach((b, i) => { b._next = blocks[i + 1]; });
  for (const b of blocks) {
    if (b.t === 'h' && b._next && b._next.t === 'img' && y > PM + 10 && y + 60 + Math.min(firstImgH(b._next), bottom - PM - 260) > bottom) newPage();
    if (b.t === 'title') textBlock(b.text, 34, { b: 1, after: 14 });
    else if (b.t === 'h') { if (y > PM + 10) y += 14; if (y + 160 > bottom) newPage(); textBlock(b.text, 25, { b: 1, color: '#1f4e79', after: 8 }); }
    else if (b.t === 'p') textBlock(b.text, 20, { color: b.muted ? '#666' : '#111' });
    else if (b.t === 'kv') table(null, b.rows, [1, 4]);
    else if (b.t === 'table') table(b.head, b.rows, b.widths);
    else if (b.t === 'pagebreak') { if (y > PM) newPage(); }
    else if (b.t === 'img') {
      const capH = b.caption ? 36 : 0;
      const fullH = bottom - PM - capH;
      for (const part of sliceCanvas(b.canvas, fullH / W)) {
        let w = W, h = Math.round(W * part.height / part.width);
        if (h > fullH) { h = fullH; w = Math.round(fullH * part.width / part.height); }
        const avail = bottom - y - capH;
        if (h > avail && y < PM + 200) { h = avail; w = Math.round(avail * part.width / part.height); } /* 쪽 맨 위 제목 바로 아래: 조금 줄여 같은 쪽에 */
        if (y + h + capH > bottom) newPage();
        const x = PM + (W - w) / 2;
        g.drawImage(part, x, y, w, h); g.strokeStyle = '#bbb'; g.strokeRect(x + 0.5, y + 0.5, w, h);
        y += h + 6;
      }
      if (b.caption) textBlock(b.caption, 17, { color: '#666', after: 16 });
    }
  }
  pages.forEach((p, i) => {
    const gg = p.getContext('2d'); gg.font = `16px ${FONT}`; gg.fillStyle = '#888'; gg.textBaseline = 'top';
    const t = `${footer ? footer + '  ·  ' : ''}${i + 1} / ${pages.length}`; gg.fillText(t, PW - PM - gg.measureText(t).width, PH - PM + 4);
  });
  return pages;
}
async function buildPdf(pages) {
  const objs = []; // [index] = Uint8Array 조각들
  const add = parts => { objs.push(parts); return objs.length; };
  const catalog = add(null), pagesObj = add(null);
  const kids = [];
  for (const c of pages) {
    const jpg = await canvasJpeg(c, 0.85);
    const img = add([enc.encode(`<< /Type /XObject /Subtype /Image /Width ${c.width} /Height ${c.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpg.length} >>\nstream\n`), jpg, enc.encode('\nendstream')]);
    const content = `q 595.28 0 0 841.89 0 0 cm /Im0 Do Q`;
    const cs = add([enc.encode(`<< /Length ${content.length} >>\nstream\n${content}\nendstream`)]);
    const pg = add(null);
    objs[pg - 1] = [enc.encode(`<< /Type /Page /Parent ${pagesObj} 0 R /MediaBox [0 0 595.28 841.89] /Resources << /XObject << /Im0 ${img} 0 R >> >> /Contents ${cs} 0 R >>`)];
    kids.push(pg);
  }
  objs[catalog - 1] = [enc.encode(`<< /Type /Catalog /Pages ${pagesObj} 0 R >>`)];
  objs[pagesObj - 1] = [enc.encode(`<< /Type /Pages /Kids [${kids.map(k => k + ' 0 R').join(' ')}] /Count ${kids.length} >>`)];
  const chunks = [enc.encode('%PDF-1.4\n%\xE2\xE3\xCF\xD3\n')]; let off = chunks[0].length; const xref = [];
  objs.forEach((parts, i) => {
    xref.push(off);
    const head = enc.encode(`${i + 1} 0 obj\n`), tail = enc.encode('\nendobj\n');
    chunks.push(head, ...parts, tail); off += head.length + parts.reduce((a, p) => a + p.length, 0) + tail.length;
  });
  let tr = `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n` + xref.map(o => String(o).padStart(10, '0') + ' 00000 n \n').join('');
  tr += `trailer\n<< /Size ${objs.length + 1} /Root ${catalog} 0 R >>\nstartxref\n${off}\n%%EOF\n`;
  chunks.push(enc.encode(tr));
  const out = new Uint8Array(chunks.reduce((a, b) => a + b.length, 0)); let p = 0; for (const ch of chunks) { out.set(ch, p); p += ch.length; }
  return out;
}

global.DocGen = { htmlToCanvas, pdfToCanvases, imageToCanvas, canvasJpeg, sliceCanvas, buildDocx, layoutPages, buildPdf, IMG_MIME };
})(typeof window !== 'undefined' ? window : globalThis);
