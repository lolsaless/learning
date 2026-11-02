/* [공통] 서버 연결·알림·확인창·탭·상태
 * api(), toast(), ask(), showTab(), refresh(), renderLegend(), quit() — 모든 페이지가 쓰는 것
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let S={state:null,work:null,view:null,sel:null,filter:"all",hist:null,inTarget:null,grid:null,gsel:null,status:{}};
const REL={match:"일치",round:"반올림 일치",scale:"단위 환산 일치",unit:"단위 다름",mismatch:"불일치"};
const BAD=["mismatch","unit","calc"], WARN=["conflict","unknown","multi","claim"];

let BUSY=0, busyT=null;
function busy(d){BUSY+=d; clearTimeout(busyT);
  if(BUSY>0) busyT=setTimeout(()=>$("#busy").classList.add("on"),250); else $("#busy").classList.remove("on");}
async function api(p,body){
  const o=body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json","X-App-Request":"1"},body:JSON.stringify(body)};
  let r; const post=body!==undefined;
  if(post) busy(1);
  try{ r=await fetch(p,o);}catch(e){ if(post)busy(-1); toast("프로그램과 연결이 끊겼습니다. 검은 창이 켜져 있는지 확인하세요",true); throw e;}
  if(post) busy(-1);
  const j=await r.json().catch(()=>({error:"응답 오류"}));
  if(!r.ok||j.error){ toast(j.error||"오류",true); throw new Error(j.error);}
  return j;
}
function toast(m,err){const d=document.createElement("div");d.textContent=m;if(err)d.className="err";$("#toast").appendChild(d);setTimeout(()=>d.remove(),err?6000:3200);}
let askCb=null;
function ask(t,html){return new Promise(res=>{$("#askT").textContent=t;$("#askB").innerHTML=html;askCb=res;$("#askModal").classList.add("on");});}
function askDone(v){$("#askModal").classList.remove("on");if(askCb){const f=askCb;askCb=null;f(v);}}

/* 탭 */
$$("#tabs button").forEach(b=>b.onclick=()=>showTab(b.dataset.p));
function showTab(p){
  $$("#tabs button").forEach(b=>b.classList.toggle("on",b.dataset.p===p));
  $$(".page").forEach(x=>x.classList.toggle("on",x.id==="p-"+p));
  if(p==="check"&&S.work&&S.work.version&&!S.view) runVerify(false);
  if(p==="check"&&S.view&&S.view.blocks) renderDoc();
  if(p==="input") enterInput();
  if(p==="hist") loadHist();
  if(p==="mock") enterMock();
  if(p==="map") enterMap();
  if(p==="conf") loadConf();
}

/* 상태 */
async function refresh(){
  const j=await api("/api/state"); S.state=j; S.work=j.work; S.status=j.status_names;
  if(j.app_name){document.title=j.app_name;$("#logo").textContent=j.app_name;}
  $("#demoCard").style.display=j.demo?"":"none";
  $("#recent").innerHTML='<option value="">최근 작업…</option>'+(j.recent||[]).map(f=>`<option value="${esc(f)}">${esc(f)}</option>`).join("");
  renderPrep(); renderLegend(); updPend();
}
function renderLegend(){
  const items=[["ok","일치"],["ok_user","확정"],["single","값 일치(위치 추정)"],["conflict","출처 간 충돌·AI 읽기 확인"],["unknown","출처 미확인"],["mismatch","불일치·단위 다름·계산 오류"],["empty","빈 칸"]];
  const h=items.map(([k,t])=>`<span><span class="num st-${k}">&nbsp;12&nbsp;</span> ${t}</span>`).join("")+`<span><span class="num pend"><span class="new">&nbsp;12&nbsp;</span></span> 저장 전 변경</span>`;
  $("#legend").innerHTML=h; $("#legend2").innerHTML=h;
}
async function quit(){if(!await ask("종료",(S.state&&S.state.app_name||"프로그램")+"을(를) 종료합니다. (저장하지 않은 변경은 대기 목록에 남아 다음에 이어서 할 수 있습니다)"))return;await api("/api/shutdown",{});document.body.innerHTML='<div class="empty" style="padding:80px">종료했습니다. 이 창을 닫으세요.</div>';}

/* 시작: 페이지 조각(ui/pages/*.html)을 읽어 넣은 뒤 상태를 불러온다 */
async function loadPages(){
  for(const sec of $$("main > section.page")){
    const name=sec.id.slice(2);                    // p-prep → prep
    const r=await fetch("/ui/pages/"+name+".html");
    sec.innerHTML=await r.text();
  }
}
loadPages().then(refresh).then(()=>{ if(S.work&&S.work.version) toast("최근 작업을 열었습니다: "+S.work.target_name); });
