#!/bin/bash
# 공문추출기 빌드 (Mac) — 더블클릭하면 소스 부품을 합쳐 공문추출기.html 을 만든다.
cd "$(dirname "$0")" || exit 1
echo "=============================================="
echo "  공문추출기 빌드 - 소스 부품을 합쳐 공문추출기.html 만들기"
echo "=============================================="
if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
  python3 tools/build.py "$@"; st=$?
else
  echo "python3 가 없어 간단 빌드로 만듭니다. 검사는 하지 않습니다."
  bash tools/build_simple.sh; st=$?
fi
echo
if [ -t 0 ]; then read -n 1 -s -r -p "아무 키나 누르면 창을 닫습니다..."; echo; fi
exit $st
