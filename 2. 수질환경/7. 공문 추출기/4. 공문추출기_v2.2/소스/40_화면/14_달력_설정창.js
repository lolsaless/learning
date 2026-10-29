/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/14_달력_설정창.js] 달력·설정 창
   하는 일 : 날짜 선택 달력, 시료접수일 입력, 휴일·처리기간·기타 설정 창
   주요 이름: calendarHtml, openDatePicker, pickRecv, setRecv, showSettings
   이럴 때 고침: 달력·설정 창 항목
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 달력 (날짜 선택 · 휴일 지정) ───── */
function calendarHtml(y, m, opt = {}) {
  const first = new Date(y, m, 1, 12), start = E2.addDays(first, -first.getDay()), H = state.settings.holidays, t = today();
  let h = `<div class="cal"><div class="cal-head"><button class="btn small" data-cal="prev">◀</button><b>${y}년 ${m + 1}월</b><button class="btn small" data-cal="next">▶</button></div><div class="cal-grid">${WEEK.map((w, i) => `<div class="cal-w ${i === 0 ? 'sun' : i === 6 ? 'sat' : ''}">${w}</div>`).join('')}`;
  for (let i = 0; i < 42; i++) {
    const dt = E2.addDays(start, i), ds = E2.ymd(dt), wd = dt.getDay();
    const cls = ['cal-d', dt.getMonth() !== m && 'other', wd === 0 && 'sun', wd === 6 && 'sat',
      state.hol.has(ds) && (H.custom[ds] != null ? 'cust' : 'hol'), state.work.has(ds) && 'work', ds === t && 'today', opt.sel === ds && 'sel'].filter(Boolean).join(' ');
    const nm = state.work.has(ds) ? '근무일로 지정' : state.holName.get(ds) || '';
    h += `<button class="${cls}" data-day="${ds}" title="${esc(nm)}">${dt.getDate()}${nm && opt.names ? `<small>${esc(nm.replace(/대체공휴일/, '대체'))}</small>` : ''}</button>`;
  }
  return h + '</div></div>';
}
let dpState = null;
function openDatePicker(anchor, value, onPick) {
  const pop = $('#datePop'), base = value ? E2.toDate(value) : new Date();
  dpState = { y: base.getFullYear(), m: base.getMonth(), value, onPick };
  const draw = () => {
    pop.innerHTML = calendarHtml(dpState.y, dpState.m, { sel: dpState.value }) + `<div class="cal-foot"><button class="btn small" data-cal="today">오늘</button><span class="spacer"></span><span class="legend"><i class="lg hol"></i>공휴일 <i class="lg cust"></i>지정 휴일</span><button class="btn small" data-cal="close">닫기</button></div>`;
  };
  draw();
  const r = anchor.getBoundingClientRect();
  pop.hidden = false;
  pop.style.left = Math.max(8, Math.min(window.innerWidth - pop.offsetWidth - 8, r.left)) + 'px';
  pop.style.top = (r.bottom + pop.offsetHeight + 8 > window.innerHeight ? Math.max(8, r.top - pop.offsetHeight - 4) : r.bottom + 4) + 'px';
  pop.onclick = e => {
    e.stopPropagation();
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.cal === 'prev') { if (--dpState.m < 0) { dpState.m = 11; dpState.y--; } draw(); }
    else if (b.dataset.cal === 'next') { if (++dpState.m > 11) { dpState.m = 0; dpState.y++; } draw(); }
    else if (b.dataset.cal === 'today') { pop.hidden = true; onPick(today()); }
    else if (b.dataset.cal === 'close') pop.hidden = true;
    else if (b.dataset.day) { pop.hidden = true; onPick(b.dataset.day); }
  };
}
function pickRecv(d, anchor) {
  const rc = caseRecv(d);
  openDatePicker(anchor, rc ? rc.date : today(), ds => setRecv(d, ds));
}
function setRecv(d, ds) {
  const n = notesOf(d.key), old = n.recv;
  n.recv = ds;
  addLog(d.key, `시료접수일 ${old ? `변경 ${old} → ` : '입력 '}${ds}`, '', true);
  saveNotesSoon(); render();
}

/* ───── 설정 (휴일 · 처리기간 · 기타) ───── */
async function showSettings(tab) {
  let cy = new Date().getFullYear(), cm = new Date().getMonth(), cur = tab || 'hol';
  const S = state.settings, H = S.holidays;
  const itemsInUse = [...new Set(state.docs.flatMap(d => d.result ? d.result.rows.flatMap(r => (r._items || []).map(i => i.name)) : []))];
  const draw = () => {
    const body = $('#modalBody');
    let h = `<div class="tabs">${[['hol', '휴일 달력'], ['std', '처리기간'], ['etc', '기타']].map(([k, l]) => `<button class="tab${cur === k ? ' on' : ''}" data-tab="${k}">${l}</button>`).join('')}</div>`;
    if (cur === 'hol') {
      const monthHol = [...state.holName.entries()].filter(([d0]) => d0.startsWith(`${cy}-${String(cm + 1).padStart(2, '0')}`) && state.hol.has(d0)).sort();
      const fetched = Object.entries(H.fetched || {}).map(([y, f]) => `${y}년: ${f.at ? `인터넷 ${f.n}일 (${f.at.slice(0, 10)})` : `내장 목록 사용 — ${esc(f.error || '')}`}`).join('<br>');
      h += `<div class="hol-wrap">${calendarHtml(cy, cm, { names: true })}<div class="hol-side">
        <p class="small">날짜를 누르면 바뀝니다.<br>· 평일 → <span class="lg-t cust">지정 휴일</span> (기관 휴무일 등)<br>· 공휴일·토·일 → <span class="lg-t work">근무일로 지정</span><br>· 다시 누르면 원래대로</p>
        <h4>${cm + 1}월 휴일</h4><ul class="flist2 small">${monthHol.map(([d0, n0]) => `<li>${esc(fmtDay(d0))} ${esc(n0)}${H.custom[d0] != null ? ' <span class="muted">(지정)</span>' : ''}</li>`).join('') || '<li class="muted">없음</li>'}</ul>
        ${[...state.work].filter(d0 => d0.startsWith(`${cy}-${String(cm + 1).padStart(2, '0')}`)).map(d0 => `<div class="small">근무일 지정: ${esc(fmtDay(d0))}</div>`).join('')}
        <h4>공휴일 자료</h4><p class="small">${fetched || '아직 가져오지 않음 (내장 2026·2027년 목록 사용)'}</p>
        <button class="btn small" data-act="hol-fetch">인터넷에서 공휴일 다시 가져오기</button><div id="holMsg" class="small muted"></div></div></div>`;
    } else if (cur === 'std') {
      const names = [...new Set([...E2.STD_DAYS.map(x => x[0]), ...itemsInUse, ...Object.keys(S.stdDays)])];
      h += `<div class="basis"><b>시료 처리기한 기준</b> — 한 시료에 검사항목이 여러 개일 때
        <label class="chk"><input type="radio" name="basis" value="max" ${S.dueBasis !== 'min' ? 'checked' : ''}> 가장 <b>긴</b> 항목 기준 (예: BOD·SS → BOD 9일)</label>
        <label class="chk"><input type="radio" name="basis" value="min" ${S.dueBasis === 'min' ? 'checked' : ''}> 가장 <b>짧은</b> 항목 기준 (예: BOD·SS → SS 5일)</label></div>
        <p class="small muted">[별표 2] 표준처리기간(시험검사기간 + 행정처리기간). 별표에 없는 항목은 비고 5에 따라 유사 항목을 준용하며, 기관 기준에 맞게 '사용자 설정'에 일수를 넣으면 그 값을 씁니다.</p>
        <table class="mini"><tr><th>항목</th><th>기본(일)</th><th>근거</th><th>사용자 설정(일)</th></tr>${names.map(k => { const def = E2.STD_DAYS.find(x => x[0] === k); return `<tr${itemsInUse.includes(k) ? ' class="inuse"' : ''}><td>${esc(k)}</td><td>${def && def[1] != null ? def[1] : '<span class="res-err">없음</span>'}</td><td class="small">${esc(def ? def[2] : '별표2에 없음 — 설정 필요')}</td><td><input type="number" min="1" max="99" class="num" data-std="${esc(k)}" value="${S.stdDays[k] != null ? esc(S.stdDays[k]) : ''}" placeholder="${def && def[1] != null ? def[1] : ''}"></td></tr>`; }).join('')}</table>
        <p class="small muted">굵은 행: 현재 공문에 있는 항목</p>`;
    } else {
      h += `<div class="opts">
        <label class="chk"><input type="checkbox" data-opt="organize.auto" ${S.organize.auto ? 'checked' : ''}> 새 의뢰공문을 공문별 폴더(의뢰기관_제목_시행번호)로 자동 정리</label>
        <label class="chk"><input type="checkbox" data-opt="nestDone" ${S.nestDone ? 'checked' : ''}> 처리 완료 시 공문 폴더를 ${DONE_DIR} 폴더로 옮기기</label>
        <label class="chk"><input type="checkbox" data-opt="watermark" ${S.watermark ? 'checked' : ''}> 의뢰공문 우측 상단에 시료접수일 워터마크 표시 (화면·인쇄·이력 문서, 원본 파일은 그대로)</label>
        <div class="row">처리기한 <b>빨간색</b>: 남은 근무일 <input type="number" min="0" max="10" class="num" data-opt="imminent" value="${S.imminent}"> 일 이하 (기한 초과는 빨간 바탕)</div>
        <div class="row">처리기한 <b>주황색</b>: 남은 근무일 <input type="number" min="0" max="20" class="num" data-opt="soon" value="${S.soon}"> 일 이하</div>
        <p class="small muted">설정은 공문 폴더의 ${SETTINGS_FILE}에 저장되어 같은 폴더를 쓰는 다른 PC에도 적용됩니다.</p></div>`;
    }
    body.innerHTML = h;
  };
  const onClick = async e => {
    const t = e.target.closest('[data-tab],[data-cal],[data-day],[data-act]'); if (!t) return;
    if (t.dataset.tab) { cur = t.dataset.tab; draw(); return; }
    if (t.dataset.cal === 'prev') { if (--cm < 0) { cm = 11; cy--; } draw(); return; }
    if (t.dataset.cal === 'next') { if (++cm > 11) { cm = 0; cy++; } draw(); return; }
    if (t.dataset.day) {
      const ds = t.dataset.day, wd = E2.toDate(ds).getDay();
      if (H.custom[ds] != null) delete H.custom[ds];
      else if (H.work[ds]) delete H.work[ds];
      else if (state.hol.has(ds) || wd === 0 || wd === 6) H.work[ds] = true;
      else H.custom[ds] = '지정 휴일';
      applySettings(); saveSettingsSoon(); draw(); return;
    }
    if (t.dataset.act === 'hol-fetch') { $('#holMsg').textContent = '가져오는 중…'; const r = await refreshHolidays(true); draw(); const m = $('#holMsg'); if (m) m.textContent = r.join(' · '); }
  };
  const onChange = e => {
    const t = e.target;
    if (t.name === 'basis') { S.dueBasis = t.value; }
    else if (t.dataset.std) { const v = t.value.trim(); if (v === '' || !(+v > 0)) delete S.stdDays[t.dataset.std]; else S.stdDays[t.dataset.std] = +v; }
    else if (t.dataset.opt) {
      const v = t.type === 'checkbox' ? t.checked : Math.max(0, +t.value || 0);
      if (t.dataset.opt === 'organize.auto') { S.organize.auto = v; S.organize.asked = true; } else S[t.dataset.opt] = v;
    } else return;
    applySettings(); saveSettingsSoon();
  };
  await info('휴일 · 처리기간 설정', '', {
    width: 'min(900px, calc(100vw - 32px))',
    onOpen: body => { draw(); body.addEventListener('click', onClick); body.addEventListener('change', onChange); },
  });
  const body = $('#modalBody'); body.removeEventListener('click', onClick); body.removeEventListener('change', onChange);
  await writeSettings(); render();
}
