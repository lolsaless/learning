#!/bin/zsh

script_dir=${0:A:h}
cd "$script_dir" || exit 1

finish() {
  local result=$1
  echo
  if [[ $result -eq 0 ]]; then
    echo "완료되었습니다. 아무 키나 누르면 이 창이 닫힙니다."
  else
    echo "실행 중 오류가 발생했습니다. 위의 오류 내용을 확인하세요."
  fi
  read -k 1
  echo
  exit $result
}

if [[ ! -x .venv/bin/python ]]; then
  echo "처음 실행을 위한 환경을 준비합니다..."
  python3 -m venv .venv || finish 1
fi

if ! .venv/bin/python -c 'import numpy, pandas, plotly, yfinance' 2>/dev/null; then
  echo "필요한 패키지를 설치합니다..."
  .venv/bin/python -m pip install -r requirements.txt || finish 1
fi

echo "settings.txt의 값으로 분석을 시작합니다."
echo
.venv/bin/python analyze.py
status_code=$?
finish $status_code
