/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/18_자료점검.js] 자료 점검 화면
   하는 일 : 점검 목록(유형별 묶음·필터), 보기·수정으로 이동
   주요 이름: qcGroups, renderQc
   이럴 때 고침: 점검 목록 표시
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
registerView({ id:"qc", label:"자료 점검", kpi:false, item:false, render:()=>renderQc(),
  badge(){ const sq = S.qcSel; S.qcSel = false; const n = qcGroups().filter(g=>g.type!=="coord").length; S.qcSel = sq; return n; },
  bind(){
    $("qcSel").onchange=e=>{ S.qcSel=e.target.checked; refresh(); };
    $("qcCopy").onclick=()=>copyText(tsvText(cache.qcTsv||[]));
  }});
/* ═════════ 자료 점검 ═════════ */
function qcGroups(){
  const names = new Set(selectedOrdered());
  const list = D.qc.filter(q=>!S.qcSel || names.has(q.st));
  const g = new Map();
  for(const q of list){
    if(q.type==="coord"){ if(!g.has("coord")) g.set("coord", {type:"coord", st:q.st, m:null, items:[], names:[], note:""}); g.get("coord").names.push(q.st); continue; }
    const key = q.type==="repeat" ? `repeat|${q.st}|${q.m}` : q.type==="manual" ? `manual|${q.st}|${q.m}` : `${q.type}|${q.st}|${q.m}|${q.item}`;
    if(!g.has(key)) g.set(key, {type:q.type, st:q.st, m:q.m, items:[], note:q.note, z:q.z});
    if(q.item && !g.get(key).items.includes(q.item)) g.get(key).items.push(q.item);
  }
  const c = g.get("coord"); if(c) c.note = `주소 기반 추정 좌표: ${c.names.join(", ")} — '지점 관리'에서 수정하세요.`;
  return [...g.values()].sort((a,b)=>(QC_RANK[a.type]??9)-(QC_RANK[b.type]??9) || String(b.m).localeCompare(String(a.m)) || (stByName[a.st]?.order??0)-(stByName[b.st]?.order??0));
}
function renderQc(){
  const all = qcGroups(), cnt = {}; all.forEach(g=>cnt[g.type]=(cnt[g.type]||0)+1);
  const types = ["outlier","manual","repeat","loq","multi","coord"].filter(t=>cnt[t]);
  if(S.qcFilter!=="all" && !cnt[S.qcFilter]) S.qcFilter = "all";
  $("qcSel").checked = S.qcSel;
  $("qcSum").innerHTML = `<button class="chip ${S.qcFilter==="all"?"on":""}" data-t="all">전체<b>${all.length}</b></button>` +
    types.map(t=>`<button class="chip ${S.qcFilter===t?"on":""}" data-t="${t}"><span class="t-${t}">●</span> ${QC_LABEL[t]}<b>${cnt[t]}</b></button>`).join("");
  $("qcSum").querySelectorAll("button").forEach(b=>b.onclick=()=>{ S.qcFilter=b.dataset.t; refresh(); });
  const rows = all.filter(g=>S.qcFilter==="all"||g.type===S.qcFilter);
  $("qcSub").textContent = `${rows.length}건 · 자동 점검(이상값·전월 동일·정량한계·중복·좌표)과 엑셀 '검토표시' 입력`;
  let h = `<thead><tr><th class="l">유형</th><th class="l">조사연월</th><th class="l stc">지점</th><th class="l">항목</th><th>값</th><th class="l">내용</th><th class="l"></th></tr></thead><tbody>`;
  const tsv = [["유형","조사연월","지점","항목","값","내용"]];
  for(const g of rows){
    const mi = g.m ? M.indexOf(g.m) : -1;
    const vals = g.items.map(c=>{ const v = mi>=0 ? D.values[g.st]?.[c]?.[mi] : null; return v==null?"":(loqText(g.st,g.m,c)||fmt(v,itemOf(c).dec)); });
    h += `<tr><td class="l"><span class="t-${g.type}">●</span> ${QC_LABEL[g.type]}</td><td class="l num">${g.m||"-"}</td><td class="l stc" data-st="${esc(g.st)}">${g.type==="coord"?`${g.names.length}개 지점`:esc(g.st)}</td>
      <td class="l">${esc(g.items.join(", ")||"-")}</td><td class="num">${esc(vals.join(" / "))}</td><td class="l wrap">${esc(g.note)}</td>
      <td class="l"><button class="btn-s" data-go="${esc(g.st)}" data-it="${esc(g.items[0]||"")}" data-m="${g.m||""}" data-t="${g.type}">${g.type==="coord"?"수정":"보기"}</button></td></tr>`;
    tsv.push([QC_LABEL[g.type], g.m||"", g.st, g.items.join(", "), vals.join(" / "), g.note]);
  }
  if(!rows.length) h += `<tr><td class="l" colspan="7" style="padding:20px">점검할 값이 없습니다.</td></tr>`;
  const tb = $("qcTbl"); tb.innerHTML = h + "</tbody>";
  tb.querySelectorAll("button[data-go]").forEach(b=>b.onclick=()=>{
    const n = b.dataset.go; S.sel.add(n); S.hl.add(n);
    if(b.dataset.it) S.item = b.dataset.it;
    if(b.dataset.m){ const i = M.indexOf(b.dataset.m); if(i<S.from||i>S.to){ S.from=0; S.to=M.length-1; syncOpts(); } }
    renderHeader();
    if(b.dataset.t==="coord"){ S.focusRow = n; setView("edit"); }
    else setView("ts");
  });
  tb.querySelectorAll("td[data-st]").forEach(x=>x.onclick=()=>toggleHl(x.dataset.st));
  cache.qcTsv = tsv;
}
