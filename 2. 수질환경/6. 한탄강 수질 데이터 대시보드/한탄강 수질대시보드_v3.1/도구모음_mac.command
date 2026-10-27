#!/bin/bash
# Mac: Finder에서 더블클릭. 처음 한 번은 오른쪽 클릭 → 열기(확인되지 않은 개발자 안내가 나올 때)
cd "$(dirname "$0")"
PY=""
if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then PY="python3"; fi
ensure_openpyxl() {
  "$PY" -c "import openpyxl" 2>/dev/null || "$PY" -m pip install --user openpyxl || "$PY" -m pip install --user --break-system-packages openpyxl
}
[ -z "$PY" ] && { echo "[오류] python3 가 없습니다."; read -n 1 -s -r; exit 1; }
ensure_openpyxl
pause() { read -n 1 -s -r -p "아무 키나 누르면 메뉴로 돌아갑니다"; echo; }
while true; do
  clear
  echo "================================================"
  echo "  한탄강 수질 대시보드 도구모음 (v3.1)"
  echo "================================================"
  echo "  1. 대시보드 열기 (권장: 저장·V월드 지도·자동 빌드)"
  echo "  2. 월별 결과 엑셀 가져오기 (YYYYMM 시트)"
  echo "  3. V월드로 좌표 일괄 검색 ('추정' 좌표만)"
  echo "  4. 빌드 (부품 + DB → HTML)"
  echo "  5. 공유용 HTML 만들기 (V월드 키 제외)"
  echo "  6. 자동 빌드 (부품을 저장할 때마다 다시 빌드, Ctrl+C로 멈춤)"
  echo "  7. 검사만 (부품 이름 중복·문법 등)"
  echo "  8. 기존 월별 엑셀 전체를 DB로 다시 변환"
  echo "  0. 끝내기"
  echo "------------------------------------------------"
  read -r -p "번호를 입력하세요: " SEL
  case "$SEL" in
    1) open -a Terminal "$(pwd)/대시보드_열기_mac.command" ;;
    2) read -r -p "가져올 결과 엑셀을 이 창에 끌어다 놓고 Enter: " F; F="${F%\"}"; F="${F#\"}"; eval "\"$PY\" tools/import_month.py $F"; echo "서버(1번)가 켜져 있으면 브라우저 새로고침만 하면 반영됩니다."; pause ;;
    3) "$PY" tools/coords_tool.py --dry; read -r -p "위 결과를 DB에 저장할까요? (Y/N): " OK; [[ "$OK" =~ ^[Yy]$ ]] && "$PY" tools/coords_tool.py; pause ;;
    4) "$PY" tools/build.py; pause ;;
    5) "$PY" tools/build.py --no-key; pause ;;
    6) "$PY" tools/build.py --watch ;;
    7) "$PY" tools/build.py --check; pause ;;
    8) read -r -p "기존 월별 시트 형식 엑셀을 끌어다 놓고 Enter: " F; eval "\"$PY\" tools/convert_legacy.py $F"; pause ;;
    0) exit 0 ;;
  esac
done
