/* [2. 검증] 문서 보기·색 칠하기·상세·고치기·저장·내보내기
 * 검증 파트(verify)·수정 파트(edit)·내보내기 파트(export) 주소를 씀
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
/* 검증 */
async function runVerify(go){
  if(!S.work||!S.work.version){toast("문서와 원본을 먼저 등록하세요",true);return;}
  if(S.busy)return; S.busy=true;
  try{
  if(go){S.view=S.view||{pending:true};showTab("check");}
  $("#docView").innerHTML='<div class="empty">검증 중…</div>';
  S.view=await api("/api/verify",{}); renderAll(); await refresh();
  }finally{S.busy=false;}
  const sm=S.view.summary; toast(`검증 완료: ${sm.total}칸`+(sm.changed?` · 직전 대비 바뀐 칸 ${sm.changed}개`:""));
}
function cnt(...ks){const sm=S.view.summary||{};return ks.reduce((a,k)=>a+(sm[k]||0),0);}
function renderAll(){renderChips();renderBanners();renderDoc();updPend();if(S.sel)showDetail(S.sel);}
function renderChips(){
  const c=[["all","전체",S.view.summary.total],["bad","불일치·오류",cnt("mismatch","unit","calc")+(S.view.text_issues||[]).length],["warn","확인 필요",cnt("conflict","unknown","multi","claim")],["ok","일치",cnt("ok","ok_calc","ok_user","single")]];
  $("#chips").innerHTML=c.map(([k,t,n])=>`<div class="chip ${S.filter===k?"on":""}" onclick="setFilter('${k}')" style="${k==="bad"?"background:var(--bad)":k==="warn"?"background:var(--warn)":k==="ok"?"background:var(--ok)":""}">${t}<b>${n}</b></div>`).join("");
}
function setFilter(k){S.filter=k;renderChips();renderDoc();}
function renderBanners(){
  let h="";
  const ch=S.view.changed||[];
  if(ch.length) h+=`<div class="banner red"><b>직전 검증 대비 상태가 바뀐 칸 ${ch.length}개</b> (원본 변경·수정 반영)<br>`+ch.map(c=>`<a href="#" onclick="pick('${esc(c.key)}');return false">${esc(c.label)}</a>: ${esc(c.before_text)} → <b>${esc(c.after_text)}</b>`).join("<br>")+"</div>";
  const ed=S.view.edits||[];
  if(ed.length) h+=`<div class="banner"><b>한글에서 직접 고친 칸 ${ed.length}개</b>를 이력에 기록했습니다.<br>`+ed.slice(0,8).map(e=>`${esc(e.label)}: ${esc(e.old)} → ${esc(e.new)}`).join("<br>")+"</div>";
  const ti=S.view.text_issues||[];
  if(ti.length) h+=`<div class="banner red"><b>날짜·요일 오류 ${ti.length}건</b><br>`+ti.map(t=>`${esc(t.raw)} — ${esc(t.msg)}`).join("<br>")+"</div>";
  const ef=(S.view.summary||{}).effect;
  if(ef) h+=`<div class="small muted" style="margin-bottom:8px">효과 추정: 손으로 대조하면 약 <b>${ef.manual_min}분</b> → 프로그램 ${ef.tool_sec}초 <span title="${esc(ef.basis)}">(가정 기준 추정 ⓘ)</span></div>`;
  h+=claimsPanel();
  $("#banners").innerHTML=h;
}
function claimsPanel(){
  const C=S.view.claims; if(!C||!(C.claims||[]).length&&!(C.rejects||[]).length) return "";
  const st=C.stat||{};
  const rows=(C.claims||[]).map(c=>`<tr class="${c.status}"><td>${c.key?`<a href="#" onclick="pick('${esc(c.key)}');return false">본문 ${c.para}</a>`:"본문 "+c.para}</td><td>${esc(c.type_name)}</td><td>${esc(c.check)}</td><td>${esc(c.by)}${c.model?" · "+esc(c.model):""}</td><td>${c.ok?"✔ 맞음":"✘ "+esc(c.msg)}</td></tr>`).join("");
  const rej=(C.rejects||[]).map(x=>`<tr><td>본문 ${x.para}</td><td colspan="4" class="muted">버림(${esc(x.by)}): ${esc(x.reason)}</td></tr>`).join("");
  return `<details class="panel" ${(st.wrong||0)>0?"open":""}><summary><b>본문 문장 검산 ${st.checked||0}건</b> · 틀림 ${st.wrong||0} · 규칙 ${st.rule||0} · AI ${st.ai||0}${st.rejected?` · AI 답 버림 ${st.rejected}`:""}
    <span class="small muted"> — 판정은 프로그램 계산. AI 가 읽은 식이 틀리면 노랑(확인 필요)</span></summary>
    <table><tr><th>위치</th><th>종류</th><th>검산식</th><th>읽은 쪽</th><th>결과</th></tr>${rows}${rej}</table></details>`;
}
async function aiRead(){
  if(!S.work||!S.work.version){toast("문서와 원본을 먼저 등록하세요",true);return;}
  const st=await api("/api/ai/settings"); if(!st.enabled){if(await ask("AI 설정 필요","AI 가 '사용 안 함'으로 되어 있습니다. 설정 탭에서 AI(예: 내 컴퓨터의 Ollama)를 고르세요.<br><span class='small muted'>AI 없이도 정해진 문형(…보다 ○건 많음, 전체 ○건 중 ○건(○%) 등)은 규칙으로 검산합니다.</span>"))showTab("conf");return;}
  toast("AI 가 문장을 읽는 중… (문장 수에 따라 시간이 걸립니다)");
  const r=await api("/api/ai/read",{on:true}); S.view=r.view; renderAll();
  const s=(r.claims||{}).stat||{}; toast(`AI 읽기 ${s.ai_calls||0}문장 · 검산 ${s.checked||0}건 · 버림 ${s.rejected||0}건 (${s.seconds||0}초)`);
}
async function aiSummary(){
  if(!S.view||!S.view.summary){toast("먼저 검증을 실행하세요",true);return;}
  const st=await api("/api/ai/settings");
  const r=await api("/api/ai/summary",{ai:!!st.enabled});
  let h=`<h4>규칙 요약(항상 정확)</h4><pre style="white-space:pre-wrap">${esc(r.rule_text)}</pre>`;
  if(r.ai_text!==null&&r.ai_text!==undefined){
    let t=esc(r.ai_text); for(const b of r.ai_bad||[]) t=t.split(esc(b.raw)).join(`<mark title="검증 결과에 없는 숫자">${esc(b.raw)}</mark>`);
    h+=`<h4>AI 요약 초안 (${esc(r.model||"")})</h4><pre style="white-space:pre-wrap">${t}</pre>`+
       ((r.ai_bad||[]).length?`<div class="banner red">AI 요약에 검증 결과에 없는 숫자 ${r.ai_bad.length}개(노란 표시) — 규칙 요약을 쓰거나 고쳐서 쓰세요.</div>`:`<div class="small muted">AI 요약의 숫자는 모두 검증 결과와 맞습니다.</div>`);
  } else if(r.error) h+=`<div class="small muted">AI 요약: ${esc(r.error)}</div>`;
  await ask("검증 요약",h);
}
function vis(st){ if(S.filter==="all")return true; if(S.filter==="bad")return BAD.includes(st); if(S.filter==="warn")return WARN.includes(st); if(S.filter==="ok")return ["ok","ok_calc","ok_user","single"].includes(st); return true;}
function numSpan(it,mode){
  const st=it.status||"none"; let inner=esc(it.raw||"");
  if(it.pending!==undefined&&it.pending!==null) inner=(it.raw?`<span class="old">${esc(it.raw)}</span>`:"")+`<span class="new">${esc(it.pending)||"(빈 칸)"}</span>`;
  else if(!it.raw) inner="&nbsp;";
  const faded=mode==="check"&&!vis(st)?' style="opacity:.25"':"";
  const tip=esc(it.label+" · "+(it.status_text||""));
  return `<span class="num st-${st} ${it.pending!=null?"pend":""} ${(mode==="check"?S.sel:S.inTarget)===it.key?"sel":""}" data-k="${esc(it.key)}" title="${tip}"${faded}>${inner}</span>`;
}
function renderDocInto(el,mode){
  const v=S.view; if(!v){el.innerHTML='<div class="empty">검증을 먼저 실행하세요</div>';return;}
  const ti=v.text_issues||[]; let h="";
  for(const b of v.blocks){
    if(b.type==="p"){
      let inner=b.pieces.map(p=>p.item?numSpan(v.items[p.item],mode):esc(p.text)).join("");
      for(const t of ti) if(t.para===b.para) inner=inner.replace(esc(t.raw),`<span class="texterr" title="${esc(t.msg)}">${esc(t.raw)}</span>`);
      h+=`<p class="${b.style}">${inner}</p>`;
    } else {
      const tm=(v.tables||{})[String(b.ti)]||[];
      h+=`<div class="ttl">표${b.ti+1}`+(tm.length?" · 대조된 원본: "+tm.map(m=>esc(m.name)+" "+esc(m.sheet)+(m.orient==="T"?"(행·열 뒤바뀜)":"")).join(", "):" · 대조된 원본 블록 없음")+`</div><table>`;
      for(const row of b.rows){h+="<tr>";for(const c of row){
        const inner=c.pieces.map(p=>p.item?numSpan(v.items[p.item],mode):esc(p.text)).join("")||"&nbsp;";
        h+=`<td class="${c.head?"h":""}" ${c.rs>1?`rowspan="${c.rs}"`:""} ${c.cs>1?`colspan="${c.cs}"`:""}>${inner}</td>`;}h+="</tr>";}
      h+="</table>";
    }
  }
  el.innerHTML=h;
  el.querySelectorAll(".num").forEach(s=>s.onclick=()=>mode==="check"?pick(s.dataset.k):pickTarget2(s.dataset.k));
}
function renderDoc(){renderDocInto($("#docView"),"check");}
function toggleDim(){$("#docView").classList.toggle("dim",$("#dimOk").checked);}
function issueKeys(){const v=S.view;return v.blocks.flatMap(b=>b.type==="p"?b.pieces.filter(p=>p.item).map(p=>p.item):b.rows.flat().flatMap(c=>c.pieces.filter(p=>p.item).map(p=>p.item))).filter(k=>{const s=v.items[k].status;return BAD.includes(s)||WARN.includes(s);});}
function nextIssue(d){const ks=issueKeys();if(!ks.length){toast("확인할 칸이 없습니다");return;}let i=ks.indexOf(S.sel);i=(i+d+ks.length)%ks.length;pick(ks[i]);}
async function pick(k){S.sel=k;$$("#docView .num").forEach(x=>x.classList.toggle("sel",x.dataset.k===k));
  const el=$(`#docView .num[data-k="${CSS.escape(k)}"]`); if(el) el.scrollIntoView({block:"center",behavior:"smooth"});
  showDetail(k);}
async function showDetail(k){
  const d=await api("/api/slot?key="+encodeURIComponent(k)); const it=d.item, r=d.result||{};
  const st=r.status||"none", stt=(S.status[st]||[st])[0];
  let h=`<h4>${esc(it.label)}</h4><div class="kv"><div>칸 이름</div><div class="path">${esc(it.key)}</div>
   <div>문서 값</div><div><b style="font-size:16px">${esc(it.raw||"(빈 칸)")}</b> ${it.unit?esc(it.unit):""}</div>
   <div>상태</div><div><span class="badge st-${st}">${esc(stt)}</span></div>`;
  if(r.fix) h+=`<div>고칠 값</div><div><b>${esc(r.fix)}</b></div>`;
  if(r.calc) h+=`<div>계산</div><div>${r.calc.ok?"✔":"✘"} ${esc(r.calc.msg)}</div>`;
  if(d.confirmed) h+=`<div>확정</div><div>${esc(d.confirmed.user)} · ${esc(d.confirmed.ts)}<br><span class="path">${esc(d.confirmed.source_path)}</span> · ${esc(d.confirmed.source_ref)} <button class="sm" onclick="unconfirm('${esc(k)}')">확정 취소</button></div>`;
  if(d.pending) h+=`<div>저장 전</div><div class="pendn">${esc(d.pending.old)} → ${esc(d.pending.new)} (${esc(d.pending.method)}) <button class="sm" onclick="dropOne('${esc(k)}')">취소</button></div>`;
  h+=`</div>`;
  if(it.context&&it.kind==="para") h+=`<div class="small muted" style="margin-bottom:6px">문장: ${esc(it.context)}</div>`;
  if(d.sources.length){
    const title=(r.status==="unknown"||r.status==="single"||r.status==="multi")&&!d.sources.some(s=>s.relation==="mismatch")?"같은 값이 있는 원본 칸":"대조한 원본";
    h+=`<div style="margin-top:6px"><b>${title}</b></div>`;
    for(const s of d.sources){
      const ag=["match","round","scale"].includes(s.relation);
      h+=`<div class="src ${ag?"agree":"dis"}"><div><b>${esc(s.source)}</b> <span class="badge">${esc(s.role)}</span> · <span class="path">${esc(s.ref)}</span></div>
       <div class="small path muted">${esc(s.path||"")}</div>
       <div>원본 값 <b>${esc(s.source_text)}</b>${s.scale!==1?` ${esc(s.scale_label)} → ${esc(s.expected_text)}`:""} · <span class="badge" style="background:${ag?"var(--ok)":"var(--bad)"}">${esc(REL[s.relation]||s.relation)}</span></div>`;
      if(s.preview) h+=miniGrid(s.preview);
      h+=`<div class="row" style="margin-top:6px">`;
      if(ag) h+=`<button class="sm" onclick='confirmSrc(${JSON.stringify(k)},${JSON.stringify(s.sid)},${JSON.stringify(s.ref)})'>이 출처로 확정</button>`;
      else h+=`<button class="sm pri" onclick='fixFrom(${JSON.stringify(k)},${JSON.stringify(s.sid)},${JSON.stringify(s.ref)},${JSON.stringify(s.expected_text)})'>이 값(${esc(s.expected_text)})으로 고치기</button>`;
      h+=`</div></div>`;
    }
  } else if(it.value!==null) h+=`<div class="banner">이 숫자와 같은 값을 등록한 원본에서 찾지 못했습니다. 계산한 값이면 계산 근거를 확인하고, 원본이 따로 있으면 [입력하기]로 출처를 붙이세요.</div>`;
  if(d.clips&&d.clips.length) h+=`<div class="src agree"><b>복사 기록</b>`+d.clips.map(c=>`<div class="small">${esc(c.at)} · ${esc(c.path)} · ${esc(c.sheet)}!${esc(c.ref)} = ${esc(c.text)}</div>`).join("")+`</div>`;
  if(it.editable) h+=`<div style="margin-top:10px"><b>직접 고치기</b><div class="row" style="margin-top:4px"><input id="manV" value="${esc(it.raw||"")}" style="width:120px"><input id="manR" placeholder="사유(선택)" style="flex:1"><button class="sm" onclick='manual(${JSON.stringify(k)})'>대기 목록에 올리기</button></div></div>`;
  else h+=`<div class="small muted" style="margin-top:8px">이 숫자는 문서 구조상 프로그램에서 직접 고칠 수 없습니다. 한글에서 고친 뒤 다시 검증하세요.</div>`;
  h+=`<div style="margin-top:12px"><b>이 칸 이력</b>`+(d.events.map(e=>`<div class="evt"><b>${esc(e.method)}</b> · v${String(e.ver||0).padStart(3,"0")} · ${esc(e.ts)} · ${esc(e.user||"")}<br>${esc(e.old??"")} → <b>${esc(e.new??"")}</b>${e.source_ref?` · ${esc((e.source_path||"").split(/[\\/]/).pop())} ${esc(e.source_ref)}`:""}${e.reason?` · ${esc(e.reason)}`:""}</div>`).join("")||'<div class="muted small">없음</div>')+`</div>`;
  $("#detail").innerHTML=h;
}
function miniGrid(p){
  let h=`<table class="mini"><tr><th></th>${p.cols.map(c=>`<th>${esc(c)}</th>`).join("")}</tr>`;
  p.grid.forEach((row,i)=>{h+=`<tr><th>${p.r0+i+1}</th>`+row.map((t,j)=>`<td class="${i===p.hit[0]&&j===p.hit[1]?"hit":""}" title="${esc(t)}">${esc(t)}</td>`).join("")+"</tr>";});
  return h+"</table>";
}
async function confirmSrc(k,sid,ref){await api("/api/confirm",{slot:k,sid,ref});toast("출처를 확정했습니다");await reloadView();showDetail(k);}
async function unconfirm(k){await api("/api/unconfirm",{slot:k});toast("확정을 취소했습니다(다시 검증하면 반영)");showDetail(k);}
async function fixFrom(k,sid,ref,val){await api("/api/fix",{slot:k,sid,ref,value:val});toast(`대기 목록: ${val} (저장하면 반영)`);await reloadView();showDetail(k);}
async function manual(k){const v=$("#manV").value.trim(),r=$("#manR").value.trim();await api("/api/pending",{slot:k,value:v,method:"직접 입력",reason:r});toast("대기 목록에 올렸습니다");await reloadView();showDetail(k);}
async function dropOne(k){await api("/api/pending/drop",{slot:k});await reloadView();showDetail(k);}
async function dropAll(){if(!await ask("변경 취소","저장하지 않은 변경을 모두 취소합니다."))return;await api("/api/pending/drop",{});await reloadView();}
async function reloadView(){S.view=await api("/api/view");await refresh();renderAll();if($("#p-input").classList.contains("on"))renderDocInto($("#docView2"),"input");}
function updPend(){const n=S.work?S.work.pending.length:0;$("#pendN").textContent=n;$("#pendN2").textContent=n;}
async function saveVersion(){
  const P=S.work?S.work.pending:[]; if(!P.length){toast("저장할 변경이 없습니다",true);return;}
  const list=P.map(p=>`<div class="small">${esc(p.label)}: ${esc(p.old??"")} → <b>${esc(p.new)}</b> <span class="muted">(${esc(p.method)})</span></div>`).join("");
  if(!await ask(`새 버전으로 저장 (${P.length}칸)`,list+`<p><input id="vnote" placeholder="메모(선택)" style="width:100%"></p>`))return;
  const note=($("#vnote")||{}).value||"";
  const r=await api("/api/save",{note}); toast(`작업본 v${String(r.ver).padStart(3,"0")} 저장 (${r.count}칸)`);
  S.view=await api("/api/verify",{}); await refresh(); renderAll(); if($("#p-input").classList.contains("on"))renderDocInto($("#docView2"),"input");
}
async function doExport(){
  toast("내보내는 중…"); const r=await api("/api/export",{});
  const f=(p,t)=>`<div style="margin:6px 0"><b>${t}</b><br><span class="path small">${esc(p)}</span> <button class="sm" onclick='api("/api/open",{path:${JSON.stringify(p)}})'>열기</button></div>`;
  await ask("내보내기 완료",f(r.ledger,"출처대장(xlsx)")+f(r.marked,`검증표시본(hwpx, 표시 ${r.marked_count}칸)`)+f(r.report,"검증보고(html, 인쇄용)")+
    `<div style="margin-top:8px"><button class="sm" onclick='api("/api/open",{path:${JSON.stringify(r.ledger.replace(/[\\/][^\\/]*$/,""))}})'>내보내기 폴더 열기</button></div>`);
}

/* 입력하기 */
