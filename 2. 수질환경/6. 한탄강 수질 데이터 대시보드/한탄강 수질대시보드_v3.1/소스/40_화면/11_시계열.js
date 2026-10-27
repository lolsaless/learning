/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/11_시계열.js] 시계열 화면
   하는 일 : 월별 변화 그래프와 데이터 표(▲▼·점검 표시·판정)
   주요 이름: renderTs, renderTable, cellHtml, rowsFor
   이럴 때 고침: 데이터 표 열·표시
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
registerView({ id:"ts", label:"시계열", kpi:true, item:true, render:()=>renderTs(),
  bind(){
    $("tblCopy").onclick=()=>copyText(tsvText(cache.tsv||[]));
    $("tblCsv").onclick=()=>{ const csv = (cache.tsv||[]).map(r=>r.map(c=>/[",\n]/.test(String(c))?`"${String(c).replace(/"/g,'""')}"`:c).join(",")).join("\n");
      saveFile(`한탄강_${cache.fname||"data"}.csv`, URL.createObjectURL(new Blob(["\ufeff"+csv],{type:"text/csv"}))); };
  }});
/* ═════════ 시계열 + 표 ═════════ */
function rowsFor(names, item){ const ms = months(); return names.map(n=>({name:n, values:series(n,item)})); }
function renderTs(){
  const it = itemOf(S.item), names = selectedOrdered(), ms = months();
  $("tsTitle").textContent = `${it.name} 월별 변화`;
  $("tsSub").textContent = `${names.length}개 지점 · ${mLong(ms[0])}~${mLong(ms[ms.length-1])} · 단위 ${it.unit}`;
  const rows = rowsFor(names, S.item), {plan} = planFor(rows);
  const opt = trendOption({cats:ms.map(mLabel), mkeys:ms, rows, item:S.item, dec:it.dec, unit:it.unit, plan});
  legendHtml($("tsLegend"), names, plan, opt._spikes);
  if(opt._cap) $("tsSub").textContent += ` · y축 ${fmt(opt._cap,it.dec)}에서 자름(📍 표시 값은 실제 값)`;
  chartOn("tsChart").setOption(opt, true);
  renderTable(rows, ms, it, plan);
}
function cellHtml(st, m, item, v, s, dec){
  if(v==null) return `<td class="num"></td>`;
  const c = cls(v, s), q = qcAt(st, m, item), lq = loqText(st, m, item), date = D.dates[st]?.[m];
  const qc = q[0] ? ` q-${q[0].type}` : "", tip = [date?"채취일 "+date:"", ...q.map(x=>QC_LABEL[x.type]+": "+x.note)].filter(Boolean).join("\n");
  return `<td class="num ${c==="up"?"up":c==="dn"?"dn":""}${qc}${lq?" q-loq":""}" title="${esc(tip)}">${lq||fmt(v,dec)}${c==="up"?'<span class="g">▲</span>':c==="dn"?'<span class="g">▼</span>':""}</td>`;
}
function renderTable(rows, ms, it, plan){
  const hasJ = !!((D.limits[S.item]||[]).length || targetOf(S.item)!=null);
  let h = `<thead><tr><th class="l stc">지점</th><th class="l">하천</th>${ms.map(m=>`<th>${mLabel(m)}</th>`).join("")}<th>최대</th><th>최소</th><th>평균</th><th>표준편차</th>${hasJ?`<th class="l" title="선택 기간 평균으로 판정">${targetOf(S.item)!=null?"목표":"생활환경기준"}*</th>`:""}</tr></thead><tbody>`;
  const tsv = [["지점","하천",...ms,"최대","최소","평균","표준편차",...(hasJ?["판정"]:[])]];
  for(const r of rows){
    const s = stats(r.values), st = stByName[r.name], j = judge(S.item, s.mean);
    h += `<tr class="${S.hl.has(r.name)?"hl":""}"><td class="l stc" data-st="${esc(r.name)}" title="${esc(st.addr)}"><span class="dot" style="background:${plan[r.name].color}"></span>${esc(r.name)}</td><td class="l">${esc(st.river)}</td>${r.values.map((v,i)=>cellHtml(r.name, ms[i], S.item, v, s, it.dec)).join("")}
      <td class="num stat">${fmt(s.max,it.dec)}</td><td class="num stat">${fmt(s.min,it.dec)}</td><td class="num stat"><b>${fmt(s.mean,it.dec)}</b></td><td class="num stat">${fmt(s.sd,it.dec)}</td>${hasJ?`<td class="l">${j.html}</td>`:""}</tr>`;
    tsv.push([r.name, st.river, ...r.values.map((v,i)=>loqText(r.name,ms[i],S.item)||(v??"")), s.max??"", s.min??"", s.mean!=null?+s.mean.toFixed(4):"", s.sd!=null?+s.sd.toFixed(4):"", ...(hasJ?[j.text]:[])]);
  }
  const tb = $("tbl"); tb.innerHTML = h + `</tbody>`;
  tb.querySelectorAll("td[data-st]").forEach(x=>x.onclick=()=>toggleHl(x.dataset.st));
  $("tblSub").textContent = `${it.name} (${it.unit}) · ${rows.length}개 지점`;
  $("tblFoot").innerHTML = `<span>${S.opt.band==="off"?"▲▼ 표시 꺼짐":`<b class="up">▲</b> ${bandText()}보다 높음 · <b class="dn">▼</b> 낮음 (지점별·선택 기간 기준)`}</span>
    <span><i class="key k-rep"></i>검토필요·전월 동일</span><span><i class="key k-out"></i>이상값 의심</span><span>* 선택 기간 평균으로 판정(연간 판정과 다를 수 있음)</span><span>지점명을 누르면 강조 전환</span>`;
  cache.tsv = tsv; cache.fname = `${S.item}_${ms[0]}_${ms[ms.length-1]}`;
}
