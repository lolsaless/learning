/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/13_히트맵.js] 히트맵 화면
   하는 일 : 시료번호×월 색칸, 측정값/평균 대비 모드
   주요 이름: renderHeat
   이럴 때 고침: 히트맵 색·라벨
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
registerView({ id:"heat", label:"히트맵", kpi:true, item:true, render:()=>renderHeat(),
  bind(){ document.querySelectorAll("#hmMode button").forEach(b=>b.onclick=()=>{ S.heatMode=b.dataset.m; refresh(); }); }});
/* ═════════ 히트맵 ═════════ */
function renderHeat(){
  const it = itemOf(S.item), names = selectedOrdered(), ms = months();
  $("hmTitle").textContent = `${it.name} 지점 × 월`;
  $("hmSub").textContent = S.heatMode==="value" ? `측정값(${it.unit}) · 진할수록 높음` : `지점 평균 대비 증감률 · 빨강=평균보다 높음, 파랑=낮음`;
  document.querySelectorAll("#hmMode button").forEach(b=>b.setAttribute("aria-pressed", b.dataset.m===S.heatMode));
  const el = $("hmChart"); el.style.height = Math.max(260, names.length*22 + 96) + "px";
  const ch = chartOn("hmChart"); ch.resize();
  const ys = names.slice().reverse(), ink = css("--ink"), panel = css("--panel");
  const data = [], vals = [];
  ys.forEach((n,yi)=>{ const v = series(n,S.item), s = stats(v);
    v.forEach((x,xi)=>{ if(x==null) return; const dev = s.mean? (x-s.mean)/s.mean*100 : 0, val = S.heatMode==="value"?x:dev;
      data.push({value:[xi, yi, val], raw:x, dev, q:qcTop(n, ms[xi], S.item), lq:loqText(n, ms[xi], S.item)}); vals.push(val); }); });
  vals.sort((a,b)=>a-b);
  const q = p => vals.length? vals[Math.min(vals.length-1, Math.floor(p*(vals.length-1)))] : 0;
  const vm = S.heatMode==="value"
    ? {min: vals[0]??0, max: q(.97)||1, inRange:{color:[css("--q100"),css("--q250"),css("--q400"),css("--q550"),css("--q700")]}}
    : (()=>{ const m = Math.max(Math.abs(q(.03)), Math.abs(q(.97)), 10); return {min:-m, max:m, inRange:{color:[css("--q550"),css("--q250"),css("--mid"),css("--r400"),css("--r600")]}}; })();
  const rng = (vm.max - vm.min) || 1;
  const labColor = v => S.heatMode==="value" ? ((v-vm.min)/rng > 0.55 ? "#ffffff" : ink) : (Math.abs(v)/vm.max > 0.6 ? "#ffffff" : ink);
  data.forEach(d=>{ d.label = {color: labColor(d.value[2])};
    if(d.q) d.itemStyle = {borderColor: d.q.type==="outlier"?css("--qc-out"):css("--warn"), borderWidth:2.5, borderType: d.q.type==="outlier"?"dotted":"dashed"}; });
  ch.setOption({
    animation:false, textStyle:{fontFamily:css("--f-ui")}, grid:{left:96, right:20, top:28, bottom:64},
    tooltip:{confine:true, backgroundColor:panel, borderColor:css("--line"), textStyle:{color:ink,fontSize:12},
      formatter:p=>`<b>${esc(ys[p.value[1]])}</b> · ${mLong(ms[p.value[0]])}<br>${p.data.lq||fmt(p.data.raw,it.dec)} ${it.unit}<br><span style="color:${css("--ink-3")}">지점 평균 대비 ${p.data.dev>=0?"+":""}${p.data.dev.toFixed(0)}%</span>${p.data.q?`<br><span style="color:${css("--warn")}">${QC_LABEL[p.data.q.type]}: ${esc(p.data.q.note)}</span>`:""}`},
    xAxis:{type:"category", data:ms.map(mLabel), position:"top", axisLine:{show:false}, axisTick:{show:false}, axisLabel:{color:css("--ink-2"), fontFamily:css("--f-num")}},
    yAxis:{type:"category", data:ys, axisLine:{show:false}, axisTick:{show:false}, axisLabel:{color:css("--ink-2"), formatter:n=>S.hl.has(n)?`{b|${n}}`:n, rich:{b:{fontWeight:700,color:ink}}}},
    visualMap:{type:"continuous", ...vm, calculable:false, orient:"horizontal", left:"center", bottom:8, itemHeight:220, itemWidth:10,
      textStyle:{color:css("--ink-2")}, formatter: v=> S.heatMode==="value"? fmt(v,it.dec) : (v>0?"+":"")+Math.round(v)+"%", dimension:2},
    series:[{type:"heatmap", data, itemStyle:{borderColor:panel, borderWidth:2, borderRadius:3},
      label:{show:true, fontSize:10.5, fontFamily:css("--f-num"), formatter:p=>p.data.lq||fmt(p.data.raw, Math.min(it.dec,2))},
      emphasis:{itemStyle:{borderColor:ink, borderWidth:1.5}}}]
  }, true);
  ch.off("click"); ch.on("click", p=>{ const n = ys[p.value[1]]; S.hl.add(n); setView("ts"); toast(`${n} 강조`); });
}
