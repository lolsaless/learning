/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/07_필터_정렬.js] 필터링·정렬
   하는 일 : 보기(처리 대기·임박·도착 등) 필터, 검색, 정렬 값
   주요 이름: isChecked, isUrgent, sortVal, visibleDocs, checkedGroups
   이럴 때 고침: 새 보기 필터·정렬 기준
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 상태 판정 · 정렬 · 필터 ───── */
const isChecked = d => d.loc === 'root' && !!state.status.checked[d.key];
const docRows = d => d.result ? d.result.rows : [{ 파일명: d.nm, 확인필요: '읽기 실패: ' + d.error }];
function docWarn(d) { return d.error ? true : docRows(d).some(r => r.확인필요); }
function isUrgent(d) { if (d.loc !== 'root') return false; const m = docDueMin(d); return !!(m && m.rem && (m.rem.overdue || m.rem.days <= state.settings.soon)); }
function sortVal(d, key) {
  const r = docRows(d)[0] || {};
  const rno = () => { const n = shortNo(r.접수); return /^\d+$/.test(n) ? n.padStart(10, '0') : ''; };
  if (key === '접수') return rno() || (state.sort.dir > 0 ? '~' : '') + (r.접수 || d.nm);
  if (key === '접수일') return (r.접수일 || (state.sort.dir > 0 ? '9999' : '0000')) + '|' + rno();
  if (key === '처리기한') { const m = docDueMin(d); return m && m.due ? m.due : (state.sort.dir > 0 ? '9999' : '0000'); }
  if (key === '시료접수일') { const rc = caseRecv(d); return rc ? rc.date : ''; }
  if (key === '진행') return d.match ? (d.match.replyOk ? 2 : 0) + (d.match.reportState === 'full' ? 2 : d.match.reportState === 'partial' ? 1 : 0) + '' : '';
  return String(r[key] == null ? '' : r[key]);
}
function visibleDocs() {
  const f = state.filter;
  const src = f.state === 'done' ? state.doneDocs : state.docs;
  const q = f.q.trim().toLowerCase();
  const list = src.filter(d => {
    if (f.state === 'checked' && !isChecked(d)) return false;
    if (f.state === 'unchecked' && isChecked(d)) return false;
    if (f.state === 'urgent' && !isUrgent(d)) return false;
    if (f.state === 'ready' && !readyToFinish(d)) return false;
    const rows = docRows(d);
    if (f.org && (rows[0].의뢰기관 || '') !== f.org) return false;
    if (f.warn && !docWarn(d)) return false;
    if (q && !d.nm.toLowerCase().includes(q) && !(d.dirName || '').toLowerCase().includes(q) && !rows.some(r => E.COLUMNS.some(c => String(r[c] || '').toLowerCase().includes(q))) && !(peekNotes(d.key).memo || '').toLowerCase().includes(q)) return false;
    return true;
  });
  const { key, dir } = state.sort;
  list.sort((a, b) => { const va = sortVal(a, key), vb = sortVal(b, key); return (va < vb ? -1 : va > vb ? 1 : 0) * dir || a.nm.localeCompare(b.nm, 'ko'); });
  return list;
}
function checkedGroups() {
  const by = new Map();
  for (const d of state.docs) if (isChecked(d)) { if (!by.has(d.key)) by.set(d.key, []); by.get(d.key).push(d); }
  return [...by.entries()].map(([key, docs]) => ({ key, docs }));
}
