/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_공통/03_자료점검_조회.js] 자료 점검 표시 조회
   하는 일 : 자동 점검 결과를 시료번호·월·항목으로 찾기
   주요 이름: QC_LABEL, QC_RANK, qcAt, qcTop, loqText
   이럴 때 고침: 점검 유형 이름·우선순위
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ═════════ 자료 점검(QC) 조회 ═════════ */
const QC_LABEL = {manual:"검토필요", repeat:"전월 동일", outlier:"이상값 의심", loq:"정량한계 미만", multi:"중복 채취", coord:"좌표 추정"};
const QC_RANK = {outlier:0, manual:1, repeat:2, loq:3, multi:4};
const qcIndex = {};
for(const q of D.qc){ if(!q.m) continue; const k = `${q.st}|${q.m}|${q.item||"*"}`; (qcIndex[k] ||= []).push(q); }
function qcAt(st, m, item){
  const a = [...(qcIndex[`${st}|${m}|${item}`]||[]), ...(qcIndex[`${st}|${m}|*`]||[])];
  return a.sort((x,y)=>QC_RANK[x.type]-QC_RANK[y.type]);
}
const qcTop = (st,m,item) => qcAt(st,m,item)[0];
const loqText = (st,m,item) => D.loq[`${st}|${m}|${item}`];
