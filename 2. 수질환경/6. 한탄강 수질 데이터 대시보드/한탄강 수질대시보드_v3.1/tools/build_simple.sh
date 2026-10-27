#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  build_simple.sh — Python 없이 부품을 합치는 간단 빌드 (Mac·Linux)
#  - 검사(이름 중복·문법 등)는 하지 않습니다.
#  - 데이터는 지난번 Python 빌드가 남긴 빌드결과/_data.js 를 씁니다(엑셀을 다시 읽지 않음).
#  - 결과는 tools/build.py --cache 와 같은 규칙으로 만듭니다.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -e
cd "$(dirname "$0")/.."
SRC="소스"; OUT="한탄강_수질대시보드.html"; DATA="빌드결과/_data.js"; TMP="빌드결과/_simple.tmp"
if [ ! -f "$DATA" ]; then echo "[오류] $DATA 가 없습니다. Python으로 한 번 빌드해야 합니다(tools/build.py)."; exit 1; fi
VER="$(tr -d '\r\n' < "$SRC/버전.txt")"
PARTS=()
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%%#*}"; line="$(printf '%s' "$line" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  [ -n "$line" ] && PARTS+=("$line")
done < "$SRC/빌드목록.txt"
for p in "${PARTS[@]}"; do [ -f "$SRC/$p" ] || { echo "[오류] 목록에 있지만 파일이 없음: $SRC/$p"; exit 1; }; done
body() { tr -d '\r' < "$SRC/$1"; }            # 줄바꿈 정리(끝 줄바꿈은 $(...)가 지움)
emit() { printf '%s' "$1" >> "$TMP"; }
: > "$TMP"
emit $'<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n<meta name="referrer" content="strict-origin-when-cross-origin">\n'
# 머리(00_틀/01_*.html)
first=1; for p in "${PARTS[@]}"; do case "$p" in 00_틀/01_*.html) [ $first = 0 ] && emit $'\n'; emit "$(body "$p")"; first=0;; esac; done
emit $'\n<style>\n'
first=1; for p in "${PARTS[@]}"; do case "$p" in *.css) [ $first = 0 ] && emit $'\n\n'; emit "/* ===== 부품: $p ===== */"$'\n'"$(body "$p")"; first=0;; esac; done
emit $'\n</style>\n</head>\n<body>\n'
first=1; for p in "${PARTS[@]}"; do case "$p" in 00_틀/01_*.html) ;; *.html) [ $first = 0 ] && emit $'\n'; emit "<!-- ===== 부품: $p ===== -->"$'\n'"$(body "$p")"; first=0;; esac; done
emit $'\n'
first=1; for p in "${PARTS[@]}"; do case "$p" in
  10_외부라이브러리/*.geojson) [ $first = 0 ] && emit $'\n'; emit "<script>window.GEO_SIGUNGU = $(body "$p");</script>"; first=0;;
  10_외부라이브러리/*.js) [ $first = 0 ] && emit $'\n'; emit "<script>$(body "$p")</script>"; first=0;;
esac; done
emit $'\n<script>window.APP_VERSION = "'"$VER"$'";\n'"$(tr -d '\r' < "$DATA")"$'</script>\n<script>\n"use strict";\n'
first=1; for p in "${PARTS[@]}"; do case "$p" in 10_외부라이브러리/*) ;; *.js) [ $first = 0 ] && emit $'\n\n'; emit "/* ===== 부품: $p ===== */"$'\n'"$(body "$p")"; first=0;; esac; done
emit $'\n</script>\n</body>\n</html>\n'
if [ -f "$OUT" ]; then mkdir -p "빌드결과/이전"; cp "$OUT" "빌드결과/이전/${OUT%.html}_$(date +%Y%m%d_%H%M%S).html"; fi
mv "$TMP" "$OUT"
echo "[완료] $OUT (간단 빌드 — 검사 없음, 데이터는 지난번 빌드 것)"
