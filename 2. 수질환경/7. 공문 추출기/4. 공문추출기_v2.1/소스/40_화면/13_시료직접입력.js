/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/13_시료직접입력.js] 시료 직접 입력
   하는 일 : 첨부를 못 읽을 때 붙여넣기 입력 창
   주요 이름: manualInput
   이럴 때 고침: 직접 입력 창
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 시료 직접 입력 (첨부 시료 목록을 읽지 못할 때) ───── */
async function manualInput(d) {
  const n = peekNotes(d.key);
  const cur = n.manual && n.manual.length ? n.manual : d.result.rows.filter(r => r.시료번호).map(r => ({ no: r.시료번호, items: r.검사항목, std: r.기준, date: /확인/.test(r.시료채취일) ? '' : r.시료채취일, note: r.비고 || '' }));
  const tsv = ['시료번호\t검사항목\t기준\t채취일\t비고', ...cur.map(x => [x.no, x.items, x.std, x.date, x.note].map(v => String(v || '').replace(/[\t\n]/g, ' ')).join('\t'))].join('\n');
  const preview = () => {
    const list = E2.parsePastedSamples($('#manText').value);
    $('#manPrev').innerHTML = list.length ? `<table class="mini"><tr><th>시료번호</th><th>검사항목</th><th>기준</th><th>채취일</th><th>비고</th></tr>${list.map(x => `<tr><td>${esc(x.no)}</td><td>${esc(x.items)}</td><td>${esc(x.std)}</td><td>${esc(x.date)}</td><td>${esc(x.note)}</td></tr>`).join('')}</table><p class="muted small">시료 ${list.length}개</p>` : '<p class="muted">시료가 없습니다.</p>';
  };
  const r = await modal('시료 직접 입력', `<p>시료 목록을 <b>엑셀·한글 표에서 복사해 붙여넣거나</b> 직접 입력합니다. 한 줄에 시료 1개, 칸은 탭(엑셀 복사 시 자동)으로 구분합니다. 첫 줄 머리글(시료번호/하천명·검사항목·기준·채취일·비고)이 있으면 열을 자동으로 맞춥니다.<br><span class="muted small">검사항목 칸이 비어 있으면 위 줄의 항목을 씁니다 (병합 칸 복사 대응).</span></p>
    <textarea id="manText" class="mantext" spellcheck="false">${esc(tsv)}</textarea><div id="manPrev"></div>
    ${n.manual ? '<label class="chk"><input type="checkbox" id="manClear"> 직접 입력을 지우고 자동 추출로 되돌리기</label>' : ''}`, '저장', {
    width: 'min(860px, calc(100vw - 32px))',
    onOpen: () => { $('#manText').addEventListener('input', preview); preview(); $('#manText').focus(); },
    collect: () => ({ list: E2.parsePastedSamples($('#manText').value), clear: !!($('#manClear') && $('#manClear').checked) }),
  });
  if (!r) return;
  const nn = notesOf(d.key);
  if (r.clear) { delete nn.manual; addLog(d.key, '직접 입력 시료 삭제 (자동 추출로 되돌림)', '', true); }
  else { nn.manual = r.list; addLog(d.key, `시료 직접 입력 ${r.list.length}개`, '', true); }
  await writeNotes();
  await scan({ quiet: true, noOrganize: true });
}
