/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/02_압축_XML_글자.js] ZIP·XML·글자 읽기
   하는 일 : ODT·HWPX(ZIP) 풀기, XML 해석, 문단 글자 꺼내기
   주요 이름: unzipEntry, unzipBytes, unzipList, parseXML, walk, findAll, inlineText, blockLines, squash
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
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
