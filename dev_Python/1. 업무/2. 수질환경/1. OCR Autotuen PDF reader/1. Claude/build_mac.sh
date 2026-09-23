#!/bin/bash
# macOS용 독립 실행 앱(.app) 빌드 스크립트
# 사용법: ./build_mac.sh
# (bin/mac/ 안에 tesseract, poppler/pdftoppm, poppler/pdfinfo, tessdata/eng.traineddata가
#  이미 준비되어 있어야 한다 - 처음 준비하는 방법은 README.md의 "macOS 바이너리 준비" 참고)
set -e
cd "$(dirname "$0")"

echo "[1/3] 이전 빌드 정리"
rm -rf build dist

echo "[2/3] PyInstaller 빌드"
python3 -m PyInstaller build_mac.spec --noconfirm

APP="dist/GCMS_Autotune_판독.app"

echo "[3/3] 코드사이닝 (ad-hoc)"
# PyInstaller가 빌드 과정에서 실행파일 자체는 이미 ad-hoc 서명을 마친 상태라
# 로컬 실행에는 보통 문제가 없다. 아래는 번들 전체에 대한 마무리 서명 시도이며,
# 실패해도(예: 리소스 포크 관련 경고) 앱 실행 자체에는 지장이 없는 경우가 많다.
set +e
xattr -cr "$APP" 2>/dev/null
find "$APP" -type f \( -name "*.dylib" -o -name "*.so" \) -exec codesign --force --sign - {} \; 2>/dev/null
find "$APP" -type f -perm +111 ! -name "*.dylib" -exec codesign --force --sign - {} \; 2>/dev/null
codesign --force --sign - "$APP" 2>/tmp/gcms_codesign.log
if codesign --verify "$APP" 2>/dev/null; then
  echo "서명 확인 완료"
else
  echo "⚠️  마무리 서명이 완전히 성공하지 못했습니다 (아래 로그 참고)."
  echo "    로컬에서 빌드해 바로 실행하는 경우 대부분 문제없이 동작합니다."
  echo "    다른 Mac으로 옮겨 실행 시 '확인되지 않은 개발자' 경고가 뜨면"
  echo "    앱 아이콘 우클릭 -> 열기로 최초 1회 승인하거나,"
  echo "    xattr -cr \"$APP\" 을 실행한 뒤 다시 열어보세요."
  cat /tmp/gcms_codesign.log
fi

echo ""
echo "빌드 완료: $APP"
echo "더블클릭하거나 open \"$APP\" 으로 실행하세요."
