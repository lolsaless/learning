/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/21_인쇄.js] 인쇄·PDF 보고서
   하는 일 : 선택 시료번호·기간의 7개 항목 그래프+통계표 인쇄
   주요 이름: buildPrint
   이럴 때 고침: 보고서 구성
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
onInit(()=>{
  $("printBtn").onclick=()=>{ if(buildPrint()) setTimeout(()=>{ try{ window.print(); }catch(e){ toast("이 환경에서는 인쇄할 수 없습니다."); } }, 100); };
  addEventListener("afterprint", ()=>{ $("print").innerHTML=""; });
});
/* ═════════ 인쇄 보고서 ═════════ */
function buildPrint(){
  const names = selectedOrdered(), ms = months();
  if(!names.length){ toast("선택된 지점이 없습니다."); return false; }
  const theme = document.documentElement.dataset.theme; document.documentElement.dataset.theme = "light";
  const plan = colorPlan(names);
  const div = document.createElement("div"); div.style.cssText = "position:fixed;left:-10000px;top:0;width:1000px;height:360px"; document.body.appendChild(div);
  const ch = echarts.init(div, null, {renderer:"canvas"});
  let h = `<h1>${esc(D.title)} 보고서</h1><div class="meta">${mLong(ms[0])} ~ ${mLong(ms[ms.length-1])} · 지점 ${names.length}개${S.hl.size?` · 강조: ${[...S.hl].filter(n=>S.sel.has(n)).map(esc).join(", ")}`:""} · ▲▼ ${bandText()||"표시 안 함"} · 출력 ${new Date().toLocaleString("ko-KR")}</div>`;
  for(const it of ITEMS){
    const rows = rowsFor(names, it.code);
    if(!rows.some(r=>r.values.some(v=>v!=null))) continue;
    const opt = trendOption({cats:ms.map(mLabel), mkeys:ms, rows, item:it.code, dec:it.dec, unit:it.unit});
    opt.animation = false; opt.dataZoom = [];
    ch.setOption(opt, true);
    const img = ch.getDataURL({pixelRatio:2, backgroundColor:"#ffffff"});
    const hasJ = !!((D.limits[it.code]||[]).length || targetOf(it.code)!=null);
    const trs = rows.map(r=>{ const s = stats(r.values); if(!s.n) return ""; const nq = ms.filter(m=>qcAt(r.name,m,it.code).length).length;
      return `<tr><td>${esc(r.name)}</td><td>${fmt(s.mean,it.dec)}</td><td>${fmt(s.max,it.dec)}</td><td>${fmt(s.min,it.dec)}</td><td>${fmt(s.sd,it.dec)}</td>${hasJ?`<td>${judge(it.code,s.mean).text}</td>`:""}<td>${nq||""}</td></tr>`; }).join("");
    h += `<section><h2>${esc(it.name)} (${it.unit})</h2><img src="${img}" alt="${esc(it.name)} 그래프">
      <table><thead><tr><th>지점</th><th>평균</th><th>최대</th><th>최소</th><th>표준편차</th>${hasJ?"<th>판정</th>":""}<th>점검</th></tr></thead><tbody>${trs}</tbody></table></section>`;
  }
  if(theme) document.documentElement.dataset.theme = theme; else delete document.documentElement.dataset.theme;
  ch.dispose(); div.remove();
  $("print").innerHTML = h;
  return true;
}
