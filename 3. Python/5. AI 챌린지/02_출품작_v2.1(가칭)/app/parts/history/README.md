# 이력 파트 (`parts/history`)

## 하는 일
값 이력·작업본 버전·원본 변경·검증 실행 기록을 읽어 보여 준다(읽기 전용, 지우는 기능 없음).

## 파일
- part.py — HistoryPart
- routes.py — 화면 주소

## 입구(다른 곳에서 부르는 기능)
- history(칸) — 전체 또는 칸 하나의 이력
- slot_events(칸)

## 출구(내놓는 것)
- {events, versions, source_events, runs}

## 화면 주소
/api/history

## 고칠 때 알아 둘 것
- 기록을 쓰는 곳은 각 파트(문서·수정·원본)이다. 이 파트는 읽기만 한다.
- 이 파트는 다른 파트를 import 하지 않는다. 다른 파트의 값이 필요하면 조립부(`app/workspace.py`)에서 넘겨받는다.

## 시험
tests/e2e_ui.py — 이력 탭 · tests/test_structure.py(구조 규칙)
