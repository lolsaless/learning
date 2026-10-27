#!/bin/bash
# Mac: Finder에서 더블클릭. 처음 한 번은 오른쪽 클릭 → 열기(확인되지 않은 개발자 안내가 나올 때)
cd "$(dirname "$0")"
PY=""
if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then PY="python3"; fi
ensure_openpyxl() {
  "$PY" -c "import openpyxl" 2>/dev/null || "$PY" -m pip install --user openpyxl || "$PY" -m pip install --user --break-system-packages openpyxl
}
if [ -z "$PY" ]; then
  echo "[오류] python3 가 없습니다. 터미널에서 xcode-select --install 또는 python.org 에서 Python 3 설치"
  echo "       보기만 하려면 한탄강_수질대시보드.html 을 Safari·Chrome으로 여세요."
  read -n 1 -s -r -p "아무 키나 누르면 닫힙니다"; exit 1
fi
ensure_openpyxl
echo "이 창을 닫으면 저장·V월드 지도·자동 빌드가 멈춥니다."
"$PY" tools/serve.py
