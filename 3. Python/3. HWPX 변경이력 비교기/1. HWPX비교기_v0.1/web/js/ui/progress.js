// 작업 상황: 진행 막대 + 로그 (서버 로그를 이어 붙임)
import { on, state } from '../store.js';
import { $, esc } from '../util.js';

const MAX_LOG = 200;

export function initProgress() {
  on('status', s => {
    const p = s.progress;
    $('#progBar').style.width = p.total ? `${Math.round((p.done / p.total) * 100)}%` : '0';
    $('#progText').textContent = !p.total ? '파일을 넣으면 해석을 시작합니다'
      : p.busy ? `해석 중 ${p.done}/${p.total}${p.parsing ? ' — ' + p.parsing : ''}`
      : `해석 완료 ${p.done}/${p.total}`;
    if (s.logs.length) {
      const ul = $('#logList');
      ul.insertAdjacentHTML('afterbegin', s.logs.slice().reverse().map(l =>
        `<li class="${l.level}"><time>${esc(l.time)}</time><span>${esc(l.msg)}</span></li>`).join(''));
      while (ul.children.length > MAX_LOG) ul.lastElementChild.remove();
      state.logSince = s.logs[s.logs.length - 1].id;
    }
  });
}
