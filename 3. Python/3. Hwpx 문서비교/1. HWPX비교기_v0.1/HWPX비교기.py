# -*- coding: utf-8 -*-
"""
HWPX 변경이력 비교기 — 실행 파일
================================================================
여러 HWPX 파일(같은 문서의 여러 버전)을 넣으면 무엇이 바뀌었는지 찾아
브라우저 대시보드로 보여 준다. 원본을 따로 지정하지 않고 문서 속 '마지막 수정일' 순으로
버전을 세운 뒤 단계별 변경과 전체 이력(되돌림 포함)을 보여 준다.

- 파이썬 3.9 이상, 표준 라이브러리만 사용 (pip 설치 불필요, 내부망 사용 가능)
- 실제 작업(파일 해석·비교)은 파이썬이, 화면(web/index.html)은 진행상황 확인·조정을 맡는다.

실행
  python HWPX비교기.py                          # 대시보드 (브라우저 자동 열림)
  python HWPX비교기.py --folder D:\\감사자료       # 폴더를 미리 넣고 대시보드
  python HWPX비교기.py a.hwpx b.hwpx --report   # 화면 없이 결과 출력
  python HWPX비교기.py --help                   # 전체 옵션
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.version_info < (3, 9):
    sys.exit("파이썬 3.9 이상이 필요합니다. (현재 %d.%d)" % sys.version_info[:2])

# Windows 콘솔 한글 출력
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from hwpxdiff.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
