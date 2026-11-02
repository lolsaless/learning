@echo off
chcp 65001 > nul
cd /d "%~dp0"
where python > nul 2> nul
if errorlevel 1 (
  echo 파이썬이 설치되어 있지 않습니다. https://www.python.org 에서 3.9 이상을 설치하세요.
  pause
  exit /b 1
)
python HWPX비교기.py %*
pause
