@echo off
chcp 65001 > nul
cd /d "%~dp0"
rem ── pywin32 설치: 한글 자동화(한글로 다시 저장 · PDF 저장)에 필요. 없어도 나머지 기능은 모두 동작합니다.
rem    1) vendor 폴더에 받아 둔 파일로 인터넷 없이 설치 (내부망)
rem    2) 없으면 인터넷으로 설치
where python > nul 2> nul || (echo 파이썬이 없습니다. https://www.python.org 에서 3.9 이상을 설치하세요. & pause & exit /b 1)
echo [1/2] vendor 폴더의 파일로 설치를 시도합니다...
python -m pip install --no-index --find-links "%~dp0vendor" pywin32 && goto ok
echo [2/2] 맞는 파일이 vendor 에 없어 인터넷으로 설치합니다...
python -m pip install pywin32 && goto ok
echo.
echo 설치하지 못했습니다. 인터넷이 되는 PC 에서 vendor\받기_pywin32.bat 을 실행해 파일을 받은 뒤
echo 이 폴더째 복사해 와서 다시 실행하세요.
pause
exit /b 1
:ok
echo.
echo 설치 완료. 프로그램을 다시 실행하면 오른쪽 위에 "한글 자동화 ✓" 가 보입니다.
pause
