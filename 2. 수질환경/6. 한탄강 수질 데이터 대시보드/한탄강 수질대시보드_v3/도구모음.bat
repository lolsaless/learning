@echo off
chcp 65001 > NUL
cd /d "%~dp0"
title 한탄강 수질 대시보드 도구모음 v3
python -c "import openpyxl" 2> NUL || python -m pip install openpyxl
:MENU
cls
echo ================================================
echo   한탄강 수질 대시보드 도구모음 (v3)
echo ================================================
echo   1. 대시보드 열기 (권장: 만들기 + 지점 수정 저장 + V월드 지도)
echo   2. 월별 결과 엑셀 가져오기 (YYYYMM 시트)
echo   3. V월드로 좌표 일괄 검색 ('추정' 좌표만)
echo   4. 대시보드 HTML 파일만 만들기 (공유용)
echo   5. 공유용 HTML 만들기 (V월드 키 제외, 기관 밖 전달용)
echo   6. 기존 월별 엑셀 전체를 DB로 다시 변환
echo   0. 끝내기
echo ------------------------------------------------
set /p SEL=번호를 입력하세요: 
if "%SEL%"=="1" goto OPEN
if "%SEL%"=="2" goto IMPORT
if "%SEL%"=="3" goto VW
if "%SEL%"=="4" goto BUILD
if "%SEL%"=="5" goto SHARE
if "%SEL%"=="6" goto LEGACY
if "%SEL%"=="0" exit /b
goto MENU

:OPEN
start "한탄강 대시보드 서버 (닫으면 저장·지도 중지)" python serve.py
goto MENU

:IMPORT
set /p F=가져올 결과 엑셀을 이 창에 끌어다 놓고 Enter: 
python 03_import_month.py %F%
echo 서버(1번)가 켜져 있으면 브라우저에서 새로고침(F5)만 하면 반영됩니다.
pause
goto MENU

:VW
echo [1/2] 미리보기(저장하지 않음)...
python 04_coords_tool.py --dry
set /p OK=위 결과를 DB에 저장할까요? (Y/N): 
if /i "%OK%"=="Y" python 04_coords_tool.py
pause
goto MENU

:BUILD
python 02_build_dashboard.py
pause
goto MENU

:SHARE
python 02_build_dashboard.py 한탄강_수질DB.xlsx 한탄강_수질대시보드_공유용.html --no-key
pause
goto MENU

:LEGACY
set /p F=기존 월별 시트 형식 엑셀을 끌어다 놓고 Enter: 
python 01_convert_legacy.py %F%
pause
goto MENU
