# 내보내기 파트 (`parts/export`)

## 하는 일
출처대장(xlsx 5시트)·검증표시본(hwpx, 빨강·노랑 표시)·검증보고(html)를 작업 폴더 '내보내기'에 만든다.

## 파일
- report.py — 파일 만들기 / part.py — ExportPart
- routes.py — 화면 주소

## 입구(다른 곳에서 부르는 기능)
- export(작업) — 작업의 folder·doc()·last·db·user 만 읽음

## 출구(내놓는 것)
- {ledger, marked, report} 경로

## 화면 주소
/api/export

## 고칠 때 알아 둘 것
- 시트 구성을 바꾸면 tests/test_all.py test_flow 의 시트 이름 목록도 함께 고친다.
- 이 파트는 다른 파트를 import 하지 않는다. 다른 파트의 값이 필요하면 조립부(`app/workspace.py`)에서 넘겨받는다.

## 시험
tests/test_all.py — T5 test_flow · tests/test_structure.py(구조 규칙)
