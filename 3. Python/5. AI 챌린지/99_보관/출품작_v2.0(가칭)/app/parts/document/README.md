# 문서 파트 (`parts/document`)

## 하는 일
검증할 한글 문서(hwpx)를 받아 숫자마다 누름틀을 씌운 작업본 v001 을 만들고, 저장할 때마다 새 버전 파일을 만든다. 원본 문서는 고치지 않는다.

## 파일
- part.py — DocumentPart
- routes.py — 화면 주소

## 입구(다른 곳에서 부르는 기능)
- set_target(경로) — 작업본 v001 생성
- doc(fresh) — 현재 작업본 읽기(파일이 바뀌면 자동으로 다시 읽음)
- detect_manual_edits() — 한글에서 직접 고친 칸을 이력에 남김
- write_version(바꿀 값들, 메모) — 새 버전 저장 후 다시 읽어 값 확인

## 출구(내놓는 것)
- 작업본 HwpxDoc
- 버전 정보(장부 versions 표)

## 화면 주소
/api/target

## 고칠 때 알아 둘 것
- 누름틀·글자 위치 처리는 app/formats/hwpx.py 에 있다. 이 파트는 '언제 어떤 파일을 만들지'만 맡는다.
- 저장 확인에 실패하면 새 파일을 지우고 멈춘다(작업본이 망가지지 않게).
- 이 파트는 다른 파트를 import 하지 않는다. 다른 파트의 값이 필요하면 조립부(`app/workspace.py`)에서 넘겨받는다.

## 시험
tests/test_all.py — T5 test_flow, test_manual_edit_detected, test_reject_hwp_and_second_target · tests/test_structure.py(구조 규칙)
