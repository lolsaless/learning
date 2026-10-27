@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 공문추출기 빌드
echo ==============================================
echo   공문추출기 빌드 - 소스 부품을 합쳐 공문추출기.html 만들기
echo ==============================================
set "PY="
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if defined PY (
  %PY% tools\build.py %*
) else (
  echo Python 이 없어 간단 빌드로 만듭니다. 검사는 하지 않습니다.
  powershell -NoProfile -ExecutionPolicy Bypass -File "tools\build_simple.ps1"
)
set "ERR=%ERRORLEVEL%"
echo.
pause
exit /b %ERR%
