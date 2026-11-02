/* [3. 입력하기] 원본 셀을 골라 문서 칸에 넣기
 * 원본 파트(grid)·수정 파트(input) 주소를 씀
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
async function enterInput(){
  if(!S.work||!S.work.version){$("#docView2").innerHTML='<div class="empty">문서를 먼저 선택하세요</div>';return;}
  if(!S.view||!S.view.blocks) S.view=await api("/api/view");
  renderDocInto($("#docView2"),"input");
  const srcs=S.work.sources; const cur=$("#inSrc").value;
  $("#inSrc").innerHTML=srcs.map(s=>`<option value="${s.sid}">${s.sid} · ${esc(s.name)}</option>`).join("");
  if(cur&&srcs.some(s=>s.sid===cur))$("#inSrc").value=cur;
  if(srcs.length) loadSheets(true);
}
function pickTarget2(k){S.inTarget=k;$("#inTarget").textContent=S.view.items[k].label+"  ("+k+")";
  $$("#docView2 .num").forEach(x=>x.classList.toggle("sel",x.dataset.k===k));}
function loadSheets(keep){const s=S.work.sources.find(x=>x.sid===$("#inSrc").value);if(!s)return;const cur=$("#inSheet").value;
  $("#inSheet").innerHTML=s.sheets.map(n=>`<option>${esc(n)}</option>`).join("");if(keep&&s.sheets.includes(cur))$("#inSheet").value=cur;loadGrid();}
async function loadGrid(){
  const sid=$("#inSrc").value,sh=$("#inSheet").value; if(!sid)return;
  const g=await api(`/api/grid?sid=${encodeURIComponent(sid)}&sheet=${encodeURIComponent(sh)}&nr=200&nc=40`); S.grid=g; S.gsel=null; $("#inSel").textContent="없음";
  let h=`<table class="grid"><tr><th></th>${g.cols.map(c=>`<th>${esc(c)}</th>`).join("")}</tr>`;
  g.rows.forEach((row,i)=>{h+=`<tr><td class="rh">${g.r0+i+1}</td>`+row.map((c,j)=>`<td data-r="${g.r0+i}" data-c="${g.c0+j}" class="${c.n?"n":""}" title="${esc(c.t)}">${esc(c.t)}</td>`).join("")+"</tr>";});
  $("#gridWrap").innerHTML=h+"</table>"+(g.maxr>=g.r0+200?'<div class="small muted" style="padding:6px">앞 200행까지 표시</div>':"");
  let down=null;
  $$("#gridWrap td[data-r]").forEach(td=>{
    td.onmousedown=e=>{down=[+td.dataset.r,+td.dataset.c];setGsel(down,down);e.preventDefault();};
    td.onmouseover=()=>{if(down)setGsel(down,[+td.dataset.r,+td.dataset.c]);};
  });
  document.onmouseup=()=>{down=null;};
}
function setGsel(a,b){S.gsel={r0:Math.min(a[0],b[0]),c0:Math.min(a[1],b[1]),r1:Math.max(a[0],b[0]),c1:Math.max(a[1],b[1])};
  $$("#gridWrap td[data-r]").forEach(td=>{const r=+td.dataset.r,c=+td.dataset.c;td.classList.toggle("on",r>=S.gsel.r0&&r<=S.gsel.r1&&c>=S.gsel.c0&&c<=S.gsel.c1);});
  const n=(S.gsel.r1-S.gsel.r0+1)*(S.gsel.c1-S.gsel.c0+1);
  const col=i=>{let s="";i++;while(i){const m=(i-1)%26;s=String.fromCharCode(65+m)+s;i=Math.floor((i-1)/26);}return s;};
  $("#inSel").textContent=S.grid.kind==="xlsx"?`${S.grid.sheet}!${col(S.gsel.c0)}${S.gsel.r0+1}`+(n>1?`:${col(S.gsel.c1)}${S.gsel.r1+1} (${n}칸)`:""):`${S.grid.sheet} ${S.gsel.r0+1}행 ${S.gsel.c0+1}열`+(n>1?` 외 (${n}칸)`:"");}
async function doInput(){
  if(!S.inTarget){toast("왼쪽 문서에서 넣을 칸을 먼저 누르세요",true);return;}
  if(!S.gsel){toast("오른쪽 원본에서 셀을 고르세요",true);return;}
  const dec=$("#inDec").value;
  const r=await api("/api/input",{sid:S.grid.sid,sheet:S.grid.sheet,...S.gsel,slot:S.inTarget,dec:dec===""?null:+dec,scale:+$("#inScale").value,comma:$("#inComma").checked});
  toast((r.count?`${r.count}칸을 대기 목록에 올렸습니다`:"")+(r.same?` 값이 이미 같은 ${r.same}칸은 출처만 확정해 기록했습니다`:"")+(r.skipped.length?` (건너뜀 ${r.skipped.length})`:""));
  S.view=await api("/api/view");await refresh();renderDocInto($("#docView2"),"input");
}

/* 이력 */
