/* [5. 설정·도움말] 작업자·클립보드 기록
 * 클립보드 파트(clip) 주소를 씀
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
async function loadConf(){await refresh(); loadAi();const c=S.state.clip;$("#uname").value=S.work?S.work.user:"";
  $("#clipBtn").textContent=c.running?"끄기":"켜기"; $("#clipBtn").disabled=!c.available;
  $("#clipSt").textContent=!c.available?"이 PC(Windows가 아님)에서는 사용할 수 없습니다":c.running?`기록 중 · ${c.count}건`:"꺼짐";
  if(S.work){const j=await api("/api/clips");$("#clipT").innerHTML="<tr><th>시각</th><th>파일</th><th>시트·시작 칸</th><th>칸 수</th></tr>"+j.clips.map(x=>`<tr><td class="small">${esc(x.ts)}</td><td class="path small">${esc(x.path)}</td><td>${esc(x.sheet)} R${x.r0+1}C${x.c0+1}</td><td>${Object.keys(x.cells).length}</td></tr>`).join("");}}
async function setUser(){S.work=await api("/api/user",{name:$("#uname").value});await refresh();toast("저장했습니다");}
async function toggleClip(){const on=!S.state.clip.running;const r=await api("/api/clip",{on});if(on&&!r.ok)toast(r.error||"켤 수 없습니다",true);loadConf();}

/* AI 설정(AI 파트 ai) */
async function loadAi(){const s=await api("/api/ai/settings");S.ai=s;
  $("#aiKind").innerHTML=Object.entries(s.kinds).map(([k,t])=>`<option value="${k}" ${s.provider===k?"selected":""}>${esc(t)}</option>`).join("");
  $("#aiUrl").value=s.url||(s.default_url[s.provider]||""); $("#aiModel").value=s.model||"";
  $("#aiSt").textContent=s.enabled?"사용 중":"사용 안 함";}
function aiKindChanged(){const k=$("#aiKind").value;$("#aiUrl").value=(S.ai.default_url||{})[k]||"";}
async function saveAi(){await api("/api/ai/settings",{provider:$("#aiKind").value,url:$("#aiUrl").value,model:$("#aiModel").value});toast("AI 설정을 저장했습니다");loadAi();}
async function testAi(){$("#aiSt").textContent="시험 중…";const r=await api("/api/ai/test",{});
  if(!r.ok){$("#aiSt").textContent="실패: "+r.error;return;}
  $("#aiModels").innerHTML=(r.models||[]).map(m=>`<option value="${esc(m)}">`).join("");
  const n=((r.sample||{}).checks||[]).length;
  $("#aiSt").textContent=`연결됨(${r.seconds}초) · ${r.model}`+(r.has_model?"":" · ⚠ 서버에 이 모델이 없습니다")+` · 시험 문장 검산식 ${n}개`;}
