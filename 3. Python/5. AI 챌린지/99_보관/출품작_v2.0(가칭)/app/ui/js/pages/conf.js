/* [5. 설정·도움말] 작업자·클립보드 기록
 * 클립보드 파트(clip) 주소를 씀
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
async function loadConf(){await refresh();const c=S.state.clip;$("#uname").value=S.work?S.work.user:"";
  $("#clipBtn").textContent=c.running?"끄기":"켜기"; $("#clipBtn").disabled=!c.available;
  $("#clipSt").textContent=!c.available?"이 PC(Windows가 아님)에서는 사용할 수 없습니다":c.running?`기록 중 · ${c.count}건`:"꺼짐";
  if(S.work){const j=await api("/api/clips");$("#clipT").innerHTML="<tr><th>시각</th><th>파일</th><th>시트·시작 칸</th><th>칸 수</th></tr>"+j.clips.map(x=>`<tr><td class="small">${esc(x.ts)}</td><td class="path small">${esc(x.path)}</td><td>${esc(x.sheet)} R${x.r0+1}C${x.c0+1}</td><td>${Object.keys(x.cells).length}</td></tr>`).join("");}}
async function setUser(){S.work=await api("/api/user",{name:$("#uname").value});await refresh();toast("저장했습니다");}
async function toggleClip(){const on=!S.state.clip.running;const r=await api("/api/clip",{on});if(on&&!r.ok)toast(r.error||"켤 수 없습니다",true);loadConf();}
