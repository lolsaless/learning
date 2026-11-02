// 빌드 스크립트 (0단계 최소판) — tools/m0/m0.html → dist/M0_확인.html
// 1단계에서 src/ 전체를 묶는 빌드로 확장한다.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const 루트 = join(dirname(fileURLToPath(import.meta.url)), '..');

// 외부 주소를 부르는 코드(R2 위반)를 찾는다. 시험용 주소(127.0.0.1·localhost)는 허용.
export function 외부참조찾기(html) {
  const 결과 = [];
  const 본위치 = new Set(); // 같은 주소를 두 패턴이 잡아도 한 번만 센다
  const 패턴 = [
    /<(?:script|img|iframe|source|video|audio|embed)\b[^>]*\ssrc\s*=\s*["']?\s*(https?:)?\/\/[^"'\s>]+/gi,
    /<link\b[^>]*\shref\s*=\s*["']?\s*(https?:)?\/\/[^"'\s>]+/gi,
    /@import\s+(?:url\()?\s*["']?(https?:)?\/\/[^"')\s;]+/gi,
    /url\(\s*["']?(https?:)?\/\/[^"')\s]+/gi,
  ];
  for (const re of 패턴) {
    for (const m of html.matchAll(re)) {
      const 끝 = m.index + m[0].length;
      if (본위치.has(끝)) continue;
      본위치.add(끝);
      결과.push(m[0].slice(0, 80));
    }
  }
  return 결과;
}

export function M0빌드(루트경로 = 루트) {
  const 원본 = readFileSync(join(루트경로, 'tools/m0/m0.html'), 'utf8');
  const 외부 = 외부참조찾기(원본);
  if (외부.length) throw new Error('외부 링크 발견(R2 위반): ' + 외부.join(' | '));
  const 출력 = join(루트경로, 'dist/M0_확인.html');
  mkdirSync(dirname(출력), { recursive: true });
  writeFileSync(출력, 원본, 'utf8');
  return { 출력, 바이트: Buffer.byteLength(원본) };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const r = M0빌드();
    console.log(`빌드 완료: ${r.출력} (${r.바이트} B), 외부 링크 0개`);
  } catch (e) {
    console.error('빌드 실패: ' + e.message);
    process.exit(1);
  }
}
