/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_공통/00_설정값.js] 설정값 읽기
   하는 일 : DB 설정 시트 값(D.settingsRaw)과 이 브라우저에 임시 저장한 값을 합쳐 화면 설정(CFG)을 만든다
   주요 이름: SETKEY, RAW_SETTINGS, LOCAL_SET, rawValue, buildCfg, RUNTIME_KEYS
   이럴 때 고침: 설정 시트에 새 설정을 추가해 화면에서 쓰고 싶을 때(buildCfg에 한 줄)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
const SETKEY = "hantan-wq-settings-v3";
const RAW_SETTINGS = D.settingsRaw || [];          // [{key, value, desc, choices}] — DB 설정 시트
let LOCAL_SET = (()=>{ try{ return JSON.parse(localStorage.getItem(SETKEY)||"{}"); }catch(e){ return {}; } })();
/* 화면을 다시 만들지 않아도 바로 적용되는 설정(나머지는 대시보드를 다시 만들 때 반영) */
const RUNTIME_KEYS = ["VWORLD_KEY","기본배경지도","기본항목","평균대비_판정","평균대비_k","평균대비_p","특이경향_기준"];
function rawValue(k){ return (k in LOCAL_SET) ? LOCAL_SET[k] : (RAW_SETTINGS.find(r=>r.key===k)||{}).value; }
function buildCfg(){
  const c = Object.assign({}, D.settings || {});
  if(!RAW_SETTINGS.length) return c;
  const n = (k, d) => { const v = parseFloat(rawValue(k)); return isFinite(v) && v>0 ? v : d; };
  c.vworldKey = String(rawValue("VWORLD_KEY") ?? "").trim();
  c.basemap = String(rawValue("기본배경지도") || "자동");
  c.item = String(rawValue("기본항목") || "색도");
  c.band = ({"표준편차":"sd", "퍼센트":"pct", "전체":"all"})[rawValue("평균대비_판정")] || "sd";
  c.k = n("평균대비_k", 1); c.p = n("평균대비_p", 30); c.spike = n("특이경향_기준", 8);
  return c;
}
