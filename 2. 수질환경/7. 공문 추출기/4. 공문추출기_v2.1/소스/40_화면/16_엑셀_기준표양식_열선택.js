/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/16_엑셀_기준표양식_열선택.js] 엑셀 저장·기준표 양식·열 선택
   하는 일 : 엑셀 행 만들기·저장, 기준표 양식 만들기, 열 선택 메뉴
   주요 이름: exportRow, exportExcel, makeStdTemplate, renderColMenu
   이럴 때 고침: 엑셀 열·색
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 엑셀 저장 ───── */
function exportRow(d, r, st) {
  const sd = rowDue(d, r), p = progressHtml(d), n = peekNotes(d.key), rc = caseRecv(d), s = r._rep && r._rep.s;
  const extra = {
    시료접수일: rc ? rc.date + (rc.est ? ' (추정)' : '') : '', 처리기한: sd && sd.due ? sd.due : '', 남은기간: sd && sd.rem && st === '처리대기' ? remText(sd.rem) : '',
    기한결정항목: sd && sd.item ? `${sd.item} ${sd.days}일` : '', 시행공문: d.match ? d.match.replies.map(x => x.f.nm).join(', ') : '',
    성적서: d.match ? d.match.reports.map(x => x.f.nm).join(', ') : '', 성적서접수번호: s ? s.접수번호 : '', 판정: s ? s.판정 : '', 결과: resultText(r).replace(/^.*? — /, ''),
    메모: [n.memo || '', ...(n.log || []).filter(x => !x.auto && (!x.sample || x.sample === r.시료번호)).map(x => `${x.date} ${x.text}`)].filter(Boolean).join('\n'), 폴더: d.dirName || '',
  };
  void p;
  return extra;
}
async function exportExcel() {
  const list = visibleDocs();
  if (!list.length) return toast('저장할 공문이 없습니다.');
  const cols = [...E.COLUMNS]; cols.splice(cols.indexOf('시료채취일') + 1, 0, ...XLSX_EXTRA.filter(k => k !== '폴더' && k !== '메모')); cols.splice(cols.indexOf('확인필요'), 0, '메모', '폴더');
  const header = ['상태', ...cols];
  const rows = [], meta = [];
  for (const d of list) {
    const st = d.loc === 'done' ? '처리완료' : isChecked(d) ? '완료체크' : '처리대기';
    for (const r of docRows(d)) {
      const ex = d.result ? exportRow(d, r, st) : {};
      rows.push([st, ...cols.map(c => ex[c] != null ? ex[c] : r[c] == null ? '' : r[c])]);
      const sd = d.result && st === '처리대기' ? rowDue(d, r) : null;
      meta.push({ dup: !!(d.result && d.result.duplicate), st, urgent: !!(sd && sd.rem && (sd.rem.overdue || sd.rem.days <= state.settings.imminent)) });
    }
  }
  const iWarn = header.indexOf('확인필요'), iDate = header.indexOf('시료채취일'), iDue = header.indexOf('처리기한'), iRem = header.indexOf('남은기간');
  const bytes = X.buildXlsx([{
    name: '공문추출', columns: header.map(h => ({ header: h, width: XLSX_W[h] || 12 })), rows,
    styleOf: (ri, k, v) => meta[ri].dup ? 3 : ((k === iWarn && v) || (k === iDate && v === '채취일자 확인 필요') || ((k === iDue || k === iRem) && meta[ri].urgent)) ? 2 : (k === 0 && meta[ri].st !== '처리대기') ? 4 : 0,
  }]);
  await saveBlob(bytes, `공문추출_${today()}.xlsx`, 'xlsx');
}

/* ───── 기준표 양식 ───── */
const unitOf = item => ({ '생태독성': 'TU', '색도': '도', 'pH': '' })[item] != null ? ({ '생태독성': 'TU', '색도': '도', 'pH': '' })[item] : 'mg/L';
async function makeStdTemplate() {
  const results = [...state.docs, ...state.doneDocs].filter(d => d.result).map(d => d.result);
  const miss = E.missingStdPairs(results);
  const hasStd = !!state.stdFile;
  if (!miss.length) return toast(hasStd ? '기준이 비어 있는 항목이 없습니다.' : '공문이 없어 양식을 만들 수 없습니다.');
  const fname = hasStd ? '기준표_추가필요.xlsx' : '기준표.xlsx';
  const ok = await modal('기준표 양식 만들기', `<p>현재 공문에서 기준이 비어 있는 <b>지역구분 × 항목 ${miss.length}개</b>를 모아 <b>${esc(state.root.name)}\\${fname}</b> 파일을 만듭니다.</p>
    <ol><li>엑셀로 열어 <b>기준값</b> 칸을 채우고 저장합니다.</li>${hasStd ? `<li>채운 행을 기존 <b>${esc(state.stdFile)}</b>에 옮겨 붙이고 저장합니다.</li>` : ''}<li>엑셀을 닫고 이 화면에서 <b>새로고침</b>을 누르면 기준이 채워집니다.</li></ol>
    <p class="muted">지역구분을 비우거나 * 로 쓰면 모든 지역에 같은 기준을 적용합니다.</p>`, '만들기');
  if (!ok) return;
  const rows = miss.map(m => [m.지역구분, m.항목, '', unitOf(m.항목), `${m.건수}건 (예: ${m.예시})`]);
  const guide = [
    ['기준표 작성 방법'], ['1. [기준표] 시트의 기준값 칸을 채우고 저장합니다. (파일 이름은 반드시 기준표.xlsx)'],
    ['2. 지역구분은 공문에 적힌 값(가, 나, 청정, 특례, 기타, 하수처리구역내 등)을 그대로 씁니다.'],
    ['3. 지역구분을 비우거나 * 로 쓰면 모든 지역에 적용합니다. 같은 항목에 지역별 기준이 있으면 지역이 맞는 쪽이 우선입니다.'],
    ['4. 공문에 기준이 적혀 있으면 공문 값을 우선하고, 기준표는 빈 항목만 채웁니다.'],
    ['5. 항목 이름은 BOD, TOC, SS, T-N, T-P, n-H(광), ABS, 생태독성, 색도 등 프로그램 표준명을 씁니다. (총인·총질소 등도 인식)'],
  ];
  const bytes = X.buildXlsx([
    { name: '기준표', columns: [{ header: '지역구분', width: 30 }, { header: '항목', width: 14 }, { header: '기준값', width: 10 }, { header: '단위', width: 8 }, { header: '참고(해당 시료)', width: 26 }], rows, styleOf: (ri, k) => k === 2 ? 2 : 0 },
    { name: '작성 안내', columns: [{ header: '안내', width: 110 }], rows: guide },
  ]);
  try {
    const fh = await state.root.getFileHandle(fname, { create: true });
    const w = await fh.createWritable(); await w.write(bytes); await w.close();
    await info('기준표 양식', `<p><b>${esc(fname)}</b> 파일을 공문 폴더에 만들었습니다.</p><p>기준값을 채워 저장한 뒤 엑셀을 닫고 <b>새로고침</b>을 누르세요.</p>`);
  } catch (e) { toast('양식을 만들지 못했습니다: ' + explain(e), 'err'); }
}

/* ───── 열 선택 ───── */
function renderColMenu() {
  const m = $('#colMenu');
  m.innerHTML = `<div class="cols">${COLS.map(c => `<label><input type="checkbox" value="${esc(c.k)}" ${state.cols.includes(c.k) ? 'checked' : ''}> ${esc(c.label || c.k)}</label>`).join('')}</div>
    <div class="pop-actions"><button class="btn small" data-act="cols-default">기본값</button><button class="btn small" data-act="cols-all">전체 표시</button></div>`;
}
