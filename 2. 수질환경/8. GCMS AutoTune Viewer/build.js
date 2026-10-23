// 단일 HTML 조립 스크립트: src/template.html 의 자리표시자에 라이브러리와 app.js 를 끼워 넣는다.
// 사용:  npm install  →  node build.js   →  gcms_autotune_viewer.html 생성
const fs = require('fs');
const L = 'node_modules/';
const rd = (p, enc = 'utf8') => fs.readFileSync(p, enc);
let t = rd('src/template.html');

// 라이브러리 내용에 '$&' 같은 치환 기호가 있어도 안전하도록 함수 치환 사용
const rep = (key, value) => {
  if (!t.includes(key)) throw new Error('template 에 자리표시자가 없습니다: ' + key);
  t = t.replace(key, () => value);
};
// <script> 안에 넣을 코드에 '</script' 가 있으면 HTML 이 깨지므로 사전 검사
const safe = (s) => { if (/<\/script/i.test(s)) throw new Error('</script 문자열 포함'); return s; };

rep('<!--@@PDFJS@@-->',      '<script>' + safe(rd(L + 'pdfjs-dist/build/pdf.min.js')) + '</script>');
rep('<!--@@TESSERACT@@-->',  '<script>' + safe(rd(L + 'tesseract.js/dist/tesseract.min.js')) + '</script>');
rep('<!--@@PDFWORKER@@-->',  safe(rd(L + 'pdfjs-dist/build/pdf.worker.min.js')));
rep('<!--@@CORE@@-->',       safe(rd(L + 'tesseract.js-core/tesseract-core-simd-lstm.wasm.js')));
rep('<!--@@TWORKER@@-->',    safe(rd(L + 'tesseract.js/dist/worker.min.js')));
rep('<!--@@ENG@@-->',        rd(L + '@tesseract.js-data/eng/4.0.0_best_int/eng.traineddata.gz', null).toString('base64'));
rep('<!--@@APP@@-->',        safe(rd('src/app.js')));

fs.writeFileSync('gcms_autotune_viewer.html', t);
console.log('완료: gcms_autotune_viewer.html', (t.length / 1e6).toFixed(2) + 'MB');
