@echo off
REM Windows용 독립 실행 exe 빌드 스크립트
REM 사용법: Windows PC에서 build_windows.bat 더블클릭 (또는 cmd에서 실행)
REM 사전 준비물: bin\windows\ 폴더 구성 (README.md 의 "Windows 바이너리 준비" 참고)

cd /d "%~dp0"

if not exist "bin\windows\tesseract.exe" (
    echo [오류] bin\windows\tesseract.exe 가 없습니다.
    echo README.md 의 "Windows 바이너리 준비" 안내를 먼저 따라주세요.
    pause
    exit /b 1
)
if not exist "bin\windows\poppler\pdftoppm.exe" (
    echo [오류] bin\windows\poppler\pdftoppm.exe 가 없습니다.
    echo README.md 의 "Windows 바이너리 준비" 안내를 먼저 따라주세요.
    pause
    exit /b 1
)

echo [1/3] 필요한 패키지 설치 확인
pip install -r requirements.txt

echo [2/3] 이전 빌드 정리
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo [3/3] PyInstaller 빌드
pyinstaller build_windows.spec --noconfirm

echo.
echo 빌드 완료: dist\GCMS_Autotune_판독.exe
pause
