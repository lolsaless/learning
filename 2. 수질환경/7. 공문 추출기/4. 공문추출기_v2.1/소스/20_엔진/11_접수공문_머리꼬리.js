/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/11_접수공문_머리꼬리.js] 접수(의뢰)공문 상단·하단
   하는 일 : 제목·기관(상단), 발신명의·시행/접수·기안자·주소·연락처(하단), 의뢰기관/의뢰자 판정
   주요 이름: parseHeader, parseFooter, senderFallback, deriveOrg
   이럴 때 고침: 의뢰자·발신명의·시행번호가 틀리게 나올 때
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───────── 8. 상단·하단 ───────── */
function parseHeader(tables) {
  for (const t of tables) {
    const g = buildGrid(t);
    let rRecv = -1, title = '', org = '';
    for (let r = 0; r < g.nrows; r++) {
      const os = rowOrigins(g, r);
      os.forEach((o, k) => {
        if (squash(o.text) === '수신' && rRecv < 0) rRecv = r;
        if (squash(o.text) === '제목' && os[k + 1]) title = os[k + 1].lines.join(' ');
      });
    }
    if (rRecv < 0 || !title) continue;
    for (let r = 0; r < rRecv; r++) for (const o of rowOrigins(g, r)) {
      const s = squash(o.text);
      if (s && /^[가-힣]+$/.test(s) && s.length <= 15) org = s;
    }
    return { org, title: title.trim() };
  }
  return null;
}
function parseFooter(tables) {
  for (const t of tables) {
    const g = buildGrid(t);
    let rSi = -1, rCoop = -1;
    for (let r = 0; r < g.nrows; r++) for (const o of rowOrigins(g, r)) {
      const s = squash(o.text);
      if (s === '시행' && rSi < 0) rSi = r;
      if (s === '협조자' && rCoop < 0) rCoop = r;
    }
    if (rSi < 0) continue;
    const f = {};
    const nextVals = (r, label) => { const os = rowOrigins(g, r).filter(o => o.text); const k = os.findIndex(o => squash(o.text) === label); return k < 0 ? [] : os.slice(k + 1).map(o => o.text.trim()); };
    let v = nextVals(rSi, '시행'); f.siNo = v[0] || ''; f.siDate = v[1] || '';
    v = nextVals(rSi, '접수'); f.rcNo = v[0] || ''; f.rcDate = v[1] || '';
    if (rCoop > 1) {
      const names = rowOrigins(g, rCoop - 1).filter(o => o.r === rCoop - 1 && o.text && !/결|\d/.test(o.text));
      const posRow = rowOrigins(g, rCoop - 2).filter(o => o.r === rCoop - 2 && o.text);
      f.drafter = names[0] ? names[0].text.trim() : '';
      f.drafterPos = posRow[0] ? posRow[0].text.trim() : '';
      for (let r = 0; r < rCoop - 2; r++) for (const o of rowOrigins(g, r)) if (o.text && !o.nested) f.sender = spacedName(o.text);
    }
    for (let r = 0; r < g.nrows; r++) {
      const os = rowOrigins(g, r).filter(o => o.text).map(o => o.text.trim());
      if (os[0] === '우') { f.zip = os[1] || ''; f.addr = os[2] || ''; }
      const k = os.indexOf('전화번호'); if (k >= 0) f.tel = os[k + 1] || '';
      const kf = os.indexOf('팩스번호'); if (kf >= 0) f.fax = os[kf + 1] || '';
      const em = os.find(x => x.includes('@')); if (em) f.email = em;
    }
    return f;
  }
  return null;
}
function senderFallback(body, posFirst) {
  const cells = [];
  walk(body, x => { if (x.n === 'table-cell' && !has(x, 'table')) { const t = blockLines(x).join(' '); if (t) cells.push(t); return false; } });
  const k = cells.findIndex(t => squash(t) === squash(posFirst));
  return k > 0 ? spacedName(cells[k - 1]) : '';
}
function deriveOrg(orgTop, addr) {
  if (ORG_EXCEPTIONS[orgTop]) return ORG_EXCEPTIONS[orgTop];
  let org = '';
  if (/^[가-힣]{1,4}(시|군)$/.test(orgTop) || /^[가-힣]{1,3}도$/.test(orgTop)) org = orgTop;
  else { const m = /(?:^|\s)([가-힣]{1,4}(?:시|군))(?=\s)/.exec(addr || ''); if (m) org = m[1]; }
  if (!org) return { 의뢰기관: orgTop, 의뢰자: '' };
  return { 의뢰기관: org, 의뢰자: org.slice(0, -1) + SIDO_TITLE[org.slice(-1)] };
}
