/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/61_원본보기_ODT.js] 원본 보기(ODT → HTML)
   하는 일 : ODT 서식(쪽 너비·표·글꼴·그림)을 HTML로 다시 그림
   주요 이름: renderOdtHtml, ODT_PREVIEW_CSS
   이럴 때 고침: 원본 보기 모양이 원본과 다를 때
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
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
