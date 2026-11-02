// ① 파일 넣기(끌어 놓기·파일/폴더 선택·경로)  ② 버전 순서 목록
import { api } from '../api.js';
import { emit, on, readyItems, state } from '../store.js';
import { $, $$, esc, fmtDate, fmtSize, toast } from '../util.js';

const isHwpx = name => /\.hwpx$/i.test(name) && !/^[~.]/.test(name);

export function initFiles() {
  const drop = $('#dropZone');
  drop.addEventListener('click', () => $('#inpFiles').click());
  drop.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') $('#inpFiles').click(); });
  ['dragenter', 'dragover'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(t => drop.addEventListener(t, () => drop.classList.remove('over')));
  drop.addEventListener('drop', async e => {
    e.preventDefault();
    const files = await filesFromDrop(e.dataTransfer);
    uploadAll(files);
  });
  // 창 아무 데나 떨어뜨려도 브라우저가 파일을 열지 않게
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => e.preventDefault());

  $('#btnPickFiles').onclick = () => $('#inpFiles').click();
  $('#btnPickFolder').onclick = () => $('#inpFolder').click();
  $('#inpFiles').onchange = e => { uploadAll([...e.target.files].map(f => ({ file: f, rel: f.name }))); e.target.value = ''; };
  $('#inpFolder').onchange = e => {
    uploadAll([...e.target.files].map(f => ({ file: f, rel: f.webkitRelativePath || f.name })));
    e.target.value = '';
  };
  $('#btnScanPath').onclick = async () => {
    const path = $('#inpPath').value.trim();
    if (!path) return toast('폴더 경로를 입력하세요');
    try {
      const r = await api.folder(path, $('#chkRecursive').checked);
      toast(r.found ? `HWPX ${r.found}개를 읽습니다` : '이 폴더에는 HWPX 파일이 없습니다');
      emit('poke');
    } catch (err) { toast(err.message); }
  };
  $('#inpPath').addEventListener('keydown', e => { if (e.key === 'Enter') $('#btnScanPath').click(); });

  $$('[data-order]').forEach(b => b.onclick = async () => {
    await api.orderBy(b.dataset.order);
    emit('poke');
  });
  $('#btnReset').onclick = async () => {
    if (!state.items.length || !confirm('넣은 파일을 모두 목록에서 뺄까요? (원본 파일은 그대로)')) return;
    await api.reset();
    emit('poke');
  };
  $('#fileList').addEventListener('click', onListClick);
  on('status', renderList);
}

/** 끌어 놓은 항목에서 HWPX 파일 모으기 (폴더면 안쪽까지) */
async function filesFromDrop(dt) {
  const out = [];
  const entries = [...(dt.items || [])].map(it => it.webkitGetAsEntry && it.webkitGetAsEntry()).filter(Boolean);
  if (!entries.length) return [...dt.files].map(f => ({ file: f, rel: f.name }));
  async function walk(entry, prefix) {
    if (entry.isFile) {
      const file = await new Promise((res, rej) => entry.file(res, rej));
      out.push({ file, rel: prefix + file.name });
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      let batch;
      do {   // readEntries 는 한 번에 100개씩만 주므로 빌 때까지 반복
        batch = await new Promise((res, rej) => reader.readEntries(res, rej));
        for (const e of batch) await walk(e, prefix + entry.name + '/');
      } while (batch.length);
    }
  }
  for (const e of entries) await walk(e, '');
  return out;
}

async function uploadAll(list) {
  const files = list.filter(x => isHwpx(x.file.name));
  const skipped = list.length - files.length;
  if (!files.length) return toast(skipped ? 'HWPX 파일이 없습니다 (.hwpx 만 읽습니다)' : '선택한 파일이 없습니다');
  let ok = 0;
  for (const [k, x] of files.entries()) {
    $('#progText').textContent = `파일 보내는 중 ${k + 1}/${files.length}: ${x.file.name}`;
    try { await api.upload(x.file, x.rel); ok++; } catch (err) { toast(`${x.file.name}: ${err.message}`); }
  }
  toast(`${ok}개 파일을 넣었습니다` + (skipped ? ` (HWPX 아닌 파일 ${skipped}개 제외)` : ''));
  emit('poke');
}

async function onListClick(e) {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;
  const id = btn.closest('li').dataset.id;
  const ids = state.items.map(i => i.id);
  const k = ids.indexOf(id);
  if (btn.dataset.act === 'remove') {
    await api.remove(id);
  } else {
    const j = btn.dataset.act === 'up' ? k - 1 : k + 1;
    if (j < 0 || j >= ids.length) return;
    [ids[k], ids[j]] = [ids[j], ids[k]];
    await api.orderIds(ids);
  }
  emit('poke');
}

const STATUS = { queued: '대기', parsing: '해석 중', ready: '완료', error: '오류' };

function renderList() {
  const list = $('#fileList');
  const items = state.items;
  $('#fileEmpty').hidden = items.length > 0;
  $$('[data-order]').forEach(b => b.classList.toggle('on', b.dataset.order === state.orderMode));
  $('#orderHint').textContent = state.orderMode === 'manual' ? '직접 지정한 순서' :
    items.length ? '위에서 아래로 v1 → 최신' : '';
  const ready = readyItems().map(i => i.id);
  list.innerHTML = items.map((it, k) => {
    const v = ready.indexOf(it.id);
    const meta = it.status === 'ready'
      ? `수정 ${esc(fmtDate(it.meta?.ModifiedDate))} · ${esc(it.meta?.lastsaveby || '-')} · ${fmtSize(it.size)}`
      : it.status === 'error' ? esc(it.error) : esc(it.label || '');
    return `<li class="file ${it.status === 'error' ? 'error' : ''} ${it.duplicate_of ? 'dup' : ''}" data-id="${it.id}">
      <span class="ver">${v >= 0 ? 'v' + (v + 1) : '–'}</span>
      <div style="min-width:0">
        <div class="name" title="${esc(it.label || it.name)}">${esc(it.name)}</div>
        <div class="meta"><span class="badge b-${it.status}">${STATUS[it.status] || it.status}</span> ${meta}
          ${it.duplicate_of ? `<br><span style="color:var(--mod)">⚠ ${esc(it.duplicate_of)} 와 같은 파일</span>` : ''}</div>
      </div>
      <div class="acts">
        <button class="icon-btn" data-act="up" title="위로" ${k === 0 ? 'disabled' : ''}>▲</button>
        <button class="icon-btn" data-act="down" title="아래로" ${k === items.length - 1 ? 'disabled' : ''}>▼</button>
        <button class="icon-btn" data-act="remove" title="목록에서 빼기">✕</button>
      </div></li>`;
  }).join('');
}
