@echo off
chcp 65001 > NUL
cd /d "%~dp0"
title 한탄강 대시보드 서버 (이 창을 닫으면 저장·V월드 지도 중지)
python -c "import openpyxl" 2> NUL || python -m pip install openpyxl
python serve.py
pause
