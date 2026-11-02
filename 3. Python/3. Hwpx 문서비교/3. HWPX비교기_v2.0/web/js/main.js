// 시작점 — 부품 초기화, 탭 전환, 서버 상태 주기적 확인(폴링), 결과 다시 계산 시점 관리
import { api } from './api.js';
import { emit, ensurePair, on, readyItems, state } from './store.js';
import { $, $$, toast } from './util.js';
import { initFiles } from './ui/files.js';
import { initProgress } from './ui/progress.js';
import { initOptions } from './ui/options.js';
import { renderSummary } from './ui/summary.js';
import { loadCompare, renderCompare } from './ui/compare.js';
import { renderHistory } from './ui/history.js';
import { renderInfo } from './ui/info.js';
import { loadDoc, renderDoc, startEdit } from './ui/docview.js';
import { initProject } from './ui/project.js';
import { loadGraph, renderGraph } from './ui/graph.js';
import { loadMerge, renderMerge } from './ui/merge.js';

const POLL_BUSY = 600;     // 해석 중일 때 확인 간격(ms)
const POLL_IDLE = 2500;    // 한가할 때
let readySig = '';
let failCount = 0;
let pollTimer;

const RENDER = { summary: renderSummary, graph: renderGraph, doc: renderDoc, merge: renderMerge,
                 compare: renderCompare, history: renderHistory, info: renderInfo };

function showTab(name) {
  state.tab = name;
  $$('.tabs [data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
  Object.keys(RENDER).forEach(k => ($(`#tab-${k}`).hidden = k !== name));
  if (name === 'compare' && !state.compare) loadCompare();
  else if (name === 'doc') loadDoc();
  else if (name === 'graph') loadGraph();
  else if (name === 'merge') loadMerge();
  else RENDER[name]();
}

/** (v2.0) 관계(계보) 다시 받기 — 요약 알림·관계도·병합 기본값에 쓰임 */
async function refreshRelations() {
  if (readyItems().length < 1) { state.lineage = null; }
  else { try { state.lineage = await api.lineage(); } catch (err) { /* 해석 중일 수 있음 */ } }
  if (state.tab === 'graph') renderGraph();
  else if (state.tab === 'summary') renderSummary();
  else if (state.tab === 'merge') loadMerge();
}

/** 문서 목록이나 옵션이 바뀌면 이력·비교를 다시 받아 온다 */
async function refreshResults() {
  state.doc.data = null;
  state.doc.key = '';
  state.merge.plan = null;
  state.merge.key = '';
  await refreshRelations();
  if (readyItems().length < 2) {
    state.history = null;
    state.compare = null;
  } else {
    try { state.history = await api.history(); } catch (err) { toast(err.message); }
    if (state.tab === 'compare') await loadCompare(); else state.compare = null;
  }
  if (state.tab === 'doc') return loadDoc();
  if (state.tab === 'merge') return loadMerge();
  if (state.tab === 'graph') return renderGraph();
  RENDER[state.tab]();
}

async function poll() {
  clearTimeout(pollTimer);
  try {
    const s = await api.status(state.logSince);
    failCount = 0;
    $('#offline').hidden = true;
    $('#serverState').className = 'pill pill-ok';
    $('#serverState').textContent = '파이썬 연결됨';
    state.items = s.items;
    state.orderMode = s.order_mode;
    state.options = s.options;
    state.progress = s.progress;
    emit('status', s);
    const sig = readyItems().map(i => i.id).join(',');
    if (sig !== readySig) {
      readySig = sig;
      await refreshResults();
    } else if (state.tab === 'info') {
      renderInfo();
    }
    pollTimer = setTimeout(poll, s.progress.busy ? POLL_BUSY : POLL_IDLE);
  } catch (err) {
    failCount++;
    $('#serverState').className = 'pill pill-bad';
    $('#serverState').textContent = '연결 끊김';
    if (failCount >= 3) $('#offline').hidden = false;
    pollTimer = setTimeout(poll, POLL_IDLE);
  }
}

function initExport() {
  const menu = $('#exportMenu');
  $('#btnExport').onclick = e => { e.stopPropagation(); menu.hidden = !menu.hidden; };
  document.addEventListener('click', () => (menu.hidden = true));
  menu.querySelectorAll('[data-export]').forEach(b => b.onclick = () => {
    const [kind, fmt] = b.dataset.export.split(':');
    if (readyItems().length < 2) return toast('HWPX 파일이 2개 이상 있어야 합니다');
    if (kind !== 'history') ensurePair();
    window.location.href = api.exportUrl(kind, fmt, state.pair.a, state.pair.b,
      state.project && $('#chkSaveReport').checked);
    if (state.project && $('#chkSaveReport').checked) toast('프로젝트 5_보고서 폴더에도 저장합니다');
  });
}

async function init() {
  initFiles();
  initProgress();
  initOptions();
  initExport();
  initProject();
  $$('.tabs [data-tab]').forEach(b => b.onclick = () => showTab(b.dataset.tab));
  $('#btnShutdown').onclick = async () => {
    if (!confirm('파이썬 서버를 끝낼까요? (이 창은 닫아도 됩니다)')) return;
    try { await api.shutdown(); } catch (_) { /* 이미 종료 */ }
    clearTimeout(pollTimer);
    $('#offline').innerHTML = '<div><b>서버를 종료했습니다.</b><br>다시 쓰려면 HWPX비교기.py 를 실행하세요.</div>';
    $('#offline').hidden = false;
  };
  on('poke', poll);
  on('options', refreshResults);
  on('open-doc', ({ a, b, cid, plain }) => {
    state.pair = { a, b };
    state.doc.editing = false;
    if (plain) state.doc.view = 'plain';
    else if (state.doc.view === 'plain') state.doc.view = 'merged';
    state.doc.data = null;
    showTab('doc');
    loadDoc(cid);
  });
  on('open-edit', ({ id }) => { showTab('doc'); startEdit(id); });
  on('open-merge', ({ base }) => {
    state.merge.base = base; state.merge.versions = null; state.merge.plan = null;
    showTab('merge');
  });
  on('relations', refreshRelations);
  on('saved-doc', ({ id, base }) => {
    // 새로 만든 문서: 기준 문서와 비교한 문서 보기로 (목록에 들어올 때까지 잠시 기다림)
    const go = (n = 0) => {
      if (readyItems().find(i => i.id === id)) return emit('open-doc', { a: base, b: id, cid: null });
      if (n < 20) setTimeout(() => go(n + 1), 300);
    };
    go();
  });
  on('open-compare', ({ a, b, cid }) => {
    state.pair = { a, b };
    state.view.type = 'all';
    state.view.q = '';
    state.view.mode = 'list';
    showTab('compare');
    loadCompare(cid);
  });
  try {
    const info = await api.info();
    $('#appVersion').textContent = `· v${info.version}`;
  } catch (_) { /* poll 에서 처리 */ }
  RENDER.summary();
  poll();
}

init();
