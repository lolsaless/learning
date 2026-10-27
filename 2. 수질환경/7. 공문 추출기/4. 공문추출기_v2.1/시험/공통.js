// 시험 공통: 빌드가 만든 엔진 묶음(_엔진_묶음.js)과 소스의 pdf.js 를 Node 에서 불러온다.
// 먼저 빌드(빌드_windows.bat / 빌드_mac.command) 해야 _엔진_묶음.js 가 최신이 된다.
const fs = require('fs'), path = require('path'), zlib = require('zlib');
const ROOT = path.join(__dirname, '..');
const E = require('./_엔진_묶음.js');
const inflate = async b => zlib.inflateRawSync(Buffer.from(b));
let pdfjs = null;
function pdf() {
  if (!pdfjs) { const L = path.join(ROOT, '소스', '10_외부라이브러리'); globalThis.pdfjsWorker = require(path.join(L, 'pdf.worker.min.js')); pdfjs = require(path.join(L, 'pdf.min.js')); }
  return pdfjs;
}
// 브라우저 화면(05_폴더읽기.js pdfTextPages)과 같은 방식으로 PDF 글자 항목을 꺼냄
async function pdfPages(file) {
  const doc = await pdf().getDocument({ data: new Uint8Array(fs.readFileSync(file)), isEvalSupported: false }).promise;
  const pages = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const p = await doc.getPage(i), vp = p.getViewport({ scale: 1 }), tc = await p.getTextContent();
    pages.push({ w: vp.width, h: vp.height, items: tc.items.filter(t => t.str != null).map(t => ({ s: t.str, x: t.transform[4], y: vp.height - t.transform[5], w: t.width, h: Math.abs(t.transform[3]) || 10 })) });
  }
  return pages;
}
const list = (dir, re) => fs.readdirSync(dir).filter(f => re.test(f)).sort().map(f => ({ name: f.normalize('NFC'), path: path.join(dir, f) }));
const odt = async f => E.extractOdt(new Uint8Array(fs.readFileSync(f.path)), f.name, inflate);
let pass = 0, fail = 0;
function check(ok, label, detail) { if (ok) pass++; else fail++; console.log(`${ok ? '  통과' : '✗ 실패'}  ${label}${detail ? '  — ' + detail : ''}`); }
function summary() { console.log(`\n결과: 통과 ${pass} · 실패 ${fail}`); process.exitCode = fail ? 1 : 0; }
module.exports = { E, fs, path, ROOT, inflate, pdfPages, list, odt, check, summary };
