/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/12_종단.js] 상·하류 종단 화면
   하는 일 : 하천별 상류→하류 그래프, 월 켜기/끄기, 구간별 변화표
   주요 이름: renderProf, monthRamp
   이럴 때 고침: 종단 그래프·구간 변화 기준(30%)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
registerView({ id:"prof", label:"상·하류 종단", kpi:true, item:true, render:()=>renderProf(),
  bind(){ $("pfCopy").onclick=()=>copyText(tsvText(cache.pfTsv||[])); }});
/* ═════════ 상·하류 종단 ═════════ */
function monthRamp(n){
  const stops = [css("--q250"),css("--q400"),css("--q550"),css("--q700")].map(toHex);
  return i => { const t = n<=1?1:i/(n-1), p = t*(stops.length-1), k = Math.min(stops.length-2, Math.floor(p)), f = p-k;
    const a = stops[k].match(/\w\w/g).map(x=>parseInt(x,16)), b = stops[k+1].match(/\w\w/g).map(x=>parseInt(x,16));
    return "#"+a.map((x,j)=>Math.round(x+(b[j]-x)*f).toString(16).padStart(2,"0")).join(""); };
}
function renderProf(){
  const it = itemOf(S.item), ms = months();
  const seg = $("pfRivers");
  seg.innerHTML = RIVERS().map(r=>`<button data-r="${esc(r)}" aria-pressed="${r===S.profRiver}">${esc(r)} ${ST.filter(s=>s.river===r).length}</button>`).join("");
  seg.querySelectorAll("button").forEach(b=>b.onclick=()=>{ S.profRiver=b.dataset.r; refresh(); });
  const chain = ST.filter(s=>s.river===S.profRiver);
  $("pfTitle").textContent = `${S.profRiver} ${it.name} 상류 → 하류`;
  $("pfSub").textContent = `${chain.length}개 지점 · 정렬순서 기준 · 단위 ${it.unit}`;
  const cats = chain.map(s=>s.name);
  const ramp = monthRamp(ms.length), ink2 = css("--ink-2"), ink3 = css("--ink-3"), panel = css("--panel");
  let last = -1; for(let i=ms.length-1;i>=0;i--) if(chain.some(s=>series(s.name,S.item)[i]!=null)){ last=i; break; }
  const means = chain.map(s=>stats(series(s.name,S.item)).mean ?? null);
  const ser = [];
  ms.forEach((m,i)=>{
    if(S.profHidden.has(m)) return;
    const isLast = i===last;
    ser.push({name:mLong(m), type:"line", data:chain.map(s=>{ const v = series(s.name,S.item)[i]; const q = v!=null?qcTop(s.name,m,S.item):null;
        return v==null?{value:null}:{value:v, _q:q, itemStyle: q?{borderColor:q.type==="outlier"?css("--qc-out"):css("--warn"), borderWidth:2.5, borderType:q.type==="outlier"?"dotted":"dashed"}:undefined}; }),
      connectNulls:true, symbol:"circle", symbolSize:isLast?8:5, z:isLast?6:2,
      lineStyle:{width:isLast?2.6:1.2, color:ramp(i), opacity:isLast?1:.75}, itemStyle:{color:ramp(i)},
      label:{show:isLast, position:"top", formatter:p=>fmt(p.value,it.dec), color:ink2, fontSize:11, fontFamily:css("--f-num")}, labelLayout:{hideOverlap:true},
      emphasis:{focus:"series"}});
  });
  ser.push({name:"기간 평균", type:"line", data:means, symbol:"rect", symbolSize:7, z:7, lineStyle:{width:2.2, type:[6,4], color:css("--ink")}, itemStyle:{color:css("--ink")},
    label:{show:S.profHidden.has("__mean")?false:last<0, formatter:p=>fmt(p.value,it.dec)}});
  if(S.profHidden.has("__mean")) ser.pop();
  if(S.opt.limits){
    const t = targetOf(S.item), L = (D.limits[S.item]||[]).filter(l=>l.max!=null);
    const vmax = Math.max(...chain.flatMap(s=>series(s.name,S.item)).filter(v=>v!=null), 0), seen = new Set(), lines = [];
    L.forEach(l=>{ if(!seen.has(l.max) && l.max<=vmax*1.15){ seen.add(l.max); lines.push({yAxis:l.max, label:{formatter:`${l.code} ≤${l.max}`}}); } });
    if(t!=null) lines.push({yAxis:t, lineStyle:{color:css("--accent"), type:"solid", width:1.4}, label:{formatter:`목표 ${t}`, color:css("--accent")}});
    if(lines.length) ser.push({name:"__limits", type:"line", data:[], silent:true, markLine:{silent:true, symbol:"none", lineStyle:{color:ink3, type:[2,4]}, label:{position:"insideStartTop", color:ink3, fontSize:10.5}, data:lines}});
  }
  chartOn("pfChart").setOption({
    animationDuration:300, textStyle:{fontFamily:css("--f-ui")}, grid:{left:56,right:28,top:30,bottom:cats.length>6?70:40},
    tooltip:{trigger:"axis", confine:true, backgroundColor:panel, borderColor:css("--line"), textStyle:{color:css("--ink"),fontSize:12},
      formatter:ps=>{ const s = chain[ps[0].dataIndex]; const extra = (s.addr.match(/\(([^)]*)\)/)||[])[1];
        return `<b>${esc(s.name)}</b>${extra?` <span style="color:${ink3}">${esc(extra)}</span>`:""}<br>`+ps.filter(p=>p.seriesName!=="__limits"&&p.value!=null).map(p=>`<span style="display:inline-block;width:10px;height:3px;background:${p.color};vertical-align:middle;margin-right:6px"></span>${p.seriesName} <b style="font-family:${css("--f-num")}">${fmt(p.value,it.dec)}</b>${p.data?._q?` <span style="color:${css("--warn")}">${QC_LABEL[p.data._q.type]}</span>`:""}`).join("<br>"); }},
    xAxis:{type:"category", data:cats, axisLabel:{color:ink2, rotate:cats.length>6?28:0, interval:0}, axisLine:{lineStyle:{color:css("--line")}}, axisTick:{show:false}},
    yAxis:{type:S.opt.scale==="log"?"log":"value", splitLine:{lineStyle:{color:css("--line-2")}}, axisLabel:{color:ink2, fontFamily:css("--f-num")}},
    series:ser
  }, true);
  // 범례(월 켜고 끄기)
  const lg = $("pfLegend");
  lg.innerHTML = `<button class="li ${S.profHidden.has("__mean")?"off":""}" data-m="__mean"><span class="ln" style="background:${css("--ink")}"></span>기간 평균</button>` +
    ms.map((m,i)=>`<button class="li ${S.profHidden.has(m)?"off":""}" data-m="${m}"><span class="ln" style="background:${ramp(i)};height:${i===last?4:3}px"></span>${mLabel(m)}${i===last?" (최근)":""}</button>`).join("") +
    `<button class="li" data-m="__only">최근월만</button><button class="li" data-m="__all">전체 월</button>`;
  lg.querySelectorAll(".li").forEach(b=>b.onclick=()=>{ const m=b.dataset.m;
    if(m==="__only"){ S.profHidden = new Set(ms.filter((x,i)=>i!==last)); }
    else if(m==="__all"){ S.profHidden = new Set(); }
    else S.profHidden.has(m)?S.profHidden.delete(m):S.profHidden.add(m); refresh(); });
  // 구간별 변화 표
  let h = `<thead><tr><th class="l stc">지점</th><th class="l">위치</th><th>기간 평균</th><th>상류 대비</th><th>변화율</th>${ms.map(m=>`<th>${mLabel(m)}</th>`).join("")}</tr></thead><tbody>`;
  const tsv = [["지점","기간 평균","상류 대비","변화율(%)",...ms]];
  chain.forEach((s,i)=>{
    const sv = series(s.name,S.item), st = stats(sv), prev = i>0?means[i-1]:null, d = (st.n && prev!=null)? st.mean-prev : null, r = d!=null && prev? d/prev*100 : null;
    const big = r!=null && r>=30, extra = (s.addr.match(/\(([^)]*)\)/)||[])[1]||"";
    h += `<tr class="${S.hl.has(s.name)?"hl":""}"><td class="l stc" data-st="${esc(s.name)}">${esc(s.name)}</td><td class="l" style="color:var(--ink-3)">${esc(extra)}</td><td class="num stat"><b>${fmt(st.mean,it.dec)}</b></td>
      <td class="num ${d>0?"up":d<0?"dn":""}">${d==null?"":(d>0?"+":"")+fmt(d,it.dec)}</td><td class="num ${big?"up":""}">${r==null?"":(Math.round(r)>0?"+":"")+(Math.round(r)||0)+"%"}${big?' <span class="g">▲</span>':""}</td>
      ${sv.map((v,k)=>cellHtml(s.name, ms[k], S.item, v, st, it.dec)).join("")}</tr>`;
    tsv.push([s.name, st.mean!=null?+st.mean.toFixed(4):"", d!=null?+d.toFixed(4):"", r!=null?+r.toFixed(1):"", ...sv.map(v=>v??"")]);
  });
  const tb = $("pfTbl"); tb.innerHTML = h + "</tbody>";
  tb.querySelectorAll("td[data-st]").forEach(x=>x.onclick=()=>toggleHl(x.dataset.st));
  cache.pfTsv = tsv;
}
