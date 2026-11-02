@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 무작위 시연자료 만들기
set PY=
if exist "python\python.exe" set PY=python\python.exe
if not defined PY (where py >nul 2>nul && set PY=py -3)
if not defined PY (where python >nul 2>nul && set PY=python)
if not defined PY (
  echo  Python 3.8 이상이 필요합니다. https://www.python.org/downloads/ 에서 설치하세요.
  echo  (설치 화면에서 "Add python.exe to PATH" 체크) 또는 이 폴더에 python 폴더(휴대용)를 넣어 두세요.
  pause
  exit /b 1
)
echo 무작위 시연자료 3개를 만듭니다(보통 크기, 오류 10개).
%PY% tools\make_mock.py --count 3 %*
pause
