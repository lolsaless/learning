/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/20_설정.js] 설정 화면(API 키 입력)
   하는 일 : V월드 인증키 입력·연결 시험, 화면 기본값·자료 점검 기준 수정, 저장(서버: DB 설정 시트 / 파일: 이 브라우저 임시 보관)
   주요 이름: SET_GROUPS, SET_EDIT, renderSettings, testVworldKey, saveSettings
   이럴 때 고침: 설정 묶음·순서, 설정 칸 모양, 키 시험 방법
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
registerView({ id:"set", label:"설정", kpi:false, item:false, render:()=>renderSettings(),
  badge(){ return Object.keys(SET_EDIT).length; },
  bind(){
    $("stSave").onclick = saveSettings;
    $("stUndo").onclick = ()=>{ SET_EDIT = {}; $("stMsg").hidden = true; renderSettings(); updateBadges(); };
    $("stLocalClear").onclick = ()=>{ LOCAL_SET = {}; try{ localStorage.removeItem(SETKEY); }catch(e){} toast("이 브라우저의 임시 설정을 지웠습니다. 다시 불러옵니다…"); setTimeout(()=>location.reload(), 600); };
  }});

/* 설정 묶음 — 설정 시트의 이름(왼쪽)과 같아야 함. 여기에 없는 설정은 '기타'에 나온다 */
const SET_GROUPS = [
  {title:"V월드 지도·주소 검색", keys:["VWORLD_KEY","VWORLD_DOMAIN"], note:"배경지도와 [V월드] 좌표 검색에 씁니다. 키는 V월드 오픈API에서 발급받고, 서비스 URL에 http://localhost:8765 를 등록하세요."},
  {title:"화면 기본값", keys:["기본배경지도","기본항목","평균대비_판정","평균대비_k","평균대비_p","특이경향_기준"], note:"저장하면 바로 적용됩니다."},
  {title:"자료 점검 기준", keys:["이상값_기준","이상값_배율","전월동일_항목수","정량한계_처리"], note:"대시보드를 다시 만들 때 계산됩니다(서버로 열었으면 저장 후 자동으로 다시 만듦)."},
];
let SET_EDIT = {};
const setVal = k => (k in SET_EDIT) ? SET_EDIT[k] : rawValue(k);
function renderSettings(){
  $("stMode").className = "mode " + (SERVER ? "on" : "off");
  $("stMode").textContent = SERVER ? "● 서버 연결됨 — 저장하면 DB 엑셀 설정 시트에 반영" : "● 파일로 열림 — 저장하면 이 브라우저에만 임시 보관(대시보드_열기로 열면 DB에 저장)";
  $("stLocalClear").hidden = !Object.keys(LOCAL_SET).length;
  const known = new Set(SET_GROUPS.flatMap(g=>g.keys));
  const groups = SET_GROUPS.concat([{title:"기타", keys: RAW_SETTINGS.map(r=>r.key).filter(k=>!known.has(k)), note:""}]).filter(g=>g.keys.length);
  let h = "";
  for(const g of groups){
    h += `<div class="setgrp"><h4>${esc(g.title)}</h4>${g.note?`<p class="hint">${esc(g.note)}</p>`:""}<div class="setrows">`;
    for(const k of g.keys){
      const r = RAW_SETTINGS.find(x=>x.key===k); if(!r) continue;
      const v = setVal(k), dirty = k in SET_EDIT, local = (k in LOCAL_SET) && !dirty;
      let input;
      if(r.choices) input = `<select data-set="${esc(k)}">${r.choices.map(c=>`<option ${String(c)===String(v)?"selected":""}>${esc(c)}</option>`).join("")}</select>`;
      else if(k==="VWORLD_KEY") input = `<span class="keyrow"><input data-set="${esc(k)}" type="password" value="${esc(v??"")}" placeholder="예: 8ED7F13B-…" autocomplete="off" spellcheck="false">
          <button class="btn-s" id="stKeyShow" type="button">보기</button><button class="btn-s" id="stKeyTest" type="button">연결 시험</button></span><span class="hint" id="stKeyRes"></span>`;
      else input = `<input data-set="${esc(k)}" type="${typeof r.value==="number"?"number":"text"}" step="any" value="${esc(v??"")}" ${k==="VWORLD_DOMAIN"?'placeholder="예: http://localhost:8765"':""}>`;
      h += `<div class="setrow ${dirty?"dirty":""}"><label class="sk">${esc(k)}${local?' <span class="pill" style="color:var(--warn)">이 브라우저 값</span>':""}</label><div class="sv">${input}</div><div class="sd">${esc(r.desc||"")}</div></div>`;
    }
    h += `</div></div>`;
  }
  $("stForm").innerHTML = h;
  $("stForm").querySelectorAll("[data-set]").forEach(x=>x.onchange=()=>{ const k = x.dataset.set, orig = rawValue(k);
    if(String(x.value) === String(orig ?? "")) delete SET_EDIT[k]; else SET_EDIT[k] = x.value;
    x.closest(".setrow").classList.toggle("dirty", k in SET_EDIT); updateBadges(); $("stSave").textContent = Object.keys(SET_EDIT).length ? `설정 저장 (${Object.keys(SET_EDIT).length})` : "설정 저장"; });
  const ks = $("stKeyShow"), kt = $("stKeyTest");
  if(ks) ks.onclick = ()=>{ const i = document.querySelector('[data-set="VWORLD_KEY"]'); i.type = i.type==="password" ? "text" : "password"; ks.textContent = i.type==="password" ? "보기" : "숨기기"; };
  if(kt) kt.onclick = ()=>testVworldKey(document.querySelector('[data-set="VWORLD_KEY"]').value.trim());
}
/* 인증키 시험: 한반도 중부 지도 조각 1장을 불러와 본다(그림이 오면 성공) */
function testVworldKey(key){
  const out = $("stKeyRes");
  if(!key){ out.textContent = "키를 넣으세요."; return; }
  out.textContent = "시험 중…";
  const img = new Image(); let done = false;
  const fin = (ok, msg)=>{ if(done) return; done = true; out.innerHTML = ok ? `<b class="ok">연결됨</b> — 배경지도를 쓸 수 있습니다.` : `<b class="ng">실패</b> — ${msg}`; };
  img.onload = ()=>fin(img.naturalWidth>0, "그림이 비어 있습니다.");
  img.onerror = ()=>fin(false, location.protocol==="file:" ? "파일로 열면 V월드가 거절할 수 있습니다. 대시보드_열기로 열어 다시 시험하세요. 키·서비스 URL·인터넷도 확인하세요." : "키·서비스 URL(이 주소: "+location.origin+")·인터넷 연결을 확인하세요.");
  setTimeout(()=>fin(false, "응답이 없습니다(인터넷·방화벽 확인)."), 8000);
  img.src = `https://api.vworld.kr/req/wmts/1.0.0/${encodeURIComponent(key)}/Base/7/49/109.png?t=${Date.now()}`;
}
function applyOptDefaults(values){
  /* 화면 기본값을 지금 화면 상태에도 바로 반영(저장된 화면 상태가 예전 값을 붙잡지 않게) */
  const m = {"표준편차":"sd","퍼센트":"pct","전체":"all"};
  if("평균대비_판정" in values) S.opt.band = m[values["평균대비_판정"]] || S.opt.band;
  if("평균대비_k" in values && +values["평균대비_k"]>0) S.opt.k = +values["평균대비_k"];
  if("평균대비_p" in values && +values["평균대비_p"]>0) S.opt.p = +values["평균대비_p"];
  if("특이경향_기준" in values && +values["특이경향_기준"]>0) S.opt.spikeZ = +values["특이경향_기준"];
  if("기본배경지도" in values) S.base = values["기본배경지도"];
  if("기본항목" in values && ITEMS.some(i=>i.code===values["기본항목"])) S.item = values["기본항목"];
  persist();
}
async function saveSettings(){
  const vals = Object.assign({}, SET_EDIT), keys = Object.keys(vals), msg = $("stMsg");
  if(!keys.length){ toast("바뀐 설정이 없습니다."); return; }
  if(!SERVER){
    Object.assign(LOCAL_SET, vals); try{ localStorage.setItem(SETKEY, JSON.stringify(LOCAL_SET)); }catch(e){}
    applyOptDefaults(vals);
    const later = keys.filter(k=>!RUNTIME_KEYS.includes(k));
    msg.hidden = false;
    msg.innerHTML = `이 브라우저에 임시 저장했습니다. 다시 불러옵니다…${later.length?`<br>${later.map(esc).join(", ")}은(는) 대시보드를 다시 만들 때 계산되므로 <b>대시보드_열기</b>로 열어 저장해야 반영됩니다.`:""}`;
    setTimeout(()=>location.reload(), later.length?2500:700); return;
  }
  $("stSave").disabled = true; msg.hidden = false; msg.textContent = "저장 중…";
  try{
    const r = await fetch("/api/settings", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({values:vals})}).then(x=>x.json());
    if(!r.ok) throw new Error(r.error);
    keys.forEach(k=>delete LOCAL_SET[k]); try{ localStorage.setItem(SETKEY, JSON.stringify(LOCAL_SET)); }catch(e){}
    applyOptDefaults(vals);
    msg.textContent = `저장했습니다(${r.changed.join(", ")}). 대시보드를 다시 불러옵니다…`;
    setTimeout(()=>location.reload(), 700);
  }catch(e){ msg.innerHTML = `<b>저장하지 못했습니다.</b> ${esc(e.message)}`; $("stSave").disabled = false; }
}
