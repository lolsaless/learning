// 빌드: src/*.js, app.css, pdf.js(Apache-2.0)를 template.html 에 넣어 단일 HTML 생성
const fs = require('fs'), path = require('path');
const src = f => fs.readFileSync(path.join(__dirname, 'src', f), 'utf8');
const lib = f => fs.readFileSync(path.join(__dirname, 'lib', f), 'utf8');
for (const f of ['engine.js', 'engine2.js', 'docgen.js', 'xlsx.js', 'app.js']) new Function(src(f)); // 문법 검사
const safe = js => js.replace(/<\/script/gi, '<\\/script').replace(/<!--/g, '<\\!--');
let html = src('template.html')
  .replace('/*CSS*/', () => src('app.css'))
  .replace('/*PDFJS*/', () => '/* pdf.js 3.11.174 — Mozilla, Apache License 2.0 */\n' + safe(lib('pdf.min.js')))
  .replace('/*PDFWORKER*/', () => '/* pdf.js worker 3.11.174 — Mozilla, Apache License 2.0 (화면 안에서 실행) */\n' + safe(lib('pdf.worker.min.js')))
  .replace('/*ENGINE*/', () => safe(src('engine.js')))
  .replace('/*ENGINE2*/', () => safe(src('engine2.js')))
  .replace('/*XLSX*/', () => safe(src('xlsx.js')))
  .replace('/*DOCGEN*/', () => safe(src('docgen.js')))
  .replace('/*APP*/', () => safe(src('app.js')));
fs.mkdirSync(path.join(__dirname, 'dist'), { recursive: true });
const out = path.join(__dirname, 'dist', '공문추출기.html');
fs.writeFileSync(out, html);
console.log('built', out, (html.length / 1024).toFixed(1) + ' KB');
