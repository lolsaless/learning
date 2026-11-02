/* [5. 시연자료] 무작위 시연자료 만들기·목록·채점·일괄 평가
 * 가상자료 파트(mockdata)와 평가 주소(/api/eval/*)를 씀
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
let MK={opts:null,items:[],report:null};
async function enterMock(){
  if(!MK.opts){MK.opts=await api("/api/mock/options");
    const so=MK.opts.sizes.map(s=>`<option${s==="보통"?" selected":""}>${s}</option>`).join("");
    $("#mkSize").innerHTML=so;$("#evSize").innerHTML=so;
    $("#mkKinds").innerHTML=MK.opts.kinds.map(k=>`<label><input type="checkbox" class="mkK" value="${k.key}" checked> ${esc(k.name)}</label>`).join("");}
  await mkLoad();
}
async function mkLoad(){
  const j=await api("/api/mock/list");$("#mkRoot").textContent=j.root;MK.items=j.items;
  if(!j.items.length){$("#mkList").innerHTML='<tr><td class="muted">아직 만든 시연자료가 없습니다</td></tr>';return;}
  $("#mkList").innerHTML="<tr><th>이름</th><th>가상 기관</th><th>크기</th><th>요구자료</th><th>심은 오류</th><th>재제출본</th><th>문서</th><th></th></tr>"+
   j.items.map(x=>`<tr><td><b>${esc(x.name)}</b></td><td>${esc(x.org)}</td><td>${esc(x.size)}</td><td title="${esc(x.domains.join(", "))}">${x.domains.length}개</td>
   <td>${x.errors}</td><td>${x.resubmit}</td><td>${x.docs}</td>
   <td class="row"><button class="sm pri" onclick="mkStart('${esc(x.name)}')">이 자료로 시연</button><button class="sm" onclick="mkScore('${esc(x.name)}')">채점</button>
   <button class="sm" onclick="mkOpen('${esc(x.name)}','')">폴더</button>
   <button class="sm" onclick="mkOpen('${esc(x.name)}','시나리오_안내.md')">안내</button></td></tr>`).join("");
}
function mkOpen(name,file){
  const x=MK.items.find(i=>i.name===name); if(!x)return;
  const sep=x.folder.includes("\\")?"\\":"/";
  api("/api/open",{path:file?x.folder+sep+file:x.folder});
}
async function mkGenerate(){
  const b={seed:$("#mkSeed").value.trim()||null,size:$("#mkSize").value,errors:+$("#mkErr").value,fmt:$("#mkFmt").value,
    kinds:$$(".mkK").filter(x=>x.checked).map(x=>x.value),gongmun:$("#mkGong").checked,guides:$("#mkGuide").checked,
    form:$("#mkForm").checked,resubmit:$("#mkResub").checked};
  $("#mkMsg").textContent="만드는 중…";
  const r=await api("/api/mock/generate",b);
  $("#mkMsg").textContent=`${r.name}: 요구자료 ${r.tables}개, 심은 오류 ${r.errors}개, 파일 ${r.files}개`;
  toast("시연자료를 만들었습니다: "+r.name); await mkLoad();
}
async function mkStart(name){
  if(!await ask("이 자료로 시연",`<b>${esc(name)}</b> 시연자료로 작업을 준비합니다. (작업 폴더: 시연자료 안의 '작업(시연)')`))return;
  S.work=await api("/api/demo/scenario",{name,reset:true});S.view=null;await refresh();toast("준비 완료: 검증 탭으로 이동합니다");showTab("check");
}
async function mkScore(name){
  const r=await api("/api/eval/score",{name});
  $("#mkScoreCard").style.display="";$("#mkScoreName").textContent=name;
  $("#mkScoreSum").innerHTML=`<span class="chip">심은 오류 검출 <b>${r["오류"]}</b></span><span class="chip">정상 판정 <b>${r["정상"]}</b></span>
   <span class="chip">빨강 오탐 <b>${r["빨강오탐"]}</b></span><span class="chip">노랑(확인 필요) <b>${r["노랑"]}</b></span><span class="chip">칸 <b>${r["칸수"]}</b></span>`;
  $("#mkScoreT").innerHTML="<tr><th>번호</th><th>종류</th><th>위치</th><th>기대</th><th>엔진 판정</th><th>결과</th></tr>"+
   r["항목"].map(x=>`<tr${x.ok?"":' style="background:var(--bad)"'}><td>${esc(x.id)}</td><td>${esc(x["구분"])}</td><td>${esc(x["위치"]||"")}</td>
   <td class="small">${esc(x["기대"].join(", "))}</td><td>${esc((S.status[x["판정"]]||[x["판정"]])[0])}</td><td>${x.ok?"맞음":"틀림"}</td></tr>`).join("");
  $("#mkScoreCard").scrollIntoView({behavior:"smooth"});
}
async function evRun(){
  const b={n:+$("#evN").value,size:$("#evSize").value,errors:+$("#evErr").value,seed:$("#evSeed").value.trim()||null};
  $("#evMsg").textContent=`시나리오 ${b.n}개를 만들어 채점하는 중…`;
  const r=await api("/api/eval/batch",b);
  MK.report=r["보고서"];
  $("#evMsg").textContent=`완료: 씨앗값 ${r["씨앗값"][0]}~${r["씨앗값"][1]}`;
  const kinds=Object.entries(r["종류별"]).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${v["검출"]}/${v["전체"]}</td><td>${v["검출률"]}%</td></tr>`).join("");
  const miss=r["시나리오"].flatMap(s=>[...s["놓침"].map(m=>`<li>${esc(s["이름"])} · 놓침 ${esc(m)}</li>`),...s["오탐"].map(m=>`<li>${esc(s["이름"])} · 빨강 오탐 ${esc(m)}</li>`)]).join("");
  $("#evOut").innerHTML=`<div class="chips" style="margin-top:10px"><span class="chip">검출 <b>${r["검출"]}/${r["심은오류"]}</b> (${r["검출률"]}%)</span>
   <span class="chip">정상 판정 <b>${r["정상맞음"]}/${r["정상전체"]}</b></span><span class="chip">빨강 오탐 <b>${r["빨강오탐"]}</b></span>
   <span class="chip">노랑 <b>${r["노랑"]}</b></span><span class="chip">출처 일치 <b>${r["출처일치"]}/${r["출처확인"]}</b></span><span class="chip">칸 <b>${r["칸수"].toLocaleString()}</b></span></div>
   <table class="list" style="max-width:420px"><tr><th>오류 종류</th><th>검출</th><th>검출률</th></tr>${kinds}</table>
   ${miss?`<div class="small" style="margin-top:8px"><b>놓친 항목·오탐</b><ul>${miss}</ul></div>`:'<div class="small muted" style="margin-top:8px">놓친 항목·오탐 없음</div>'}
   <div class="row small" style="margin-top:8px">보고서: <span class="path">${esc(r["보고서"])}</span><button class="sm" onclick="api('/api/open',{path:MK.report})">열기</button></div>`;
}
