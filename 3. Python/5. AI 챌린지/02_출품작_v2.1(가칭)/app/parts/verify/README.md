# 검증 파트 (`parts/verify`)

## 하는 일
문서의 모든 숫자를 원본과 대조하고, 합계·비율·증감률·요일을 다시 계산한다. 판정은 모두 규칙과 계산으로 한다(AI 판정 없음).

## 파일
- engine.py — 대조 엔진(SourceIndex, Verifier) / part.py — VerifyPart(엔진 호출·결과 정리)
- routes.py — 화면 주소

## 입구(다른 곳에서 부르는 기능)
- add_book / remove_book — 원본 색인에 넣고 빼기
- run(문서, 원본 이름·경로·역할, 클립보드 기록, 확정, 대기, 직접 수정) — 검증 실행
- view(문서, 대기, 이름) — 화면용 결과
- slot_detail(칸) — 칸 하나의 출처 후보와 미리보기

## 출구(내놓는 것)
- last — 마지막 결과(items, text_issues, tables, summary, changed)
- affected_by_source() — 원본별 영향 칸

## 화면 주소
/api/verify · /api/view · /api/slot

## 고칠 때 알아 둘 것
- 판정 기준값(배율·허용 오차·사전)은 app/config.py 에 있다. 먼저 그것을 고친다.
- 엔진을 고친 뒤에는 반드시 tests/score_demo.py 로 정답표 18/18 을 확인한다.
- 이 파트는 다른 파트를 import 하지 않는다. 다른 파트의 값이 필요하면 조립부(`app/workspace.py`)에서 넘겨받는다.

## 시험
tests/score_demo.py(정답표 채점) · tests/test_all.py — T3·T4·T7 · tests/test_structure.py(구조 규칙)
