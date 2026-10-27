/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [90_시작/01_갱신_알림_복사.js] 화면 갱신·알림·복사
   하는 일 : 옵션 칸 맞추기, 화면 전체 다시 그리기, 알림, 표 복사, 파일 저장
   주요 이름: syncOpts, refresh, toast, copyText, saveFile, tsvText
   이럴 때 고침: 고칠 일 거의 없음
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ═════════ 공통 갱신 ═════════ */
function syncOpts(){
  $("oBand").value=S.opt.band; $("oK").value=S.opt.k; $("oP").value=S.opt.p; $("oKwrap").hidden=S.opt.band!=="sd"; $("oPwrap").hidden=S.opt.band!=="pct";
  $("oLabels").value=S.opt.labels; $("oMean").checked=S.opt.mean; $("oLimits").checked=S.opt.limits; $("oScale").value=S.opt.scale; $("oGaps").checked=S.opt.gaps;
  $("oFrom").value=S.from; $("oTo").value=S.to;
  $("oSpike").checked=S.opt.spike; $("oSpikeZ").value=S.opt.spikeZ; $("oSpikeWrap").hidden=!S.opt.spike;
}
function refresh(){
  persist();
  $("app").style.setProperty("--hdr", $("hdr").offsetHeight+"px");
  if(!viewOf(S.view)) S.view = VIEW_REG[0].id;
  const cur = viewOf(S.view);
  VIEW_REG.forEach(v=>{ const el = $("v-"+v.id); if(el) el.hidden = v.id!==S.view; });
  $("itemSeg").style.visibility = (typeof cur.item==="function" ? cur.item() : cur.item) ? "visible" : "hidden";
  $("kpis").hidden = !cur.kpi;
  renderSide(); if(cur.kpi) renderKpis();
  cur.render();
  REFRESH_HOOKS.forEach(f=>f());
  updateBadges();
}
function toast(t){ const el=$("toast"); el.textContent=t; el.classList.add("show"); clearTimeout(toast._t); toast._t=setTimeout(()=>el.classList.remove("show"),1900); }
const tsvText = rows => rows.map(r=>r.join("\t")).join("\n");
async function copyText(t){ try{ await navigator.clipboard.writeText(t); toast("복사했습니다. 엑셀에 붙여넣기 하세요."); }
  catch(e){ const ta=document.createElement("textarea"); ta.value=t; document.body.appendChild(ta); ta.select(); try{ document.execCommand("copy"); toast("복사했습니다."); }catch(_){ toast("복사가 막혀 있습니다. 표를 직접 선택해 복사하세요."); } ta.remove(); } }
function saveFile(name, href){ try{ const a=document.createElement("a"); a.href=href; a.download=name; document.body.appendChild(a); a.click(); setTimeout(()=>a.remove(),500); }catch(e){ toast("이 환경에서는 저장할 수 없습니다."); } }
