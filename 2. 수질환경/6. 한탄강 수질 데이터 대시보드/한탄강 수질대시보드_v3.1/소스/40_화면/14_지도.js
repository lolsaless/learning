/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/14_지도.js] 지도 화면
   하는 일 : V월드 배경지도(자동 전환), 시군 경계, 시료번호 원·값 라벨(겹침 방지), 그래프 배너
   주요 이름: VW, setTiles, checkTiles, initMap, renderMap, placeLabels, openBanner
   이럴 때 고침: 배경지도 종류·주소, 원 크기·색, 배너 내용
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
registerView({ id:"map", label:"지도", kpi:true, item:true, render:()=>renderMap(),
  bind(){
    $("mpMonth").onchange=e=>{ S.mapMonth=e.target.value; renderMap(); };
    $("mpLabels").onchange=e=>{ S.mapLabels=e.target.checked; persist(); renderMap(); };
    $("mpLines").onchange=e=>{ S.mapLines=e.target.checked; persist(); renderMap(); };
    $("bnClose").onclick=()=>{ $("banner").classList.add("closed"); $("banner").setAttribute("aria-hidden","true"); bannerSt=null; };
    $("bnGo").onclick=()=>{ const n=bannerSt; S.sel.add(n); S.hl.add(n); setView("ts"); };
    $("bnProf").onclick=()=>{ const n=bannerSt; S.profRiver=stByName[n].river; S.hl.add(n); S.sel.add(n); setView("prof"); };
    $("bnHl").onclick=()=>{ toggleHl(bannerSt); };
    $("bnEdit").onclick=()=>{ S.focusRow = bannerSt; setView("edit"); };
    onTheme(()=>{ tileStat.key=""; });   // 다크/라이트가 바뀌면 배경지도 다시 고르기
  }});
/* ═════════ 지도 ═════════ */
let map, geoLayer, mkLayer, labLayer, lineLayer, tiles = [], bannerSt = null, tileStat = {ok:0, err:0, key:""};
const VW = {일반:["Base","png"], 백지도:["white","png"], 야간:["midnight","png"], 위성:["Satellite","jpeg"], 하이브리드:["Satellite","jpeg","Hybrid"]};
function rampColor(t){
  const stops = [css("--q100"),css("--q250"),css("--q400"),css("--q550"),css("--q700")].map(toHex);
  t = Math.max(0, Math.min(1, t)); const p = t*(stops.length-1), i = Math.min(stops.length-2, Math.floor(p)), f = p-i;
  const a = stops[i].match(/\w\w/g).map(x=>parseInt(x,16)), b = stops[i+1].match(/\w\w/g).map(x=>parseInt(x,16));
  return "#"+a.map((x,k)=>Math.round(x+(b[k]-x)*f).toString(16).padStart(2,"0")).join("");
}
function isDark(){ return document.documentElement.dataset.theme==="dark" || (document.documentElement.dataset.theme!=="light" && matchMedia("(prefers-color-scheme: dark)").matches); }
function baseName(){ const b = S.base==="자동" ? (isDark()?"야간":"일반") : S.base; return CFG.vworldKey ? b : "없음"; }
function setTiles(){
  const b = baseName(), key = b+"|"+CFG.vworldKey;
  if(tileStat.key===key) return;
  tiles.forEach(t=>map.removeLayer(t)); tiles = []; tileStat = {ok:0, err:0, key}; $("mpMsg").hidden = true;
  if(b!=="없음" && VW[b]){
    const [lay, ext, over] = VW[b];
    const mk = (l,e) => L.tileLayer(`https://api.vworld.kr/req/wmts/1.0.0/${CFG.vworldKey}/${l}/{z}/{y}/{x}.${e}`,
      {minZoom:6, maxZoom:19, maxNativeZoom:18, attribution:'© <a href="https://www.vworld.kr" target="_blank" rel="noopener">V월드(국토교통부)</a>', errorTileUrl:""});
    tiles.push(mk(lay,ext)); if(over) tiles.push(mk(over,"png"));
    tiles.forEach(t=>{ t.on("tileload", ()=>tileStat.ok++); t.on("tileerror", ()=>{ tileStat.err++; checkTiles(); }); t.addTo(map); t.bringToBack(); });
    setTimeout(checkTiles, 5000);
  }
  if(geoLayer) geoLayer.setStyle(geoStyle);
  document.querySelectorAll("#mpBase button").forEach(x=>x.setAttribute("aria-pressed", x.dataset.b===S.base));
}
function checkTiles(){
  if(tileStat.err>=4 && tileStat.ok===0){
    const file = location.protocol==="file:";
    $("mpMsg").hidden = false;
    $("mpMsg").innerHTML = `<button class="iconbtn" style="float:right;padding:0 6px;margin-left:6px" onclick="this.parentElement.hidden=true" aria-label="닫기">✕</button><b>V월드 배경지도를 불러오지 못했습니다.</b><br>${file?"파일을 직접 열면 V월드가 요청을 거절할 수 있습니다. 폴더의 <b>대시보드_열기.bat</b>로 열어 보세요.<br>":""}인증키 발급 때 등록한 서비스 URL과 지금 주소(${esc(location.origin==="null"?"파일":location.origin)})가 같은지, 인터넷 연결이 되는지 확인하세요. 지금은 시군 경계만 표시합니다.`;
    tiles.forEach(t=>map.removeLayer(t)); tiles = []; if(geoLayer) geoLayer.setStyle(geoStyle);
  }
}
const geoStyle = f => { const t = tiles.length>0;
  return {color:css("--map-stroke"), weight:f.properties.focus?1.6:0.8, dashArray:f.properties.focus?null:"3 3",
    fillColor:f.properties.focus?css("--map-focus"):css("--map-fill"), fillOpacity: t ? 0 : (f.properties.focus?.6:.35)}; };
function initMap(){
  if(map) return;
  map = L.map("map", {zoomControl:false, attributionControl:true}).setView([37.93,127.15], 10);
  L.control.zoom({position:"bottomright"}).addTo(map);
  if(D.geo){ geoLayer = L.geoJSON(D.geo, {style:geoStyle, interactive:false}).addTo(map); }
  lineLayer = L.layerGroup().addTo(map); mkLayer = L.layerGroup().addTo(map); labLayer = L.layerGroup().addTo(map);
  const pts = ST.filter(s=>s.lat&&s.lon).map(s=>[s.lat,s.lon]);
  if(pts.length) map.fitBounds(pts, {paddingTopLeft:[30,60], paddingBottomRight:[innerWidth>900?450:30, 30]});
  map.on("zoomend moveend", placeLabels);
  map.on("click", onMapPick);
  const seg = $("mpBase");
  const opts = CFG.vworldKey ? ["자동","일반","백지도","위성","하이브리드","야간","없음"] : ["없음"];
  seg.innerHTML = opts.map(b=>`<button data-b="${b}" aria-pressed="${b===S.base}">${b==="없음"?"경계만":b}</button>`).join("");
  seg.querySelectorAll("button").forEach(b=>b.onclick=()=>{ S.base=b.dataset.b; persist(); setTiles(); });
  if(!CFG.vworldKey){ $("mpMsg").hidden=false; $("mpMsg").textContent = "V월드 인증키가 없어 시군 경계만 표시합니다. DB '설정' 시트의 VWORLD_KEY에 키를 넣고 대시보드를 다시 만드세요."; }
}
function mapValue(n){
  const v = series(n,S.item);
  if(S.mapMonth==="mean") return stats(v).mean;
  const idx = S.mapMonth==="last" ? v.reduce((a,x,i)=>x!=null?i:a,-1) : months().indexOf(S.mapMonth);
  return idx>=0 ? v[idx] : null;
}
let labelItems = [];
function placeLabels(){
  if(!map) return; labLayer.clearLayers();
  if(!S.mapLabels) return;
  const placed = [], W = 7.2;
  const items = labelItems.slice().sort((a,b)=>(b.hl-a.hl)||(b.v-a.v));
  for(const it of items){
    const p = map.latLngToContainerPoint([it.lat,it.lon]), w = it.text.length*W+12, h = 16;
    const boxes = [{x:p.x+10, y:p.y-8, cls:""}, {x:p.x-10-w, y:p.y-8, cls:"left"}];
    const ok = boxes.find(b=>!placed.some(o=>b.x<o.x+o.w && b.x+w>o.x && b.y<o.y+o.h && b.y+h>o.y));
    if(!ok) continue;
    placed.push({x:ok.x, y:ok.y, w, h});
    L.marker([it.lat,it.lon], {interactive:false, keyboard:false, icon:L.divIcon({className:"", iconSize:[0,0],
      html:`<span class="vlab ${ok.cls} ${it.over?"over":""}">${esc(it.text)}</span>`})}).addTo(labLayer);
  }
}
function renderMap(){
  const it = itemOf(S.item), ms = months();
  $("mpTitle").textContent = `${it.name} 지점 분포`;
  const sel = $("mpMonth");
  sel.innerHTML = `<option value="last">최근 측정월</option><option value="mean">기간 평균</option>` + ms.slice().reverse().map(m=>`<option value="${m}">${mLong(m)}</option>`).join("");
  if(!(S.mapMonth==="last"||S.mapMonth==="mean"||ms.includes(S.mapMonth))) S.mapMonth="last";
  sel.value = S.mapMonth;
  $("mpLabels").checked = S.mapLabels; $("mpLines").checked = S.mapLines;
  initMap(); setTiles(); setTimeout(()=>map.invalidateSize(), 50);
  mkLayer.clearLayers(); lineLayer.clearLayers(); labelItems = [];
  const vs = ST.map(s=>mapValue(s.name)).filter(v=>v!=null).sort((a,b)=>a-b);
  const lo = vs[0] ?? 0, hi = vs[Math.floor((vs.length-1)*.95)] ?? 1;
  if(S.mapLines){
    RIVERS().forEach(rv=>{ const pts = ST.filter(s=>s.river===rv && s.lat).map(s=>[s.lat,s.lon]);
      if(pts.length>1) L.polyline(pts,{color:css("--accent"),weight:2,opacity:.5,dashArray:"5 6",interactive:false}).addTo(lineLayer); });
  }
  const t = targetOf(S.item);
  for(const s of ST){
    if(!s.lat||!s.lon) continue;
    const v = mapValue(s.name), on = S.sel.has(s.name), hl = S.hl.has(s.name), est = s.coord==="추정"||s.coord==="미입력";
    const fill = v==null ? css("--panel-2") : rampColor((v-lo)/((hi-lo)||1));
    const m = L.circleMarker([s.lat,s.lon], {radius: hl?11:8, color: hl?css("--ink"):css("--ink-2"), weight: hl?2.5:1.6, dashArray: est?"3 3":null,
      fillColor:fill, fillOpacity: on?0.95:0.35, opacity: on?1:0.5});
    m.bindTooltip(`<b>${esc(s.name)}</b> ${v!=null?fmt(v,it.dec)+" "+it.unit:"자료 없음"}${est?'<br><span style="color:var(--warn)">추정 좌표</span>':""}`, {direction:"top", offset:[0,-8], className:"nm"});
    m.on("click", ()=>openBanner(s.name));
    m.addTo(mkLayer);
    if(v!=null && on) labelItems.push({lat:s.lat, lon:s.lon, v, hl:hl?1:0, text:fmt(v,it.dec), over: t!=null && v>t});
  }
  placeLabels();
  const nEst = ST.filter(s=>s.coord==="추정"||s.coord==="미입력").length;
  $("mpLegend").innerHTML = `<b>${it.code}</b> <span style="color:var(--ink-3)">${S.mapMonth==="mean"?"기간 평균":S.mapMonth==="last"?"최근 측정월":mLong(S.mapMonth)} · ${it.unit}</span>
    <div class="bar" style="background:linear-gradient(90deg,${[0,.25,.5,.75,1].map(rampColor).join(",")})"></div>
    <div class="ends num"><span>${fmt(lo,it.dec)}</span><span>${fmt(hi,it.dec)}+</span></div>
    ${t!=null&&S.mapLabels?`<div class="lg"><b style="color:${col("above")}">빨간 값</b> 목표(${t}) 초과</div>`:""}
    ${nEst?`<div class="lg"><span class="cm est"></span>점선 = 추정 좌표 ${nEst}곳</div>`:""}
`;
  if(bannerSt) openBanner(bannerSt);
}
function openBanner(n){
  bannerSt = n;
  const s = stByName[n], it = itemOf(S.item), ms = months();
  const b = $("banner"); b.classList.remove("closed"); b.setAttribute("aria-hidden","false");
  $("bnName").textContent = n;
  $("bnSub").textContent = `${s.river} · ${s.addr}`;
  const qs = D.qc.filter(q=>q.st===n && q.type!=="coord" && ms.includes(q.m));
  $("bnWarn").innerHTML = [
    (s.coord==="추정"||s.coord==="미입력") ? `<div class="warnchip">지도 위치는 주소로 추정한 좌표입니다. [정보 수정]에서 지도로 지정하거나 V월드로 검색하세요.</div>` : (s.coordSrc?`<div class="infochip">좌표: ${esc(s.coordSrc)}</div>`:""),
    qs.length ? `<div class="warnchip">자료 점검 ${qs.length}건: ${[...new Set(qs.map(q=>`${mLabel(q.m)} ${q.item||""} ${QC_LABEL[q.type]}`))].slice(0,6).map(esc).join(", ")}${qs.length>6?" …":""}</div>` : ""].join("");
  const rows = [{name:n, values:series(n,S.item)}];
  const plan = {[n]:{color: S.custom[n] || css("--s1"), emph:true, dim:false}};
  const opt = trendOption({cats:ms.map(mLabel), mkeys:ms, rows, item:S.item, dec:it.dec, unit:it.unit, plan, compact:true, force:{labels:"all"}});
  const ch = chartOn("bnChart"); ch.setOption(opt, true); setTimeout(()=>ch.resize(), 30);
  const last = ms.length-1;
  $("bnItems").innerHTML = ITEMS.map(i=>{
    const v = series(n,i.code), k = v.reduce((a,x,j)=>x!=null?j:a,-1), sm = stats(v), val = k>=0?v[k]:null, c = cls(val, sm);
    return `<button class="c ${i.code===S.item?"on":""}" data-it="${i.code}" title="${esc(i.name)}${k>=0?" · "+mLong(ms[k]):""}"><div class="k">${i.code}${k>=0&&k!==last?" ("+mLabel(ms[k])+")":""}</div>
      <div class="v num">${val!=null?(loqText(n,ms[k],i.code)||fmt(val,i.dec)):"–"} ${c==="up"?`<span style="color:${col("above")};font-size:11px">▲</span>`:c==="dn"?`<span style="color:${col("below")};font-size:11px">▼</span>`:""}</div></button>`;
  }).join("");
  document.querySelectorAll("#bnItems .c").forEach(x=>x.onclick=()=>{ S.item=x.dataset.it; renderHeader(); refresh(); });
  $("bnHl").textContent = S.hl.has(n) ? "강조 해제" : "강조 추가";
  $("bnProf").hidden = !RIVERS().includes(s.river);
}
