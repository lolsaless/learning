/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/18_이벤트_연결.js] 버튼·클릭 연결
   하는 일 : 버튼·표·상세 패널의 클릭·입력을 기능에 연결
   주요 이름: bindUi
   이럴 때 고침: 새 버튼을 기능에 연결할 때
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 이벤트 ───── */
function bindUi() {
  $('#btnPick').onclick = pickFolder;
  $('#btnRefresh').onclick = () => scan();
  $('#btnHelp').onclick = showHelp;
  $('#btnDone').onclick = processChecked;
  $('#btnExcel').onclick = exportExcel;
  $('#btnStd').onclick = makeStdTemplate;
  $('#btnSettings').onclick = () => showSettings();
  $('#fWm').onchange = e => { state.settings.watermark = e.target.checked; saveSettingsSoon(); renderDetail(); };
  let qt;
  $('#fSearch').oninput = e => { clearTimeout(qt); qt = setTimeout(() => { state.filter.q = e.target.value; render(); }, 150); };
  $('#fOrg').onchange = e => { state.filter.org = e.target.value; render(); };
  $('#fState').onchange = async e => { state.filter.state = e.target.value; state.selected = null; if (e.target.value === 'done') await scan({ noOrganize: true }); else render(); };
  $('#fWarn').onchange = e => { state.filter.warn = e.target.checked; render(); };
  $('#btnCols').onclick = e => { e.stopPropagation(); const m = $('#colMenu'); if (m.hidden) { renderColMenu(); m.hidden = false; } else m.hidden = true; };
  $('#colMenu').addEventListener('click', e => e.stopPropagation());
  $('#colMenu').addEventListener('change', e => {
    if (e.target.type !== 'checkbox') return;
    const k = e.target.value;
    state.cols = e.target.checked ? COLS.map(c => c.k).filter(x => x === k || state.cols.includes(x)) : state.cols.filter(x => x !== k);
    saveCols(); render();
  });
  $('#colMenu').addEventListener('click', e => {
    const a = e.target.dataset.act;
    if (a === 'cols-default') state.cols = COLS.filter(c => c.def).map(c => c.k);
    else if (a === 'cols-all') state.cols = COLS.map(c => c.k);
    else return;
    saveCols(); renderColMenu(); render();
  });
  document.addEventListener('click', e => { $('#colMenu').hidden = true; if (!e.target.closest('#datePop')) $('#datePop').hidden = true; });
  $('#banner').addEventListener('click', e => {
    const a = e.target.dataset.act;
    if (a === 'organize') organizeAll(false); else if (a === 'inbox') showInbox();
  });

  const grid = $('#grid');
  grid.tHead.addEventListener('click', e => {
    const th = e.target.closest('th[data-k]'); if (!th) return;
    const k = th.dataset.k;
    state.sort = state.sort.key === k ? { key: k, dir: -state.sort.dir } : { key: k, dir: k === '접수일' ? -1 : 1 };
    render();
  });
  grid.tHead.addEventListener('change', e => {
    if (e.target.id !== 'chkAll') return;
    const on = e.target.checked;
    for (const d of visibleDocs()) if (d.loc === 'root') setChecked(d, on);
    render();
  });
  grid.tBodies[0].addEventListener('click', e => {
    const tr = e.target.closest('tr[data-id]'); if (!tr) return;
    const d = findDoc(tr.dataset.id); if (!d) return;
    const act = e.target.closest('[data-act]') && e.target.closest('[data-act]').dataset.act;
    if (act === 'check') { setChecked(d, e.target.checked); render(); return; }
    if (act === 'restore') { restore(d); return; }
    if (act === 'recv') { e.stopPropagation(); pickRecv(d, e.target.closest('[data-act]')); return; }
    if (e.target.closest('td.c-chk')) return;
    state.selected = state.selected === d.id ? null : d.id;
    render();
  });
  const det = $('#detail');
  det.addEventListener('click', e => {
    const el = e.target.closest('[data-act]'); if (!el) return;
    const act = el.dataset.act;
    const d = findDoc(det.dataset.id);
    if (act === 'close') { state.selected = null; render(); }
    else if (act.startsWith('mode-')) { state.detailMode = act.slice(5); savePref('odt-detail-mode', state.detailMode); renderDetail(); }
    else if (!d) return;
    else if (act.startsWith('view:')) { state.viewer = act.slice(5); if (state.detailMode === 'ext') { state.detailMode = 'side'; savePref('odt-detail-mode', 'side'); } renderDetail(); }
    else if (act === 'pv-big') openPreviewWindow(d);
    else if (act === 'pv-download') { const v = viewerList(d).find(x => x.k === state.viewer) || viewerList(d)[0]; downloadFile(v.f); }
    else if (act === 'check-toggle') { setChecked(d, !isChecked(d)); render(); }
    else if (act === 'restore') restore(d);
    else if (act === 'recv') { e.stopPropagation(); pickRecv(d, el); }
    else if (act === 'recv-doc') { const rc = caseRecv(d); if (rc) setRecv(d, rc.date); }
    else if (act === 'settings') showSettings('std');
    else if (act === 'manual') manualInput(d);
    else if (act === 'organize-one') organizeSelected(d);
    else if (act.startsWith('adopt:')) { const [, t, i] = act.split(':'); adopt(d, t, +i); }
    else if (act.startsWith('hist:')) makeHistory(d, act.slice(5));
    else if (act === 'log-add') {
      const text = $('#logText').value.trim(); if (!text) { $('#logText').focus(); return; }
      const n = notesOf(d.key); n.log = n.log || [];
      n.log.push({ id: uid(), at: nowIso(), date: $('#logDate').value || today(), sample: $('#logSample').value, text, auto: false });
      saveNotesSoon(); render();
    } else if (act.startsWith('log-del:')) {
      const id = act.slice(8), n = notesOf(d.key); n.log = (n.log || []).filter(x => x.id !== id); saveNotesSoon(); render();
    }
  });
  det.addEventListener('change', e => {
    const act = e.target.dataset.act, d = findDoc(det.dataset.id); if (!d) return;
    if (act === 'before13') { const n = notesOf(d.key); n.before13 = e.target.checked; addLog(d.key, `13시 이전 접수 ${e.target.checked ? '지정' : '해제'}`, '', true); saveNotesSoon(); render(); }
    else if (act === 'wm') { state.settings.watermark = e.target.checked; $('#fWm').checked = e.target.checked; saveSettingsSoon(); renderDetail(); }
  });
  det.addEventListener('input', e => {
    if (e.target.dataset.act !== 'memo') return;
    const d = findDoc(det.dataset.id); if (!d) return;
    notesOf(d.key).memo = e.target.value; saveNotesSoon();
  });
  det.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.id === 'logText') { e.preventDefault(); det.querySelector('[data-act=log-add]').click(); } });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('#modal').hidden && $('#datePop').hidden && state.selected) { state.selected = null; render(); } });
  window.addEventListener('focus', () => { if (state.root && !state.busy && $('#modal').hidden && Date.now() - state.lastScan > 2000) scan({ quiet: true }); });
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(fitPreview, 150); });
  window.addEventListener('beforeunload', () => { if (saveTimer) writeStatus(); if (notesTimer) writeNotes(); if (setTimer) writeSettings(); });
}
