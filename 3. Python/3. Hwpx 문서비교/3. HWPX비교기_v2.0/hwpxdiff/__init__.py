"""HWPX 변경이력 비교기 — 파이썬 엔진 패키지.

구성 (각 하위 패키지는 아래 방향으로만 의존한다: server → service → compare → hwpx)
    hwpx/     HWPX 파일 읽기 → Document(문단·표 셀 블록 목록) 만들기
    compare/  두 Document 비교, 여러 버전 이력 추적
    service/  작업공간(불러온 문서·작업 진행상황·로그·결과 캐시)
    server/   대시보드(HTML)와 통신하는 로컬 HTTP 서버
    render/   (v1.1) 원본 문서 모양 그대로 그리고 바뀐 곳 표시
    export/   비교 결과를 HTML/CSV 보고서로 저장
"""

VERSION = "2.0.0"
APP_NAME = "HWPX 변경이력 비교기"
