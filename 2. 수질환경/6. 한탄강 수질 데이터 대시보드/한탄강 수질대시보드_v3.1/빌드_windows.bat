@echo off
chcp 65001 > NUL
cd /d "%~dp0"
title 한탄강 대시보드 빌드
set "PY="
python -c "import sys" >NUL 2>NUL && set "PY=python"
if not defined PY ( py -3 -c "import sys" >NUL 2>NUL && set "PY=py -3" )
if defined PY (
  %PY% -c "import openpyxl" 2> NUL || %PY% -m pip install openpyxl
  %PY% tools\build.py %*
) else (
  echo [안내] Python이 없어 간단 빌드로 합칩니다(검사 없음, 데이터는 지난번 빌드 것).
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_simple.ps1
)
pause
