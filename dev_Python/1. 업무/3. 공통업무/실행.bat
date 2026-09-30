@echo off
chcp 65001 >nul
cd /d "%~dp0"
python "장비입력도우미.py"
if errorlevel 1 pause
