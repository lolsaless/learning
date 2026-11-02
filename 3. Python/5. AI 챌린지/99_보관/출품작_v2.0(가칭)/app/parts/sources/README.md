# 원본 파트 (`parts/sources`)

## 하는 일
원본 자료(엑셀 xlsx·xlsm, 팀 제출 hwpx)를 등록하고 읽는다. 내용 고유값(SHA-256)으로 바뀐 원본을 찾는다.

## 파일
- part.py — SourcesPart
- routes.py — 화면 주소

## 입구(다른 곳에서 부르는 기능)
- add(경로들, 역할) — 폴더째 또는 파일 등록. 임시 파일·작업 폴더 안 파일·대상 문서 자신은 건너뜀
- remove(sid) / set_role(sid, 역할)
- check(영향표) — 바뀐 원본·사라진 원본 목록
- cells(sid, 시트, 범위, 자릿수, 배율, 쉼표) — 입력하기용 셀 값
- grid(sid, 시트, …) — 입력하기 화면의 격자

## 출구(내놓는 것)
- books — sid → 읽은 원본
- errors — sid → 오류 문구
- rows() — 화면 목록
- 알림 on_load / on_unload — 조립부가 검증 파트 색인에 연결

## 화면 주소
/api/sources/add · /api/sources/remove · /api/sources/role · /api/sources/check · /api/grid

## 고칠 때 알아 둘 것
- 새 파일 형식(예: csv)을 받으려면 SUPPORTED 와 _load() 만 고친다.
- 한 파일이 깨져도 전체가 멈추지 않게 _load() 는 예외를 잡아 errors 에 적는다.
- 이 파트는 다른 파트를 import 하지 않는다. 다른 파트의 값이 필요하면 조립부(`app/workspace.py`)에서 넘겨받는다.

## 시험
tests/test_all.py — T5 test_bad_sources_do_not_stop, test_source_change_and_missing · tests/test_structure.py(구조 규칙)
