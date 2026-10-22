@echo off
chcp 65001 > NUL
cd /d "%~dp0"
netstat -ano | findstr ":8765" | findstr "LISTENING" > NUL || start "한탄강 대시보드 서버(닫으면 지도 배경 중지)" /min python -m http.server 8765 --bind 127.0.0.1
timeout /t 1 > NUL
start "" "http://localhost:8765/한탄강_수질대시보드.html"
