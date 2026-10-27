/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/17_경향분석.js] 경향 분석 화면
   하는 일 : 추세 검정·항목 간 상관·월별 분포·기준 초과율 화면
   주요 이름: renderAna, anaTrend, anaCorr, anaBox, anaExceed
   이럴 때 고침: 분석 화면 표시·설명 문구
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
registerView({ id:"ana", label:"경향 분석", kpi:false, item:()=>!["trend","corr"].includes(S.anaTab), render:()=>renderAna(),
  bind(){ $("anCopy").onclick=()=>copyText(tsvText(cache.anTsv||[])); }});
/* ═════════ 경향 분석 화면 ═════════ */
function renderAna(){
  document.querySelectorAll("#anTabs button").forEach(b=>{ b.setAttribute("aria-pressed", b.dataset.a===S.anaTab); b.onclick=()=>{ S.anaTab=b.dataset.a; refresh(); }; });
  $("anTop").innerHTML = ""; $("anFoot").innerHTML = ""; $("anNote").hidden = true;
  if(S.anaTab!=="exceed"){ $("anChart").style.height = ""; chartOn("anChart").resize(); }
  const names = selectedOrdered(), ms = months();
  if(!names.length){ $("anSub").textContent = "선택된 시료번호가 없습니다."; chartOn("anChart").clear(); $("anTbl").innerHTML=""; return; }
  ({trend:anaTrend, corr:anaCorr, box:anaBox, exceed:anaExceed})[S.anaTab](names, ms);
}
const LONG = () => months().length >= 24;
function pctOf(r){ if(!r.ok || !r.med) return null; return LONG() ? r.slope*12/r.med*100 : r.slope*(months().length-1)/r.med*100; }
function pctLabel(r){ const v = pctOf(r); return v==null ? "" : `${v<=-100?"≤-100":(v>0?"+":"")+Math.round(v)}%${LONG()?"/년":" (기간 전체)"}`; }
function anaTrend(names, ms){
  const res = {}; let up=0, dn=0;
  for(const n of names){ res[n] = {}; for(const it of ITEMS){ const r = mannKendall(series(n,it.code), ms); res[n][it.code] = r; if(r.ok && r.p<0.05){ r.slope>0?up++:dn++; } } }
  const anySeasonal = names.some(n=>ITEMS.some(i=>res[n][i.code].seasonal));
  $("anTitle").textContent = "추세 검정 (Mann-Kendall · Sen 기울기)";
  $("anSub").textContent = `${names.length}개 시료번호 × ${ITEMS.length}개 항목 · ${mLong(ms[0])}~${mLong(ms[ms.length-1])} · 유의(p<0.05) 증가 ${up}건 · 감소 ${dn}건`;
  $("anNote").hidden = false;
  $("anNote").innerHTML = `측정값이 시간에 따라 꾸준히 <b>증가·감소하는지</b>를 순위로 검정합니다(분포 가정 없음, 이상값에 강함). 칸의 숫자는 <b>Sen 기울기로 본 ${LONG()?"연간 변화율(%/년)":"기간 전체 변화율(%)"}</b>입니다(중앙값 대비). ${anySeasonal?"3년 이상 자료는 계절(월별) 검정을 적용했습니다.":`자료가 ${ms.length}개월뿐이라 <b>참고용</b>입니다(계절 변동과 추세를 구분하려면 3년 이상 자료 필요).`} 칸을 누르면 아래에 추세선이 그려집니다.`;
  const sel = S.anaCell && res[S.anaCell.st] && ITEMS.some(i=>i.code===S.anaCell.it) ? S.anaCell : {st:names[0], it:S.item};
  S.anaCell = sel;
  const cell = r => { if(!r.ok) return {bg:"", t:"–"}; const sig = r.p<0.05 ? 1 : r.p<0.1 ? .5 : 0;
    const c = r.slope>0 ? col("above") : col("below");
    return {bg: sig ? `background:color-mix(in oklab, ${c} ${sig===1?38:16}%, var(--panel))` : "", t: `${r.slope>0?"▲":r.slope<0?"▼":"–"} ${pctOf(r)==null?"":pctOf(r)<=-100?"≤-100%":(pctOf(r)>0?"+":"")+Math.round(pctOf(r))+"%"}`, sig}; };
  let h = `<thead><tr><th class="l stc">시료번호</th><th class="l">하천</th>${ITEMS.map(i=>`<th class="it">${i.code}</th>`).join("")}</tr></thead><tbody>`;
  const tsv = [["시료번호","하천",...ITEMS.flatMap(i=>[i.code+" 기울기(/월)", i.code+(LONG()?" %/년":" %/기간"), i.code+" p"])]];
  for(const n of names){ const st = stByName[n];
    h += `<tr><td class="l stc">${esc(n)}</td><td class="l rv">${esc(st.river)}</td>` + ITEMS.map(i=>{ const r = res[n][i.code], c = cell(r);
      return `<td class="c num ${sel.st===n&&sel.it===i.code?"sel":""}" style="${c.bg}" data-st="${esc(n)}" data-it="${i.code}" title="${r.ok?`n=${r.n} · τ=${r.tau.toFixed(2)} · p=${pTxt(r.p)} · ${fmt(r.slope,itemOf(i.code).dec+1)} ${itemOf(i.code).unit}/월`:"자료 부족"}">${c.t}</td>`; }).join("") + `</tr>`;
    tsv.push([n, st.river, ...ITEMS.flatMap(i=>{ const r=res[n][i.code]; return r.ok?[+r.slope.toFixed(5), pctOf(r)==null?"":+pctOf(r).toFixed(1), +r.p.toFixed(4)]:["","",""]; })]);
  }
  $("anTblTitle").textContent = "추세 행렬"; $("anTblSub").textContent = "진한 색 p<0.05 · 옅은 색 p<0.1 · 빨강=증가(악화 방향), 파랑=감소";
  const tb = $("anTbl"); tb.className = "dt mtx"; tb.innerHTML = h + "</tbody>";
  tb.querySelectorAll("td.c").forEach(x=>x.onclick=()=>{ S.anaCell={st:x.dataset.st, it:x.dataset.it}; renderAna(); $("anChart").scrollIntoView({behavior:"smooth", block:"center"}); });
  cache.anTsv = tsv;
  // 선택 칸 상세 그래프
  const it = itemOf(sel.it), r = res[sel.st][sel.it], v = series(sel.st, sel.it);
  const ink2 = css("--ink-2"), c = r.ok && r.slope>0 ? col("above") : col("below");
  const ch = chartOn("anChart");
  ch.setOption({animationDuration:300, textStyle:{fontFamily:css("--f-ui")}, grid:{left:56,right:28,top:70,bottom:36},
    title:{text:`${sel.st} · ${it.name}`, subtext: r.ok ? `Sen 기울기 ${fmt(r.slope,it.dec+1)} ${it.unit}/월 (${pctLabel(r)}) · Kendall τ ${r.tau.toFixed(2)} · p=${pTxt(r.p)} · n=${r.n} → ${r.p<0.05?(r.slope>0?"유의한 증가":"유의한 감소"):"유의한 추세 없음"}` : "자료가 4개 미만이라 검정할 수 없습니다",
      left:8, top:0, textStyle:{fontSize:13, color:css("--ink")}, subtextStyle:{color:ink2, fontSize:12}},
    tooltip:{trigger:"axis", backgroundColor:css("--panel"), borderColor:css("--line"), textStyle:{color:css("--ink")}},
    xAxis:{type:"category", data:ms.map(mLabel), boundaryGap:false, axisLabel:{color:ink2}, axisLine:{lineStyle:{color:css("--line")}}},
    yAxis:{type:"value", axisLabel:{color:ink2, fontFamily:css("--f-num")}, splitLine:{lineStyle:{color:css("--line-2")}}},
    series:[{name:"측정값", type:"line", data:v, connectNulls:S.opt.gaps, symbolSize:7, lineStyle:{color:css("--s1"), width:2}, itemStyle:{color:css("--s1")},
        label:{show:true, position:"top", formatter:p=>fmt(p.value,it.dec), color:ink2, fontSize:11}},
      ...(r.ok ? [{name:"Sen 추세선", type:"line", data: ms.map(m=>+(r.icpt + r.slope*M.indexOf(m)).toFixed(6)), symbol:"none", lineStyle:{color:c, type:[8,5], width:2.4}}] : [])]}, true);
  $("anFoot").innerHTML = `<span>Mann-Kendall: 모든 두 시점 쌍의 증감 부호를 세어 추세를 검정. Sen 기울기: 모든 쌍 기울기의 중앙값(이상값에 강함). 변화율 = 기울기×${LONG()?"12(연간)":"기간 개월 수"} ÷ 중앙값.</span>`;
}
function anaCorr(names, ms){
  const codes = ITEMS.map(i=>i.code), mi = ms.map(m=>M.indexOf(m));
  const pairs = (a,b)=>{ const x=[], y=[], who=[]; for(const n of names){ const va=D.values[n][a], vb=D.values[n][b]; for(const i of mi){ if(va[i]!=null && vb[i]!=null){ x.push(va[i]); y.push(vb[i]); who.push([n,M[i]]); } } } return {x,y,who}; };
  const R = {}; let best = null;
  codes.forEach(a=>{ R[a]={}; codes.forEach(b=>{ if(a===b){ R[a][b]={rho:1,n:0}; return; } const pr = pairs(a,b); R[a][b] = spearman(pr.x, pr.y);
    if(a<b && R[a][b].rho!=null && (!best || Math.abs(R[a][b].rho)>Math.abs(best.rho))) best = {a,b,rho:R[a][b].rho}; }); });
  if(!S.anaPair || !codes.includes(S.anaPair[0]) || !codes.includes(S.anaPair[1])) S.anaPair = best ? [best.a, best.b] : [codes[0], codes[1]];
  const [A,B] = S.anaPair, ia = itemOf(A), ib = itemOf(B), pr = pairs(A,B), sr = R[A][B];
  $("anTitle").textContent = "항목 간 상관 (Spearman 순위상관)";
  $("anSub").textContent = `${names.length}개 시료번호 · ${ms.length}개월 · 같은 시료·같은 달 값끼리 비교`;
  $("anNote").hidden = false;
  $("anNote").innerHTML = `두 항목이 <b>함께 오르내리는지</b> 봅니다(ρ: -1~+1). 예: SS·색도·T-P가 함께 높으면 강우 유출·토사 영향, BOD·TOC·T-N이 함께 높으면 생활·축산 오수 영향을 의심할 수 있습니다. 상관은 원인을 증명하지 않습니다. 아래 표의 칸을 누르면 산점도가 바뀝니다.`;
  $("anTop").innerHTML = `<div class="anrow"><label>x축 <select id="anA">${codes.map(c=>`<option ${c===A?"selected":""}>${c}</option>`).join("")}</select></label>
    <label>y축 <select id="anB">${codes.map(c=>`<option ${c===B?"selected":""}>${c}</option>`).join("")}</select></label>
    <label><input type="checkbox" id="anLog" ${S.anaLog?"checked":""}> 로그 축</label>
    <span>ρ = <b class="num">${sr.rho==null?"-":sr.rho.toFixed(2)}</b> · p = ${pTxt(sr.p)} · n = ${sr.n}</span></div>`;
  $("anA").onchange=e=>{ S.anaPair=[e.target.value,B]; renderAna(); }; $("anB").onchange=e=>{ S.anaPair=[A,e.target.value]; renderAna(); };
  $("anLog").onchange=e=>{ S.anaLog=e.target.checked; renderAna(); };
  const plan = colorPlan(names), byS = {};
  pr.who.forEach(([n,m],k)=>{ (byS[n] ||= []).push([pr.x[k], pr.y[k], m]); });
  const lx = S.anaLog ? pr.x.map(v=>Math.log10(Math.max(v,1e-6))) : pr.x, ly = S.anaLog ? pr.y.map(v=>Math.log10(Math.max(v,1e-6))) : pr.y;
  const n = lx.length, mx = lx.reduce((a,b)=>a+b,0)/n, my = ly.reduce((a,b)=>a+b,0)/n;
  let sxy=0, sxx=0; for(let i=0;i<n;i++){ sxy+=(lx[i]-mx)*(ly[i]-my); sxx+=(lx[i]-mx)**2; }
  const k = sxx? sxy/sxx : 0, c0 = my - k*mx, xs = [Math.min(...lx), Math.max(...lx)];
  const fit = xs.map(x=>S.anaLog ? [10**x, 10**(c0+k*x)] : [x, c0+k*x]);
  const ink2 = css("--ink-2");
  chartOn("anChart").setOption({animationDuration:300, textStyle:{fontFamily:css("--f-ui")}, grid:{left:64,right:28,top:40,bottom:48},
    tooltip:{trigger:"item", backgroundColor:css("--panel"), borderColor:css("--line"), textStyle:{color:css("--ink")},
      formatter:p=>p.seriesName==="추세선"?"":`<b>${esc(p.seriesName)}</b> ${mLong(p.data[2])}<br>${A} ${fmt(p.data[0],ia.dec)} · ${B} ${fmt(p.data[1],ib.dec)}`},
    xAxis:{type:S.anaLog?"log":"value", name:`${A} (${ia.unit})`, nameLocation:"middle", nameGap:28, axisLabel:{color:ink2}, splitLine:{lineStyle:{color:css("--line-2")}}},
    yAxis:{type:S.anaLog?"log":"value", name:`${B} (${ib.unit})`, axisLabel:{color:ink2}, splitLine:{lineStyle:{color:css("--line-2")}}},
    series:[...names.filter(n=>byS[n]).map(nm=>({name:nm, type:"scatter", data:byS[nm], symbolSize: plan[nm].hl?11:8,
        itemStyle:{color:plan[nm].color, opacity: plan[nm].emph?0.85:0.45, borderColor:css("--panel"), borderWidth:1}})),
      {name:"추세선", type:"line", data:fit, symbol:"none", lineStyle:{color:css("--ink"), type:[6,4], width:1.6}, silent:true}]}, true);
  // 상관 행렬 표
  let h = `<thead><tr><th class="l"></th>${codes.map(c=>`<th class="it">${c}</th>`).join("")}</tr></thead><tbody>`;
  const tsv = [["", ...codes]];
  codes.forEach(a=>{ h += `<tr><th class="l">${a}</th>` + codes.map(b=>{ const r = R[a][b];
      if(a===b) return `<td class="c" style="color:var(--ink-3)">–</td>`;
      const v = r.rho, cc = v>0 ? col("above") : col("below"), w = v==null?0:Math.round(Math.abs(v)*55);
      return `<td class="c num ${(a===A&&b===B)?"sel":""}" data-a="${a}" data-b="${b}" style="${v==null?"":`background:color-mix(in oklab, ${cc} ${w}%, var(--panel))`}" title="n=${r.n} · p=${pTxt(r.p)}">${v==null?"":v.toFixed(2)}${r.p!=null&&r.p<0.05?"*":""}</td>`; }).join("") + `</tr>`;
    tsv.push([a, ...codes.map(b=>a===b?1:(R[a][b].rho==null?"":+R[a][b].rho.toFixed(3)))]); });
  $("anTblTitle").textContent = "상관 행렬 (Spearman ρ)"; $("anTblSub").textContent = "* p<0.05 · 빨강=같은 방향, 파랑=반대 방향 · 칸을 누르면 산점도";
  const tb = $("anTbl"); tb.className = "dt mtx"; tb.innerHTML = h + "</tbody>";
  tb.querySelectorAll("td.c[data-a]").forEach(x=>x.onclick=()=>{ S.anaPair=[x.dataset.a, x.dataset.b]; renderAna(); $("anChart").scrollIntoView({behavior:"smooth", block:"center"}); });
  cache.anTsv = tsv;
  $("anFoot").innerHTML = `<span>점 색 = 시료번호(왼쪽 패널 색과 같음). 점선 = ${S.anaLog?"로그 축 기준 ":""}최소제곱 추세선.</span>`;
}
function anaBox(names, ms){
  const it = itemOf(S.item), plan = colorPlan(names);
  const boxes = ms.map((m,i)=>{ const v = names.map(n=>series(n,S.item)[i]).filter(x=>x!=null); return v.length ? quart(v) : null; });
  const meds = boxes.map(b=>b?b.box[2]:null), peak = meds.indexOf(Math.max(...meds.filter(x=>x!=null)));
  $("anTitle").textContent = `월별 분포 · ${it.name}`;
  $("anSub").textContent = `${names.length}개 시료번호의 달마다 값 분포(상자 = 중간 50%, 가로선 = 중앙값)`;
  $("anNote").hidden = false;
  $("anNote").innerHTML = `달마다 전체 시료번호의 값이 어떻게 퍼져 있는지 봅니다. 중앙값이 가장 높은 달은 <b>${peak>=0?mLong(ms[peak]):"-"}</b>입니다. 상자가 함께 올라가면 수계 전체에 영향을 준 요인(강우·계절)을, 점 하나만 튀면 그 시료번호의 국지적 요인을 의심할 수 있습니다. ☆ 강조한 시료번호는 선으로 겹쳐 그립니다.`;
  const ink2 = css("--ink-2"), outs = [];
  boxes.forEach((b,i)=>{ if(!b) return; const [lo,,,,hi] = b.box; names.forEach(n=>{ const v = series(n,S.item)[i]; if(v!=null && (v<lo || v>hi)) outs.push([i, v, n]); }); });
  const hl = names.filter(n=>S.hl.has(n));
  chartOn("anChart").setOption({animationDuration:300, textStyle:{fontFamily:css("--f-ui")}, grid:{left:56,right:28,top:20,bottom:36},
    tooltip:{trigger:"item", backgroundColor:css("--panel"), borderColor:css("--line"), textStyle:{color:css("--ink")},
      formatter:p=>{ if(p.seriesType==="boxplot"){ const d=p.data.slice(-5); return `${mLong(ms[p.dataIndex])}<br>최대 ${fmt(d[4],it.dec)}<br>Q3 ${fmt(d[3],it.dec)}<br>중앙값 <b>${fmt(d[2],it.dec)}</b><br>Q1 ${fmt(d[1],it.dec)}<br>최소 ${fmt(d[0],it.dec)}`; }
        if(p.seriesName==="이상치") return `${esc(p.data[2])} · ${mLong(ms[p.data[0]])}<br>${fmt(p.data[1],it.dec)} ${it.unit}`;
        return `${esc(p.seriesName)} ${fmt(p.value,it.dec)}`; }},
    xAxis:{type:"category", data:ms.map(mLabel), axisLabel:{color:ink2}, axisLine:{lineStyle:{color:css("--line")}}},
    yAxis:{type:S.opt.scale==="log"?"log":"value", axisLabel:{color:ink2, fontFamily:css("--f-num")}, splitLine:{lineStyle:{color:css("--line-2")}}},
    series:[{name:"분포", type:"boxplot", data:boxes.map(b=>b?b.box:[null,null,null,null,null]), itemStyle:{color:css("--q100"), borderColor:css("--q550"), borderWidth:1.5}},
      {name:"이상치", type:"scatter", data:outs, symbolSize:8, itemStyle:{color:col("spike")}, label:{show:true, position:"right", formatter:p=>p.data[2], fontSize:10.5, color:ink2}, labelLayout:{hideOverlap:true}},
      ...hl.map(n=>({name:n, type:"line", data:series(n,S.item), connectNulls:S.opt.gaps, symbolSize:6, lineStyle:{color:plan[n].color, width:2.2}, itemStyle:{color:plan[n].color}}))]}, true);
  let h = `<thead><tr><th class="l">월</th><th>n</th><th>최소</th><th>Q1</th><th>중앙값</th><th>Q3</th><th>최대</th><th class="l">이상치(1.5×IQR 밖)</th></tr></thead><tbody>`;
  const tsv = [["월","n","최소","Q1","중앙값","Q3","최대","이상치"]];
  ms.forEach((m,i)=>{ const b = boxes[i]; const v = names.map(n=>series(n,S.item)[i]).filter(x=>x!=null); const o = outs.filter(x=>x[0]===i);
    h += `<tr><td class="l">${mLong(m)}</td><td class="num">${v.length}</td>${b?b.box.map((x,k)=>`<td class="num ${k===2?"stat":""}">${fmt(x,it.dec)}</td>`).join(""):"<td colspan=5></td>"}<td class="l">${o.map(x=>`${esc(x[2])} ${fmt(x[1],it.dec)}`).join(", ")}</td></tr>`;
    tsv.push([m, v.length, ...(b?b.box.map(x=>+x.toFixed(4)):["","","","",""]), o.map(x=>`${x[2]} ${x[1]}`).join(", ")]); });
  $("anTblTitle").textContent = "월별 요약 통계"; $("anTblSub").textContent = `${it.unit} · 상자그림(Tukey) 기준`;
  const tb = $("anTbl"); tb.className = "dt"; tb.innerHTML = h + "</tbody>";
  cache.anTsv = tsv;
}
function anaExceed(names, ms){
  const it = itemOf(S.item), L = (D.limits[S.item]||[]).filter(l=>l.max!=null), t = targetOf(S.item);
  const opts = [...(t!=null?[{k:"t", v:t, label:`목표 ${t} 초과`}]:[]), ...L.filter((l,i,a)=>a.findIndex(x=>x.max===l.max)===i).map(l=>({k:"g"+l.code, v:l.max, label:`${l.code}(${l.name}) 상한 ${l.max} 초과`}))];
  let thr = S.exThr && S.exThr.item===S.item ? S.exThr.v : (opts.find(o=>o.k==="t") || opts.find(o=>o.k==="gII") || opts[0] || {v:null}).v;
  if(thr==null){ const all = names.flatMap(n=>series(n,S.item)).filter(v=>v!=null).sort((a,b)=>a-b); thr = all.length ? +all[Math.floor(all.length*.75)].toPrecision(3) : 0; }
  $("anTitle").textContent = `기준 초과율 · ${it.name}`;
  $("anSub").textContent = `${names.length}개 시료번호 · ${ms.length}개월 · 기준 ${thr} ${it.unit} 초과 횟수 ÷ 측정 횟수`;
  $("anNote").hidden = false;
  $("anNote").innerHTML = `평균만 보면 가려지는 <b>얼마나 자주 기준을 넘는지</b>를 봅니다. 평균은 낮아도 초과율이 높은 시료번호는 간헐적 오염원(비점·방류)을 점검할 대상입니다.`;
  $("anTop").innerHTML = `<div class="anrow"><label>기준 <select id="exSel">${opts.map(o=>`<option value="${o.v}" ${o.v===thr?"selected":""}>${esc(o.label)}</option>`).join("")}<option value="custom" ${opts.some(o=>o.v===thr)?"":"selected"}>직접 입력</option></select></label>
    <label>값 <input type="number" id="exVal" step="any" value="${thr}"> ${it.unit}</label></div>`;
  $("exSel").onchange=e=>{ if(e.target.value!=="custom"){ S.exThr={item:S.item, v:+e.target.value}; renderAna(); } else $("exVal").focus(); };
  $("exVal").onchange=e=>{ S.exThr={item:S.item, v:+e.target.value}; renderAna(); };
  const rows = names.map(n=>{ const v = series(n,S.item).filter(x=>x!=null), ex = v.filter(x=>x>thr).length; return {n, cnt:v.length, ex, r: v.length? ex/v.length*100 : null, mean: stats(v).mean}; })
    .filter(r=>r.cnt).sort((a,b)=>b.r-a.r || b.mean-a.mean);
  const plan = colorPlan(names), ink2 = css("--ink-2");
  const el = $("anChart"); el.style.height = Math.max(320, rows.length*20 + 60) + "px"; chartOn("anChart").resize();
  chartOn("anChart").setOption({animationDuration:300, textStyle:{fontFamily:css("--f-ui")}, grid:{left:96,right:60,top:10,bottom:30},
    tooltip:{trigger:"axis", axisPointer:{type:"shadow"}, backgroundColor:css("--panel"), borderColor:css("--line"), textStyle:{color:css("--ink")},
      formatter:ps=>{ const r = rows[rows.length-1-ps[0].dataIndex]; return `<b>${esc(r.n)}</b><br>초과 ${r.ex}/${r.cnt}회 (${r.r.toFixed(0)}%)<br>기간 평균 ${fmt(r.mean,it.dec)} ${it.unit}`; }},
    xAxis:{type:"value", max:100, axisLabel:{formatter:"{value}%", color:ink2}, splitLine:{lineStyle:{color:css("--line-2")}}},
    yAxis:{type:"category", data:rows.map(r=>r.n).reverse(), axisLabel:{color:ink2}, axisTick:{show:false}},
    series:[{type:"bar", data:rows.map(r=>({value:+r.r.toFixed(1), itemStyle:{color: r.r>=50 ? col("above") : r.r>0 ? css("--q400") : css("--line"), borderRadius:[0,4,4,0]}})).reverse(), barMaxWidth:14,
      label:{show:true, position:"right", formatter:p=>`${p.value.toFixed(0)}%`, color:ink2, fontSize:11}}]}, true);
  let h = `<thead><tr><th class="l stc">시료번호</th><th class="l">하천</th><th>측정</th><th>초과</th><th>초과율</th><th>기간 평균</th><th class="l">초과한 달</th></tr></thead><tbody>`;
  const tsv = [["시료번호","하천","측정","초과","초과율(%)","기간 평균","초과한 달"]];
  for(const r of rows){ const exm = ms.filter((m,i)=>{ const v = series(r.n,S.item)[i]; return v!=null && v>thr; });
    h += `<tr class="${S.hl.has(r.n)?"hl":""}"><td class="l stc" data-st="${esc(r.n)}"><span class="dot" style="background:${plan[r.n].color}"></span>${esc(r.n)}</td><td class="l">${esc(stByName[r.n].river)}</td><td class="num">${r.cnt}</td><td class="num">${r.ex}</td><td class="num stat ${r.r>=50?"up":""}"><b>${r.r.toFixed(0)}%</b></td><td class="num">${fmt(r.mean,it.dec)}</td><td class="l">${exm.map(mLabel).join(" ")}</td></tr>`;
    tsv.push([r.n, stByName[r.n].river, r.cnt, r.ex, +r.r.toFixed(1), r.mean!=null?+r.mean.toFixed(4):"", exm.join(" ")]); }
  $("anTblTitle").textContent = "시료번호별 초과율"; $("anTblSub").textContent = `기준 ${thr} ${it.unit} 초과`;
  const tb = $("anTbl"); tb.className = "dt"; tb.innerHTML = h + "</tbody>";
  tb.querySelectorAll("td[data-st]").forEach(x=>x.onclick=()=>toggleHl(x.dataset.st));
  cache.anTsv = tsv;
}
