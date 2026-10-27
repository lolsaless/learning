/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_공통/02_통계_판정.js] 통계·평균 대비 판정·등급
   하는 일 : 평균·표준편차, ▲▼ 판정 범위, 생활환경기준 등급·목표 달성
   주요 이름: stats, series, band, cls, grade, judge, fmt
   이럴 때 고침: ▲▼ 판정 규칙, 등급 판정 방식, 숫자 표기
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ═════════ 통계 · 판정 ═════════ */
const fmt = (v, dec) => { if(v==null||isNaN(v)) return ""; let r = +(+v).toFixed(dec); if(r===0) r = 0; return r.toLocaleString("ko-KR",{minimumFractionDigits:dec,maximumFractionDigits:dec}); };
function stats(arr){
  const v = arr.filter(x=>x!=null);
  if(!v.length) return {n:0};
  const mean = v.reduce((a,b)=>a+b,0)/v.length;
  const sd = v.length>1 ? Math.sqrt(v.reduce((a,b)=>a+(b-mean)**2,0)/(v.length-1)) : 0;
  return {n:v.length, mean, sd, max:Math.max(...v), min:Math.min(...v)};
}
const series = (st, item) => (D.values[st]?.[item] || []).slice(S.from, S.to+1);
const months = () => M.slice(S.from, S.to+1);
/* 평균 대비 판정: up / dn / in */
function band(st){
  if(!st.n || st.n<2) return null;
  if(S.opt.band==="sd") return [st.mean - S.opt.k*st.sd, st.mean + S.opt.k*st.sd];
  if(S.opt.band==="pct") return [st.mean*(1-S.opt.p/100), st.mean*(1+S.opt.p/100)];
  if(S.opt.band==="all") return [st.mean, st.mean];
  return null;
}
function cls(v, st){
  if(v==null) return "in"; const b = band(st); if(!b) return "in";
  const e = 1e-9; if(v > b[1]+e) return "up"; if(v < b[0]-e) return "dn"; return "in";
}
const bandText = () => S.opt.band==="sd" ? `평균 ± ${S.opt.k}σ` : S.opt.band==="pct" ? `평균 ± ${S.opt.p}%` : S.opt.band==="all" ? "평균" : "";
function grade(item, mean){
  const L = D.limits[item]; if(!L || !L.length || mean==null) return null;
  for(let i=0;i<L.length;i++){ if(L[i].max==null || mean <= L[i].max + 1e-12) return {i, ...L[i]}; }
  return {i:L.length-1, ...L[L.length-1]};
}
const targetOf = item => D.target[item];
function judge(item, mean){
  const g = grade(item, mean);
  if(g) return {html:`<span class="pill g${g.i}">${g.code} ${g.name}</span>`, text:`${g.code} ${g.name}`, i:g.i};
  const t = targetOf(item);
  if(t!=null && mean!=null){ const ok = mean <= t; return {html:`<span class="pill ${ok?"ok":"ng"}">${ok?"달성":"미달성"}</span>`, text: ok?"달성":"미달성", ok}; }
  return {html:"", text:""};
}
