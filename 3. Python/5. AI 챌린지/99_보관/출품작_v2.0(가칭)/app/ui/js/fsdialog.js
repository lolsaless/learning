/* [공통] 폴더·파일 고르기 창
 * openFs(제목, 'dir'|'file', 받을함수, 옵션)
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
/* 파일 고르기 창 */
let FS={mode:"dir",path:"",sel:new Set(),multi:false,ext:null,cb:null};
function openFs(title,mode,cb,opt={}){FS={mode,path:"",sel:new Set(),multi:!!opt.multi,ext:opt.ext||null,cb,allowDir:!!opt.allowDir};
  $("#fsTitle").textContent=title;$("#fsNew").style.display=mode==="dir"?"":"none";
  $("#fsHint").textContent=mode==="dir"?(FS.multi?"폴더를 눌러 고르거나(여러 개, 두 번 누르면 들어감) 고르지 않고 [선택]하면 지금 폴더 전체":"폴더 안으로 들어간 뒤 [선택]"):"파일을 누르고 [선택]"+(FS.multi?" (여러 개 가능)":"");
  $("#fsModal").classList.add("on");fsGo(opt.start||"");}
function closeModal(){$("#fsModal").classList.remove("on");}
async function fsGo(p){const j=await api("/api/fs?path="+encodeURIComponent(p));FS.path=j.path;FS.parent=j.parent;$("#fsPath").value=j.path;
  $("#fsList").innerHTML=j.entries.map((e,i)=>{const ok=e.dir||!FS.ext||FS.ext.some(x=>e.name.toLowerCase().endsWith(x));
    if(!ok)return"";return `<div class="fsitem" data-i="${i}" data-p="${esc(e.path)}" data-d="${e.dir?1:0}">${e.dir?"📁":(e.name.endsWith(".xlsx")?"📊":"📄")} <span>${esc(e.name)}</span></div>`}).join("")||'<div class="muted">비어 있음</div>';
  $$("#fsList .fsitem").forEach(el=>{el.onclick=()=>{const p=el.dataset.p;
     if(el.dataset.d==="1"&&!(FS.allowDir&&FS.multi)){fsGo(p);return;}
     if(el.dataset.d==="1"&&FS.allowDir&&FS.multi){ if(FS.sel.has(p))FS.sel.delete(p);else FS.sel.add(p); el.classList.toggle("sel");return;}
     if(!FS.multi){FS.sel=new Set([p]);$$("#fsList .fsitem").forEach(x=>x.classList.remove("sel"));}
     else if(FS.sel.has(p))FS.sel.delete(p);else FS.sel.add(p);
     el.classList.toggle("sel",FS.sel.has(p));};
   el.ondblclick=()=>{if(el.dataset.d==="1")fsGo(el.dataset.p);};});}
function fsUp(){if(FS.parent!==null)fsGo(FS.parent||"");}
async function fsMkdir(){const n=prompt("새 폴더 이름");if(!n||!FS.path)return;const j=await api("/api/fs/mkdir",{path:FS.path+(FS.path.endsWith("/")||FS.path.endsWith("\\")?"":(FS.path.includes("\\")?"\\":"/"))+n});fsGo(j.path);}
function fsOk(){let v;if(FS.mode==="dir"){ if(FS.multi&&FS.sel.size)v=[...FS.sel]; else v=FS.path; if(!v||!v.length){toast("폴더를 고르세요",true);return;} }
  else {v=[...FS.sel];if(!v.length){toast("파일을 고르세요",true);return;} if(!FS.multi)v=v[0];}
  closeModal();FS.cb(v);}
