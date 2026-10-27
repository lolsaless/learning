/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/09_상세_추출결과.js] 상세 패널: 추출결과·처리기한·진행·첨부·메모
   하는 일 : 오른쪽 패널의 구역들과 패널 틀
   주요 이름: dueSection, progressSection, attachSection, notesSection, extractedHtml, viewerList, renderDetail
   이럴 때 고침: 상세 패널 내용·순서
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 상세 패널 ───── */
function highlightDates(p) {
  return esc(p).replace(/((?:\d{4}|&#39;\d{2}|'\d{2})\s*[.\-\/]\s*\d{1,2}\s*[.\-\/]\s*\d{1,2}\.?(?:\s*\([월화수목금토일]\))?)/g, '<mark>$1</mark>');
}
const sec = (title, body, extra) => `<section class="dsec"><h4>${title}${extra ? `<span class="h4-act">${extra}</span>` : ''}</h4>${body}</section>`;
function dueSection(d) {
  const rc = caseRecv(d), n = peekNotes(d.key), live = d.loc === 'root';
  let h = `<div class="recv-row"><span class="lbl">시료접수일</span>`;
  h += live ? `<button class="btn small date-btn" data-act="recv">${rc ? esc(fmtFull(rc.date)) : '날짜 선택'} ▾</button>` : `<b>${rc ? esc(fmtFull(rc.date)) : '-'}</b>`;
  if (rc && rc.est) h += `<span class="muted small">공문 접수일 기준(추정)</span>${live ? ' <button class="btn small link" data-act="recv-doc">이 날짜로 확정</button>' : ''}`;
  h += `</div>`;
  if (live) h += `<label class="chk small"><input type="checkbox" data-act="before13" ${n.before13 ? 'checked' : ''}> 13시 이전 접수 (접수일을 처리기간에 포함)</label>`;
  const rows = d.result.rows.filter(r => r.시료번호);
  const trs = rows.map(r => {
    const sd = rowDue(d, r);
    if (!sd) return `<tr><td>${esc(r.시료번호)}</td><td colspan="3" class="muted">-</td></tr>`;
    const cls = dueClass(sd, d.loc !== 'root');
    return `<tr><td>${esc(r.시료번호)}</td><td>${sd.item ? `${esc(sd.item)} ${sd.days}일${sd.flagged.length ? ' <sup title="준용 항목 — 확인 필요">*</sup>' : ''}` : '<span class="muted">미설정</span>'}${sd.unknown.length ? `<div class="muted small">미설정: ${esc(sd.unknown.join(', '))}</div>` : ''}</td><td>${esc(fmtDay(sd.due))}</td><td class="${cls ? 'td-' + cls : ''}">${d.loc !== 'root' ? '완료' : esc(remText(sd.rem))}</td></tr>`;
  }).join('');
  h += `<table class="mini"><tr><th>시료</th><th>기간(결정 항목)</th><th>처리기한</th><th>남은 기간</th></tr>${trs}</table>`;
  h += `<p class="muted small">[별표 2] 표준처리기간 — 토·일·공휴일·지정 휴일 제외, 13시 이후 접수는 접수일 제외. 시료에 항목이 여러 개면 <b>${state.settings.dueBasis === 'min' ? '가장 짧은' : '가장 긴'} 항목</b> 기준(설정에서 변경). 남은 기간은 근무일, 초과 일수는 달력일 기준.</p>`;
  return sec('처리기한', h, `<button class="btn small link" data-act="settings">휴일·처리기간 설정</button>`);
}
function progressSection(d) {
  const m = d.match; let h = '';
  h += `<div class="sub">시행공문</div>`;
  h += m.replies.length ? '<ul class="flist2">' + m.replies.map((x, i) => `<li><span class="pill ${x.score === 1 ? 'ok' : 'part'}">${x.score === 1 ? '일치' : '기관 확인'}</span> ${esc(x.f.nm)} <span class="muted small">(${esc(x.info.관련기관)} ${esc(x.info.관련공문번호)}${x.info.부적합 ? ', 부적합' : ''}${x.inCase ? ', 공문 폴더 안' : ''})</span> <button class="btn small link" data-act="view:rep:${i}">보기</button></li>`).join('') + '</ul>'
    : `<p class="muted small">아직 없습니다. 시행공문(결과 알림 ODT)을 공문 폴더에 넣으면 본문의 '○○과-1234(날짜)호' 번호로 찾아 연결합니다.</p>`;
  h += `<div class="sub">시험성적서</div>`;
  h += m.reports.length ? '<ul class="flist2">' + m.reports.map((x, i) => `<li><span class="pill ${x.m.level === 'full' ? 'ok' : 'part'}">${x.m.matched.length}/${m.total}</span> ${esc(x.f.nm)}${x.m.missing.length && x.m.matched.length ? `<div class="muted small">이 파일에 없는 시료: ${esc(x.m.missing.join(', '))}</div>` : ''}${x.m.extra.length ? `<div class="res-err small">공문에 없는 시료: ${esc(x.m.extra.join(', '))}</div>` : ''}${x.m.orgGood === false ? `<div class="res-err small">의뢰기관 다름: ${esc(x.rep.의뢰기관)}</div>` : ''} <button class="btn small link" data-act="view:pdf:${i}">보기</button></li>`).join('') + '</ul>'
    : `<p class="muted small">아직 없습니다. 성적서 PDF를 공문 폴더에 넣으면 공문번호·시료명으로 찾아 연결합니다.</p>`;
  const rows = d.result.rows.filter(r => r._rep);
  if (rows.length) {
    h += `<div class="sub">결과</div><table class="mini"><tr><th>시료</th><th>접수번호</th><th>결과</th><th>판정</th></tr>` + rows.map(r => {
      const s = r._rep.s;
      return `<tr><td>${esc(r.시료번호)}</td><td>${esc(s.접수번호)}</td><td>${s.결과.map(x => `${esc(x.항목명 || x.항목)} <b>${esc(x.결과)}</b>${x.기준 ? `<span class="muted small">(${esc(x.기준)})</span>` : ''}`).join('<br>')}</td><td class="${/부적합/.test(s.판정) ? 'res-bad' : ''}">${esc(s.판정)}</td></tr>`;
    }).join('') + '</table>';
  }
  const ready = readyToFinish(d);
  return sec('시행공문 · 시험성적서', h, d.loc === 'root' ? (ready ? '<span class="pill ok">완료 가능</span>' : '') : '');
}
function attachSection(d) {
  let h = '';
  const atts = d.C.attach;
  h += atts.length ? '<ul class="flist2">' + atts.map((f, i) => `<li>${esc(f.nm)} <button class="btn small link" data-act="view:att:${i}">보기</button></li>`).join('') + '</ul>' : '<p class="muted small">첨부 파일 없음</p>';
  if (d.loc === 'root') {
    const um = unmatchedInbox();
    const pool = [...um.attach.map((f, i) => ({ t: 'att', f, i, label: '첨부' })), ...um.replies.map((x, i) => ({ t: 'rep', f: x.f, i, label: '시행공문' })), ...um.reports.map((x, i) => ({ t: 'pdf', f: x.f, i, label: '성적서' }))];
    if (pool.length) h += `<details class="pool"><summary>짝을 찾지 못한 파일 ${pool.length}개 — 이 공문에 넣기</summary><ul class="flist2">${pool.map(p => `<li><span class="muted small">${p.label}</span> ${esc(p.f.path ? p.f.path + '/' : '')}${esc(p.f.nm)} <button class="btn small link" data-act="adopt:${p.t}:${p.i}">이 공문 폴더로 옮기기</button></li>`).join('')}</ul></details>`;
  }
  return sec('첨부 파일 (추가 자료)', h);
}
function notesSection(d) {
  const n = peekNotes(d.key), live = true;
  const samples = d.result.rows.map(r => r.시료번호).filter(Boolean);
  const log = (n.log || []).slice().sort((a, b) => (a.date + a.at < b.date + b.at ? -1 : 1));
  let h = `<textarea class="memo" data-act="memo" placeholder="이 공문에 대한 메모 (자동 저장)">${esc(n.memo || '')}</textarea>`;
  h += `<div class="sub">시료 이력</div>`;
  h += log.length ? `<table class="mini log"><tr><th>일자</th><th>시료</th><th>내용</th><th></th></tr>${log.map(x => `<tr class="${x.auto ? 'auto' : ''}"><td>${esc(x.date)}</td><td>${esc(x.sample || '전체')}</td><td>${esc(x.text)}</td><td><button class="btn small link" data-act="log-del:${esc(x.id)}" title="삭제">✕</button></td></tr>`).join('')}</table>` : '<p class="muted small">기록 없음</p>';
  if (live) h += `<div class="log-add"><input type="date" id="logDate" value="${today()}"><select id="logSample"><option value="">전체 시료</option>${samples.map(s => `<option>${esc(s)}</option>`).join('')}</select><input type="text" id="logText" placeholder="이력 내용 (예: 재시험 요청, 추가 시료 접수)"><button class="btn small primary" data-act="log-add">추가</button></div>`;
  h += `<div class="hist-btns"><button class="btn small" data-act="hist:docx">이력 문서 Word</button><button class="btn small" data-act="hist:pdf">이력 문서 PDF</button><span class="muted small">의뢰공문·시행공문·성적서·첨부를 그림으로 넣고 이력을 덧붙입니다.</span></div>`;
  return sec('메모 · 이력', h);
}
function extractedHtml(d) {
  const res = d.result;
  let h = '';
  if (d.error) h += `<ul class="warnlist"><li>읽기 실패: ${esc(d.error)}</li></ul>`;
  if (!res) return h;
  const warns = [...new Set(res.rows.map(r => r.확인필요).filter(Boolean).join(' / ').split(' / ').filter(Boolean))];
  if (warns.length) h += `<ul class="warnlist">${warns.map(w => `<li>${esc(w)}${w === '시료표 미인식' ? ' — 첨부 파일(HWPX)이 없으면 아래 <b>[시료 직접 입력]</b>으로 넣을 수 있습니다.' : ''}</li>`).join('')}</ul>`;
  h += dueSection(d) + progressSection(d) + attachSection(d) + notesSection(d);
  const dd = res.doc, rs = res.rows.filter(r => r.시료번호);
  const srcNote = res.source ? `<span class="muted small">${res.source.type === 'manual' ? '직접 입력한 시료' : '첨부 ' + esc((res.source.files || []).join(', ')) + '에서 읽은 시료'}</span>` : '';
  h += sec(`추출된 시료 (${rs.length})`, srcNote + `<table class="mini"><tr><th>시료번호</th><th>검사항목</th><th>기준</th><th>지역</th><th>채취일</th></tr>`
    + rs.map(r => `<tr><td>${esc(r.시료번호)}</td><td>${esc(r.검사항목)}</td><td>${esc(r.기준)}</td><td>${esc(r.지역구분)}</td><td>${esc(r.시료채취일)}${r.채취일출처 === '본문' ? ' (본문)' : ''}</td></tr>`).join('') + '</table>',
    d.loc === 'root' ? `<button class="btn small link" data-act="manual">${peekNotes(d.key).manual ? '직접 입력 수정' : '시료 직접 입력'}</button>` : '');
  h += sec('공문 정보', `<dl>
    <dt>파일</dt><dd>${esc(d.nm)}${d.loc === 'done' ? ' <span class="badge">처리완료</span>' : ''}</dd>
    <dt>폴더</dt><dd>${esc(d.dirName || (d.loc === 'root' ? '공문 폴더 (정리 전)' : DONE_DIR))}</dd>
    <dt>의뢰기관</dt><dd>${esc(dd.의뢰기관)} / ${esc(dd.의뢰자)}</dd>
    <dt>발신명의</dt><dd>${esc(dd.발신명의)}</dd>
    <dt>시행</dt><dd>${esc(dd.시행)} (${esc(dd.시행일)})</dd>
    <dt>접수</dt><dd>${esc(dd.접수)} (${esc(dd.접수일)})</dd>
    <dt>시료채취자</dt><dd>${esc(dd.시료채취자)} ${dd.기안자직위 ? '(' + esc(dd.기안자직위) + ')' : ''}</dd>
    <dt>주소</dt><dd>${esc(dd.우편번호)} ${esc(dd.주소)}</dd>
    <dt>연락처</dt><dd>${esc(dd.전화번호)} ${esc(dd.이메일)}</dd>
  </dl>`);
  for (const t of res.tables || []) h += sec('시료 표 원문', `<table class="mini">` + (t.raw || [t.headers]).map((row, i) => `<tr>${row.map(c => i === 0 ? `<th>${esc(c)}</th>` : `<td>${esc(c)}</td>`).join('')}</tr>`).join('') + '</table>');
  if (dd.본문 && dd.본문.length) h += sec('본문', `<div class="paras">${dd.본문.map(p => `<p>${highlightDates(p)}</p>`).join('')}</div>`);
  return h;
}
function viewerList(d) {
  const L = [{ k: 'req', label: '의뢰공문', type: 'odt', f: d.f, req: true }];
  d.C.attach.forEach((f, i) => L.push({ k: 'att:' + i, label: '첨부: ' + f.nm.replace(/\.[^.]+$/, ''), type: f.kind, f }));
  if (d.match) {
    d.match.replies.forEach((x, i) => L.push({ k: 'rep:' + i, label: '시행공문' + (d.match.replies.length > 1 ? ' ' + (i + 1) : ''), type: 'odt', f: x.f }));
    d.match.reports.forEach((x, i) => L.push({ k: 'pdf:' + i, label: '성적서' + (d.match.reports.length > 1 ? ' ' + (i + 1) : ''), type: 'pdf', f: x.f }));
  }
  return L;
}
function renderDetail() {
  const box = $('#detail');
  const d = findDoc(state.selected);
  if (!d) { box.hidden = true; box.className = 'detail'; box.dataset.id = ''; return; }
  const same = box.dataset.id === d.id;
  if (!same) state.viewer = 'req';
  const keep = { a: (box.querySelector('.pane-ext') || {}).scrollTop || 0, b: (box.querySelector('.pane-org') || {}).scrollTop || 0 };
  const mode = state.detailMode;
  box.hidden = false; box.className = 'detail mode-' + mode;
  const r0 = docRows(d)[0] || {};
  const seg = [['ext', '추출 결과'], ['org', '원본 보기'], ['side', '나란히']].map(([k, l]) => `<button class="seg-btn${mode === k ? ' on' : ''}" data-act="mode-${k}">${l}</button>`).join('');
  let h = `<div class="detail-head"><h3 title="${esc(d.nm)}">${esc(r0.제목 || d.nm)}</h3><div class="seg">${seg}</div><button class="btn small" data-act="close">닫기</button></div>`;
  h += '<div class="detail-body">';
  if (mode !== 'org') h += `<div class="pane pane-ext">${extractedHtml(d)}</div>`;
  if (mode !== 'ext') {
    const L = viewerList(d); if (!L.find(x => x.k === state.viewer)) state.viewer = 'req';
    const cur = L.find(x => x.k === state.viewer);
    h += `<div class="pane pane-org"><div class="pv-tabs">${L.map(x => `<button class="pv-tab${x.k === state.viewer ? ' on' : ''}" data-act="view:${x.k}" title="${esc(x.f.nm)}">${esc(x.label)}</button>`).join('')}</div>
      <div class="pv-tools"><span class="muted">${esc(cur.f.nm)}</span><span class="spacer"></span>${cur.req ? `<label class="chk small" title="의뢰공문 우측 상단에 시료접수일 표시 (원본 파일은 바꾸지 않음)"><input type="checkbox" data-act="wm" ${state.settings.watermark ? 'checked' : ''}> 접수일 워터마크</label>` : ''}<button class="btn small" data-act="pv-big">새 창으로 크게 보기·인쇄</button><button class="btn small" data-act="pv-download" title="원본 파일을 내려받아 한글 등에서 엽니다">원본 파일 열기</button></div><div class="pv" id="pv"><div class="muted pv-msg">불러오는 중…</div></div></div>`;
  }
  h += '</div><div class="detail-foot">';
  if (d.loc === 'done') h += `<button class="btn" data-act="restore">공문 폴더로 되돌리기</button>`;
  else h += `<button class="btn ${isChecked(d) ? '' : 'primary'}" data-act="check-toggle">${isChecked(d) ? '완료 체크 해제' : '완료 체크'}</button>${!d.organized ? '<button class="btn" data-act="organize-one">이 공문 폴더 만들기</button>' : ''}`;
  h += `<span class="spacer"></span><span class="muted small">${esc(d.dirName ? '폴더: ' + d.dirName : '')}</span></div>`;
  box.innerHTML = h;
  box.dataset.id = d.id;
  if (same) { const a = box.querySelector('.pane-ext'), b = box.querySelector('.pane-org'); if (a) a.scrollTop = keep.a; if (b) b.scrollTop = keep.b; }
  if (mode !== 'ext') showPreview(d, same ? keep.b : 0);
}
