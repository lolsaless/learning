#!/bin/bash
# 더블클릭으로 실행 (처음 한 번: 터미널에서 chmod +x 실행_mac.command)
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 가 없습니다. https://www.python.org 에서 3.9 이상을 설치하세요."
  read -r -p "엔터를 누르면 닫힙니다"
  exit 1
fi
python3 HWPX비교기.py "$@"
