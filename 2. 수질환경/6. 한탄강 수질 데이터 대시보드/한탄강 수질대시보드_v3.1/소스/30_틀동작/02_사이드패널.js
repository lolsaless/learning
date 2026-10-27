/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [30_틀동작/02_사이드패널.js] 왼쪽 패널(하천·시료번호 목록)
   하는 일 : 하천(대분류) 묶음·시료번호 줄 그리기, 하천명 클릭=그 하천만, ☆ 강조, ● 색 지정
   주요 이름: renderSide, toHex, toggleHl
   이럴 때 고침: 목록 모양·하천명 클릭 동작
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function renderSide(){
  const q = S.q.trim();
  const match = s => !q || (s.name+s.river+s.addr).includes(q);
  const names = selectedOrdered(), {plan, spikes: spk} = planFor(rowsFor(names, S.item));
  let h = "";
  for(const rv of RIVERS_ALL()){
    const rs = ST.filter(s=>s.river===rv && match(s)); if(!rs.length) continue;
    const all = ST.filter(s=>s.river===rv);
    const a = all.every(s=>S.sel.has(s.name)), so = all.some(s=>S.sel.has(s.name));
    h += `<div class="rgrp"><div class="rh"><input type="checkbox" data-grp="${esc(rv)}" ${a?"checked":""} ${!a&&so?'data-ind="1"':""} aria-label="${esc(rv)} 전체 선택">
      <button class="rname" data-only="${esc(rv)}" title="${esc(rv)}만 보기(시료번호마다 다른 색)">${esc(rv)}</button><span class="n">${all.length}</span></div>`;
    for(const s of rs){
      const on = S.sel.has(s.name), hl = S.hl.has(s.name), pc = plan[s.name];
      const c = S.custom[s.name] || (pc?.emph ? pc.color : null) || col("base");
      h += `<div class="st ${hl?"hl":""}"><input type="checkbox" id="c_${s.id}" data-st="${esc(s.name)}" ${on?"checked":""}>
        <label for="c_${s.id}" title="${esc(s.addr)}">${esc(s.name)}${spk[s.name]?`<span class="spk" title="${S.item} 특이 경향 z=${spk[s.name].z.toFixed(1)}">⚡</span>`:""}${s.note?`<span class="note">${esc(s.note)}</span>`:""}</label>
        <button class="star" data-hl="${esc(s.name)}" aria-pressed="${hl}" title="강조">${hl?"★":"☆"}</button>
        <span class="sw ${S.custom[s.name]?"custom":""}" style="background:${c}" title="색상 지정(오른쪽 클릭: 자동색)" data-sw="${esc(s.name)}"><input type="color" value="${toHex(c)}" data-col="${esc(s.name)}" aria-label="${esc(s.name)} 색상"></span></div>`;
    }
    h += `</div>`;
  }
  const list = $("stlist"); list.innerHTML = h;
  list.querySelectorAll("input[data-ind]").forEach(x=>x.indeterminate=true);
  list.querySelectorAll("input[data-st]").forEach(x=>x.onchange=()=>{ x.checked?S.sel.add(x.dataset.st):S.sel.delete(x.dataset.st); refresh(); });
  list.querySelectorAll("input[data-grp]").forEach(x=>x.onchange=()=>{ ST.filter(s=>s.river===x.dataset.grp).forEach(s=> x.checked?S.sel.add(s.name):S.sel.delete(s.name)); refresh(); });
  list.querySelectorAll("button[data-only]").forEach(x=>x.onclick=()=>{
    const ns = ST.filter(s=>s.river===x.dataset.only).map(s=>s.name);
    S.sel = new Set(ns); reassignColors(ns, false); refresh(); toast(`${x.dataset.only} ${ns.length}개 시료번호`); });
  list.querySelectorAll("button[data-hl]").forEach(x=>x.onclick=()=>toggleHl(x.dataset.hl));
  list.querySelectorAll("input[data-col]").forEach(x=>{
    x.oninput=()=>{ S.custom[x.dataset.col]=x.value; x.parentElement.style.background=x.value; };
    x.onchange=()=>{ S.sel.add(x.dataset.col); refresh(); };
  });
  list.querySelectorAll("[data-sw]").forEach(x=>x.oncontextmenu=e=>{ e.preventDefault(); delete S.custom[x.dataset.sw]; refresh(); toast(`${x.dataset.sw} 색상을 자동색으로 되돌렸습니다`); });
  $("selCount").textContent = `${S.sel.size}/${ST.length} 선택 · 강조 ${[...S.hl].filter(n=>S.sel.has(n)).length}`;
}
function toHex(c){ if(/^#[0-9a-f]{6}$/i.test(c)) return c; const x=document.createElement("canvas").getContext("2d"); x.fillStyle=c; return /^#[0-9a-f]{6}$/i.test(x.fillStyle)?x.fillStyle:"#888888"; }
function toggleHl(n){ S.hl.has(n)?S.hl.delete(n):(S.hl.add(n), S.sel.add(n)); refresh(); }
