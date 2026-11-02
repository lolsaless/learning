/* [1. 작업 준비] 작업 폴더·대상 문서·원본 등록
 * 원본 파트(sources)·문서 파트(document) 주소를 씀
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
function renderPrep(){
  const w=S.work;
  $("#hdmeta").textContent=w?`작업 폴더: ${w.folder}  ·  문서: ${w.target_name||"-"}  ·  작업본 ${w.version?"v"+String(w.version.ver).padStart(3,"0"):"-"}  ·  작업자: ${w.user}`:"작업 폴더를 여세요";
  $("#wfolder").textContent=w?w.folder:"열린 작업 폴더 없음";
  $("#target").innerHTML=w&&w.target?`<div><b>${esc(w.target_name)}</b> ${w.read_only?'<span class="badge" style="background:var(--warn)">읽기 전용 검증</span>':'<span class="badge" style="background:var(--ok)">고칠 수 있음(hwpx)</span>'}</div><div class="path muted">${esc(w.target)}</div><div class="small">작업본: <span class="path">${esc(w.version.path)}</span></div>`:'<span class="muted">선택한 문서 없음</span>';
  $("#btnTarget").disabled=!w||!!(w&&w.version);
  $("#btnPaste").disabled=!w||!!(w&&w.version);
  if(S.state&&S.state.formats)$("#fmtList").textContent="("+[...new Set(S.state.formats.map(f=>f.ext.slice(1)))].join(" · ")+")";
  const srcs=w?w.sources:[];
  $("#srcCount").textContent=srcs.length?`${srcs.length}개 등록 · 기준 폴더: ${w.base_folder||"-"}`:"";
  if(!srcs.length){$("#srcTable").innerHTML='<tr><td class="muted">등록한 원본이 없습니다</td></tr>';return;}
  const base=w.base_folder||"";
  $("#srcTable").innerHTML="<tr><th>번호</th><th>파일</th><th>위치(기준 폴더 아래)</th><th>구분</th><th>시트·표</th><th>상태</th><th></th></tr>"+
   srcs.map(s=>{
     const rel=s.path.startsWith(base)?s.path.slice(base.length).replace(/^[\\/]/,""):s.path;
     const st=!s.exists?'<span class="badge" style="background:var(--bad)">파일 없음</span>':s.error&&s.status==="fail"?`<span class="badge" style="background:var(--bad)" title="${esc(s.error)}">읽기 실패</span>`:s.error?`<span class="badge" style="background:var(--warn)" title="${esc(s.error)}">주의</span>`:'<span class="badge" style="background:var(--ok)">정상</span>';
     return `<tr><td>${s.sid}</td><td>${esc(s.name)}</td><td class="path muted">${esc(rel)} <span class="badge">${esc(s.fmt||"")}</span></td>
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
  let h=r.changed.map(c=>`<p><b>${esc(c.name)}</b> 내용이 바뀌었습니다.<br><span class="small muted">이 파일을 출처로 쓰는 칸 ${c.affected.length}개</span></p>`+(c.diff?diffHtml(c.diff,c.impact):"")).join("")+
        r.missing.map(m=>`<p><b>${esc(m.name)}</b> 파일이 없습니다(이동·삭제).</p>`).join("");
  if(await ask("원본 변경 감지",h+"<p>지금 다시 검증할까요? 바뀐 칸만 따로 보여 드립니다.</p>")) {showTab("check");runVerify(false);}
}
function pickWork(){openFs("작업 폴더 열기·만들기","dir",openWork);}
function pickTarget(){if(!S.work){toast("먼저 작업 폴더를 여세요",true);return;}
  openFs("검증할 문서 선택(한글·워드·PDF·글자 파일)","file",async p=>{toast("문서를 읽는 중…");const r=await api("/api/target",{path:p});S.work=r.state;renderPrep();
    toast(r.read_only?`읽기 전용 검증 준비: 숫자 칸 ${r.items}개 (고치기는 hwpx 에서만)`:`작업본 v001 생성: 숫자 칸 ${r.items}개`);
    (r.warnings||[]).forEach(w=>toast(w,true));},{ext:docExts()});}
function docExts(){return (S.state.formats||[]).filter(f=>f.kind==="doc").map(f=>f.ext);}
function allExts(){return (S.state.formats||[]).map(f=>f.ext);}
async function pasteTarget(){if(!S.work){toast("먼저 작업 폴더를 여세요",true);return;}
  const ok=await ask("글 붙여넣기로 검증",`<div class="small muted" style="margin-bottom:6px">생성형 AI 가 쓴 보고서 초안, 메일 본문 등을 붙여 넣으면 숫자·합계·증감률·요일을 원본과 대조합니다. 원본에 없는 숫자는 '출처 미확인'으로 표시됩니다(AI 가 지어낸 숫자 찾기).</div>
    <input id="pasteName" placeholder="이름(선택)" style="width:100%;margin-bottom:6px"><textarea id="pasteText" style="width:100%;height:260px" placeholder="여기에 글을 붙여 넣으세요. 표는 마크다운 표(| 가 | 나 |)나 탭으로 구분된 줄이면 표로 읽습니다."></textarea>`);
  if(!ok)return;
  const r=await api("/api/target/text",{text:$("#pasteText").value,name:$("#pasteName").value});S.work=r.state;renderPrep();toast(`붙여 넣은 글 검증 준비: 숫자 칸 ${r.items}개`);}
function pickSources(folder){if(!S.work){toast("먼저 작업 폴더를 여세요",true);return;}
  if(folder) openFs("원본 폴더 추가(폴더 안의 xlsx·hwpx 모두)","dir",async p=>addSrc(Array.isArray(p)?p:[p]),{multi:true,allowDir:true});
  else openFs("원본 파일 추가","file",async p=>addSrc(p),{multi:true,ext:allExts()});}
async function addSrc(paths){toast("원본을 읽는 중…");const r=await api("/api/sources/add",{paths});S.work=r.state;renderPrep();
  toast(`추가 ${r.added.length}개`+(r.skipped.length?` · 건너뜀 ${r.skipped.length}개`:"")+(r.failed.length?` · 실패 ${r.failed.length}개`:""),r.failed.length>0);}

/* 재제출 비교(재제출 비교 파트 compare) */
function diffHtml(d,imp){
  const ch=(d.changed||[]).filter(c=>c.numeric).slice(0,40);
  let h=`<div class="small">숫자 칸 <b>${d.numeric_changed}</b>개 바뀜`+(d.added_rows.length?` · 행 추가 ${d.added_rows.length}`:"")+(d.removed_rows.length?` · 행 삭제 ${d.removed_rows.length}`:"")+(d.truncated?" · (일부만 표시)":"")+`</div>`;
  if(ch.length) h+=`<table class="list small"><tr><th>원본 칸</th><th>이전</th><th>이후</th></tr>`+ch.map(c=>`<tr><td>${esc(c.ref)}</td><td>${esc(c.old_text)}</td><td><b>${esc(c.new_text)}</b></td></tr>`).join("")+"</table>";
  if(imp&&imp.length) h+=`<div class="small" style="margin-top:6px"><b>고쳐야 할 문서 칸 ${imp.length}개</b></div><table class="list small"><tr><th>문서 칸</th><th>지금</th><th>새 값(배율·자릿수 반영)</th></tr>`+imp.map(x=>`<tr><td>${esc(x.label)}</td><td>${esc(x.doc_now)}</td><td><b>${esc(x.doc_new||"(다시 검증해 확인)")}</b>${x.same?" (그대로)":""}</td></tr>`).join("")+"</table>";
  else if(imp) h+=`<div class="small muted">이 칸들을 출처로 쓰는 문서 칸은 없습니다(검증을 먼저 하면 영향을 계산합니다).</div>`;
  return h;
}
function pickResubmit(){if(!S.work||!S.work.sources.length){toast("먼저 원본을 등록하세요",true);return;}
  openFs("다시 받은 파일 선택","file",async p=>{
    const r=await api("/api/resubmit/check",{path:p});
    if(!r.candidates.length){toast("등록된 원본 중 짝이 되는 파일을 찾지 못했습니다(이름·내용이 많이 다름)",true);return;}
    const c=r.candidates[0];
    const h=`<p><b>${esc(r.name)}</b> → 등록 원본 <b>${esc(c.name)}</b>의 새 판으로 보입니다 <span class="small muted">(이름 ${Math.round(c.name_match*100)}% · 내용 ${Math.round(c.content*100)}%)</span></p>`+diffHtml(r.diff,r.impact)+
      `<p class="small muted">[확인]을 누르면 원본을 이 파일로 바꾸고(이전 판은 작업 폴더 '원본보관'에 남음) 다시 검증합니다.</p>`;
    if(await ask("다시 받은 파일 비교",h)){await api("/api/resubmit/apply",{sid:r.sid,path:p});await refresh();showTab("check");runVerify(false);}
  },{ext:allExts()});}
