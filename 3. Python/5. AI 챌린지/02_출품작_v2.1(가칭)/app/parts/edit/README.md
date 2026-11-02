# 수정·입력 파트 (`parts/edit`)

## 하는 일
고칠 값을 바로 쓰지 않고 '대기 목록'에 모은다. 원본 셀을 골라 넣는 [입력하기]와 [출처 확정]을 맡고, 저장 결과를 값 이력에 남긴다.

## 파일
- part.py — EditPart
- routes.py — 화면 주소

## 입구(다른 곳에서 부르는 기능)
- set_pending(문서, 칸, 새 값, 방법, 원본, 위치, 이유) / drop_pending(칸)
- input_values(문서, 시작 칸, 원본, 셀 값, 위치 함수, 범위) — 같은 모양으로 채움
- confirm(문서, 칸, 원본, 위치) / unconfirm(칸)
- after_save(버전, 반영된 변경) — 이력 기록·출처 확정·대기 비우기

## 출구(내놓는 것)
- 장부의 pending · confirms · events 표

## 화면 주소
/api/pending · /api/pending/drop · /api/fix · /api/input · /api/confirm · /api/unconfirm · /api/save

## 고칠 때 알아 둘 것
- 값이 이미 같으면 바꾸지 않고 출처만 확정한다(쓸데없는 버전이 생기지 않게).
- 한 번에 넣을 수 있는 칸 수는 MAX_INPUT_CELLS.
- 이 파트는 다른 파트를 import 하지 않는다. 다른 파트의 값이 필요하면 조립부(`app/workspace.py`)에서 넘겨받는다.

## 시험
tests/test_all.py — T5 test_flow, test_input_values · tests/test_structure.py(구조 규칙)
