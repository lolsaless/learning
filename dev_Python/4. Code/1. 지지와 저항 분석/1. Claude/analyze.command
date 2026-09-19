#!/bin/bash
# 더블클릭으로 실행하는 런처.
# Finder에서 analyze.command 아이콘을 더블클릭하면 터미널이 열리고,
# 티커/기간을 입력받아 분석 후 결과 HTML을 자동으로 브라우저에 띄운다.

cd "$(dirname "$0")"

VENV_PY="/Users/lol/Documents/GitHub/.venv/bin/python"
if [ -x "$VENV_PY" ]; then
    PYTHON="$VENV_PY"
else
    PYTHON="python3"
fi

"$PYTHON" analyze.py

echo
read -p "창을 닫으려면 엔터를 누르세요..." _
