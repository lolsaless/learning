/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/12_처리완료_되돌리기.js] 처리 완료·되돌리기·파일 연결
   하는 일 : 처리 완료(시행공문·성적서 이동, 성적처리완료로), 되돌리기, 짝 못 찾은 파일 넣기
   주요 이름: processChecked, restore, adopt, organizeSelected, showInbox
   이럴 때 고침: 완료 처리 순서·복사/이동 규칙
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 처리 완료 ───── */
async function processChecked() {
  const groups = checkedGroups();
  if (!groups.length) return toast('완료 체크한 공문이 없습니다.');
  const batchKeys = new Set(groups.map(g => g.key)), doneKeys = new Set();
  const rowsHtml = groups.map(g => {
    const d = g.docs[0], m = d.match || { replies: [], reports: [] };
    return `<tr><td>${esc((d.result && d.result.doc.제목) || d.nm)}</td><td>${m.replyOk ? '<span class="pill ok">일치</span>' : m.replies.length ? '<span class="pill part">확인</span>' : '<span class="pill none">없음</span>'}</td><td>${m.reportState === 'full' ? `<span class="pill ok">${m.got}/${m.total}</span>` : m.reportState === 'partial' ? `<span class="pill part">${m.got}/${m.total}</span>` : '<span class="pill none">없음</span>'}</td></tr>`;
  }).join('');
  const r = await modal('처리 완료', `<p>완료 체크한 공문 <b>${groups.length}건</b>을 처리합니다.</p>
    <ol><li>짝지은 <b>시행공문·시험성적서</b>를 각 공문 폴더(의뢰기관_제목_시행번호)로 옮깁니다. 다른 공문과 함께 쓰는 성적서는 복사합니다.</li>
    <li>${state.settings.nestDone ? `공문 폴더를 <b>${DONE_DIR}</b> 폴더 안으로 옮깁니다.` : '공문 폴더는 공문 폴더에 그대로 둡니다.'}</li></ol>
    <table class="mini"><tr><th>공문</th><th>시행공문</th><th>성적서</th></tr>${rowsHtml}</table>
    <label class="chk"><input type="checkbox" id="optNest" ${state.settings.nestDone ? 'checked' : ''}> 공문 폴더를 ${DONE_DIR}로 옮기기</label>
    <label class="chk"><input type="checkbox" id="optPartial"> 일부만 일치하는 성적서·기관 확인이 필요한 시행공문도 함께 옮기기</label>`, '처리 완료', { width: 'min(760px, calc(100vw - 32px))', collect: () => ({ nest: $('#optNest').checked, partial: $('#optPartial').checked }) });
  if (!r) return;
  if (state.settings.nestDone !== r.nest) { state.settings.nestDone = r.nest; saveSettingsSoon(); }
  busy(true, '처리하는 중…');
  const okList = [], failList = [];
  try {
    const doneDir = r.nest ? await getDoneDir(true) : null;
    for (const g of groups) {
      const d = g.docs[0];
      try {
        // 1) 공문 폴더 확보 (정리 전이면 먼저 정리)
        let caseDir = d.dir, caseName = d.dirName;
        if (!d.organized) {
          const pool = d.C.attach.map(f => f);
          const res = await organizeOne({ f: d.f, p: { result: d.base } }, d.dir, pool, []);
          for (const o of g.docs.slice(1)) if (!o.organized) await moveFile(o.dir, o.name, res.dir).catch(() => {});
          caseDir = res.dir; caseName = res.name;
        }
        // 2) 시행공문·성적서 옮기기
        const m = d.match || { replies: [], reports: [] }, files = [];
        for (const x of m.replies) {
          if (x.inCase || (x.score < 1 && !r.partial)) continue;
          files.push({ from: x.f.nm, to: await moveFile(x.f.dir, x.f.name, caseDir), kind: '시행공문' });
        }
        for (const x of m.reports) {
          if (x.inCase || (x.m.level !== 'full' && !r.partial && !(x.m.matched.length && !x.m.extra.length && x.m.orgGood !== false))) continue;
          // 다른 공문도 쓰는 성적서: 아직 처리하지 않는 공문이 있거나, 이번 묶음에서 뒤에 처리할 공문이 있으면 복사
          const users = [...((state.inbox.reports.find(y => y.f === x.f) || {}).usedBy || [])];
          const left = users.filter(k => k !== d.key && (!batchKeys.has(k) || !doneKeys.has(k)));
          const keep = left.length > 0;
          files.push({ from: x.f.nm, to: await moveFile(x.f.dir, x.f.name, caseDir, keep), kind: keep ? '성적서(복사)' : '성적서' });
        }
        // 3) 성적처리완료로
        let finalName = caseName;
        if (r.nest && doneDir) finalName = DONE_DIR + '/' + await moveDir(state.root, caseName, doneDir);
        doneKeys.add(g.key);
        delete state.status.checked[g.key];
        state.status.history.unshift({ at: nowIso(), action: '처리완료', key: g.key, folder: finalName, files });
        addLog(g.key, `처리 완료 — ${files.length ? files.map(f => f.kind).join(', ') + ' 정리, ' : ''}${finalName}`, '', true);
        okList.push({ title: (d.result && d.result.doc.제목) || d.nm, folder: finalName, files });
      } catch (e) { console.error(e); failList.push({ file: d.nm, msg: explain(e) }); }
    }
    await writeStatus(); await writeNotes();
  } catch (e) { failList.push({ file: '(전체)', msg: explain(e) }); }
  busy(false);
  state.selected = null;
  await scan({ quiet: true, noOrganize: true });
  let html = `<p class="res-ok">처리 완료 <b>${okList.length}</b>건</p><ul class="flist">${okList.map(o => `<li><b>${esc(o.title)}</b><br><span class="muted">${esc(o.folder)}${o.files.length ? ' · ' + esc(o.files.map(f => f.kind + ' ' + f.to).join(', ')) : ''}</span></li>`).join('')}</ul>`;
  if (failList.length) html += `<h4 class="res-err">처리하지 못한 공문 ${failList.length}건</h4><ul class="flist">${failList.map(f => `<li><b>${esc(f.file)}</b><br>${esc(f.msg)}</li>`).join('')}</ul><p>실패한 공문은 완료 체크가 그대로 남아 있습니다. 원인을 해결한 뒤 다시 [처리 완료]를 누르세요.</p>`;
  await info('처리 완료 결과', html);
}
async function restore(d) {
  if (!d || d.loc !== 'done') return;
  const isFolder = !!d.dirName;
  const ok = await modal('되돌리기', `<p><b>${esc(isFolder ? d.dirName : d.nm)}</b><br>이 ${isFolder ? '공문 폴더' : '공문'}를 <b>${esc(state.root.name)}</b> 폴더로 되돌립니다. 완료 체크는 해제됩니다.${isFolder ? '<br><span class="muted">폴더 안의 시행공문·성적서도 함께 옮겨집니다.</span>' : ''}</p>`, '되돌리기');
  if (!ok) return;
  busy(true, '되돌리는 중…');
  try {
    const doneDir = await getDoneDir(false);
    const to = isFolder ? await moveDir(doneDir, d.dirName, state.root) : await moveFile(doneDir, d.name, state.root);
    delete state.status.checked[d.key];
    state.status.history.unshift({ at: nowIso(), action: '되돌리기', key: d.key, files: [{ from: d.dirName || d.nm, to }] });
    addLog(d.key, `되돌리기 — ${to}`, '', true);
    await writeStatus(); await writeNotes();
    toast(`되돌렸습니다: ${to}`);
  } catch (e) { toast('되돌리지 못했습니다: ' + explain(e), 'err'); }
  busy(false); state.selected = null;
  await scan({ quiet: true, noOrganize: true });
}
// 짝을 찾지 못한 파일을 이 공문 폴더로
async function adopt(d, t, i) {
  const um = unmatchedInbox();
  const f = t === 'att' ? um.attach[i] : t === 'rep' ? (um.replies[i] || {}).f : (um.reports[i] || {}).f;
  if (!f) return;
  try {
    let dir = d.dir;
    if (!d.organized) { const res = await organizeOne({ f: d.f, p: { result: d.base } }, d.dir, d.C.attach.map(x => x), []); dir = res.dir; }
    const to = await moveFile(f.dir, f.name, dir);
    state.status.history.unshift({ at: nowIso(), action: '파일연결', key: d.key, files: [{ from: f.nm, to }] });
    addLog(d.key, `파일 연결: ${to}`, '', true);
    await writeStatus();
    toast(`옮겼습니다: ${to}`);
  } catch (e) { toast('옮기지 못했습니다: ' + explain(e), 'err'); }
  state.selected = null; await scan({ quiet: true, noOrganize: true });
  const nd = state.docs.find(x => x.key === d.key); if (nd) { state.selected = nd.id; render(); }
}
async function organizeSelected(d) {
  try {
    const res = await organizeOne({ f: d.f, p: { result: d.base } }, d.dir, d.C.attach.map(x => x), []);
    await writeStatus(); toast(`폴더를 만들었습니다: ${res.name}`);
  } catch (e) { toast('폴더를 만들지 못했습니다: ' + explain(e), 'err'); }
  await scan({ quiet: true, noOrganize: true });
  const nd = state.docs.find(x => x.key === d.key); if (nd) { state.selected = nd.id; render(); }
}
function showInbox() {
  const um = unmatchedInbox();
  const li = (f, extra) => `<li>${esc(f.path ? f.path + '/' : '')}<b>${esc(f.nm)}</b>${extra ? ` <span class="muted">— ${esc(extra)}</span>` : ''}</li>`;
  info('짝을 찾지 못한 파일', `
    <p class="muted">공문 폴더에 있지만 어느 의뢰공문과도 짝지어지지 않은 파일입니다. 해당 의뢰공문이 아직 없거나, 공문번호·시료명이 다를 수 있습니다. 의뢰공문 상세 화면의 [첨부 파일] 칸에서 직접 넣을 수 있습니다.</p>
    <h4>시행공문 ${um.replies.length}</h4><ul class="flist">${um.replies.map(x => li(x.f, `관련 ${x.info.관련기관} ${x.info.관련공문번호}`)).join('') || '<li class="muted">없음</li>'}</ul>
    <h4>시험성적서 ${um.reports.length}</h4><ul class="flist">${um.reports.map(x => li(x.f, `공문번호 ${x.rep.공문번호} · ${x.rep.의뢰기관} · 시료 ${x.rep.samples.map(s => s.시료명).slice(0, 4).join(', ')}${x.rep.samples.length > 4 ? ' 외' : ''}`)).join('') || '<li class="muted">없음</li>'}</ul>
    <h4>첨부·기타 ${um.attach.length}</h4><ul class="flist">${um.attach.map(f => li(f)).join('') || '<li class="muted">없음</li>'}</ul>`, { width: 'min(820px, calc(100vw - 32px))' });
}
