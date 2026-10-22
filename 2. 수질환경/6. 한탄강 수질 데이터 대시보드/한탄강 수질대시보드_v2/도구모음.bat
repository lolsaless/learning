@echo off
chcp 65001 > NUL
cd /d "%~dp0"
title 한탄강 수질 대시보드 도구모음 v2
python -c "import openpyxl" 2> NUL || python -m pip install openpyxl
:MENU
cls
echo ================================================
echo   한탄강 수질 대시보드 도구모음 (v2)
echo ================================================
echo   1. 대시보드 만들기 (DB 엑셀 → HTML) 후 열기
echo   2. 월별 결과 엑셀 가져오기 (YYYYMM 시트)
echo   3. 국가측정망 좌표표(hwpx) 가져오기
echo   4. V월드로 지점 좌표 자동 보정
echo   5. 대시보드 열기 (V월드 배경지도용 로컬 서버)
echo   6. 기존 월별 엑셀 전체를 DB로 다시 변환
echo   0. 끝내기
echo ------------------------------------------------
set /p SEL=번호를 입력하세요: 
if "%SEL%"=="1" goto BUILD
if "%SEL%"=="2" goto IMPORT
if "%SEL%"=="3" goto NET
if "%SEL%"=="4" goto VW
if "%SEL%"=="5" goto OPEN
if "%SEL%"=="6" goto LEGACY
if "%SEL%"=="0" exit /b
goto MENU

:BUILD
python 02_build_dashboard.py
if errorlevel 1 (pause & goto MENU)
call :SERVE
pause
goto MENU

:IMPORT
set /p F=가져올 결과 엑셀을 이 창에 끌어다 놓고 Enter: 
python 03_import_month.py %F%
pause
goto MENU

:NET
set /p F=국가측정망 좌표 hwpx 파일을 끌어다 놓고 Enter: 
python 04_coords_tool.py network %F%
pause
goto MENU

:VW
echo [1/2] 미리보기(저장하지 않음)...
python 04_coords_tool.py vworld --dry
set /p OK=위 결과를 DB에 저장할까요? (Y/N): 
if /i "%OK%"=="Y" python 04_coords_tool.py vworld
pause
goto MENU

:OPEN
call :SERVE
pause
goto MENU

:LEGACY
set /p F=기존 월별 시트 형식 엑셀을 끌어다 놓고 Enter: 
python 01_convert_legacy.py %F%
pause
goto MENU

:SERVE
netstat -ano | findstr ":8765" | findstr "LISTENING" > NUL || start "한탄강 대시보드 서버(닫으면 지도 배경 중지)" /min python -m http.server 8765 --bind 127.0.0.1
timeout /t 1 > NUL
start "" "http://localhost:8765/한탄강_수질대시보드.html"
echo 브라우저에서 http://localhost:8765/한탄강_수질대시보드.html 을 열었습니다.
exit /b
