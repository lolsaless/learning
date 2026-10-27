/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_공통/04_색상_특이경향.js] 색 배정·특이 경향
   하는 일 : 시료번호별 색 자동 배정(16색), 무작위 재배정, ⚡ 특이 경향(로버스트 z) 계산
   주요 이름: colorPlan, reassignColors, spikeOf, planFor, spikeSet
   이럴 때 고침: 색 배정 규칙, 특이 경향 판정식
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ═════════ 색 배정: 색은 지점을 따라간다 ═════════ */
function selectedOrdered(){ return ST.filter(s=>S.sel.has(s.name)).map(s=>s.name); }
function colorPlan(names, extra){
  extra = extra || {};
  /* 16개 이하: 시료번호마다 고유 색(9~16번째는 같은 색 계열의 진한/연한 색 + 네모 표식)
     17개 이상: ☆ 강조한 시료번호만 색, 나머지는 기본 회색 선 */
  const many = names.length > 16;
  const needs = names.filter(n => !many || S.hl.has(n) || extra[n]);
  for(const k of Object.keys(S.slots)) if(!needs.includes(k)) delete S.slots[k];
  const perm = (S.slotPerm && S.slotPerm.length===16) ? S.slotPerm : [...Array(16).keys()];
  const used = new Set(Object.values(S.slots));
  for(const n of needs){ if(S.slots[n]==null){ const f = perm.find(i=>!used.has(i)); S.slots[n] = f ?? (Object.keys(S.slots).length % 16); used.add(S.slots[n]); } }
  const pal = PAL(), base = col("base");
  const out = {};
  for(const n of names){
    const hl = S.hl.has(n), emph = many ? (hl || !!extra[n]) : true;
    const c = S.custom[n] || (S.slots[n]!=null ? pal[S.slots[n]] : base);
    out[n] = {color: emph ? c : base, emph, hl, dim: !emph, ring2: !S.custom[n] && S.slots[n]>=8};
  }
  return out;
}
function reassignColors(names, random){
  for(const n of names) delete S.slots[n];
  const p = [...Array(16).keys()];
  if(random){ for(let i=p.length-1;i>0;i--){ const j = Math.floor(Math.random()*(i+1)); [p[i],p[j]]=[p[j],p[i]]; } }
  S.slotPerm = p;
}
/* ⚡ 특이 경향(급변): 기간 안에서 지점 중앙값 대비 로버스트 z 최대값 */
function spikeOf(values){
  const v = values.filter(x=>x!=null); if(v.length<5) return {z:0, i:-1};
  const sorted = v.slice().sort((a,b)=>a-b), med = sorted[Math.floor((sorted.length-1)/2)]*0.5 + sorted[Math.ceil((sorted.length-1)/2)]*0.5;
  const dev = v.map(x=>Math.abs(x-med)).sort((a,b)=>a-b);
  let mad = dev[Math.floor((dev.length-1)/2)]*0.5 + dev[Math.ceil((dev.length-1)/2)]*0.5;
  if(!mad) mad = dev.reduce((a,b)=>a+b,0)/dev.length || 0;
  if(!mad) return {z:0, i:-1};
  let z = 0, idx = -1;
  values.forEach((x,i)=>{ if(x==null) return; const zz = Math.abs(0.6745*(x-med)/mad); if(zz>z){ z=zz; idx=i; } });
  return {z, i:idx, med};
}
/* 색 배정 + 특이 경향을 함께 계산 (지점이 많을 때 특이 경향 지점도 고유 색을 받음) */
function planFor(rows){
  const spikes = {};
  if(S.opt.spike) for(const r of rows){ const sp = spikeOf(r.values); if(sp.z >= S.opt.spikeZ) spikes[r.name] = sp; }
  return {plan: colorPlan(rows.map(r=>r.name), spikes), spikes};
}
function spikeSet(names, item){
  const out = {};
  if(!S.opt.spike) return out;
  for(const n of names){ const r = spikeOf(series(n,item)); if(r.z >= S.opt.spikeZ) out[n] = r; }
  return out;
}
