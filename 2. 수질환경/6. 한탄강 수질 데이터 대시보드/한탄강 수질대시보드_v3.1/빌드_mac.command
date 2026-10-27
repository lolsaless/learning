#!/bin/bash
# Mac: Finder에서 더블클릭. 처음 한 번은 오른쪽 클릭 → 열기(확인되지 않은 개발자 안내가 나올 때)
cd "$(dirname "$0")"
PY=""
if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then PY="python3"; fi
ensure_openpyxl() {
  "$PY" -c "import openpyxl" 2>/dev/null || "$PY" -m pip install --user openpyxl || "$PY" -m pip install --user --break-system-packages openpyxl
}
if [ -n "$PY" ]; then
  ensure_openpyxl
  "$PY" tools/build.py "$@"
else
  echo "[안내] python3 가 없어 간단 빌드로 합칩니다(검사 없음, 데이터는 지난번 빌드 것)."
  bash tools/build_simple.sh
fi
read -n 1 -s -r -p "아무 키나 누르면 닫힙니다"; echo
