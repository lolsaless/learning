/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [90_시작/02_이벤트_연결.js] 버튼 연결
   하는 일 : 왼쪽 패널(선택·표시 옵션·색상)과 공통 버튼(그림 저장·테마 변화)을 기능에 연결하고, 각 화면 부품의 bind를 부른다
   주요 이름: bind
   이럴 때 고침: 왼쪽 패널에 새 옵션·버튼을 연결할 때(화면 안 버튼은 그 화면 부품의 bind에서 연결)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function bind(){
  /* 왼쪽 패널: 선택 */
  $("selAll").onclick=()=>{ S.sel=new Set(ST.map(s=>s.name)); refresh(); };
  $("selNone").onclick=()=>{ S.sel=new Set(); refresh(); };
  $("hlNone").onclick=()=>{ S.hl=new Set(); refresh(); };
  $("reColor").onclick=()=>{ const ns = selectedOrdered(); reassignColors(ns, true); ns.forEach(n=>delete S.custom[n]); refresh(); toast("색을 무작위로 다시 배정했습니다"); };
  $("q").oninput=e=>{ S.q=e.target.value; renderSide(); };
  $("menuBtn").onclick=()=>{ const s=$("side"); s.classList.toggle("collapsed"); $("menuBtn").setAttribute("aria-expanded", !s.classList.contains("collapsed")); };
  /* 왼쪽 패널: 표시 옵션 */
  const mo = M.map((m,i)=>`<option value="${i}">${multiYear?m:mLabel(m)}</option>`).join("");
  $("oFrom").innerHTML=mo; $("oTo").innerHTML=mo; syncOpts();
  $("oBand").onchange=e=>{ S.opt.band=e.target.value; syncOpts(); refresh(); };
  $("oK").onchange=e=>{ const v=+e.target.value; if(v>0){ S.opt.k=v; refresh(); } };
  $("oP").onchange=e=>{ const v=+e.target.value; if(v>0){ S.opt.p=v; refresh(); } };
  $("oLabels").onchange=e=>{ S.opt.labels=e.target.value; refresh(); };
  $("oMean").onchange=e=>{ S.opt.mean=e.target.checked; refresh(); };
  $("oLimits").onchange=e=>{ S.opt.limits=e.target.checked; refresh(); };
  $("oScale").onchange=e=>{ S.opt.scale=e.target.value; refresh(); };
  $("oGaps").onchange=e=>{ S.opt.gaps=e.target.checked; refresh(); };
  $("oSpike").onchange=e=>{ S.opt.spike=e.target.checked; syncOpts(); refresh(); };
  $("oSpikeZ").onchange=e=>{ const v=+e.target.value; if(v>0){ S.opt.spikeZ=v; refresh(); } };
  $("oFrom").onchange=e=>{ S.from=+e.target.value; if(S.to<S.from) S.to=S.from; syncOpts(); refresh(); };
  $("oTo").onchange=e=>{ S.to=+e.target.value; if(S.from>S.to) S.from=S.to; syncOpts(); refresh(); };
  /* 왼쪽 패널: 색상 */
  const setC = () => { $("cAbove").value=toHex(col("above")); $("cBelow").value=toHex(col("below")); $("cBase").value=toHex(col("base")); $("cSpike").value=toHex(col("spike")); };
  setC();
  [["cAbove","above"],["cBelow","below"],["cBase","base"],["cSpike","spike"]].forEach(([id,k])=>$(id).onchange=e=>{ S.colors[k]=e.target.value; refresh(); });
  $("cReset").onclick=()=>{ S.colors={}; S.custom={}; setC(); refresh(); toast("색상을 기본값으로 되돌렸습니다"); };
  $("resetAll").onclick=()=>{ store.clear(); const d = defaults(); Object.assign(S, d, {sel:new Set(d.sel), hl:new Set(d.hl), profHidden:new Set()}); syncOpts(); setC(); renderHeader(); refresh(); toast("처음 화면으로 돌아갔습니다(저장 안 한 지점 수정은 유지)"); };
  /* 공통: 그림 저장 버튼(data-img="그래프 id") */
  document.querySelectorAll("[data-img]").forEach(b=>b.onclick=()=>{ const c = charts[b.dataset.img]; if(!c) return;
    saveFile(`한탄강_${S.item}_${b.dataset.img==="pfChart"?S.profRiver+"_종단":"시계열"}.png`, c.getDataURL({pixelRatio:2, backgroundColor:css("--panel")})); });
  /* 공통: 라이트/다크 바뀜 → 색 다시 읽기 */
  const rerender = ()=>{ setC(); THEME_HOOKS.forEach(f=>f()); refresh(); };
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", rerender);
  new MutationObserver(rerender).observe(document.documentElement, {attributes:true, attributeFilter:["data-theme"]});
  addEventListener("resize", ()=>$("app").style.setProperty("--hdr", $("hdr").offsetHeight+"px"));
  if(matchMedia("(min-width:981px)").matches) $("side").classList.remove("collapsed");
  /* 각 화면·부품의 버튼 연결 */
  VIEW_REG.forEach(v=>v.bind && v.bind());
  INIT_HOOKS.forEach(f=>f());
}
