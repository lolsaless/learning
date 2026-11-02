@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 숫자지기 (이 창을 닫으면 종료)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app\server.py %*
  goto :end
)
where python >nul 2>nul
if %errorlevel%==0 (
  python app\server.py %*
  goto :end
)
if exist "python\python.exe" (
  python\python.exe app\server.py %*
  goto :end
)
echo.
echo  Python 3.8 이상이 필요합니다.
echo  https://www.python.org/downloads/ 에서 설치한 뒤 다시 실행하세요.
echo  (설치 화면에서 "Add python.exe to PATH"를 체크)
echo  또는 이 폴더에 python 폴더(휴대용 Python)를 넣어 두면 그대로 사용합니다.
:end
pause
