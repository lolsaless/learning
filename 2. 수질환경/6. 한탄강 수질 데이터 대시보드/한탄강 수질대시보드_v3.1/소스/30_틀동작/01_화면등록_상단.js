/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [30_틀동작/01_화면등록_상단.js] 화면 등록·상단
   하는 일 : 화면(탭) 등록표, 탭 만들기, 화면 전환, 항목 버튼, 탭 숫자 꼬리표
   주요 이름: registerView, VIEW_REG, setView, renderHeader
   이럴 때 고침: 탭 이름·순서(빌드목록 순서), 상단 표시
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ── 화면 등록표 ──────────────────────────────────────────────
   각 화면 부품(40_화면/*.js) 맨 위에서 registerView({...})를 부르면
   상단 탭·화면 전환·요약 카드 표시·버튼 연결이 자동으로 된다.
     id     : 화면 이름. 02_화면/*.html 의 <section id="v-○○"> 와 같아야 함
     label  : 탭에 보이는 글자
     render : 화면을 그리는 함수
     kpi    : 위쪽 요약 카드를 보일지(true/false)
     item   : 상단 항목 버튼(TOC~색도)을 보일지(true/false 또는 함수)
     badge  : 탭 옆 숫자를 돌려주는 함수(없으면 생략)
     bind   : 그 화면의 버튼을 연결하는 함수(처음 한 번 실행)
   탭 순서 = 소스/빌드목록.txt 에 적힌 화면 부품 순서 */
const VIEW_REG = [];
const INIT_HOOKS = [];      // 화면이 아닌 부품(인쇄 등)이 처음에 한 번 할 일
const REFRESH_HOOKS = [];   // 화면을 다시 그릴 때마다 할 일
const THEME_HOOKS = [];     // 라이트/다크가 바뀔 때 할 일(지도 배경 바꾸기 등)
function onTheme(fn){ THEME_HOOKS.push(fn); }
function registerView(v){ VIEW_REG.push(Object.assign({kpi:false, item:true}, v)); }
function onInit(fn){ INIT_HOOKS.push(fn); }
function onRefresh(fn){ REFRESH_HOOKS.push(fn); }
const viewOf = id => VIEW_REG.find(v=>v.id===id);
function updateBadges(){
  for(const v of VIEW_REG){ if(!v.badge) continue; const el = $("cnt-"+v.id); if(!el) continue; const n = v.badge(); el.textContent = n || ""; el.hidden = !n; }
}
function setView(v){ S.view = v; document.querySelectorAll("#tabs button").forEach(x=>x.setAttribute("aria-selected", x.dataset.view===v)); refresh(); scrollTo({top:0}); }
function renderHeader(){
  $("ver").textContent = "v" + (window.APP_VERSION || "?");
  $("meta").textContent = `${mLong(M[0])} ~ ${mLong(M[M.length-1])} · 지점 ${ST.length}개 · 생성 ${D.generated}`;
  const seg = $("itemSeg");
  seg.innerHTML = ITEMS.map(i=>`<button data-it="${i.code}" aria-pressed="${i.code===S.item}" title="${esc(i.name)}">${i.code}</button>`).join("");
  seg.querySelectorAll("button").forEach(b=>b.onclick=()=>{ S.item=b.dataset.it; seg.querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed", x===b)); refresh(); });
  $("tabs").innerHTML = VIEW_REG.map(v=>`<button role="tab" data-view="${v.id}" aria-selected="${v.id===S.view}">${esc(v.label)}${v.badge?`<span class="cnt" id="cnt-${v.id}" hidden></span>`:""}</button>`).join("");
  document.querySelectorAll("#tabs button").forEach(b=>b.onclick=()=>setView(b.dataset.view));
  updateBadges();
}
