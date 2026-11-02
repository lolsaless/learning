/* [6. 구성도] 층·구성요소·파일·함수·화면 주소를 코드에서 읽어 보여 준다
 * /api/partmap 을 씀(app/web/partmap.py)
 * 화면 파일 규칙: 함수 이름은 전역(onclick="…"에서 부름). 서버와는 api() 로만 주고받는다.
 */
"use strict";
let MAP=null;
async function enterMap(){
  MAP=await api("/api/partmap");
  $("#mapSum").textContent=`${MAP.app} v${MAP.version} · 구성요소 ${MAP.components.length}개 · 파일 ${MAP.total_files}개 · 코드 ${MAP.total_lines.toLocaleString()}줄`;
  $("#mapLayers").innerHTML=MAP.layers.map(l=>`<div class="lay"><div class="layh"><b>[${l.id}] ${esc(l.name)}</b> <span class="muted small">${esc(l.role)}</span></div>
    <div class="comps">${MAP.components.filter(c=>c.layer===l.id).map(c=>`<div class="comp${c.on===false?" off":""}" data-id="${c.id}" onclick="mapPick('${c.id}')">
    <div class="cid">${c.id}</div><div class="cn">${esc(c.name)}</div><div class="cl muted">${c.files.length}파일 · ${c.lines.toLocaleString()}줄</div></div>`).join("")}</div></div>`).join("");
  $("#mapFix").innerHTML="<tr><th>하고 싶은 일</th><th>구성요소</th><th>볼 곳</th></tr>"+MAP.fix_guide.map(g=>`<tr><td>${esc(g.task)}</td><td>${esc(g.where)}</td><td class="path">${esc(g.file)}</td></tr>`).join("");
}
function mapPick(id){
  const c=MAP.components.find(x=>x.id===id); if(!c)return;
  const usedBy=MAP.components.filter(x=>x.uses.includes(id)).map(x=>x.id);
  $$(".comp").forEach(el=>{const i=el.dataset.id;el.classList.toggle("sel",i===id);el.classList.toggle("use",c.uses.includes(i));el.classList.toggle("usedby",usedBy.includes(i));});
  const link=ids=>ids.length?ids.map(i=>{const x=MAP.components.find(y=>y.id===i);return `<a href="#" onclick="mapPick('${i}');return false">${i} ${esc(x?x.name:"")}</a>`;}).join(", "):"없음";
  $("#mapDetail").innerHTML=`<div class="detail"><h4>${c.id} ${esc(c.name)}${c.on===false?' <span class="badge">꺼짐</span>':""}</h4>
   <div class="small" style="margin:6px 0">${esc(c.role||"")}</div>
   <div class="kv"><div>쓰는 것</div><div>${link(c.uses)}</div><div>쓰이는 곳</div><div>${link(usedBy)}</div>
   <div>화면 주소</div><div class="path">${c.routes.length?c.routes.map(esc).join("<br>"):"없음"}</div></div>
   ${c.files.map(f=>`<div class="src"><div><b class="path">${esc(f.path)}</b> <span class="muted small">${f.lines}줄</span></div>
     <div class="small">${esc(f.doc||"")}</div>
     ${(f.classes||[]).map(k=>`<div class="small" style="margin-top:4px"><b>class ${esc(k.name)}</b> <span class="muted">${esc(k.doc)}</span>
       ${k.methods.length?`<div class="muted" style="margin-left:10px">${k.methods.map(m=>esc(m.name)+"()").join(" · ")}</div>`:""}</div>`).join("")}
     ${(f.funcs||[]).length?`<div class="small muted" style="margin-top:4px">${f.funcs.map(x=>`<span title="${esc(x.doc)}">${esc(x.name)}()</span>`).join(" · ")}</div>`:""}
     ${(f.api||[]).length?`<div class="small muted">부르는 주소: ${f.api.map(esc).join(", ")}</div>`:""}</div>`).join("")}</div>`;
}
