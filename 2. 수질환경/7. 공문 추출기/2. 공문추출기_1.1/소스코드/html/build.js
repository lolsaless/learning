// 빌드: src/*.js, app.css 를 template.html 에 넣어 단일 HTML 생성
const fs = require('fs'), path = require('path');
const src = f => fs.readFileSync(path.join(__dirname, f), 'utf8');
const safe = js => js.replace(/<\/script/gi, '<\\/script');
let html = src('template.html')
  .replace('/*CSS*/', () => src('app.css'))
  .replace('/*ENGINE*/', () => safe(src('engine.js')))
  .replace('/*XLSX*/', () => safe(src('xlsx.js')))
  .replace('/*APP*/', () => safe(src('app.js')));
const out = path.join(__dirname, 'dist', '공문추출기.html');
fs.writeFileSync(out, html);
console.log('built', out, (html.length / 1024).toFixed(1) + ' KB');
