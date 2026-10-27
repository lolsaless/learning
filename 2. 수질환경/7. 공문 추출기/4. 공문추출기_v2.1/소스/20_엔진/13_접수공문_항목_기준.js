/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/13_접수공문_항목_기준.js] 검사항목·기준 해석
   하는 일 : 항목 칸 → 항목 목록, BOD(20이하) 같은 항목 안 기준 분리, 기준 열 대응
   주요 이름: parseItems, splitItemStd, applyStdColumn, STD_PAREN, STD_PLAIN, STD_UNIT
   이럴 때 고침: 항목·기준 표기가 잘못 나뉠 때
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function parseItems(text) {
  let region = '';
  let s = (text || '').replace(/[·•▪◦]/g, ',');
  const ar = /(?:→|->|⇒)\s*([^,\n]+)/.exec(s);
  if (ar) { region = ar[1].trim(); s = s.slice(0, ar.index) + s.slice(ar.index + ar[0].length); }
  s = s.replace(/\n/g, ',');
  const toks = []; let depth = 0, cur = '';
  for (const ch of s) {
    if (ch === '(' || ch === '（') depth++; else if (ch === ')' || ch === '）') depth = Math.max(0, depth - 1);
    if ((ch === ',' || ch === '，' || ch === '、') && depth === 0) { toks.push(cur); cur = ''; } else cur += ch;
  }
  toks.push(cur);
  const items = [];
  for (let t of toks) {
    t = t.replace(/^[\s\-–]+/, '').replace(/^[(\[]?\s*추가\s*[)\]]?\s*[:：]?\s*/, '').trim(); if (!t) continue; // v2.0: '(추가) COD'
    const sp = splitItemStd(t);
    t = sp.name; const std = sp.std;
    const name = normItem(t);
    items.push({ raw: t, name: name || t, known: !!name, std });
  }
  return { items, region };
}
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
/* v1.1: 항목 안의 기준 표기 — BOD(20), BOD(20이하), BOD(20 ㎎/L 이하), BOD(기준 20), BOD(≤20), T-P(0.5미만),
   pH(5.8~8.6), 대장균군(3,000개/mL), BOD 20이하, SS: 20  → 이름과 기준값 분리 */
const STD_UNIT = '(?:mg\\s*/\\s*[lLℓ]|㎎\\s*/\\s*[lLℓ]|㎎/ℓ|mg/ℓ|ppm|ppb|도|TU|개\\s*/\\s*(?:100\\s*)?m[lL]|%)';
const STD_NUM = '(\\d[\\d.,]*(?:\\s*[~∼-]\\s*\\d[\\d.,]*)?)';
const STD_PAREN = new RegExp('^(.*?\\S)\\s*[(（]\\s*(?:기준\\s*[:：]?\\s*)?(≤|<=|<|이하|미만)?\\s*' + STD_NUM + '\\s*' + STD_UNIT + '?\\s*(이하|미만)?\\s*[)）]$');
const STD_PLAIN = new RegExp('^(.*?\\S)\\s*([:：])?\\s*(≤|<=|<)?\\s*' + STD_NUM + '\\s*' + STD_UNIT + '?\\s*(이하|미만)?$');
const fmtStd = (num, q) => num.replace(/\s+/g, '').replace(/∼/g, '~') + (q === '미만' || q === '<' ? ' 미만' : '');
function splitItemStd(t) {
  let m = STD_PAREN.exec(t);
  if (m && !/^[\d.,]+$/.test(m[1])) return { name: m[1].trim(), std: fmtStd(m[3], m[2] || m[4]) };
  m = STD_PLAIN.exec(t);
  if (m && normItem(m[1].trim()) && (m[2] || m[3] || m[5] || /\s/.test(t.slice(m[1].length, m[1].length + 1)))) return { name: m[1].trim(), std: fmtStd(m[4], m[3] || m[5]) };
  return { name: t, std: '' };
}
function applyStdColumn(items, std) {
  if (!std) return;
  const v = std.replace(/\n/g, ' ');
  const each = /각\s*([\d.]+)/.exec(v);
  if (each) { items.forEach(i => { if (!i.std) i.std = each[1]; }); return; }
  let hit = false;
  for (const i of items) {
    for (const key of new Set([i.raw, i.name])) {
      const m = new RegExp(esc(key) + '\\s*[:：]?\\s*([\\d.]+)', 'i').exec(v);
      if (m) { if (!i.std) i.std = m[1]; hit = true; break; }
    }
  }
  if (hit) return;
  const nums = v.match(/\d+(?:\.\d+)?/g) || [];
  if (nums.length === items.length) items.forEach((i, k) => { if (!i.std) i.std = nums[k]; });
}
