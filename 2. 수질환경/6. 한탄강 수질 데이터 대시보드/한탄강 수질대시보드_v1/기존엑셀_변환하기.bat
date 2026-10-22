@echo off
chcp 65001 > NUL
cd /d "%~dp0"
set /p SRC=기존 월별 시트 형식 엑셀 파일을 이 창에 끌어다 놓고 Enter: 
python -c "import openpyxl" 2> NUL || python -m pip install openpyxl
python 01_convert_legacy.py %SRC% 한탄강_수질DB.xlsx
pause
