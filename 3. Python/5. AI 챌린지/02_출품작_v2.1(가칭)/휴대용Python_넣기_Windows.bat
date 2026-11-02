@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY (where python >nul 2>nul && set PY=python)
if not defined PY (
  echo  이 도구를 돌릴 Python 이 없습니다. Python 이 있는 PC 에서 한 번만 실행해 python 폴더를 만든 뒤 폴더째 옮기세요.
  pause
  exit /b 1
)
%PY% tools\make_portable.py %*
pause
