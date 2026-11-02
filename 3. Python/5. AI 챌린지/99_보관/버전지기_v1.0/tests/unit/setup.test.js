// 0단계 점검 시험 — 폴더 구조, 빌드, 외부 링크 0개(R2)
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { 외부참조찾기, M0빌드 } from '../../tools/build.js';

const 루트 = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

test('설계서 2.3의 기본 폴더가 있다', () => {
  for (const d of ['src/core', 'src/extract', 'src/lineage', 'src/diff', 'src/classify', 'src/integrate',
    'src/ai', 'src/ui/views', 'src/config', 'tests/unit', 'tests/scenario', 'samples', 'docs', 'dist', 'tools']) {
    assert.ok(existsSync(join(루트, d)), d + ' 폴더 없음');
  }
});

test('package.json: ES 모듈, 의존 패키지 0개, test·build 스크립트', () => {
  const p = JSON.parse(readFileSync(join(루트, 'package.json'), 'utf8'));
  assert.equal(p.type, 'module');
  assert.equal(Object.keys(p.dependencies ?? {}).length, 0);
  assert.equal(Object.keys(p.devDependencies ?? {}).length, 0);
  assert.ok(p.scripts.test && p.scripts.build);
});

test('.gitignore가 samples의 실제 파일을 제외한다(R3)', () => {
  const g = readFileSync(join(루트, '.gitignore'), 'utf8');
  assert.match(g, /^samples\/\*$/m);
});

test('외부참조찾기: 외부 주소는 잡고 로컬 주소·일반 글은 통과', () => {
  assert.equal(외부참조찾기('<script src="https://cdn.x/a.js"></script>').length, 1);
  assert.equal(외부참조찾기('<link rel="stylesheet" href="//fonts.x/a.css">').length, 1);
  assert.equal(외부참조찾기('<style>@import url("https://x/a.css");</style>').length, 1);
  assert.equal(외부참조찾기('<style>a{background:url(http://x/a.png)}</style>').length, 1);
  assert.equal(외부참조찾기('<p>https://ollama.com 에서 설치</p><script>fetch("http://127.0.0.1:11434")</script>').length, 0);
});

test('M0빌드: 원본을 dist에 복사하고, 외부 링크가 있으면 실패한다', () => {
  const 임시 = mkdtempSync(join(tmpdir(), 'vk-'));
  mkdirSync(join(임시, 'tools/m0'), { recursive: true });
  writeFileSync(join(임시, 'tools/m0/m0.html'), '<!doctype html><p>안녕</p>');
  const r = M0빌드(임시);
  assert.equal(readFileSync(r.출력, 'utf8'), '<!doctype html><p>안녕</p>');
  writeFileSync(join(임시, 'tools/m0/m0.html'), '<script src="https://a.b/c.js"></script>');
  assert.throws(() => M0빌드(임시), /외부 링크/);
});

test('실제 M0 확인 HTML에 외부 링크가 없다', () => {
  const html = readFileSync(join(루트, 'tools/m0/m0.html'), 'utf8');
  assert.deepEqual(외부참조찾기(html), []);
});
