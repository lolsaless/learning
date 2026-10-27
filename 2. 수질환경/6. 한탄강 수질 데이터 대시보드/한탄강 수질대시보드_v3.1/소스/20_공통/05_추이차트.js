/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_공통/05_추이차트.js] 공통 추이 그래프
   하는 일 : 시계열·연도별·배너·인쇄가 함께 쓰는 꺾은선 그래프(▲▼·라벨·평균선·기준선·특이 경향 선), 툴팁, 범례
   주요 이름: trendOption, tooltipHtml, legendHtml, pct
   이럴 때 고침: 선 굵기·점 모양·라벨·기준선 표시 방식
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ═════════ 공통 추이 차트(시계열·연도별·배너·인쇄) ═════════ */
function pct(arr, p){ const v = arr.filter(x=>x!=null).sort((a,b)=>a-b); if(!v.length) return null; return v[Math.min(v.length-1, Math.floor(p*(v.length-1)))]; }
function trendOption({cats, mkeys, rows, item, dec, unit, plan, compact=false, force}){
  const o = Object.assign({}, S.opt, force||{});
  const ink = css("--ink"), ink2 = css("--ink-2"), ink3 = css("--ink-3"), line = css("--line"), panel = css("--panel");
  const above = col("above"), below = col("below"), warn = css("--warn"), qout = css("--qc-out");
  const names = rows.map(r=>r.name);
  if(!plan){ const pf = planFor(rows); plan = pf.plan; }
  const emphN = names.filter(n=>plan[n].emph).length;
  const all = rows.flatMap(r=>r.values);
  // y축: 이상치 자르기
  let cap = null;
  if(o.scale==="clip"){ const p = pct(all,.95), mx = Math.max(...all.filter(x=>x!=null)); if(p!=null && mx > p*1.6) cap = +(p*1.25).toPrecision(2); }
  const log = o.scale==="log";
  const ser = [], spikes = {};
  if(o.spike) for(const r of rows){ const sp = spikeOf(r.values); if(sp.z >= o.spikeZ) spikes[r.name] = sp; }
  for(const r of rows){
    const p0 = plan[r.name], sp = spikes[r.name];
    const p = sp && p0.dim ? {...p0, color: col("spike"), dim:false, emph:true} : p0;
    const userEmph = p0.hl || (p0.emph && !sp);
    const st = stats(r.values);
    const mk = o.band!=="off" && p.emph;
    const lastIdx = r.values.reduce((a,v,i)=>v!=null?i:a,-1);
    const labMode = o.labels==="off" ? "off" : (p.emph && (emphN<=6 || p.hl || sp || o.labels==="all")) ? o.labels : "off";
    let isolated = false;
    const data = r.values.map((v,i)=>{
      if(v==null || (log && v<=0)) return {value:null};
      if(!o.gaps && (r.values[i-1]==null) && (r.values[i+1]==null)) isolated = true;
      const c = cls(v, st), q = mkeys ? qcTop(r.name, mkeys[i], item) : null, lq = mkeys ? loqText(r.name, mkeys[i], item) : null;
      const clipped = cap!=null && v>cap;
      const d = {value: clipped?cap:v, _raw:v, _c:c, _q:q, _lq:lq};
      const qShow = q && (p.emph || q.type==="outlier");
      if(mk || qShow || clipped){
        const up = c==="up", dn = c==="dn";
        d.symbol = clipped ? "pin" : (up||dn ? "triangle" : "circle");
        d.symbolRotate = dn ? 180 : 0;
        d.symbolSize = clipped ? 20 : (up||dn ? 11 : (mk?6:7));
        d.itemStyle = {color: up?above:dn?below:p.color, borderColor: qShow ? (q.type==="outlier"?qout:warn) : panel,
                       borderWidth: qShow?2.5:1.5, borderType: qShow ? (q.type==="outlier"?"dotted":"dashed") : "solid"};
      }
      if(sp && i===sp.i){
        d.symbol = clipped ? "pin" : "diamond"; d.symbolRotate = 0; d.symbolSize = clipped ? 22 : 16;
        d.itemStyle = {color:col("spike"), borderColor:panel, borderWidth:2, shadowBlur:10, shadowColor:col("spike")};
      }
      const showLab = clipped || (sp && i===sp.i && labMode!=="off") || (labMode==="all") || (labMode==="auto" && (c!=="in" || i===lastIdx || qShow));
      if(showLab) d.label = {show:true, position: clipped?"left":c==="dn"?"bottom":"top", distance:6,
        formatter: (sp && i===sp.i?"⚡":"") + (clipped?"↑":"") + (lq || fmt(v,dec)), color: c==="up"?above:c==="dn"?below:ink2, fontSize:11, fontFamily:css("--f-num")};
      return d;
    });
    const s = {
      name:r.name, type:"line", data, connectNulls:!!o.gaps, smooth:false,
      showSymbol: true, symbol: p.ring2 ? "rect" : ((mk||isolated) ? "circle" : "none"), symbolSize: p.ring2 ? 6 : (mk?6:(isolated?4:0)),
      lineStyle:{width: (p.hl ? 3.4 : p.emph ? (emphN>16?2.4:2) : 1.3) + (sp?1:0), color:p.color, opacity: p.dim ? 0.55 : 1,
        type: sp ? [10,5] : "solid", shadowBlur: sp ? 12 : 0, shadowColor: sp ? col("spike") : "transparent"},
      itemStyle:{color:p.color, opacity: p.dim && !mk ? .6 : 1},
      z: p.hl ? 7 : sp ? 6 : p.emph ? 5 : 2, emphasis:{focus:"series", lineStyle:{width:3.6}}, labelLayout:{hideOverlap:true}, clip:true
    };
    if(o.mean && userEmph && st.n && emphN<=3){
      const b = band(st);
      s.markLine = {silent:true, symbol:"none", data:[{yAxis:st.mean, lineStyle:{color:p.color, type:[4,4], width:1.2},
        label:{show:true, position:"insideEndTop", formatter:`평균 ${fmt(st.mean,dec)}`, color:ink2, fontSize:11}}]};
      if(b && b[1]>b[0] && emphN<=2) s.markArea = {silent:true, itemStyle:{color:p.color, opacity:.08},
        data:[[{yAxis: log? Math.max(b[0], st.min*0.9) : b[0]}, {yAxis:b[1]}]]};
    }
    ser.push(s);
  }
  if(o.limits){
    const L = (D.limits[item]||[]).filter(l=>l.max!=null), t = targetOf(item);
    const vmax = cap ?? Math.max(...all.filter(x=>x!=null), 0);
    const seen = new Set(), lines = [];
    L.forEach(l=>{ if(seen.has(l.max)) return; seen.add(l.max); if(l.max <= vmax*1.15) lines.push({yAxis:l.max, label:{formatter:`${l.code} ≤${l.max}`}}); });
    if(t!=null) lines.push({yAxis:t, lineStyle:{color:css("--accent"), type:"solid", width:1.4}, label:{formatter:`목표 ${t}`, color:css("--accent"), fontWeight:600}});
    if(lines.length) ser.push({name:"__limits", type:"line", data:[], silent:true, tooltip:{show:false},
      markLine:{silent:true, symbol:"none", lineStyle:{color:ink3, type:[2,4], width:1}, label:{position:"insideStartTop", color:ink3, fontSize:10.5}, data:lines}});
  }
  const means = Object.fromEntries(rows.map(r=>[r.name, stats(r.values)]));
  return {
    animationDuration:350, animationDurationUpdate:250,
    grid: compact ? {left:44,right:14,top:24,bottom:26} : {left:56, right:28, top:30, bottom: cats.length>24?64:36},
    textStyle:{fontFamily:css("--f-ui")},
    tooltip:{trigger:"axis", confine:true, backgroundColor:panel, borderColor:line, textStyle:{color:ink,fontSize:12},
      axisPointer:{type:"line", lineStyle:{color:ink3, type:"dashed"}},
      formatter: ps => tooltipHtml(ps, cats, dec, unit, plan, means)},
    xAxis:{type:"category", data:cats, boundaryGap:false, axisLine:{lineStyle:{color:line}}, axisTick:{show:false}, axisLabel:{color:ink2, fontFamily:css("--f-num")}},
    yAxis:{type: log?"log":"value", logBase:10, max: cap ?? undefined, splitLine:{lineStyle:{color:css("--line-2")}},
      axisLabel:{color:ink2, fontFamily:css("--f-num")}},
    dataZoom: cats.length>24 ? [{type:"inside"},{type:"slider", height:18, bottom:8}] : [{type:"inside"}],
    series:ser, _cap:cap, _spikes:spikes, _plan:plan
  };
}
function tooltipHtml(ps, cats, dec, unit, plan, means){
  ps = ps.filter(p=>p.seriesName!=="__limits" && p.data && p.data._raw!=null);
  if(!ps.length) return "";
  const idx = ps[0].dataIndex;
  const rows = ps.map(p=>({n:p.seriesName, v:p.data._raw, c:p.color||plan[p.seriesName]?.color, e:plan[p.seriesName]?.emph||plan[p.seriesName]?.hl, k:p.data._c, q:p.data._q, lq:p.data._lq}));
  rows.sort((a,b)=> (b.e-a.e) || (b.v-a.v));
  const lim = 14, more = rows.length - lim, ab = col("above"), be = col("below");
  const lines = rows.slice(0,lim).map(r=>{
    const g = r.k==="up"?`<span style="color:${ab}">▲</span>`:r.k==="dn"?`<span style="color:${be}">▼</span>`:"";
    const q = r.q ? ` <span style="color:${r.q.type==="outlier"?css("--qc-out"):css("--warn")}">${QC_LABEL[r.q.type]}</span>` : "";
    return `<div style="display:flex;gap:8px;align-items:center;${r.e?"font-weight:600":""}"><span style="width:10px;height:3px;background:${r.c};border-radius:2px"></span><span style="flex:1">${esc(r.n)}${q}</span><span style="font-family:${css("--f-num")}">${r.lq||fmt(r.v,dec)}</span>${g}</div>`;
  }).join("");
  const one = rows.length===1 && means[rows[0].n]?.n ? `<div style="color:${css("--ink-3")};margin-top:4px">평균 ${fmt(means[rows[0].n].mean,dec)} · ${bandText()||"판정 끔"}</div>` : "";
  return `<div style="min-width:190px"><div style="color:${css("--ink-3")};margin-bottom:4px">${cats[idx]} · ${unit}</div>${lines}${more>0?`<div style="color:${css("--ink-3")}">외 ${more}개 지점</div>`:""}${one}</div>`;
}
function legendHtml(el, names, plan, spikes){
  spikes = spikes || {};
  const emph = names.filter(n=>plan[n].emph), rest = names.length - emph.length;
  let h = emph.map(n=>`<button class="li" data-st="${esc(n)}" title="눌러서 강조 전환"><span class="ln" style="background:${plan[n].color};${plan[n].hl?"height:5px":""}"></span>${plan[n].ring2?"▪":""}${esc(n)}${spikes[n]?' <span class="spkchip">⚡</span>':""}</button>`).join("");
  if(rest>0) h += `<span class="li muted"><span class="ln" style="background:${col("base")}"></span>그 밖의 시료번호 ${rest}개</span>`;
  const spk = Object.keys(spikes);
  if(spk.length) h += `<span class="li muted"><span class="ln" style="background:repeating-linear-gradient(90deg,${col("spike")} 0 6px,transparent 6px 9px)"></span><b class="spkchip">⚡ 특이 경향 ${spk.length}</b>(z≥${S.opt.spikeZ}): ${spk.map(n=>`<button class="li" style="padding:0 2px" data-st="${esc(n)}" title="z=${spikes[n].z.toFixed(1)} · 눌러서 강조">${esc(n)}</button>`).join("")}</span>`;
  if(S.opt.band!=="off") h += `<span class="li muted"><span style="color:${col("above")}">▲</span>${bandText()}보다 높음 <span style="color:${col("below")}">▼</span>낮음</span>`;
  el.innerHTML = h;
  el.querySelectorAll(".li[data-st]").forEach(x=>x.onclick=()=>toggleHl(x.dataset.st));
}
