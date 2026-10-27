/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/71_폴더이름.js] 공문별 폴더 이름
   하는 일 : "의뢰기관_제목_시행번호" 폴더 이름 만들기(쓸 수 없는 글자 제거)
   주요 이름: safeName, caseFolderName
   이럴 때 고침: 폴더 이름 규칙
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───────── 8. 폴더 이름 ───────── */
function safeName(s, max) {
  let t = NFC(s).replace(/[\\/:*?"<>|\u0000-\u001f]/g, ' ').replace(/\s+/g, ' ').trim();
  if (max && t.length > max) t = t.slice(0, max).trim();
  return t.replace(/[. ]+$/, '');
}
// "의뢰기관_의뢰공문 제목_시행(공문번호)"
function caseFolderName(doc) {
  const org = safeName(doc.의뢰기관 || doc.상단기관명 || '기관미상', 20);
  const no = safeName(doc.시행 || '번호없음', 40);
  const title = safeName(doc.제목 || String(doc.파일명 || '').replace(/\.odt$/i, ''), 80);
  return `${org}_${title}_${no}`;
}
