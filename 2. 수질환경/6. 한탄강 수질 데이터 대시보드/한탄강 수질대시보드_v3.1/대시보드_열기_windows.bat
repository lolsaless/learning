@echo off
chcp 65001 > NUL
cd /d "%~dp0"
title 한탄강 대시보드 서버 (이 창을 닫으면 저장·V월드 지도·자동 빌드가 멈춥니다)
set "PY="
python -c "import sys" >NUL 2>NUL && set "PY=python"
if not defined PY ( py -3 -c "import sys" >NUL 2>NUL && set "PY=py -3" )
if not defined PY (
  echo [오류] Python이 없습니다. python.org 에서 Python 3을 설치하세요(설치 화면에서 "Add python.exe to PATH" 체크).
  echo        Python 없이 보기만 하려면 한탄강_수질대시보드.html 을 Edge로 여세요.
  pause & exit /b 1
)
%PY% -c "import openpyxl" 2> NUL || %PY% -m pip install openpyxl
%PY% tools\serve.py
pause
