/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/19_지점관리.js] 지점 관리 화면
   하는 일 : 주소·좌표 편집, 지도 클릭 지정, V월드 후보, 저장(서버)·임시 보관(파일)
   주요 이름: setEdit, renderEdit, geoSearch, startPick, onMapPick, saveEdits, detectServer
   이럴 때 고침: 편집 가능한 칸, 저장 방식
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
registerView({ id:"edit", label:"지점 관리", kpi:false, item:false, render:()=>renderEdit(),
  badge(){ return editCount(); },
  bind(){
    $("edQ").oninput=()=>renderEdit();
    $("edSave").onclick=saveEdits;
    $("edUndo").onclick=()=>{ if(!editCount()) return; EDITS = {}; persistEdits(); applyEdits(); $("edMsg").hidden=true; refresh(); toast("저장하지 않은 수정 내용을 모두 취소했습니다"); };
    $("edCopy").onclick=()=>copyText(tsvText(stationTsv()));
    detectServer();
    if(editCount()) setTimeout(()=>toast(`저장하지 않은 지점 수정 ${editCount()}건이 화면에 반영되어 있습니다 — 지점 관리에서 저장하세요`), 600);
  }});
/* ═════════ 지점 관리(주소·좌표 수정) ═════════ */
const editCount = () => Object.values(EDITS).reduce((a,o)=>a+Object.keys(o).length,0);
function setEdit(name, key, val){
  const o = ORIG[name]; let v = val;
  if(["lat","lon","order"].includes(key)) v = (val===""||val==null) ? null : +val;
  if(typeof v==="string") v = v.trim();
  EDITS[name] ||= {};
  const same = (o[key]??"")==(v??"") ;
  if(same) delete EDITS[name][key]; else EDITS[name][key] = v;
  if(!Object.keys(EDITS[name]).length) delete EDITS[name];
  persistEdits(); applyEdits(); updateEditBadge();
}
function updateEditBadge(){ const n = editCount(); updateBadges(); if($("edSave")) $("edSave").textContent = n ? `변경 저장 (${n})` : "변경 저장"; }
onRefresh(updateEditBadge);
function renderEdit(){
  const q = ($("edQ").value||"").trim();
  $("edMode").className = "mode " + (SERVER?"on":"off");
  $("edMode").textContent = SERVER ? "● 서버 연결됨 — 저장하면 DB 엑셀에 바로 반영" : "● 파일로 열림 — 저장하려면 대시보드_열기.bat로 여세요";
  $("riverList").innerHTML = RIVERS_ALL().map(r=>`<option value="${esc(r)}">`).join("");
  const coordOpts = ["확인","브이월드","추정","미입력"];
  let h = `<thead><tr><th>정렬</th><th class="l">하천명(대분류)</th><th class="l">시료번호</th><th class="l">시군</th><th class="l">주소</th><th>위도</th><th>경도</th><th class="l">좌표상태</th><th class="l">비고</th><th class="l">좌표</th></tr></thead><tbody>`;
  for(const s of ST){
    if(q && !(s.name+s.river+s.addr+(s.note||"")).includes(q)) continue;
    const e = EDITS[s.name]||{}, d = k => k in e ? "dirty" : "";
    const inp = (k, w, cls="", type="text") => `<td class="${d(k)}"><input data-n="${esc(s.name)}" data-k="${k}" type="${type}" class="${cls}" value="${esc(s[k]??"")}" ${w?`style="min-width:${w}px"`:""} ${k==="river"?'list="riverList"':""} step="any"></td>`;
    h += `<tr data-row="${esc(s.name)}">${inp("order",52,"num","number")}${inp("river",90)}<td class="l"><b>${esc(s.name)}</b></td>${inp("sigun",62)}${inp("addr",250)}${inp("lat",92,"num","number")}${inp("lon",100,"num","number")}
      <td class="${d("coord")}"><select data-n="${esc(s.name)}" data-k="coord">${coordOpts.map(o=>`<option ${o===s.coord?"selected":""}>${o}</option>`).join("")}</select></td>${inp("note",90)}
      <td class="l" style="white-space:nowrap"><button class="btn-s" data-pick="${esc(s.name)}" title="지도를 눌러 위치 지정">지도</button> <button class="btn-s" data-geo="${esc(s.name)}" ${SERVER&&CFG.vworldKey?"":"disabled"} title="${SERVER?(CFG.vworldKey?"V월드로 주소 검색":"설정 시트에 V월드 키 필요"):"서버로 열어야 사용 가능"}">V월드</button></td></tr>`;
  }
  const tb = $("edTbl"); tb.innerHTML = h + "</tbody>";
  tb.querySelectorAll("[data-k]").forEach(x=>x.onchange=()=>{ setEdit(x.dataset.n, x.dataset.k, x.value); x.closest("td").classList.toggle("dirty", x.dataset.k in (EDITS[x.dataset.n]||{})); });
  tb.querySelectorAll("[data-pick]").forEach(b=>b.onclick=()=>startPick(b.dataset.pick));
  tb.querySelectorAll("[data-geo]").forEach(b=>b.onclick=()=>geoSearch(b.dataset.geo, b));
  if(S.focusRow){ const r = tb.querySelector(`tr[data-row="${CSS.escape(S.focusRow)}"]`); if(r){ r.scrollIntoView({block:"center"}); r.querySelector('input[data-k="addr"]')?.focus(); } S.focusRow = null; }
  updateEditBadge();
}
async function geoSearch(name, btn){
  const s = stByName[name], tr = btn.closest("tr");
  tr.nextElementSibling?.classList.contains("sub") && tr.nextElementSibling.remove();
  const sub = document.createElement("tr"); sub.className = "sub"; sub.innerHTML = `<td colspan="10">V월드에서 '${esc(s.addr)}' 검색 중…</td>`; tr.after(sub);
  try{
    const r = await fetch("/api/geocode", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({addr:s.addr, sigun:s.sigun})}).then(x=>x.json());
    if(!r.ok) throw new Error(r.error);
    if(!r.hits.length){ sub.firstElementChild.textContent = "검색 결과가 없습니다. 주소에 지번(예: ○○리 123-4)이나 다리 이름을 넣고 다시 검색하거나 [지도]로 지정하세요."; return; }
    sub.firstElementChild.innerHTML = `<div class="hits">${r.hits.map((h,i)=>`<button class="btn-s" data-i="${i}">${h.inside?"":"⚠ 시군 밖 · "}${esc(h.label)} <span class="num" style="color:var(--ink-3)">${h.lat.toFixed(5)}, ${h.lon.toFixed(5)}</span></button>`).join("")}<button class="btn-s" data-x>닫기</button></div>`;
    sub.querySelectorAll("[data-i]").forEach(b=>b.onclick=()=>{ const h = r.hits[+b.dataset.i];
      setEdit(name,"lat",h.lat); setEdit(name,"lon",h.lon); setEdit(name,"coord","브이월드"); setEdit(name,"coordSrc","V월드 "+h.label); renderEdit(); toast(`${name} 좌표를 바꿨습니다. [변경 저장]을 누르세요.`); });
    sub.querySelector("[data-x]").onclick=()=>sub.remove();
  }catch(e){ sub.firstElementChild.textContent = "검색 실패: " + e.message; }
}
let pickName = null;
function startPick(name){
  pickName = name; setView("map");
  setTimeout(()=>{
    $("mpMsg").hidden = false;
    $("mpMsg").innerHTML = `<b>${esc(name)}</b> 위치를 지도에서 누르세요. <button class="iconbtn" id="pickCancel" style="padding:0 8px">취소</button>`;
    $("pickCancel").onclick = ()=>{ pickName=null; $("map").parentElement.classList.remove("picking"); $("mpMsg").hidden=true; };
    $("map").parentElement.classList.add("picking");
    const s = stByName[name]; if(s.lat) map.setView([s.lat,s.lon], Math.max(map.getZoom(), 13));
  }, 120);
}
function onMapPick(e){
  if(!pickName) return false;
  const n = pickName; pickName = null; $("map").parentElement.classList.remove("picking");
  setEdit(n,"lat",+e.latlng.lat.toFixed(6)); setEdit(n,"lon",+e.latlng.lng.toFixed(6)); setEdit(n,"coord","확인"); setEdit(n,"coordSrc","대시보드에서 지도로 지정");
  renderMap();
  $("mpMsg").hidden = false;
  $("mpMsg").innerHTML = `<b>${esc(n)}</b> 위치를 ${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}로 바꿨습니다(아직 저장 안 됨). <button class="iconbtn" id="pickGo" style="padding:0 8px">지점 관리에서 저장</button>`;
  $("pickGo").onclick = ()=>{ S.focusRow = n; setView("edit"); };
  return true;
}
async function saveEdits(){
  const n = editCount(); if(!n){ toast("바뀐 내용이 없습니다."); return; }
  const msg = $("edMsg");
  if(!SERVER){ msg.hidden=false; msg.innerHTML = `지금은 HTML 파일로 열려 있어 DB 엑셀에 저장할 수 없습니다. 수정 내용 ${n}건은 <b>이 브라우저에 임시 보관</b>되어 화면에는 반영됩니다.<br>DB에 저장하려면 ① 폴더의 <b>대시보드_열기.bat</b>로 열어 [변경 저장]을 누르거나 ② [표 복사]로 복사해 엑셀 지점정보 시트에 붙여넣으세요.`; return; }
  const edits = {};
  for(const [name, o] of Object.entries(EDITS)){ edits[name] = {}; for(const [k,v] of Object.entries(o)) edits[name][EDIT_FIELDS[k]] = v; }
  $("edSave").disabled = true; msg.hidden=false; msg.textContent = "저장 중…";
  try{
    const r = await fetch("/api/stations", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({edits})}).then(x=>x.json());
    if(!r.ok) throw new Error(r.error);
    EDITS = {}; persistEdits();
    msg.textContent = `저장했습니다(${r.changed.length}개 시료번호). 대시보드를 다시 불러옵니다…`;
    setTimeout(()=>location.reload(), 700);
  }catch(e){ msg.innerHTML = `<b>저장하지 못했습니다.</b> ${esc(e.message)}`; $("edSave").disabled = false; }
}
function stationTsv(){
  return [["정렬순서","지점ID","하천명","시료번호","시군","주소","위도","경도","좌표상태","좌표출처","비고"],
    ...ST.map(s=>[s.order??"", s.id, s.river, s.name, s.sigun, s.addr, s.lat??"", s.lon??"", s.coord, s.coordSrc, s.note])];
}
async function detectServer(){
  if(!/^https?:/.test(location.protocol)) return;
  try{ const r = await fetch("/api/ping", {cache:"no-store"}).then(x=>x.json()); SERVER = !!r.server; }catch(e){ SERVER = false; }
  if(["edit","set"].includes(S.view)) refresh();
}
