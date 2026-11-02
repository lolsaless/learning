// (v2.0) 프로젝트 막대 — 새 프로젝트 만들기 / 열기 / 닫기. 저장 폴더는 [찾아보기](폴더 고르기 창) 또는 직접 입력.
import { api } from '../api.js';
import { emit, on, state } from '../store.js';
import { $, dialog, esc, toast } from '../util.js';

export function initProject() {
  on('status', s => {
    const sig = JSON.stringify(s.project);
    state.hangul = s.hangul || { ok: false };
    const hs = $('#hangulState');
    hs.className = 'pill ' + (state.hangul.ok ? 'pill-ok' : '');
    hs.textContent = state.hangul.ok ? '한글 자동화 ✓' : '한글 연동: 기본';
    hs.title = state.hangul.ok ? 'pywin32 로 한글 다시 저장·PDF 저장 가능'
      : '[한글에서 열기]만 가능. ' + (state.hangul.reason || '') + ' → 설치_pywin32.bat';
    if (sig === renderProject.sig) return;
    renderProject.sig = sig;
    state.project = s.project;
    renderProject();
  });
  $('#projBar').addEventListener('click', async e => {
    const act = e.target.closest('[data-pact]')?.dataset.pact;
    if (act === 'create') createDialog();
    else if (act === 'open') openDialog();
    else if (act === 'close') {
      if (!confirm('프로젝트를 닫을까요? (불러온 문서는 그대로, 이후 변경은 프로젝트에 기록되지 않음)')) return;
      await api.projectClose(); emit('poke');
    } else if (act === 'info') infoDialog();
  });
}

function renderProject() {
  const p = state.project;
  $('#projBar').innerHTML = p
    ? `<span title="프로젝트 정보" data-pact="info" style="cursor:pointer">📁 <span class="pname">${esc(p.name)}</span></span>
       <span class="pfold" title="${esc(p.folder)}">${esc(p.folder)}</span>
       <button class="btn btn-sm" data-pact="info">이력</button><button class="btn btn-sm btn-ghost" data-pact="close">닫기</button>`
    : `<span class="hint">프로젝트 없음 — 저장하면 원본·수정본·최종본 폴더와 이력(JSON)이 생깁니다</span>
       <button class="btn btn-sm btn-primary" data-pact="create">새 프로젝트로 저장</button>
       <button class="btn btn-sm" data-pact="open">프로젝트 열기</button>`;
}

function folderField(id, label, hint) {
  return `<label>${label}<span class="hint">${hint}</span>
    <div class="row gap"><input type="text" id="${id}" placeholder="예) D:\\업무\\행정사무감사_2026" style="flex:1">
    <button class="btn" type="button" data-pick="${id}">찾아보기…</button></div></label>`;
}

function bindPick(box) {
  box.querySelectorAll('[data-pick]').forEach(b => b.onclick = async () => {
    const inp = box.querySelector('#' + b.dataset.pick);
    b.disabled = true; b.textContent = '창 확인…';
    try {
      const r = await api.pickFolder('프로젝트 폴더 고르기', inp.value);
      if (r.path) inp.value = r.path;
    } catch (err) { toast(err.message, 5000); }
    b.disabled = false; b.textContent = '찾아보기…';
  });
}

async function createDialog() {
  const v = await dialog({
    title: '새 프로젝트로 저장',
    body: `<div class="notice info">지금 불러온 문서들을 폴더에 역할별로 복사하고 이력(project.json)을 만듭니다.<br>
      원본·최종본은 관계도의 추정(또는 직접 지정한 것)을 따르며 나중에 바꿀 수 있습니다.</div>
      ${folderField('pjFolder', '저장할 폴더', '없으면 새로 만듭니다. 이 안에 1_원본 / 2_수정본 / 3_최종본 / 4_보관 / 5_보고서 가 생깁니다')}
      <label>프로젝트 이름<input type="text" id="pjName" placeholder="비우면 폴더 이름"></label>`,
    buttons: [{ label: '만들기', primary: true, value: box => ({ folder: box.querySelector('#pjFolder').value, name: box.querySelector('#pjName').value }) }],
    onOpen: bindPick,
  });
  if (!v) return;
  try {
    const r = await api.projectCreate(v.folder, v.name);
    toast(`프로젝트를 만들었습니다: ${r.project.folder}`, 4000);
    emit('poke'); emit('relations');
  } catch (err) { toast(err.message, 5000); }
}

async function openDialog() {
  const v = await dialog({
    title: '프로젝트 열기',
    body: `${folderField('pjOpen', 'project.json 이 있는 폴더', '지금 불러온 문서는 비워지고 프로젝트 문서로 바뀝니다')}`,
    buttons: [{ label: '열기', primary: true, value: box => box.querySelector('#pjOpen').value }],
    onOpen: bindPick,
  });
  if (!v) return;
  try {
    await api.projectOpen(v);
    toast('프로젝트를 열었습니다');
    emit('poke'); emit('relations');
  } catch (err) { toast(err.message, 5000); }
}

async function infoDialog() {
  const { project: p } = await api.project();
  if (!p) return;
  const ev = p.events.slice().reverse().map(e => `<li><span class="mono">${esc(e.time)}</span> ${esc(e.detail)}</li>`).join('');
  await dialog({
    title: `프로젝트 이력 — ${p.name}`,
    body: `<div class="hint">${esc(p.folder)}</div>
      <div class="tbl-wrap"><table class="grid"><tr><th>역할</th><th>파일</th><th>만든 방법</th></tr>
      ${p.documents.map(d => `<tr><td>${esc({ original: '원본', revision: '수정본', final: '최종본', archived: '보관' }[d.role])}</td>
        <td>${esc(d.file)}</td><td>${esc({ import: '가져옴', merge: '병합', edit: '직접 고침' }[d.origin] || d.origin)}</td></tr>`).join('')}</table></div>
      <b>작업 기록</b><ul style="max-height:200px;overflow:auto;margin:0;padding-left:18px">${ev}</ul>`,
    buttons: [],
  });
}
