/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/08_목록표_그리기.js] 목록 표 그리기
   하는 일 : 칸 값(시료접수일·처리기한·진행·결과·메모), 표 그리기, 알림줄, 통계
   주요 이름: progressHtml, cellOf, render, renderBanner, renderStats, unmatchedInbox
   이럴 때 고침: 표에 보이는 글자·색, 통계 줄
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 칸 값 ───── */
function progressHtml(d) {
  if (!d.match || !d.result) return { html: '', text: '' };
  const m = d.match, nrep = m.replies.length;
  const a = m.replyOk ? `<span class="pill ok" title="${esc(m.replies.map(x => x.f.nm).join('\n'))}">시행 ✔</span>` : nrep ? `<span class="pill part" title="공문번호는 같지만 기관명이 다릅니다">시행 △</span>` : `<span class="pill none">시행 —</span>`;
  const b = m.reportState === 'full' ? `<span class="pill ok" title="${esc(m.reports.map(x => x.f.nm).join('\n'))}">성적서 ${m.got}/${m.total}</span>`
    : m.reportState === 'partial' ? `<span class="pill part" title="${esc(['일부만 일치', ...m.reports.map(x => x.f.nm), m.extra.length ? '공문에 없는 시료: ' + m.extra.join(', ') : '', m.orgBad ? '의뢰기관 다름' : ''].filter(Boolean).join('\n'))}">성적서 ${m.got}/${m.total}${m.extra.length ? '+' + m.extra.length : ''}</span>` : `<span class="pill none">성적서 —</span>`;
  const text = `${m.replyOk ? '시행공문 일치' : nrep ? '시행공문 일부' : '시행공문 없음'} · ${m.reportState === 'none' ? '성적서 없음' : `성적서 ${m.got}/${m.total}`}`;
  return { html: a + ' ' + b, text };
}
function resultText(r) {
  if (!r._rep) return '';
  const s = r._rep.s;
  return (s.판정 ? s.판정 + ' — ' : '') + s.결과.map(x => `${x.항목명 || x.항목} ${x.결과}`).join(', ');
}
function cellOf(d, r, c, finished) {
  const k = c.k;
  if (k === '시료접수일') {
    if (!d.result) return { html: '' };
    const rc = caseRecv(d);
    const btn = d.loc === 'root' ? ` data-act="recv" title="눌러서 시료접수일 입력 (달력)"` : '';
    if (!rc) return { html: `<span class="recv-cell empty"${btn}>입력</span>`, text: '' };
    return { html: `<span class="recv-cell${rc.est ? ' est' : ''}"${btn}>${esc(fmtDay(rc.date))}${rc.est ? '<small> 추정</small>' : ''}${rc.before13 ? '<small> 13시前</small>' : ''}</span>`, text: rc.date + (rc.est ? ' (공문 접수일 기준)' : '') };
  }
  if (k === '처리기한') {
    const sd = rowDue(d, r); if (!sd) return { html: '' };
    if (!sd.due) return { html: `<span class="muted" title="처리기간이 정해지지 않은 항목: ${esc(sd.unknown.join(', '))}">기간 미설정</span>`, text: '' };
    const cls = dueClass(sd, finished);
    const tip = `${sd.item} ${sd.days}일 (${sd.why})${sd.unknown.length ? '\n기간 미설정 항목: ' + sd.unknown.join(', ') : ''}${sd.flagged.length ? '\n준용 항목(확인 필요): ' + sd.flagged.join(', ') : ''}${sd.est ? '\n시료접수일 미입력 — 공문 접수일 기준' : ''}`;
    return { html: `<span class="due ${cls}" title="${esc(tip)}">${esc(fmtDay(sd.due))} <b>${finished ? '완료' : esc(remText(sd.rem))}</b>${sd.unknown.length || sd.flagged.length ? '<sup>*</sup>' : ''}</span>`, text: sd.due, cls: cls ? 'td-' + cls : '' };
  }
  if (k === '진행') { const p = progressHtml(d); return { html: p.html, text: p.text }; }
  if (k === '결과') { const t = resultText(r); const bad = r._rep && /부적합/.test(r._rep.s.판정); return { html: t ? `<span class="${bad ? 'res-bad' : ''}">${esc(t)}</span>` : '', text: t }; }
  if (k === '메모') { const n = peekNotes(d.key); const cnt = (n.log || []).filter(x => !x.auto).length; const t = (n.memo || '').split('\n')[0]; return { html: (cnt ? `<span class="badge">${cnt}</span> ` : '') + esc(t), text: n.memo || '' }; }
  if (k === '폴더') return { html: esc(d.dirName || (d.loc === 'root' ? '(정리 전)' : '')), text: d.dirName || '' };
  const v = r[k] == null ? '' : r[k];
  return { text: v, html: esc(c.fmt ? c.fmt(v) : v) };
}

/* ───── 그리기 ───── */
function activeCols() { return COLS.filter(c => state.cols.includes(c.k)); }
function render() {
  $('#toolbar').hidden = false; $('#bottombar').hidden = false;
  renderOrgOptions(); renderBanner();
  $('#fState').querySelector('option[value=done]').textContent = `성적처리완료 폴더 (${state.doneCount})`;
  const cols = activeCols(), list = visibleDocs(), isDone = state.filter.state === 'done';
  const grid = $('#grid'), empty = $('#emptyBox');
  if (!list.length) {
    grid.hidden = true; empty.hidden = false;
    const none = (isDone ? state.doneDocs : state.docs).length === 0;
    empty.innerHTML = none
      ? (isDone ? '<h2>성적처리완료 폴더가 비어 있습니다</h2>' : `<h2>공문 폴더에 의뢰 공문(ODT)이 없습니다</h2><p>검사의뢰 공문(ODT)을 <b>${esc(state.root.name)}</b> 폴더에 저장한 뒤 <b>새로고침</b>을 누르세요. 이 창으로 돌아오면 자동으로 다시 읽습니다.</p>`)
      : '<h2>조건에 맞는 공문이 없습니다</h2><p>검색어나 필터를 바꿔 보세요.</p>';
  } else {
    empty.hidden = true; grid.hidden = false;
    const s = state.sort;
    let th = `<tr><th class="c-chk">${isDone ? '되돌리기' : `<input type="checkbox" id="chkAll" title="보이는 공문 모두 완료 체크">`}</th>`;
    for (const c of cols) th += `<th data-k="${esc(c.k)}" class="${s.key === c.k ? 'sorted' : ''}" data-dir="${s.dir > 0 ? '▲' : '▼'}">${esc(c.label || c.k)}</th>`;
    th += `<th data-k="확인필요" class="${s.key === '확인필요' ? 'sorted' : ''}" data-dir="${s.dir > 0 ? '▲' : '▼'}">확인필요</th></tr>`;
    grid.tHead.innerHTML = th;
    const parts = [];
    for (const d of list) {
      const rows = docRows(d), n = rows.length, chk = isChecked(d), finished = isDone;
      const dup = d.result && d.result.duplicate;
      const cls = [chk && 'is-checked', isDone && 'is-done', dup && 'is-dup', d.error && 'is-err', state.selected === d.id && 'is-sel', readyToFinish(d) && !chk && !isDone && 'is-ready'].filter(Boolean).join(' ');
      rows.forEach((r, i) => {
        let tr = `<tr data-id="${esc(d.id)}" class="${cls}${i === 0 ? ' grp-first' : ''}">`;
        if (i === 0) tr += `<td class="c-chk" rowspan="${n}">${isDone ? `<button class="btn small" data-act="restore" title="공문 폴더로 되돌리기">되돌리기</button>` : `<input type="checkbox" data-act="check" ${chk ? 'checked' : ''} title="이 공문 완료 체크">`}</td>`;
        if (d.error) { tr += `<td class="c-warn err wrap" colspan="${cols.length + 1}">⚠ 읽기 실패 — <b>${esc(d.nm)}</b> : ${esc(d.error)}</td></tr>`; parts.push(tr); return; }
        for (const c of cols) {
          if (c.doc && i > 0) continue;
          const v = cellOf(d, r, c, finished);
          const span = c.doc && n > 1 ? ` rowspan="${n}"` : '';
          let extra = (c.wrap ? 'wrap' : '') + (v.cls ? ' ' + v.cls : '');
          let html = v.html;
          if (c.k === '시료채취일' && r.시료채취일 === '채취일자 확인 필요') extra += ' cell-warn';
          if (c.k === '시료채취일' && r.채취일출처 === '본문') html += '<span class="badge" title="공문 본문 문장에서 찾은 날짜">본문</span>';
          if (c.k === '시료번호' && r.시료출처) html += `<span class="badge" title="시료 목록 출처">${esc(r.시료출처 === '직접 입력' ? '직접' : '첨부')}</span>`;
          if (c.k === '기준' && /기준표/.test(r.기준출처 || '')) html += '<span class="badge ok" title="기준표에서 찾은 값 포함">기준표</span>';
          tr += `<td class="${extra.trim()}"${span} title="${esc(v.text)}">${html}</td>`;
        }
        const w = r.확인필요 || '';
        tr += `<td class="c-warn${d.error ? ' err' : ''}" title="${esc(w)}">${w ? '⚠ ' + esc(w) : ''}</td></tr>`;
        parts.push(tr);
      });
    }
    grid.tBodies[0].innerHTML = parts.join('');
    const all = $('#chkAll');
    if (all) { const vis = list.filter(d => d.loc === 'root'); all.checked = vis.length > 0 && vis.every(isChecked); all.indeterminate = !all.checked && vis.some(isChecked); }
  }
  renderStats(list);
  renderDetail();
}
function renderOrgOptions() {
  const sel = $('#fOrg'), cur = state.filter.org;
  const orgs = [...new Set([...state.docs, ...state.doneDocs].map(d => (docRows(d)[0] || {}).의뢰기관).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko'));
  sel.innerHTML = '<option value="">기관 전체</option>' + orgs.map(o => `<option ${o === cur ? 'selected' : ''}>${esc(o)}</option>`).join('');
}
function unmatchedInbox() {
  const ib = state.inbox;
  return { replies: ib.replies.filter(x => !x.usedBy || !x.usedBy.size), reports: ib.reports.filter(x => !x.usedBy || !x.usedBy.size), attach: ib.attach.filter(f => !state.docs.some(d => !d.organized && d.C.attach.includes(f))) };
}
function renderBanner() {
  const b = $('#banner'), ib = state.inbox;
  const loose = ib.requests.length + ib.groups.reduce((a, g) => a + g.C.requests.length, 0);
  const um = unmatchedInbox(), bits = [];
  if (loose && state.filter.state !== 'done') bits.push(`<span>공문별 폴더로 정리되지 않은 공문 <b>${loose}</b>건</span><button class="btn small primary" data-act="organize">공문별 폴더로 정리</button>`);
  if (um.replies.length || um.reports.length || um.attach.length) bits.push(`<span class="muted">짝을 찾지 못한 파일: 시행공문 ${um.replies.length} · 성적서 ${um.reports.length} · 첨부 ${um.attach.length}</span><button class="btn small" data-act="inbox">목록 보기</button>`);
  if (!window.pdfjsLib) bits.push('<span class="res-err">PDF 읽기 기능을 불러오지 못해 성적서를 대조할 수 없습니다.</span>');
  b.hidden = !bits.length; b.innerHTML = bits.join('<span class="sep"></span>');
}
function renderStats(list) {
  const docs = state.docs, live = docs.filter(d => !(d.result && d.result.duplicate));
  const samples = live.reduce((a, d) => a + (d.result ? d.result.rows.filter(r => r.시료번호).length : 0), 0);
  const warn = docs.filter(docWarn).length, err = docs.filter(d => d.error).length, dup = docs.length - live.length;
  let over = 0, imm = 0;
  for (const d of live) { if (isChecked(d)) continue; const m = docDueMin(d); if (m && m.rem) { if (m.rem.overdue) over++; else if (m.rem.days <= state.settings.imminent) imm++; } }
  const ready = live.filter(d => readyToFinish(d)).length;
  const groups = checkedGroups();
  $('#btnDone').textContent = `완료 체크한 공문 처리 완료 (${groups.length})`;
  $('#btnDone').disabled = !groups.length || state.filter.state === 'done';
  const bits = [`공문 <b>${live.length}</b>건`, `시료 <b>${samples}</b>개`];
  if (over) bits.push(`<span class="res-err">기한 초과 <b>${over}</b></span>`);
  if (imm) bits.push(`<span class="res-err">임박 <b>${imm}</b></span>`);
  bits.push(`성적서 도착 <b>${ready}</b>`, `확인필요 <b>${warn}</b>`, `완료체크 <b>${groups.length}</b>`);
  if (dup) bits.push(`중복 ${dup}`); if (err) bits.push(`읽기실패 ${err}`);
  bits.push(state.stdFile ? `<span title="기준표에서 채운 항목 수">기준표 ${state.stdTable.length}행 · ${state.stdFilled}항목</span>` : '기준표 없음');
  if (list.length !== (state.filter.state === 'done' ? state.doneDocs : docs).length) bits.push(`표시 ${list.length}건`);
  $('#stats').innerHTML = bits.join(' · ');
}
