@echo off
chcp 65001 > nul
rem ── 인터넷이 되는 PC 에서 한 번 실행: 파이썬 3.9~3.13 용 pywin32 설치 파일(각 7MB 안팎)을 이 폴더에 받습니다.
rem    받은 뒤 프로그램 폴더째 내부망 PC 로 복사 → 설치_pywin32.bat 실행.
cd /d "%~dp0"
for %%v in (3.9 3.10 3.11 3.12 3.13) do (
  echo 파이썬 %%v 용 받는 중...
  python -m pip download pywin32 --platform win_amd64 --python-version %%v --only-binary=:all: --no-deps -d "%~dp0."
)
echo 완료. 이 폴더(vendor)를 함께 복사하세요.
pause
