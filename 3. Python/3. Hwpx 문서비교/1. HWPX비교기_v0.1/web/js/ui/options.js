// ③ 비교 옵션 — 바꾸면 서버에 저장하고 결과를 다시 계산한다.
//   옵션을 새로 추가하려면: hwpxdiff/config.py DEFAULT_OPTIONS + compare/options.py + 아래 FIELDS 에 한 줄
import { api } from '../api.js';
import { emit, on, state } from '../store.js';
import { $, toast } from '../util.js';

const FIELDS = [
  { key: 'ignore_whitespace', type: 'check', label: '공백 개수 차이 무시' },
  { key: 'include_format', type: 'check', label: '서식 변경(글자색·크기·굵게 등)도 보기' },
  { key: 'include_tables', type: 'check', label: '표 안 내용도 비교' },
  { key: 'granularity', type: 'select', label: '비교 단위', choices: [['word', '단어'], ['char', '글자']] },
  { key: 'similarity', type: 'range', label: '수정 판정', min: 0.2, max: 0.9, step: 0.05,
    hint: '두 문단이 이 비율 이상 비슷하면 "수정", 아니면 "삭제+추가"로 봅니다' },
];

let rendered = '';

export function initOptions() {
  on('status', s => {
    const sig = JSON.stringify(s.options);
    if (sig === rendered) return;
    rendered = sig;
    render(s.options);
  });
  $('#optionsBox').addEventListener('change', async e => {
    const el = e.target.closest('[data-key]');
    if (!el) return;
    const f = FIELDS.find(x => x.key === el.dataset.key);
    const value = f.type === 'check' ? el.checked : f.type === 'range' ? parseFloat(el.value) : el.value;
    try {
      const r = await api.setOptions({ [f.key]: value });
      state.options = r.options;
      rendered = JSON.stringify(r.options);
      emit('options');
      toast('옵션을 바꿨습니다 — 결과를 다시 계산합니다');
    } catch (err) { toast(err.message); }
  });
  $('#optionsBox').addEventListener('input', e => {
    if (e.target.type === 'range') e.target.nextElementSibling.textContent = Number(e.target.value).toFixed(2);
  });
}

function render(o) {
  $('#optionsBox').innerHTML = FIELDS.map(f => {
    if (f.type === 'check') {
      return `<label class="check"><input type="checkbox" data-key="${f.key}" ${o[f.key] ? 'checked' : ''}> ${f.label}</label>`;
    }
    if (f.type === 'select') {
      return `<div class="opt-line"><span>${f.label}</span><select data-key="${f.key}">${
        f.choices.map(([v, t]) => `<option value="${v}" ${o[f.key] === v ? 'selected' : ''}>${t}</option>`).join('')}</select><span></span></div>`;
    }
    return `<div class="opt-line" title="${f.hint || ''}"><span>${f.label}</span>
      <input type="range" data-key="${f.key}" min="${f.min}" max="${f.max}" step="${f.step}" value="${o[f.key]}">
      <span class="mono">${Number(o[f.key]).toFixed(2)}</span></div>`;
  }).join('');
}
