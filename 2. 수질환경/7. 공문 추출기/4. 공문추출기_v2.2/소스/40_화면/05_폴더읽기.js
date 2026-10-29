/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/05_폴더읽기.js] 폴더 읽기(scan)
   하는 일 : 폴더·하위 폴더 목록, ODT/PDF/HWPX 해석(캐시), 의뢰공문·시행공문·성적서·첨부 분류, 공문 목록 만들기, 성적처리완료 읽기
   주요 이름: listDir, parseOdtEntry, parseReportEntry, classifyFiles, scan, makeDoc, augment, scanDone
   이럴 때 고침: 어떤 파일을 어떻게 분류할지
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 폴더 읽기 ───── */
async function listDir(dir, path) {
  const files = [], dirs = [];
  for await (const [name, h] of dir.entries()) {
    const nm = name.normalize('NFC');
    if (h.kind === 'directory') { dirs.push({ name, nm, handle: h }); continue; }
    if (IGNORE(nm)) { if (STD_RE.test(nm) && !path) files.push({ dir, path, name, nm, handle: h, kind: 'std' }); continue; }
    files.push({ dir, path, name, nm, handle: h, kind: kindOf(nm) });
  }
  for (const f of files) { try { const file = await f.handle.getFile(); f.size = file.size; f.mtime = file.lastModified; } catch (e) { f.size = 0; f.mtime = 0; } }
  files.sort((a, b) => a.nm.localeCompare(b.nm, 'ko')); dirs.sort((a, b) => a.nm.localeCompare(b.nm, 'ko'));
  return { files, dirs };
}
const fkey = f => `${f.path}/${f.nm}|${f.size}|${f.mtime}`;
async function fileBytes(f) { return new Uint8Array(await (await f.handle.getFile()).arrayBuffer()); }
// ODT 읽기 → {result, reply, error}
async function parseOdtEntry(f) {
  const ck = 'odt:' + fkey(f);
  if (state.fileCache.has(ck)) return state.fileCache.get(ck);
  const out = {};
  try {
    if (!f.size) throw new Error('빈 파일 (다운로드 중이거나 손상된 파일)');
    out.result = await E.extractOdt(await fileBytes(f), f.nm, inflateRaw);
    if (E2.isReply(out.result)) out.reply = E2.parseReply(out.result);
  } catch (e) { out.error = (e && e.message) || String(e); }
  state.fileCache.set(ck, out);
  return out;
}
// PDF 텍스트 → 시험성적서이면 해석 결과, 아니면 null
async function pdfTextPages(bytes) {
  const doc = await window.pdfjsLib.getDocument({ data: bytes, isEvalSupported: false }).promise;
  const pages = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const p = await doc.getPage(i), vp = p.getViewport({ scale: 1 }), tc = await p.getTextContent();
    pages.push({ w: vp.width, h: vp.height, items: tc.items.filter(t => t.str != null).map(t => ({ s: t.str, x: t.transform[4], y: vp.height - t.transform[5], w: t.width, h: Math.abs(t.transform[3]) || 10 })) });
    if (i === 1 && !pages[0].items.some(t => /접|수|번|호/.test(t.s))) break; // 성적서 아님 (스캔 PDF 등) — 첫 쪽만 확인
  }
  doc.destroy && doc.destroy();
  return pages;
}
async function parseReportEntry(f) {
  const ck = 'pdf:' + fkey(f);
  if (state.fileCache.has(ck)) return state.fileCache.get(ck);
  let rep = null;
  if (window.pdfjsLib && f.size) {
    try { const r = E2.parseReportPdf(await pdfTextPages(await fileBytes(f)), f.nm); if (r.samples.length) rep = r; } catch (e) { rep = null; }
  }
  state.fileCache.set(ck, rep);
  return rep;
}
async function parseHwpxEntry(f) {
  const ck = 'hwpx:' + fkey(f);
  if (state.fileCache.has(ck)) return state.fileCache.get(ck);
  let h = null; try { h = await E2.parseHwpx(await fileBytes(f), inflateRaw); } catch (e) { h = { grids: [], paras: [], error: e.message }; }
  state.fileCache.set(ck, h);
  return h;
}
// v2.2: 첨부 엑셀(xlsx) 보기용 해석 (캐시)
async function parseXlsxEntry(f) {
  const ck = 'xlsx:' + fkey(f);
  if (state.fileCache.has(ck)) return state.fileCache.get(ck);
  const v = await E2.parseXlsxView(await fileBytes(f), inflateRaw);   // 실패하면 오류 → 보기 화면에 사유 표시
  state.fileCache.set(ck, v);
  return v;
}
// 폴더 하나의 파일 분류: 의뢰공문 / 시행공문 / 성적서 / 첨부
async function classifyFiles(files, progress) {
  const out = { requests: [], replies: [], reports: [], attach: [], std: null };
  for (const f of files) {
    if (f.kind === 'std') { out.std = f; continue; }
    if (f.kind === 'odt') {
      const p = await parseOdtEntry(f); progress && progress();
      if (p.reply) out.replies.push({ f, info: p.reply, result: p.result });
      else out.requests.push({ f, p });
    } else if (f.kind === 'pdf' && !isHistoryDoc(f.nm)) {
      const rep = await parseReportEntry(f); progress && progress();
      if (rep) out.reports.push({ f, rep }); else out.attach.push(f);
    } else if (!isHistoryDoc(f.nm)) out.attach.push(f);
  }
  return out;
}
async function getDoneDir(create) { try { return await state.root.getDirectoryHandle(DONE_DIR, create ? { create: true } : undefined); } catch (e) { return null; } }

/* ───── 읽기 전체 (scan) ───── */
const keyOfReq = req => req.p && req.p.result && req.p.result.doc.접수 ? req.p.result.doc.접수 : 'file:' + req.f.nm;
async function scan(opts = {}) {
  if (!state.root) return;
  if (state.busy) { state.pendingScan = { ...(state.pendingScan || {}), ...opts }; return; } // 읽는 중이면 끝난 뒤 한 번 더
  state.busy = true;
  let organizeNow = false;
  try {
    if (!opts.quiet) busy(true, '공문 폴더 읽는 중…');
    let n = 0; const prog = () => { n++; if (!opts.quiet && n % 4 === 0) busy(true, `파일 읽는 중… ${n}`); };
    const top = await listDir(state.root, '');
    const rc = await classifyFiles(top.files, prog);
    const inbox = { replies: rc.replies, reports: rc.reports, attach: rc.attach, requests: rc.requests.map(x => ({ ...x, dir: state.root })), groups: [] };
    const cases = [], other = [];
    for (const d of top.dirs) {
      if (SKIP_DIR(d.nm)) continue;
      const L = await listDir(d.handle, d.nm);
      const C = await classifyFiles(L.files, prog);
      if (C.requests.length) {
        const multi = new Set(C.requests.map(keyOfReq)).size > 1;
        cases.push({ dir: d.handle, name: d.nm, C, multi });
        if (multi) inbox.groups.push({ dir: d.handle, name: d.nm, C });
      } else { inbox.replies.push(...C.replies); inbox.reports.push(...C.reports); inbox.attach.push(...C.attach); }
      L.dirs.forEach(x => other.push(d.nm + '/' + x.nm));
    }
    state.inbox = inbox; state.excluded = other;
    const docs = [];
    for (const c of cases) for (const req of c.C.requests) docs.push(await makeDoc(req, c.dir, c.name, c.multi ? subsetFor(req, c.C) : c.C, 'root', !c.multi));
    for (const req of inbox.requests) docs.push(await makeDoc(req, state.root, '', subsetFor(req, { replies: [], reports: [], attach: inbox.attach.filter(f => f.dir === state.root) }), 'root', false));
    state.docs = docs;
    await scanDone(opts);
    await loadStd(rc.std);
    E.markDuplicates(state.docs.filter(d => d.result).map(d => d.result));
    E.markDuplicates(state.doneDocs.filter(d => d.result).map(d => d.result));
    state.stdFilled = E.applyStdTable([...state.docs, ...state.doneDocs].filter(d => d.result).map(d => d.result), state.stdTable);
    for (const d of state.docs) matchDoc(d, inbox);
    for (const d of state.doneDocs) matchDoc(d, { replies: [], reports: [] });
    state.lastScan = Date.now();
    render();
    const loose = inbox.requests.length + inbox.groups.reduce((a, g) => a + g.C.requests.length, 0);
    if (loose && !opts.noOrganize) organizeNow = state.settings.organize.auto ? 'auto' : (!state.settings.organize.asked ? 'ask' : '');
  } catch (e) {
    if (e && e.name === 'NotAllowedError') { toast('폴더 접근 권한이 없습니다. 다시 연결해 주세요.', 'err'); showWelcome(state.root.name); }
    else { console.error(e); toast('폴더를 읽지 못했습니다: ' + explain(e), 'err'); }
  } finally { state.busy = false; busy(false); }
  if (state.pendingScan) { const p = state.pendingScan; state.pendingScan = null; return scan(p); }
  if (organizeNow === 'auto') await organizeAll(true);
  else if (organizeNow === 'ask') await askOrganize();
}
// 여러 공문이 한 폴더에 있을 때: 붙임 이름이 맞는 첨부만 그 공문 것으로 봄
function subsetFor(req, C) {
  const names = E2.attachmentNames(req.p.result ? req.p.result.doc.본문 : []);
  return { replies: [], reports: [], attach: C.attach.filter(f => names.length && E2.attachScore(f.nm, names) >= 0.6), shared: true };
}
async function makeDoc(req, dir, dirName, C, loc, organized) {
  const f = req.f, p = req.p;
  const d = { id: `${loc}|${fkey(f)}`, f, name: f.name, nm: f.nm, handle: f.handle, loc, dir, dirName, organized, C: C || { replies: [], reports: [], attach: [] }, base: p.result || null, error: p.error };
  d.key = p.result && p.result.doc.접수 ? p.result.doc.접수 : 'file:' + f.nm;
  d.result = await augment(d);
  return d;
}
// 시료 표가 없는 공문: 직접 입력 > 첨부 HWPX > 원래 결과
async function augment(d) {
  const base = d.base; if (!base) return null;
  const n = peekNotes(d.key);
  if (n.manual && n.manual.length) { try { return E2.samplesFromManual(base, n.manual); } catch (e) { console.error(e); } }
  if (base.warnings.includes('시료표 미인식')) {
    const hw = d.C.attach.filter(f => f.kind === 'hwpx');
    if (hw.length) {
      const list = []; for (const f of hw) list.push({ name: f.nm, parsed: await parseHwpxEntry(f) });
      const r = E2.samplesFromAttachments(base, list); if (r) return r;
    }
  }
  return base;
}
async function scanDone(opts) {
  state.doneDocs = []; state.doneCount = 0;
  const doneDir = await getDoneDir(false); if (!doneDir) return;
  const L = await listDir(doneDir, DONE_DIR);
  state.doneCount = L.files.filter(f => f.kind === 'odt').length + L.dirs.length;
  if (state.filter.state !== 'done') return;
  let i = 0;
  const C0 = await classifyFiles(L.files.filter(f => f.kind === 'odt'));
  for (const req of C0.requests) state.doneDocs.push(await makeDoc(req, doneDir, '', { replies: [], reports: [], attach: [] }, 'done', false));
  for (const d of L.dirs) {
    const S = await listDir(d.handle, DONE_DIR + '/' + d.nm);
    const C = await classifyFiles(S.files);
    for (const req of C.requests) state.doneDocs.push(await makeDoc(req, d.handle, d.nm, C, 'done', true));
    if (!opts.quiet && ++i % 5 === 0) busy(true, `완료 공문 읽는 중… ${i} / ${L.dirs.length}`);
  }
}
async function loadStd(en) {
  state.stdTable = []; state.stdFile = '';
  if (!en) return;
  try {
    const b = await fileBytes(en);
    const rows = /\.csv$/i.test(en.nm) ? E.parseCsv(E.decodeText(b)) : await E.readXlsxRows(b, inflateRaw);
    state.stdTable = E.parseStdTable(rows); state.stdFile = en.nm;
  } catch (e) { toast(`기준표(${en.nm})를 읽지 못했습니다. 엑셀에서 열려 있다면 닫고 [새로고침] 하세요. (${explain(e)})`, 'err'); }
}
