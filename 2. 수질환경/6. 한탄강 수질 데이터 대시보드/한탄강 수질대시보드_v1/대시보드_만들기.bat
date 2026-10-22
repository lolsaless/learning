@echo off
chcp 65001 > NUL
cd /d "%~dp0"
echo [1/2] 필요한 패키지 확인(openpyxl)...
python -c "import openpyxl" 2> NUL || python -m pip install openpyxl
echo [2/2] 대시보드 생성 중...
python 02_build_dashboard.py
if errorlevel 1 (echo 오류가 발생했습니다. 위 메시지를 확인하세요. & pause & exit /b 1)
start "" "한탄강_수질대시보드.html"
pause
