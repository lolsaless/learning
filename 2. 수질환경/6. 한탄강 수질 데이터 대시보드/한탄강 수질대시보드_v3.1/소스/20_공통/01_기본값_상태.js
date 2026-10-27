/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_공통/01_기본값_상태.js] 기본값·화면 상태·도우미
   하는 일 : 데이터(D) 꺼내기, 설정(CFG), 화면 상태(S)·저장(persist), 지점 수정 덮어쓰기, 하천 목록, 날짜·글자 도우미
   주요 이름: ST, M, ITEMS, CFG, S, defaults, persist, applyEdits, RIVERS_ALL, mLabel, esc, col, PAL
   이럴 때 고침: 처음 열 때 기본 화면(항목·선택·옵션 기본값), 저장할 상태 항목
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ═════════ 기본값 · 상태 ═════════ */
const SKEY = "hantan-wq-dashboard-v3", EKEY = "hantan-wq-station-edits-v3";
const store = { get(){ try{ return JSON.parse(localStorage.getItem(SKEY)||"{}"); }catch(e){ return {}; } },
                set(v){ try{ localStorage.setItem(SKEY, JSON.stringify(v)); }catch(e){} },
                clear(){ try{ localStorage.removeItem(SKEY); }catch(e){} } };
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const $ = id => document.getElementById(id);
D.geo = D.geo || window.GEO_SIGUNGU || null;
const ST = D.stations, M = D.months, ITEMS = D.items, CFG = buildCfg();
const stByName = Object.fromEntries(ST.map(s=>[s.name,s]));
/* 지점 관리: 원본값 보관 + 저장 전 수정값(EDITS)을 화면에 덮어씀 */
const EDIT_FIELDS = {order:"정렬순서", river:"하천명", sigun:"시군", addr:"주소", lat:"위도", lon:"경도", coord:"좌표상태", coordSrc:"좌표출처", note:"비고"};
const ORIG = Object.fromEntries(ST.map(s=>[s.name, Object.fromEntries(Object.keys(EDIT_FIELDS).map(k=>[k, s[k]]))]));
let EDITS = (()=>{ try{ return JSON.parse(localStorage.getItem(EKEY)||"{}"); }catch(e){ return {}; } })();
let SERVER = false;
function applyEdits(){
  for(const s of ST){ Object.assign(s, ORIG[s.name], EDITS[s.name]||{}); }
  ST.sort((a,b)=>(a.order??999)-(b.order??999));
}
for(const n of Object.keys(EDITS)) if(!stByName[n]) delete EDITS[n];
applyEdits();
const RIVERS_ALL = () => { const o = []; ST.forEach(s=>{ if(!o.includes(s.river)) o.push(s.river); }); return o; };
const RIVERS = () => RIVERS_ALL().filter(r=>ST.filter(s=>s.river===r).length>1);
const itemOf = c => ITEMS.find(i=>i.code===c) || {code:c,name:c,unit:"",dec:2};
const multiYear = new Set(M.map(m=>m.slice(0,4))).size>1;
const mLabel = m => multiYear ? m.slice(2,4)+"."+m.slice(5) : (+m.slice(5))+"월";
const mLong = m => m ? m.slice(0,4)+"년 "+(+m.slice(5))+"월" : "";
const esc = s => String(s??"").replace(/[&<>"]/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function defaults(){
  return {
    item: ITEMS.some(i=>i.code===CFG.item) ? CFG.item : (ITEMS.some(i=>i.code==="색도")?"색도":ITEMS[0].code),
    view: "ts", sel: ST.map(s=>s.name), hl: [],
    custom: {}, slots: {}, slotPerm: null, colors: {},
    opt: {band: CFG.band||"sd", k: CFG.k||1, p: CFG.p||30, labels:"auto", mean:true, limits:true, scale:"linear", gaps:false, spike:true, spikeZ: CFG.spike||8},
    from: 0, to: M.length-1, heatMode: "value", profRiver: RIVERS().includes("신천") ? "신천" : RIVERS()[0], profHidden: [],
    base: CFG.basemap || "자동", mapMonth: "last", mapLabels: true, mapLines: false, qcFilter: "all", qcSel: false,
    anaTab: "trend", anaCell: null, anaPair: null, exThr: null
  };
}
const saved = store.get();
const S = Object.assign(defaults(), saved, {opt: Object.assign(defaults().opt, saved.opt||{})});
S.sel = new Set((S.sel||[]).filter(n=>stByName[n])); S.hl = new Set((S.hl||[]).filter(n=>stByName[n]));
S.profHidden = new Set(S.profHidden||[]);
if(!(S.from>=0 && S.from<M.length)) S.from = 0;
if(!(S.to>=S.from && S.to<M.length)) S.to = M.length-1;
if(!ITEMS.some(i=>i.code===S.item)) S.item = defaults().item;
if(!RIVERS().includes(S.profRiver)) S.profRiver = defaults().profRiver;
S.q = ""; S.retired = false;
const persist = () => store.set({item:S.item, view:S.view, sel:[...S.sel], hl:[...S.hl], custom:S.custom, slots:S.slots, slotPerm:S.slotPerm, opt:S.opt,
  colors:S.colors, heatMode:S.heatMode, from:S.from, to:S.to, profRiver:S.profRiver, profHidden:[...S.profHidden],
  base:S.base, mapLabels:S.mapLabels, mapLines:S.mapLines, qcFilter:S.qcFilter, qcSel:S.qcSel, anaTab:S.anaTab, anaPair:S.anaPair, exThr:S.exThr});
const persistEdits = () => { try{ localStorage.setItem(EKEY, JSON.stringify(EDITS)); }catch(e){} };

const col = k => S.colors[k] || css("--"+k);
const PAL = () => [1,2,3,4,5,6,7,8].map(i=>css("--s"+i)).concat([1,2,3,4,5,6,7,8].map(i=>css("--t"+i)));
