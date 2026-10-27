/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/15_이력문서.js] 이력 문서(Word·PDF)
   하는 일 : 이력 문서 옵션 창, 문서 내용 구성(요약·그림·이력), 저장
   주요 이름: saveBlob, makeHistory, historyBlocks
   이럴 때 고침: 이력 문서에 넣을 내용·순서
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 이력 문서 (Word · PDF) ───── */
async function saveBlob(bytes, name, kind) {
  const T = { xlsx: ['엑셀 파일', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'], docx: ['Word 문서', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'], pdf: ['PDF 문서', 'application/pdf'] }[kind];
  if (window.showSaveFilePicker) {
    try {
      const h = await window.showSaveFilePicker({ id: 'odt-save-' + kind, suggestedName: name, types: [{ description: T[0], accept: { [T[1]]: ['.' + kind] } }] });
      const w = await h.createWritable(); await w.write(bytes); await w.close();
      toast(`저장했습니다: ${h.name}`); return true;
    } catch (e) {
      if (e.name === 'AbortError') return false;
      if (e.name === 'NoModificationAllowedError' || e.name === 'InvalidModificationError') { toast('같은 이름의 파일이 열려 있어 저장할 수 없습니다. 파일을 닫거나 다른 이름으로 저장하세요.', 'err'); return false; }
    }
  }
  const url = URL.createObjectURL(new Blob([bytes], { type: T[1] }));
  const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  toast(`다운로드 폴더에 저장했습니다: ${name}`); return true;
}
const RENDERABLE = f => /^(hwpx|img|pdf)$/.test(f.kind);
async function makeHistory(d, fmt) {
  const m = d.match || { replies: [], reports: [] };
  const samples = d.result.rows.map(r => r.시료번호).filter(Boolean);
  const atts = d.C.attach;
  const canFolder = !!(d.dirName && d.dir);
  const o = await modal(`이력 문서 만들기 (${fmt === 'pdf' ? 'PDF' : 'Word'})`, `
    <div class="form"><label>대상 시료 <select id="hSample"><option value="">공문 전체 (시료 ${samples.length}개)</option>${samples.map(s => `<option>${esc(s)}</option>`).join('')}</select></label>
    <h4>그림으로 넣을 문서</h4>
    <label class="chk"><input type="checkbox" id="hReq" checked> 의뢰공문</label>
    <label class="chk" style="margin-left:22px"><input type="checkbox" id="hWm" ${state.settings.watermark ? 'checked' : ''} ${peekNotes(d.key).recv ? '' : 'disabled'}> 시료접수일 워터마크 ${peekNotes(d.key).recv ? '' : '<span class="muted small">(시료접수일 입력 후 사용)</span>'}</label>
    <label class="chk"><input type="checkbox" id="hRep" ${m.replies.length ? 'checked' : 'disabled'}> 시행공문 ${m.replies.length ? `(${m.replies.length})` : '<span class="muted small">(없음)</span>'}</label>
    <label class="chk"><input type="checkbox" id="hPdf" ${m.reports.length ? 'checked' : 'disabled'}> 시험성적서 ${m.reports.length ? `(${m.reports.length}개 파일, 대상 시료 쪽만)` : '<span class="muted small">(없음)</span>'}</label>
    <label class="chk"><input type="checkbox" id="hAtt" ${atts.length ? 'checked' : 'disabled'}> 추가 자료 (공문 폴더의 HWPX·그림·PDF) ${atts.length ? `(${atts.length})` : '<span class="muted small">(없음)</span>'}</label>
    <h4>저장</h4>
    <label class="chk"><input type="checkbox" id="hFolder" ${canFolder ? 'checked' : 'disabled'}> 공문 폴더에 저장 ${canFolder ? `<span class="muted small">(${esc(d.dirName)})</span>` : '<span class="muted small">(공문 폴더 정리 후 사용)</span>'}</label></div>`, '만들기', {
    collect: () => ({ sample: $('#hSample').value, req: $('#hReq').checked, wm: $('#hWm').checked, rep: $('#hRep').checked, pdf: $('#hPdf').checked, att: $('#hAtt').checked, folder: $('#hFolder').checked }),
  });
  if (!o) return;
  busy(true, '이력 문서 만드는 중… (문서를 그림으로 바꾸는 중)');
  try {
    const blocks = await historyBlocks(d, o);
    busy(true, '이력 문서 저장하는 중…');
    const stamp = today().replace(/-/g, '');
    const fname = E2.safeName(`이력_${o.sample || (d.result.doc.시행 || '공문')}_${stamp}.${fmt}`, 120);
    const bytes = fmt === 'pdf' ? await DG.buildPdf(DG.layoutPages(blocks, `${d.result.doc.의뢰기관} ${d.result.doc.시행} 시료 처리 이력`)) : await DG.buildDocx(blocks, blocks[0].text);
    let saved = false;
    if (o.folder && canFolder) {
      const name = await uniqueName(d.dir, fname);
      const fh = await d.dir.getFileHandle(name, { create: true }); const w = await fh.createWritable(); await w.write(bytes); await w.close();
      toast(`공문 폴더에 저장했습니다: ${name}`); saved = true;
    } else saved = await saveBlob(bytes, fname, fmt);
    if (saved) { addLog(d.key, `이력 문서 작성 (${fmt === 'pdf' ? 'PDF' : 'Word'}${o.sample ? ', ' + o.sample : ''})`, o.sample, true); await writeNotes(); render(); }
  } catch (e) { console.error(e); toast('이력 문서를 만들지 못했습니다: ' + explain(e), 'err'); }
  busy(false);
}
async function historyBlocks(d, o) {
  const doc = d.result.doc, n = peekNotes(d.key), m = d.match || { replies: [], reports: [] };
  const rows = d.result.rows.filter(r => r.시료번호 && (!o.sample || r.시료번호 === o.sample));
  const rc = caseRecv(d), B = [];
  B.push({ t: 'title', text: `시료 처리 이력 — ${o.sample || doc.제목}` });
  B.push({ t: 'kv', rows: [
    ['의뢰기관', `${doc.의뢰기관} (${doc.의뢰자})`], ['의뢰공문', doc.제목], ['공문번호(시행)', `${doc.시행}${doc.시행일 ? ' (' + doc.시행일 + ')' : ''}`],
    ['접수', `${doc.접수}${doc.접수일 ? ' (' + doc.접수일 + ')' : ''}`], ['시료접수일', rc ? `${fmtFull(rc.date)}${rc.est ? ' (공문 접수일 기준)' : ''}${rc.before13 ? ', 13시 이전 접수' : ''}` : '-'],
    ['시료채취자', doc.시료채취자], ['폴더', d.dirName || '-'], ['작성일', fmtFull(today())],
  ] });
  B.push({ t: 'table', head: ['시료번호', '검사항목', '처리기한', '성적서 접수번호', '결과', '판정'], widths: [16, 22, 12, 14, 26, 10], rows: rows.map(r => {
    const sd = rowDue(d, r), s = r._rep && r._rep.s;
    return [r.시료번호, r.검사항목, sd && sd.due ? `${sd.due} (${sd.item} ${sd.days}일)` : '-', s ? s.접수번호 : '-', s ? s.결과.map(x => `${x.항목명 || x.항목} ${x.결과}`).join(', ') : '-', s ? s.판정 : '-'];
  }) });
  const css = (await odtPreview(d.f)).css + WM_CSS + '.odt-page{padding:1cm 1.2cm}';
  const odtImg = async (f, wm) => { const r = await odtPreview(f); return DG.htmlToCanvas(`<div style="padding:8px 0">${wm ? `<div class="wm-wrap">${wmHtml(d)}${r.html}</div>` : r.html}</div>`, css, 820, 2); };
  let sn = 0;
  if (o.req) { B.push({ t: 'h', text: `${++sn}. 의뢰공문` }); B.push({ t: 'img', canvas: await odtImg(d.f, o.wm && n.recv), caption: d.f.nm }); }
  if (o.rep && m.replies.length) { B.push({ t: 'h', text: `${++sn}. 시행공문 (결과 알림)` }); for (const x of m.replies) B.push({ t: 'img', canvas: await odtImg(x.f, false), caption: x.f.nm }); }
  if (o.pdf && m.reports.length) {
    B.push({ t: 'h', text: `${++sn}. 시험성적서` });
    for (const x of m.reports) {
      const want = new Set(rows.map(r => E2.noKey(r.시료번호)));
      const pages = x.rep.samples.filter(s => want.has(E2.noKey(s.시료명))).flatMap(s => s.쪽 || []);
      if (!pages.length) continue;
      const cs = await DG.pdfToCanvases(await fileBytes(x.f), pages, 2);
      cs.forEach((c, i) => B.push({ t: 'img', canvas: c, caption: `${x.f.nm} — ${pages[i]}쪽` }));
    }
  }
  if (o.att && d.C.attach.length) {
    B.push({ t: 'h', text: `${++sn}. 추가 자료` });
    for (const f of d.C.attach) {
      try {
        if (f.kind === 'hwpx') { const h = await parseHwpxEntry(f); B.push({ t: 'img', canvas: await DG.htmlToCanvas(E2.hwpxHtml(h, ''), '', 900, 2), caption: f.nm }); }
        else if (f.kind === 'img') B.push({ t: 'img', canvas: await DG.imageToCanvas(await fileBytes(f), f.nm), caption: f.nm });
        else if (f.kind === 'pdf') { const cs = await DG.pdfToCanvases(await fileBytes(f), null, 2); cs.forEach((c, i) => B.push({ t: 'img', canvas: c, caption: `${f.nm} — ${i + 1}쪽` })); }
        else B.push({ t: 'p', text: `· ${f.nm} (그림으로 넣을 수 없는 형식 — 공문 폴더의 원본 파일 참고)`, muted: true });
      } catch (e) { B.push({ t: 'p', text: `· ${f.nm} (변환 실패: ${explain(e)})`, muted: true }); }
    }
  }
  B.push({ t: 'h', text: `${++sn}. 메모 · 이력` });
  if (n.memo) B.push({ t: 'p', text: n.memo });
  const log = (n.log || []).filter(x => !o.sample || !x.sample || x.sample === o.sample).sort((a, b) => (a.date + a.at < b.date + b.at ? -1 : 1));
  if (log.length) B.push({ t: 'table', head: ['일자', '시료', '내용'], widths: [14, 18, 68], rows: log.map(x => [x.date, x.sample || '전체', x.text + (x.auto ? ' (자동 기록)' : '')]) });
  if (!n.memo && !log.length) B.push({ t: 'p', text: '기록 없음', muted: true });
  return B;
}
