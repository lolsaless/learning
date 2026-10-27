/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/16_경향분석_통계.js] 경향 분석 통계 함수
   하는 일 : Mann-Kendall·Sen 기울기, Spearman 상관, 사분위수(화면과 무관한 계산)
   주요 이름: normCdf, mannKendall, spearman, quart, rankArr, median
   이럴 때 고침: 통계 계산 방식
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ═════════ 경향 분석: 통계 함수 ═════════ */
function normCdf(z){ // 표준정규 누적분포 (Abramowitz-Stegun 7.1.26)
  const t = 1/(1+0.3275911*Math.abs(z)/Math.SQRT2), y = 1 - (((((1.061405429*t - 1.453152027)*t) + 1.421413741)*t - 0.284496736)*t + 0.254829592)*t*Math.exp(-z*z/2);
  return z>=0 ? (1+y)/2 : (1-y)/2;
}
const median = a => { const v = a.slice().sort((x,y)=>x-y), n = v.length; return n ? (n%2 ? v[(n-1)/2] : (v[n/2-1]+v[n/2])/2) : null; };
function mkCore(xs){ // xs: [{t, v}] 시간순
  const n = xs.length; let S = 0;
  for(let i=0;i<n-1;i++) for(let j=i+1;j<n;j++) S += Math.sign(xs[j].v - xs[i].v);
  const ties = {}; xs.forEach(p=>{ const k = p.v.toPrecision(10); ties[k]=(ties[k]||0)+1; });
  let tv = 0; Object.values(ties).forEach(t=>{ if(t>1) tv += t*(t-1)*(2*t+5); });
  const varS = (n*(n-1)*(2*n+5) - tv)/18;
  return {S, varS, n};
}
/* Mann-Kendall 추세 검정 + Sen 기울기. 3년 이상 자료면 계절(월별) Mann-Kendall */
function mannKendall(values, mkeys){
  const pts = values.map((v,i)=>v==null?null:{v, t: M.indexOf(mkeys[i]), mon: +mkeys[i].slice(5), yr: +mkeys[i].slice(0,4)}).filter(Boolean);
  const n = pts.length; if(n<4) return {n, ok:false};
  const years = new Set(pts.map(p=>p.yr)).size, seasonal = years>=3;
  let S = 0, varS = 0, slopes = [];
  if(seasonal){
    for(let m=1;m<=12;m++){ const g = pts.filter(p=>p.mon===m); if(g.length<2) continue; const c = mkCore(g); S += c.S; varS += c.varS;
      for(let i=0;i<g.length-1;i++) for(let j=i+1;j<g.length;j++) slopes.push((g[j].v-g[i].v)/(g[j].t-g[i].t)); }
  } else {
    const c = mkCore(pts); S = c.S; varS = c.varS;
    for(let i=0;i<n-1;i++) for(let j=i+1;j<n;j++) slopes.push((pts[j].v-pts[i].v)/(pts[j].t-pts[i].t));
  }
  const Z = varS>0 ? (S>0 ? (S-1)/Math.sqrt(varS) : S<0 ? (S+1)/Math.sqrt(varS) : 0) : 0;
  const p = 2*(1-normCdf(Math.abs(Z)));
  const slope = median(slopes) ?? 0, med = median(pts.map(x=>x.v));
  const icpt = median(pts.map(x=>x.v - slope*x.t));
  return {ok:true, n, S, Z, p, tau: S/(n*(n-1)/2), slope, slopeYr: slope*12, pctYr: med? slope*12/med*100 : null, icpt, seasonal, med};
}
function rankArr(a){ const idx = a.map((v,i)=>[v,i]).sort((x,y)=>x[0]-y[0]), r = new Array(a.length);
  for(let i=0;i<idx.length;){ let j=i; while(j+1<idx.length && idx[j+1][0]===idx[i][0]) j++; const rr=(i+j)/2+1; for(let k=i;k<=j;k++) r[idx[k][1]]=rr; i=j+1; } return r; }
function pearson(x, y){ const n=x.length, mx=x.reduce((a,b)=>a+b,0)/n, my=y.reduce((a,b)=>a+b,0)/n; let sxy=0,sxx=0,syy=0;
  for(let i=0;i<n;i++){ sxy+=(x[i]-mx)*(y[i]-my); sxx+=(x[i]-mx)**2; syy+=(y[i]-my)**2; } return sxx&&syy ? sxy/Math.sqrt(sxx*syy) : 0; }
function spearman(x, y){ const n = x.length; if(n<4) return {rho:null, n, p:null};
  const rho = pearson(rankArr(x), rankArr(y)); const t = rho*Math.sqrt((n-2)/Math.max(1e-12, 1-rho*rho));
  return {rho, n, p: 2*(1-normCdf(Math.abs(t)))}; }
function quart(a){ const v = a.slice().sort((x,y)=>x-y), q = p=>{ const h=(v.length-1)*p, lo=Math.floor(h); return v[lo]+(v[Math.ceil(h)]-v[lo])*(h-lo); };
  const q1=q(.25), q3=q(.75), iqr=q3-q1, lo=q1-1.5*iqr, hi=q3+1.5*iqr; const inr = v.filter(x=>x>=lo&&x<=hi);
  return {box:[inr[0]??v[0], q1, q(.5), q3, inr[inr.length-1]??v[v.length-1]], out: v.filter(x=>x<lo||x>hi)}; }
const pTxt = p => p==null ? "" : p<0.001 ? "<0.001" : p.toFixed(3);
