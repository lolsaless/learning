/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_공통/06_차트_도구.js] 그래프 만들기 도우미
   하는 일 : ECharts 그래프 만들기·크기 자동 맞춤, 표 복사용 임시 저장
   주요 이름: charts, chartOn, cache
   이럴 때 고침: 고치지 않음
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ═════════ 차트 인스턴스 ═════════ */
const charts = {};
function chartOn(id){
  const el = $(id);
  if(!charts[id]){ charts[id] = echarts.init(el, null, {renderer:"canvas"}); new ResizeObserver(()=>charts[id].resize()).observe(el); }
  return charts[id];
}
const cache = {};
