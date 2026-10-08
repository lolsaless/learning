'use strict';
const $ = id => document.getElementById(id);
const OUT_NAME = '사진변환파일';
const EXT = /\.(heic|heif|jpe?g|jfif|png|webp|bmp|dib|gif|tiff?|ico|avif)$/i;
const CAN_WRITE = typeof window.showDirectoryPicker === 'function';   // Chrome·Edge

let items = [];      // {file, path, root(폴더 핸들|null), status, msg}
let busy = false;
let dest = null;     // {handle, name, auto}  사진변환파일 폴더를 만들 위치

/* ======================= 옵션 화면 ======================= */
const mode = () => document.querySelector('input[name=mode]:checked').value;
function syncOptions() {
  const m = mode();
  $('boxWH').classList.toggle('hide', m !== 'fit' && m !== 'exact');
  $('boxPct').classList.toggle('hide', m !== 'percent');
  $('boxNone').classList.toggle('hide', m !== 'none');
  $('enlWrap').classList.toggle('hide', m !== 'fit');
  $('whHint').textContent = m === 'fit'
    ? '이 크기를 넘는 사진만 비율을 유지하며 줄입니다. 한쪽만 입력해도 됩니다.'
    : '한쪽만 입력하면 비율 유지, 둘 다 입력하면 정확히 그 크기로 맞춥니다.';
}
document.querySelectorAll('input[name=mode]').forEach(r => r.onchange = syncOptions);
$('pct').oninput = () => $('pctV').textContent = $('pct').value;
$('quality').oninput = () => $('qV').textContent = $('quality').value;
syncOptions();

/* ======================= 저장 위치 ======================= */
function showDest() {
  if (!CAN_WRITE) {
    $('destLabel').textContent = '다운로드 폴더 › ' + OUT_NAME + '.zip';
    $('bDest').classList.add('hide');
    $('zipNote').classList.remove('hide');
    $('destHint').classList.add('hide');
    return;
  }
  $('destLabel').textContent = dest
    ? '📁 ' + dest.name + ' › ' + OUT_NAME
    : '변환 시작 시 선택';
  $('destLabel').title = $('destLabel').textContent;
}
$('bDest').onclick = async () => {
  try {
    const h = await window.showDirectoryPicker({id: 'photo-dest', mode: 'readwrite'});
    dest = {handle: h, name: h.name, auto: false};
    showDest();
  } catch (e) { /* 취소 */ }
};
showDest();

/* ======================= 파일 추가 ======================= */
function addFile(file, path, root) {
  if (!EXT.test(file.name)) return;
  if (items.some(i => i.path === path && i.file.size === file.size)) return;
  items.push({file, path, root: root || null, status: 'wait', msg: ''});
}
function useFolderAsDest(handle) {          // 처음 넣은 폴더 안에 사진변환파일 생성
  if (CAN_WRITE && handle && (!dest || dest.auto && !items.some(i => i.root === dest.handle)))
    dest = {handle, name: handle.name, auto: true};
}

// 폴더 핸들(Chrome·Edge) 순회
async function walkHandle(dir, prefix, root) {
  for await (const h of dir.values()) {
    if (h.kind === 'file') {
      if (EXT.test(h.name)) addFile(await h.getFile(), prefix + h.name, root);
    } else if (h.name !== OUT_NAME) {
      await walkHandle(h, prefix + h.name + '/', root);
    }
  }
}
// 구형 방식(Safari·Firefox) 폴더 순회
function readAll(reader) {
  return new Promise((resolve, reject) => {
    const all = [];
    const next = () => reader.readEntries(b => b.length ? (all.push(...b), next()) : resolve(all), reject);
    next();
  });
}
async function walkEntry(entry, prefix) {
  if (entry.isFile) {
    const f = await new Promise((res, rej) => entry.file(res, rej));
    addFile(f, prefix + f.name, null);
  } else if (entry.isDirectory && entry.name !== OUT_NAME) {
    for (const c of await readAll(entry.createReader())) await walkEntry(c, prefix + entry.name + '/');
  }
}

async function adding(fn) {
  const before = items.length;
  $('sum').textContent = '사진을 불러오는 중...';
  try { await fn(); } catch (e) { console.error(e); }
  const added = items.length - before;
  $('sum').textContent = added ? `${added}개를 추가했습니다.` : '추가된 사진이 없습니다. (지원하지 않는 형식이거나 이미 목록에 있음)';
  showDest(); render();
}

// 드래그 앤 드롭: 페이지 어디에 놓아도 받음
let depth = 0;
window.addEventListener('dragenter', e => { e.preventDefault(); depth++; $('drop').classList.add('over'); });
window.addEventListener('dragleave', () => { if (--depth <= 0) { depth = 0; $('drop').classList.remove('over'); } });
window.addEventListener('dragover', e => { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'; });
window.addEventListener('drop', e => {
  e.preventDefault(); depth = 0; $('drop').classList.remove('over');
  if (busy || !e.dataTransfer) return;
  // drop 이벤트가 끝나면 데이터가 사라지므로 여기서 동기적으로 모두 꺼낸다
  const dtItems = [...e.dataTransfer.items].filter(i => i.kind === 'file');
  const handleP = CAN_WRITE && dtItems.length && 'getAsFileSystemHandle' in DataTransferItem.prototype
    ? dtItems.map(i => i.getAsFileSystemHandle()) : null;
  const entries = dtItems.map(i => i.webkitGetAsEntry ? i.webkitGetAsEntry() : null);
  const files = [...e.dataTransfer.files];

  adding(async () => {
    const handles = handleP ? await Promise.all(handleP.map(p => p.catch(() => null))) : [];
    if (handles.length && handles.every(Boolean)) {
      for (const h of handles) {
        if (h.kind === 'directory') { await walkHandle(h, h.name + '/', h); useFolderAsDest(h); }
        else addFile(await h.getFile(), h.name, null);
      }
    } else if (entries.length && entries.every(Boolean)) {
      for (const en of entries) await walkEntry(en, '');
    } else {
      files.forEach(f => addFile(f, f.name, null));
    }
  });
});

$('bFiles').onclick = () => $('inFiles').click();
$('inFiles').onchange = e => {
  const fs = [...e.target.files]; e.target.value = '';
  adding(async () => fs.forEach(f => addFile(f, f.name, null)));
};
$('bDir').onclick = async () => {
  if (!CAN_WRITE) return $('inDir').click();
  let h;
  try { h = await window.showDirectoryPicker({id: 'photo-src', mode: 'readwrite'}); } catch (e) { return; }
  adding(async () => { await walkHandle(h, h.name + '/', h); useFolderAsDest(h); });
};
$('inDir').onchange = e => {
  const fs = [...e.target.files]; e.target.value = '';
  adding(async () => fs.forEach(f => {
    if (!f.webkitRelativePath.split('/').includes(OUT_NAME)) addFile(f, f.webkitRelativePath || f.name, null);
  }));
};

/* ======================= 목록 ======================= */
const fmt = n => n >= 1048576 ? (n / 1048576).toFixed(1) + 'MB' : Math.max(1, Math.round(n / 1024)) + 'KB';
function render() {
  $('count').textContent = `선택된 사진 ${items.length}개`;
  $('bGo').disabled = busy || !items.some(i => i.status !== 'ok');
  $('bClear').disabled = busy || !items.length;
  $('bFiles').disabled = $('bDir').disabled = $('bDest').disabled = busy;
  const list = $('list');
  list.textContent = '';
  if (!items.length) {
    const d = document.createElement('div'); d.className = 'empty'; d.textContent = '아직 추가된 사진이 없습니다';
    list.append(d); return;
  }
  const frag = document.createDocumentFragment();
  items.forEach((it, idx) => {
    const row = document.createElement('div'); row.className = 'it ' + it.status;
    const n = document.createElement('span'); n.className = 'n ell'; n.textContent = n.title = it.path;
    const s = document.createElement('span'); s.className = 's ell'; s.textContent = s.title = it.msg || fmt(it.file.size);
    row.append(n, s);
    if (!busy) {
      const x = document.createElement('button'); x.className = 'rm'; x.type = 'button'; x.textContent = '✕'; x.title = '목록에서 빼기';
      x.onclick = () => { items.splice(idx, 1); render(); };
      row.append(x);
    }
    frag.append(row);
  });
  list.append(frag);
}
$('bClear').onclick = () => {
  items = []; if (dest && dest.auto) dest = null;
  $('sum').textContent = ''; $('prog').classList.add('hide'); showDest(); render();
};

/* ======================= 이미지 읽기 ======================= */
let heicChain = Promise.resolve();          // HEIC 해독은 한 번에 하나씩 (메모리 절약)
function decodeHeic(file) {
  const job = heicChain.then(() => HeicTo({blob: file, type: 'bitmap'}));
  heicChain = job.catch(() => {});
  return job;
}
async function decodeTiff(file) {
  const buf = await file.arrayBuffer();
  const ifds = UTIF.decode(buf);
  const page = ifds.find(i => i.width && i.height) || ifds[0];
  UTIF.decodeImage(buf, page, ifds);
  const rgba = new Uint8ClampedArray(UTIF.toRGBA8(page).buffer);
  return createImageBitmap(new ImageData(rgba, page.width, page.height));
}
function decodeByImg(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file), im = new Image();
    im.onload = () => { URL.revokeObjectURL(url); resolve(im); };
    im.onerror = () => { URL.revokeObjectURL(url); reject(new Error('읽을 수 없는 이미지입니다')); };
    im.src = url;
  });
}
async function decode(file) {
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  if (ext === 'heic' || ext === 'heif') return decodeHeic(file);
  if (ext === 'tif' || ext === 'tiff') return decodeTiff(file);
  try { return await createImageBitmap(file); }        // 회전 정보(EXIF) 자동 반영
  catch (e) {
    if (await HeicTo.isHeic(file).catch(() => false)) return decodeHeic(file);   // 확장자만 jpg인 HEIC
    return decodeByImg(file);
  }
}

/* ======================= 크기 계산 · JPG 만들기 ======================= */
function opts() {
  return {mode: mode(), w: Math.max(0, +$('w').value | 0), h: Math.max(0, +$('h').value | 0),
    pct: +$('pct').value, quality: +$('quality').value / 100,
    enlarge: $('enlarge').checked, tree: $('tree').checked, overwrite: $('overwrite').checked};
}
function calcSize(w, h, o) {
  const r = (a, f) => Math.max(1, Math.round(a * f));
  if (o.mode === 'percent') return [r(w, o.pct / 100), r(h, o.pct / 100)];
  if (o.mode === 'fit') {
    const f = Math.min((o.w || w) / w, (o.h || h) / h);
    return f >= 1 && !o.enlarge ? [w, h] : [r(w, f), r(h, f)];
  }
  if (o.mode === 'exact') {
    if (o.w && o.h) return [o.w, o.h];
    if (o.w) return [o.w, r(h, o.w / w)];
    if (o.h) return [r(w, o.h / h), o.h];
  }
  return [w, h];
}
async function toJpeg(file, o) {
  let src = await decode(file);
  const w = src.naturalWidth || src.width, h = src.naturalHeight || src.height;
  const [nw, nh] = calcSize(w, h, o);
  if ((nw !== w || nh !== h) && src instanceof ImageBitmap) {
    try {                                    // 고품질 축소
      const r = await createImageBitmap(src, {resizeWidth: nw, resizeHeight: nh, resizeQuality: 'high'});
      src.close(); src = r;
    } catch (e) { /* 아래 drawImage로 처리 */ }
  }
  const c = document.createElement('canvas'); c.width = nw; c.height = nh;
  const g = c.getContext('2d');
  g.fillStyle = '#fff'; g.fillRect(0, 0, nw, nh);   // 투명 배경 → 흰색
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
  g.drawImage(src, 0, 0, nw, nh);
  if (src.close) src.close();
  const blob = await new Promise(res => c.toBlob(res, 'image/jpeg', o.quality));
  c.width = c.height = 0;                    // 메모리 해제
  if (!blob) throw new Error('JPG를 만들지 못했습니다 (사진이 너무 큽니다)');
  return {blob, from: `${w}×${h}`, to: `${nw}×${nh}`};
}

/* ======================= 저장 ======================= */
const cleanName = s => s.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/[. ]+$/, '') || '_';
function outParts(it, o, baseRoots) {
  let parts = it.path.split('/').filter(Boolean);
  if (it.root && baseRoots.has(it.root)) parts = parts.slice(1);   // 저장 위치 = 그 폴더 → 폴더명 중복 제거
  if (!o.tree) parts = parts.slice(-1);
  parts = parts.map(cleanName);
  parts[parts.length - 1] = parts[parts.length - 1].replace(/\.[^.]*$/, '') + '.jpg';
  return parts;
}
const reserved = new Set();
async function writeFile(root, parts, blob, overwrite) {
  let dir = root;
  for (const d of parts.slice(0, -1)) dir = await dir.getDirectoryHandle(d, {create: true});
  const name = parts[parts.length - 1], stem = name.slice(0, -4), key = parts.slice(0, -1).join('/') + '/';
  let fn = name;
  if (!overwrite) {
    for (let i = 1; ; i++) {
      let exists = reserved.has((key + fn).toLowerCase());
      if (!exists) { try { await dir.getFileHandle(fn); exists = true; } catch (e) { /* 없음 */ } }
      if (!exists) break;
      fn = `${stem}_${i}.jpg`;
    }
  }
  reserved.add((key + fn).toLowerCase());
  const fh = await dir.getFileHandle(fn, {create: true});
  const ws = await fh.createWritable();
  await ws.write(blob); await ws.close();
  return key + fn;
}

// ZIP 만들기 (Safari·Firefox용, 무압축 · 한글 파일명)
const CRC_T = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(u8) { let c = 0xFFFFFFFF; for (let i = 0; i < u8.length; i++) c = CRC_T[(c ^ u8[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
async function makeZip(files) {
  const enc = new TextEncoder(), out = [], cen = []; let off = 0;
  const d = new Date(), tm = (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1),
    dt = ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();
  for (const f of files) {
    const nm = enc.encode(f.name), data = new Uint8Array(await f.blob.arrayBuffer()), crc = crc32(data), sz = data.length;
    const L = new DataView(new ArrayBuffer(30));
    L.setUint32(0, 0x04034b50, true); L.setUint16(4, 20, true); L.setUint16(6, 0x0800, true);
    L.setUint16(10, tm, true); L.setUint16(12, dt, true); L.setUint32(14, crc, true);
    L.setUint32(18, sz, true); L.setUint32(22, sz, true); L.setUint16(26, nm.length, true);
    out.push(L.buffer, nm, data);
    const C = new DataView(new ArrayBuffer(46));
    C.setUint32(0, 0x02014b50, true); C.setUint16(4, 20, true); C.setUint16(6, 20, true); C.setUint16(8, 0x0800, true);
    C.setUint16(12, tm, true); C.setUint16(14, dt, true); C.setUint32(16, crc, true);
    C.setUint32(20, sz, true); C.setUint32(24, sz, true); C.setUint16(28, nm.length, true); C.setUint32(42, off, true);
    cen.push(C.buffer, nm);
    off += 30 + nm.length + sz;
  }
  const csz = cen.reduce((a, x) => a + x.byteLength, 0), E = new DataView(new ArrayBuffer(22));
  E.setUint32(0, 0x06054b50, true); E.setUint16(8, files.length, true); E.setUint16(10, files.length, true);
  E.setUint32(12, csz, true); E.setUint32(16, off, true);
  return new Blob([...out, ...cen, E.buffer], {type: 'application/zip'});
}

/* ======================= 변환 실행 ======================= */
$('bGo').onclick = async () => {
  const o = opts();
  if ((o.mode === 'fit' || o.mode === 'exact') && !o.w && !o.h) { alert('가로 또는 세로 크기를 입력해 주세요.'); return; }
  if (typeof HeicTo === 'undefined') { alert('프로그램을 불러오는 중입니다. 잠시 후 다시 눌러 주세요.'); return; }

  // 저장 위치 준비 (사용자 클릭 직후에 권한을 받아야 함)
  let outRoot = null;
  if (CAN_WRITE) {
    try {
      if (!dest) {
        $('sum').textContent = `'${OUT_NAME}' 폴더를 만들 위치를 선택해 주세요.`;
        const h = await window.showDirectoryPicker({id: 'photo-dest', mode: 'readwrite'});
        dest = {handle: h, name: h.name, auto: false}; showDest();
      }
      if (await dest.handle.queryPermission({mode: 'readwrite'}) !== 'granted' &&
          await dest.handle.requestPermission({mode: 'readwrite'}) !== 'granted') {
        alert('폴더에 저장할 권한이 없습니다. 권한을 허용해 주세요.'); return;
      }
      outRoot = await dest.handle.getDirectoryHandle(OUT_NAME, {create: true});
    } catch (e) {
      if (e.name !== 'AbortError') alert('저장 폴더를 준비하지 못했습니다: ' + e.message);
      return;
    }
  }

  const baseRoots = new Set();
  if (dest) for (const r of new Set(items.map(i => i.root).filter(Boolean)))
    if (await r.isSameEntry(dest.handle)) baseRoots.add(r);

  busy = true; reserved.clear(); render();
  const todo = items.filter(i => i.status !== 'ok');
  const prog = $('prog'); prog.classList.remove('hide'); prog.max = todo.length; prog.value = 0;
  const zipFiles = [];
  let ok = 0, fail = 0, next = 0;
  const tick = () => { prog.value = ok + fail; $('sum').textContent = `변환 중... ${ok + fail} / ${todo.length}`; };
  tick();

  async function worker() {
    while (next < todo.length) {
      const it = todo[next++];
      try {
        const r = await toJpeg(it.file, o);
        const parts = outParts(it, o, baseRoots);
        if (outRoot) await writeFile(outRoot, parts, r.blob, o.overwrite);
        else {
          let name = parts.join('/'), k = 0; const stem = name.slice(0, -4);
          while (reserved.has(name.toLowerCase())) name = `${stem}_${++k}.jpg`;
          reserved.add(name.toLowerCase()); zipFiles.push({name: OUT_NAME + '/' + name, blob: r.blob});
        }
        it.status = 'ok'; it.msg = `✓ ${r.from} → ${r.to} · ${fmt(r.blob.size)}`; ok++;
      } catch (e) {
        console.error(it.path, e);
        it.status = 'err'; it.msg = '✗ ' + (e && e.message ? e.message : '변환 실패'); fail++;
      }
      tick();
      if ((ok + fail) % 10 === 0) render();
    }
  }
  await Promise.all([worker(), worker()]);

  let where = '';
  if (outRoot) where = `📁 ${dest.name} › ${OUT_NAME} 폴더에 저장했습니다.`;
  else if (zipFiles.length) {
    $('sum').textContent = 'ZIP 파일을 만드는 중...';
    const a = document.createElement('a');
    a.href = URL.createObjectURL(await makeZip(zipFiles));
    a.download = OUT_NAME + '.zip'; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    where = `${OUT_NAME}.zip 으로 내려받았습니다.`;
  }
  busy = false; render();
  $('sum').textContent = `완료: 성공 ${ok}개` + (fail ? `, 실패 ${fail}개` : '') + (ok ? ' — ' + where : '');
};

render();
