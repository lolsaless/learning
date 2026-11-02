/* [4. 이력] 값 이력·버전·원본 변경·검증 기록
 * 이력 파트(history) 주소를 씀
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
async function loadHist(){if(!S.work)return;S.hist=await api("/api/history");renderHist();}
function renderHist(){
  const H=S.hist; if(!H)return; const q=$("#hq").value.trim(), hide=$("#hHideInit").checked;
  const ev=H.events.filter(e=>!(hide&&e.method==="작업본 생성")).filter(e=>!q||[e.slot,e.label,e.source_path,e.source_ref,e.method,e.reason].join(" ").includes(q));
  $("#histT").innerHTML="<tr><th>시각</th><th>버전</th><th>위치</th><th>이전</th><th>새 값</th><th>방법</th><th>출처</th><th>사유</th><th>작업자</th></tr>"+
    ev.map(e=>`<tr><td class="small">${esc(e.ts)}</td><td>v${String(e.ver||0).padStart(3,"0")}</td><td>${esc(e.label)}<div class="small muted path">${esc(e.slot)}</div></td><td>${esc(e.old??"")}</td><td><b>${esc(e.new??"")}</b></td><td>${esc(e.method)}</td><td class="small"><span class="path">${esc(e.source_path||"")}</span> ${esc(e.source_ref||"")}</td><td class="small">${esc(e.reason||"")}</td><td>${esc(e.user||"")}</td></tr>`).join("");
  $("#verT").innerHTML="<tr><th>버전</th><th>만든 시각</th><th>메모</th><th>작업자</th><th>파일</th><th></th></tr>"+H.versions.map(v=>`<tr><td>v${String(v.ver).padStart(3,"0")}</td><td>${esc(v.created)}</td><td>${esc(v.note)}</td><td>${esc(v.user)}</td><td class="path small">${esc(v.path)}</td><td><button class="sm" onclick='api("/api/open",{path:${JSON.stringify(v.path)}})'>한글로 열기</button></td></tr>`).join("");
  $("#srcEvT").innerHTML="<tr><th>시각</th><th>번호</th><th>파일</th><th>내용</th><th>고유값 변화</th><th>비고</th></tr>"+H.source_events.map(e=>`<tr><td class="small">${esc(e.ts)}</td><td>${esc(e.sid)}</td><td>${esc(e.name)}</td><td>${esc(e.kind)}</td><td class="path small">${esc((e.old_sha||"").slice(0,10))}${e.old_sha?" → ":""}${esc((e.new_sha||"").slice(0,10))}</td><td class="small path">${esc(e.note||"")}</td></tr>`).join("");
  $("#runT").innerHTML="<tr><th>시각</th><th>버전</th><th>결과</th></tr>"+H.runs.map(r=>{const s=JSON.parse(r.summary||"{}");return `<tr><td>${esc(r.ts)}</td><td>v${String(r.ver).padStart(3,"0")}</td><td class="small">전체 ${s.total||0} · 일치 ${(s.ok||0)+(s.ok_calc||0)+(s.ok_user||0)+(s.single||0)} · 불일치·오류 ${(s.mismatch||0)+(s.unit||0)+(s.calc||0)} · 확인 필요 ${(s.conflict||0)+(s.unknown||0)+(s.multi||0)}${s.changed?` · 바뀐 칸 ${s.changed}`:""}</td></tr>`}).join("");
}

/* 설정 */
