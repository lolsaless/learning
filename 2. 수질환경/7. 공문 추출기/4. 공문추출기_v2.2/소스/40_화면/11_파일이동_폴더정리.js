/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/11_파일이동_폴더정리.js] 파일 이동·공문별 폴더 정리
   하는 일 : 완료 체크, 파일·폴더 옮기기(실패 시 되돌림), "의뢰기관_제목_시행" 폴더 정리
   주요 이름: setChecked, moveFile, moveDir, organizeOne, organizeAll, askOrganize
   이럴 때 고침: 첨부를 함께 옮기는 규칙
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 체크 ───── */
function setChecked(d, on) {
  if (!d || d.loc !== 'root') return;
  if (on) state.status.checked[d.key] = { at: nowIso(), file: d.nm };
  else delete state.status.checked[d.key];
  saveStatusSoon();
}
function findDoc(id) { return [...state.docs, ...state.doneDocs].find(x => x.id === id); }

/* ───── 파일·폴더 이동 ───── */
function explain(e) {
  const n = e && e.name;
  if (n === 'NoModificationAllowedError' || n === 'InvalidModificationError' || n === 'InvalidStateError') return '파일이 다른 프로그램(한글·엑셀·PDF 뷰어 등)에서 열려 있어 처리할 수 없습니다. 파일을 닫고 다시 시도하세요.';
  if (n === 'NotFoundError') return '파일이 이미 옮겨졌거나 없습니다. [새로고침] 후 다시 확인하세요.';
  if (n === 'NotAllowedError' || n === 'SecurityError') return '폴더 쓰기 권한이 없습니다. 폴더를 다시 연결해 주세요.';
  if (n === 'QuotaExceededError') return '저장 공간이 부족합니다.';
  return (e && e.message) || String(e);
}
async function exists(dir, name) { try { await dir.getFileHandle(name); return true; } catch (e) { return false; } }
async function dirExists(dir, name) { try { await dir.getDirectoryHandle(name); return true; } catch (e) { return false; } }
async function uniqueName(dir, name) {
  if (!(await exists(dir, name))) return name;
  const dot = name.lastIndexOf('.'), base = dot > 0 ? name.slice(0, dot) : name, ext = dot > 0 ? name.slice(dot) : '';
  for (let k = 2; k < 1000; k++) { const c = `${base} (${k})${ext}`; if (!(await exists(dir, c))) return c; }
  throw new Error('같은 이름의 파일이 너무 많습니다.');
}
async function uniqueDirName(parent, name) {
  if (!(await dirExists(parent, name)) && !(await exists(parent, name))) return name;
  for (let k = 2; k < 1000; k++) { const c = `${name} (${k})`; if (!(await dirExists(parent, c))) return c; }
  throw new Error('같은 이름의 폴더가 너무 많습니다.');
}
// 복사 → 크기 확인 → 원본 삭제 (실패하면 복사본을 지우고 원본 유지). keep=true면 복사만
async function moveFile(srcDir, name, dstDir, keep) {
  const fh = await srcDir.getFileHandle(name);
  const target = await uniqueName(dstDir, name.normalize('NFC'));
  if (!keep && typeof fh.move === 'function') {
    try { await fh.move(dstDir, target); if (await exists(dstDir, target)) return target; } catch (e) { /* 아래 방식으로 다시 시도 */ }
    if (await exists(dstDir, target) && !(await exists(srcDir, name))) return target;
  }
  const file = await fh.getFile();
  const nh = await dstDir.getFileHandle(target, { create: true });
  try {
    const w = await nh.createWritable(); await w.write(file); await w.close();
    if ((await nh.getFile()).size !== file.size) throw new Error('복사한 파일 크기가 원본과 다릅니다.');
  } catch (e) { await dstDir.removeEntry(target).catch(() => {}); throw e; }
  if (keep) return target;
  try { await srcDir.removeEntry(name); }
  catch (e) { await dstDir.removeEntry(target).catch(() => {}); throw e; }
  return target;
}
// 폴더 옮기기: 대상에 새 폴더를 만들고 안의 파일을 하나씩 옮긴 뒤 빈 폴더를 지움. 실패하면 옮긴 파일을 되돌림
async function moveDir(parent, name, dstParent) {
  const src = await parent.getDirectoryHandle(name);
  const tname = await uniqueDirName(dstParent, name.normalize('NFC'));
  const dst = await dstParent.getDirectoryHandle(tname, { create: true });
  const moved = [];
  try {
    for await (const [n, h] of src.entries()) {
      if (h.kind === 'directory') { await moveDir(src, n, dst); moved.push({ dir: true, n }); }
      else { const to = await moveFile(src, n, dst); moved.push({ n, to }); }
    }
  } catch (e) {
    for (const m of moved.reverse()) { try { if (m.dir) await moveDir(dst, m.n, src); else await moveFile(dst, m.to, src); } catch (e2) { /* 되돌리기 실패는 아래 메시지로 안내 */ } }
    await dstParent.removeEntry(tname).catch(() => {});
    throw e;
  }
  await parent.removeEntry(name).catch(() => {}); // 빈 폴더 삭제 (남은 파일이 있으면 그대로 둠)
  return tname;
}

/* ───── 공문별 폴더 정리 ───── */
// 의뢰공문 1건 + 첨부(붙임 이름 일치, 또는 3분 안에 함께 저장된 파일)를 "의뢰기관_제목_시행" 폴더로
async function organizeOne(req, srcDir, pool, siblings) {
  const doc = req.p.result ? req.p.result.doc : { 파일명: req.f.nm };
  const key = keyOfReq(req);
  const names = E2.attachmentNames(doc.본문 || []);
  const base = E2.caseFolderName(doc);
  let name = base, dir = null;
  for (let k = 2; k < 50; k++) {
    if (await dirExists(state.root, name)) {
      const d0 = await state.root.getDirectoryHandle(name), L = await listDir(d0, name);
      let clash = false;
      for (const f of L.files.filter(f => f.kind === 'odt')) { const p = await parseOdtEntry(f); if (!p.reply && p.result && (p.result.doc.접수 || 'file:' + f.nm) !== key) clash = true; }
      if (!clash) { dir = d0; break; }
      name = `${base} (${k})`;
    } else { dir = await state.root.getDirectoryHandle(name, { create: true }); break; }
  }
  if (!dir) throw new Error('폴더 이름을 정하지 못했습니다.');
  const take = [];
  for (const f of pool) {
    if (f.taken || f.dir !== srcDir) continue;
    const score = names.length ? E2.attachScore(f.nm, names) : 0;
    // 붙임 이름이 안 맞으면: 3분 안에 함께 저장된 의뢰공문이 이 공문 하나뿐일 때만 (여러 공문을 한꺼번에 복사한 경우 제외)
    const close = s => Math.abs((f.mtime || 0) - (s.f.mtime || 0)) <= 180000;
    const near = names.length && /^(hwpx|xlsx|img|tif|doc|pdf)$/.test(f.kind) && close(req) && !siblings.some(s => s !== req && s.f !== req.f && close(s));
    if (score >= 0.6 || near) take.push(f);
  }
  const moved = [];
  moved.push({ from: req.f.nm, to: await moveFile(srcDir, req.f.name, dir) });
  for (const f of take) { try { moved.push({ from: f.nm, to: await moveFile(srcDir, f.name, dir) }); f.taken = true; } catch (e) { /* 첨부는 실패해도 계속 */ } }
  state.status.history.unshift({ at: nowIso(), action: '폴더정리', key, folder: name, files: moved });
  addLog(key, `공문 폴더 정리: ${name}${take.length ? ` (첨부 ${take.length}개 포함)` : ''}`, '', true);
  return { dir, name, moved };
}
async function organizeAll(silent) {
  const ib = state.inbox, jobs = [];
  for (const req of ib.requests) jobs.push({ req, srcDir: state.root, pool: ib.attach, siblings: ib.requests });
  for (const g of ib.groups) for (const req of g.C.requests) jobs.push({ req, srcDir: g.dir, pool: g.C.attach.map(f => f), siblings: g.C.requests, group: g });
  if (!jobs.length) return;
  busy(true, `공문별 폴더 만드는 중… 0 / ${jobs.length}`);
  const ok = [], fail = [];
  for (let i = 0; i < jobs.length; i++) {
    const j = jobs[i];
    try { const r = await organizeOne(j.req, j.srcDir, j.pool, j.siblings); ok.push(r.name); } catch (e) { fail.push(`${j.req.f.nm}: ${explain(e)}`); }
    busy(true, `공문별 폴더 만드는 중… ${i + 1} / ${jobs.length}`);
  }
  for (const g of ib.groups) await state.root.removeEntry(g.name).catch(() => {}); // 비었으면 삭제
  await writeStatus(); await writeNotes();
  busy(false);
  await scan({ quiet: true, noOrganize: true });
  if (fail.length) await info('공문별 폴더 정리', `<p class="res-ok">정리한 공문 ${ok.length}건</p><h4 class="res-err">정리하지 못한 공문 ${fail.length}건</h4><ul class="flist">${fail.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`);
  else if (!silent || ok.length) toast(`공문 ${ok.length}건을 공문별 폴더로 정리했습니다.`);
}
async function askOrganize() {
  const ib = state.inbox, n = ib.requests.length + ib.groups.reduce((a, g) => a + g.C.requests.length, 0);
  const ex = [...ib.requests, ...ib.groups.flatMap(g => g.C.requests)].slice(0, 6).map(r => `<li>${esc(E2.caseFolderName(r.p.result ? r.p.result.doc : { 파일명: r.f.nm }))}</li>`).join('');
  const r = await modal('공문별 폴더 정리', `<p>공문 폴더에 정리되지 않은 의뢰공문 <b>${n}건</b>이 있습니다. 공문마다 <b>의뢰기관_제목_시행번호</b> 폴더를 만들고 공문과 첨부 파일(붙임)을 옮깁니다.</p><ul class="flist">${ex}${n > 6 ? '<li>…</li>' : ''}</ul>
    <p class="muted">시행공문·성적서는 처리 완료할 때 해당 공문 폴더로 옮겨집니다. 원본 내용은 바뀌지 않습니다.</p>
    <label class="chk"><input type="checkbox" id="orgAuto" checked> 앞으로 새 공문은 묻지 않고 자동으로 정리</label>`, '정리하기', { cancelLabel: '나중에', collect: () => ({ auto: $('#orgAuto').checked }) });
  state.settings.organize.asked = true;
  if (r) state.settings.organize.auto = !!r.auto;
  await writeSettings();
  if (r) await organizeAll(false);
}
