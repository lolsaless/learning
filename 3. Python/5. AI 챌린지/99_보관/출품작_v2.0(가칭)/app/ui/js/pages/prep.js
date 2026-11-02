/* [1. 작업 준비] 작업 폴더·대상 문서·원본 등록
 * 원본 파트(sources)·문서 파트(document) 주소를 씀
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
function renderPrep(){
  const w=S.work;
  $("#hdmeta").textContent=w?`작업 폴더: ${w.folder}  ·  문서: ${w.target_name||"-"}  ·  작업본 ${w.version?"v"+String(w.version.ver).padStart(3,"0"):"-"}  ·  작업자: ${w.user}`:"작업 폴더를 여세요";
  $("#wfolder").textContent=w?w.folder:"열린 작업 폴더 없음";
  $("#target").innerHTML=w&&w.target?`<div><b>${esc(w.target_name)}</b></div><div class="path muted">${esc(w.target)}</div><div class="small">작업본: <span class="path">${esc(w.version.path)}</span></div>`:'<span class="muted">선택한 문서 없음</span>';
  $("#btnTarget").disabled=!w||!!(w&&w.version);
  const srcs=w?w.sources:[];
  $("#srcCount").textContent=srcs.length?`${srcs.length}개 등록 · 기준 폴더: ${w.base_folder||"-"}`:"";
  if(!srcs.length){$("#srcTable").innerHTML='<tr><td class="muted">등록한 원본이 없습니다</td></tr>';return;}
  const base=w.base_folder||"";
  $("#srcTable").innerHTML="<tr><th>번호</th><th>파일</th><th>위치(기준 폴더 아래)</th><th>구분</th><th>시트·표</th><th>상태</th><th></th></tr>"+
   srcs.map(s=>{
     const rel=s.path.startsWith(base)?s.path.slice(base.length).replace(/^[\\/]/,""):s.path;
     const st=!s.exists?'<span class="badge" style="background:var(--bad)">파일 없음</span>':s.error&&s.status==="fail"?`<span class="badge" style="background:var(--bad)" title="${esc(s.error)}">읽기 실패</span>`:s.error?`<span class="badge" style="background:var(--warn)" title="${esc(s.error)}">주의</span>`:'<span class="badge" style="background:var(--ok)">정상</span>';
     return `<tr><td>${s.sid}</td><td>${esc(s.name)}</td><td class="path muted">${esc(rel)}</td>
     <td><select onchange="setRole('${s.sid}',this.value)"><option ${s.role==="원본"?"selected":""}>원본</option><option ${s.role==="팀제출"?"selected":""}>팀제출</option><option ${s.role==="기타"?"selected":""}>기타</option></select></td>
     <td>${s.sheets.length}</td><td>${st}</td><td><button class="sm" onclick="removeSrc('${s.sid}')">빼기</button></td></tr>`;}).join("");
}
async function setRole(sid,role){S.work=await api("/api/sources/role",{sid,role});}
async function removeSrc(sid){if(!await ask("원본 빼기","이 원본을 대조 목록에서 뺍니다. (파일은 지우지 않습니다)"))return;S.work=await api("/api/sources/remove",{sid});renderPrep();}
async function openWork(f){S.work=await api("/api/work/open",{folder:f});S.view=null;await refresh();toast("작업 폴더를 열었습니다");}
async function demoSetup(reset){
  if(reset&&!await ask("시연 처음부터","시연용 작업 폴더(작업(시연))의 이력·작업본을 지우고 처음 상태로 되돌립니다."))return;
  toast("시연 자료를 준비합니다…");S.work=await api("/api/demo/setup",{reset});S.view=null;await refresh();toast("준비 완료: 원본 "+S.work.sources.length+"개");
}
async function checkSources(){
  const r=await api("/api/sources/check",{});
  if(!r.changed.length&&!r.missing.length){toast("바뀐 원본이 없습니다");return;}
  S.srcChange=r; await refresh();
  let h=r.changed.map(c=>`<p><b>${esc(c.name)}</b> 내용이 바뀌었습니다.<br><span class="small muted">이 파일을 출처로 쓰는 칸 ${c.affected.length}개</span></p>`).join("")+
        r.missing.map(m=>`<p><b>${esc(m.name)}</b> 파일이 없습니다(이동·삭제).</p>`).join("");
  if(await ask("원본 변경 감지",h+"<p>지금 다시 검증할까요? 바뀐 칸만 따로 보여 드립니다.</p>")) {showTab("check");runVerify(false);}
}
function pickWork(){openFs("작업 폴더 열기·만들기","dir",openWork);}
function pickTarget(){if(!S.work){toast("먼저 작업 폴더를 여세요",true);return;}
  openFs("검증할 한글 문서(hwpx) 선택","file",async p=>{toast("작업본을 만드는 중…");const r=await api("/api/target",{path:p});S.work=r.state;renderPrep();toast(`작업본 v001 생성: 숫자 칸 ${r.items}개`);},{ext:[".hwpx"]});}
function pickSources(folder){if(!S.work){toast("먼저 작업 폴더를 여세요",true);return;}
  if(folder) openFs("원본 폴더 추가(폴더 안의 xlsx·hwpx 모두)","dir",async p=>addSrc(Array.isArray(p)?p:[p]),{multi:true,allowDir:true});
  else openFs("원본 파일 추가","file",async p=>addSrc(p),{multi:true,ext:[".xlsx",".xlsm",".hwpx"]});}
async function addSrc(paths){toast("원본을 읽는 중…");const r=await api("/api/sources/add",{paths});S.work=r.state;renderPrep();
  toast(`추가 ${r.added.length}개`+(r.skipped.length?` · 건너뜀 ${r.skipped.length}개`:"")+(r.failed.length?` · 실패 ${r.failed.length}개`:""),r.failed.length>0);}
