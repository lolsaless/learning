/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/15_연도별.js] 연도별 색도 화면
   하는 일 : 2019년~ 연평균 색도 그래프·표, 부분 연도 경고
   주요 이름: renderYear
   이럴 때 고침: 연도별 화면 표시
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
registerView({ id:"year", label:"연도별 색도", kpi:false, item:false, render:()=>renderYear(),
  bind(){
    $("yrRetired").onchange=e=>{ S.retired=e.target.checked; renderYear(); };
    $("yrCopy").onclick=()=>copyText(tsvText(cache.yrTsv||[]));
  }});
/* ═════════ 연도별 색도 ═════════ */
function renderYear(){
  const cur = [...new Set(M.map(m=>+m.slice(0,4)))];
  const years = [...new Set([...Object.values(D.yearly).flatMap(o=>Object.keys(o).map(Number)), ...cur])].sort();
  const val = (n, y) => { if(cur.includes(y)){ const v = M.map((m,i)=>m.startsWith(y+"-")?D.values[n]?.["색도"]?.[i]:null); const s = stats(v); return s.n? +s.mean.toFixed(2) : null; } return D.yearly[n]?.[y] ?? null; };
  let names = selectedOrdered().slice();
  if(S.retired) Object.keys(D.yearly).forEach(n=>{ if(!stByName[n] && !names.includes(n)) names.push(n); });
  const rows = names.map(n=>({name:n, values:years.map(y=>val(n,y))})).filter(r=>r.values.some(v=>v!=null));
  const lastY = cur.at(-1), curMonths = M.filter(m=>m.startsWith(lastY+"-")), partial = curMonths.length<12;
  const cats = years.map(y=> cur.includes(y) && partial && y===lastY ? `${y}*` : String(y));
  $("yrSub").textContent = `${rows.length}개 지점`;
  $("yrNote").hidden = !partial;
  $("yrNote").innerHTML = partial ? `<b>${lastY}*</b>년 값은 ${+curMonths[0].slice(5)}~${+curMonths.at(-1).slice(5)}월(${curMonths.length}개월) 측정결과의 평균입니다. 강우기(6~9월) 비중이 커서 12개월 연평균보다 높게 나올 수 있으니, 연간 비교는 연말 자료가 모두 들어온 뒤에 하세요.` : "";
  const {plan} = planFor(rows);
  const opt = trendOption({cats, rows, item:"색도", dec:1, unit:"도", plan});
  legendHtml($("yrLegend"), rows.map(r=>r.name), plan, opt._spikes);
  if(partial){ const lim = opt.series.find(s=>s.name==="__limits") || (opt.series.push({name:"__limits",type:"line",data:[],silent:true}), opt.series.at(-1));
    lim.markArea = {silent:true, itemStyle:{color:css("--warn-soft"), opacity:.7}, label:{show:true, position:"insideTop", color:css("--warn"), fontSize:11, formatter:"부분 연도"},
      data:[[{xAxis:cats[cats.length-2]},{xAxis:cats[cats.length-1]}]]}; }
  chartOn("yrChart").setOption(opt, true);
  const t = targetOf("색도");
  let h = `<thead><tr><th class="l stc">지점</th>${cats.map(c=>`<th>${c}</th>`).join("")}<th>평균</th>${t!=null?`<th class="l">최근 연도 목표(${t})</th>`:""}</tr></thead><tbody>`;
  const tsv = [["지점",...cats,"평균"]];
  for(const r of rows){ const s = stats(r.values), lastV = r.values.at(-1);
    h += `<tr class="${S.hl.has(r.name)?"hl":""}"><td class="l stc" data-st="${esc(r.name)}"><span class="dot" style="background:${plan[r.name]?.color||col("base")}"></span>${esc(r.name)}${stByName[r.name]?"":' <span class="hint">(중단)</span>'}</td>${r.values.map(v=>{ if(v==null) return `<td></td>`; const c = cls(v,s); return `<td class="num ${c==="up"?"up":c==="dn"?"dn":""}">${fmt(v,1)}${c==="up"?'<span class="g">▲</span>':c==="dn"?'<span class="g">▼</span>':""}</td>`; }).join("")}
      <td class="num stat"><b>${fmt(s.mean,1)}</b></td>${t!=null?`<td class="l">${lastV!=null?`<span class="pill ${lastV<=t?"ok":"ng"}">${lastV<=t?"달성":"미달성"}</span>${partial?' <span class="hint">부분</span>':""}`:""}</td>`:""}</tr>`;
    tsv.push([r.name, ...r.values.map(v=>v??""), s.mean!=null?+s.mean.toFixed(2):""]); }
  const tb = $("yrTbl"); tb.innerHTML = h + "</tbody>";
  tb.querySelectorAll("td[data-st]").forEach(x=>{ if(stByName[x.dataset.st]) x.onclick=()=>toggleHl(x.dataset.st); });
  $("yrTblSub").textContent = `단위 도 · ▲▼ ${bandText()||"판정 끔"} (지점의 연도 평균 기준)`;
  cache.yrTsv = tsv;
}
