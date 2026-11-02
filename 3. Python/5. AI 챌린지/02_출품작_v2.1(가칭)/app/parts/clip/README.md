# 클립보드 파트 (`parts/clip`)

## 하는 일
(Windows 전용) 엑셀에서 Ctrl+C 할 때 파일·시트·칸을 기록하고, 검증 때 '붙여 넣은 숫자의 출처 힌트'로 쓴다.

## 파일
- clipwatch.py — 감시기·형식 해석 / part.py — ClipPart(기록 저장·조회)
- routes.py — 화면 주소

## 입구(다른 곳에서 부르는 기능)
- record(복사 정보)
- clips(개수)

## 출구(내놓는 것)
- 장부의 clips 표

## 화면 주소
/api/clip · /api/clips

## 고칠 때 알아 둘 것
- 감시기는 프로그램 전체에 하나(app/web/server.py 의 App.clip).
- Windows 가 아니면 감시기는 '사용 불가'로 표시되고 나머지 기능은 그대로 동작한다.
- 이 파트는 다른 파트를 import 하지 않는다. 다른 파트의 값이 필요하면 조립부(`app/workspace.py`)에서 넘겨받는다.

## 시험
tests/test_all.py — T5 test_clip_hint, T6 · tests/test_structure.py(구조 규칙)
