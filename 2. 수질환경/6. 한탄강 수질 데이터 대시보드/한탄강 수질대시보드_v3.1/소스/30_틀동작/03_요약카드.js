/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [30_틀동작/03_요약카드.js] 요약 카드(KPI)
   하는 일 : 상단 요약 카드 5개(최근월·최고 지점·최고값·기준·점검)
   주요 이름: renderKpis
   이럴 때 고침: 요약 카드 내용
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ═════════ KPI ═════════ */
function renderKpis(){
  const it = itemOf(S.item), names = selectedOrdered(), ms = months(), el = $("kpis");
  if(!names.length){ el.innerHTML = `<div class="kpi" style="grid-column:1/-1"><div class="k">선택된 지점이 없습니다</div><div class="s">왼쪽에서 지점을 선택하세요.</div></div>`; return; }
  // 1) 최근 측정월
  let li = -1; for(let i=ms.length-1;i>=0;i--) if(names.some(n=>series(n,S.item)[i]!=null)){ li=i; break; }
  let t1 = `<div class="k">최근 측정월</div><div class="v">-</div>`;
  if(li>=0){
    const cur = names.map(n=>series(n,S.item)[li]).filter(v=>v!=null), cm = stats(cur).mean;
    let sub = `${cur.length}개 지점 평균`;
    if(li>0){ let up=0, dn=0, dsum=0, dn_=0;
      names.forEach(n=>{ const a=series(n,S.item)[li-1], b=series(n,S.item)[li]; if(a!=null&&b!=null){ dsum+=b-a; dn_++; if(b>a) up++; else if(b<a) dn++; } });
      if(dn_){ const d = dsum/dn_; sub = `전월 대비 <b class="${d>0?"up":d<0?"dn":""}">${d>0?"+":""}${fmt(d,it.dec)}</b> · 상승 ${up} · 하락 ${dn}`; } }
    t1 = `<div class="k">${mLong(ms[li])} 평균 (${it.code})</div><div class="v num">${fmt(cm,it.dec)}<small>${it.unit}</small></div><div class="s">${sub}</div>`;
  }
  // 2) 기간 평균 최고 지점
  const ranked = names.map(n=>({n, s:stats(series(n,S.item))})).filter(x=>x.s.n).sort((a,b)=>b.s.mean-a.s.mean);
  const top = ranked[0];
  const t2 = `<div class="k">기간 평균이 가장 높은 지점</div><div class="v">${top?esc(top.n):"-"} <small class="num">${top?fmt(top.s.mean,it.dec)+" "+it.unit:""}</small></div><div class="s">${ranked[1]?`2위 ${esc(ranked[1].n)} ${fmt(ranked[1].s.mean,it.dec)}`:""}</div>`;
  // 3) 단일 최고값
  let mx = {v:-Infinity};
  names.forEach(n=>series(n,S.item).forEach((v,i)=>{ if(v!=null && v>mx.v) mx={v,n,m:ms[i]}; }));
  const mq = mx.n ? qcTop(mx.n, mx.m, S.item) : null;
  const t3 = `<div class="k">단일 최고값</div><div class="v num">${mx.n?fmt(mx.v,it.dec):"-"}<small>${it.unit}</small></div><div class="s">${mx.n?esc(mx.n)+" · "+mLong(mx.m):""}${mq?` · <span class="t-${mq.type}">${QC_LABEL[mq.type]}</span>`:""}</div>`;
  // 4) 기준
  let t4; const t = targetOf(S.item), L = D.limits[S.item];
  if(t!=null){ const ok = ranked.filter(x=>x.s.mean<=t).length;
    t4 = `<div class="k">목표(${t}${it.unit}) 달성 지점</div><div class="v num">${ok}<small>/ ${ranked.length}</small></div><div class="s">지점별 기간 평균 기준</div>`; }
  else if(L && L.length){ const cnt = {}; ranked.forEach(x=>{ const g = grade(S.item, x.s.mean); if(g) cnt[g.i]=(cnt[g.i]||0)+1; });
    const good = Object.entries(cnt).filter(([i])=>+i<=2).reduce((a,[,c])=>a+c,0);
    t4 = `<div class="k">II등급(약간좋음) 이상 지점</div><div class="v num">${good}<small>/ ${ranked.length}</small></div><div class="s">${Object.entries(cnt).sort((a,b)=>a[0]-b[0]).map(([i,c])=>`${L[i].code} ${c}`).join(" · ")}</div>`; }
  else t4 = `<div class="k">생활환경기준</div><div class="v" style="font-size:15px;padding-top:6px">해당 없음</div><div class="s">${esc(it.desc||"")}</div>`;
  // 5) 자료 점검
  const nameSet = new Set(names), mset = new Set(ms);
  const qs = D.qc.filter(q=>q.type!=="coord" && nameSet.has(q.st) && mset.has(q.m) && (q.item===S.item || q.item==null));
  const byT = {}; qs.forEach(q=>byT[q.type]=(byT[q.type]||0)+1);
  const t5 = `<div class="k">자료 점검 (${it.code})</div><div class="v num">${qs.length}<small>건</small></div><div class="s">${Object.entries(byT).map(([k,v])=>`${QC_LABEL[k]} ${v}`).join(" · ")||"점검할 값 없음"}</div>`;
  el.innerHTML = `<div class="kpi">${t1}</div><div class="kpi">${t2}</div><div class="kpi">${t3}</div><div class="kpi">${t4}</div><div class="kpi click ${qs.length?"warn":""}" id="kpiQc" title="자료 점검 화면으로">${t5}</div>`;
  $("kpiQc").onclick = ()=>{ S.qcFilter="all"; setView("qc"); };
}
