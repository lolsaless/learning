@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (py -3 tools\make_demo.py & goto :end)
python tools\make_demo.py
:end
pause
