/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/15_접수공문_추출조립.js] 접수공문 추출 조립
   하는 일 : ODT 1건 → 공문 정보 + 시료 1행씩, 확인필요 경고, 엑셀 열 목록, 중복 공문 표시
   주요 이름: extractOdt, buildResult, rebuildResult, COLUMNS, markDuplicates
   이럴 때 고침: 행을 만드는 규칙·엑셀 열 순서
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───────── 12. 메인 ───────── */
async function extractOdt(bytes, fileName, inflateRaw) {
  const xml = await unzipEntry(bytes, 'content.xml', inflateRaw);
  const root = parseXML(xml);
  const officeBody = findAll(root, 'body')[0];
  const body = (officeBody && kids(officeBody, 'text')[0]) || root;
  const tables = findAll(body, 'table').filter(t => !findAll(t, 'table').length); // 중첩 없는 표만
  const hdr = parseHeader(tables) || { org: '', title: '' };
  const ftr = parseFooter(tables) || {};
  if (!ftr.sender && ftr.drafterPos) ftr.sender = senderFallback(body, ftr.drafterPos);
  const org = deriveOrg(hdr.org, ftr.addr);
  const paras = bodyParagraphs(body);
  const doc = {
    파일명: (fileName || '').normalize('NFC'), 제목: hdr.title, 상단기관명: hdr.org,
    의뢰기관: org.의뢰기관, 의뢰자: org.의뢰자, 발신명의: ftr.sender || '',
    시행: ftr.siNo || '', 시행일: (parseDate(ftr.siDate) || {}).date || '',
    접수: ftr.rcNo || '', 접수일: (parseDate(ftr.rcDate) || {}).date || '',
    시료채취자: ftr.drafter || '', 기안자직위: ftr.drafterPos || '',
    우편번호: ftr.zip || '', 주소: ftr.addr || '', 전화번호: ftr.tel || '', 이메일: ftr.email || '',
  };
  return buildResult(doc, paras, findSampleTables(tables));
}
// v2.0: 공문 정보 + 시료 표(격자) → 결과. 첨부 HWPX의 시료 목록에도 같은 규칙을 쓴다
function buildResult(doc, paras, sts) {
  const docWarn = [];
  if (!doc.접수) docWarn.push('접수번호 없음');
  if (!doc.의뢰자) docWarn.push('의뢰자 판정 불가');
  if (!sts.length) docWarn.push('시료표 미인식');
  const bodyDates = dateFromBody(paras);
  const bodyDate = bodyDates[0] || null;
  const bset = [...new Set(bodyDates.map(d => d.date))];
  if (bset.length > 1) docWarn.push('본문 채취일 여러 개: ' + bset.join(', '));
  const rows = [], allSamples = [], tableInfo = []; let baseTotal = 0;
  for (const st of sts) {
    const { headers, raw, samples } = readSampleTable(st);
    tableInfo.push({ headers, raw });
    for (const s of samples) {
      const ex = expandNo(s.rawNo); baseTotal += ex.baseCount; allSamples.push(s);
      const warn = [];
      const groups = s.groups.map(gp => {
        const p = parseItems(gp.items);
        let std = gp.std, region = gp.region;
        if (std && !/\d/.test(std)) { region = region || std; std = ''; } // '수질기준' 열에 지역코드가 들어간 경우
        applyStdColumn(p.items, std);
        const rg = (region || p.region || '').replace(/\s*\n\s*/g, ' ').trim();
        p.items.forEach(i => { i.region = rg; });
        return { items: p.items, region: rg };
      });
      const items = [];
      groups.forEach(gp => gp.items.forEach(i => { if (!items.some(x => x.name === i.name)) items.push(i); }));
      if (/기준/.test(s.note)) applyStdColumn(items, s.note);
      const unknown = items.filter(i => !i.known).map(i => i.raw);
      if (unknown.length) warn.push('미등록 항목: ' + unknown.join(', '));
      if (!items.length) warn.push('검사항목 없음');
      const regs = groups.map(gp => gp.region).filter(Boolean);
      const regionText = new Set(regs).size > 1
        ? groups.filter(gp => gp.region).map(gp => `${gp.region}(${gp.items.map(i => i.name).join(', ')})`).join(' / ')
        : (regs[0] || '');
      let date, time = '', src;
      const pd = parseDate(s.date);
      if (pd) { date = pd.date; time = pd.time; src = '표'; }
      else if (bodyDate) { date = bodyDate.date; time = bodyDate.time; src = '본문'; }
      else { date = '채취일자 확인 필요'; src = '확인필요'; warn.push('채취일자 확인 필요'); }
      if (pd && doc.접수일 && pd.date > doc.접수일) warn.push('채취일이 접수일보다 늦음');
      for (const no of ex.list) {
        const row = {
          ...doc, 시료번호: no, 시료번호원문: s.rawNo,
          검사항목: items.map(i => i.name).join(', '),
          기준: '', 기준출처: '',
          지역구분: regionText, 시료채취일: date, 채취시각: time, 채취일출처: src,
          '업종/성상': spacedName(s.industry.replace(/\n/g, ' ')), 시료량: s.qty.replace(/\n/g, ', '),
          채취지점: s.point.replace(/\n/g, ' '), 비고: s.note.replace(/\n/g, ' '), 기타: s.other,
          _items: items.map(i => ({ name: i.name, region: i.region || regionText, stdDoc: i.std || '', std: i.std || '', src: i.std ? '공문' : '' })),
          _warn: warn,
        };
        refreshStdText(row);
        rows.push(row);
      }
    }
  }
  const tc = titleCheck(doc.제목, allSamples, baseTotal); if (tc) docWarn.push(tc);
  if (doc.시행일 && doc.접수일 && doc.접수일 < doc.시행일) docWarn.push('접수일이 시행일보다 빠름');
  if (!rows.length) rows.push({ ...doc, 시료번호: '', _items: [], _warn: [] });
  rows.forEach(r => { r._baseWarn = [...docWarn, ...r._warn]; delete r._warn; r.확인필요 = r._baseWarn.join(' / '); });
  return { doc: { ...doc, 본문: paras }, rows, warnings: docWarn, tables: tableInfo };
}
function rebuildResult(result, sts) {
  const doc = { ...result.doc }; const paras = doc.본문 || []; delete doc.본문;
  return buildResult(doc, paras, sts);
}

// v1.1: 엑셀·화면 기본 순서 — 접수일, 의뢰기관, 의뢰자, 발신명의, 시행, 시료번호, 검사항목, 시료채취일 먼저
const COLUMNS = ['접수일','의뢰기관','의뢰자','발신명의','시행','시료번호','검사항목','시료채취일','기준','기준출처','지역구분',
  '채취시각','채취일출처','시료채취자','접수','시행일','제목','업종/성상','시료량','채취지점','비고','기타','우편번호','주소','전화번호','이메일','확인필요','파일명'];

/* ───────── 13. 중복 공문 ───────── */
function markDuplicates(results) {
  const by = {};
  results.forEach(r => { r.duplicate = false; r.dupWarn = ''; if (r.doc && r.doc.접수) (by[r.doc.접수] = by[r.doc.접수] || []).push(r); });
  for (const k in by) if (by[k].length > 1) by[k].forEach((r, i) => {
    const others = by[k].filter(x => x !== r).map(x => x.doc.파일명).join(', ');
    r.duplicate = i > 0;
    r.dupWarn = (i > 0 ? '중복 공문(집계 제외)' : '중복 공문 있음') + ': ' + others;
  });
  results.forEach(r => r.rows.forEach(x => { x.확인필요 = [...(x._baseWarn || []), ...(r.dupWarn ? [r.dupWarn] : [])].join(' / '); }));
  return results;
}
