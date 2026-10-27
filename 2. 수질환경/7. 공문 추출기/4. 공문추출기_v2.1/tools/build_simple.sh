#!/bin/bash
# 공문추출기 간단 빌드 (python3 가 없을 때 빌드_mac.command 가 부름)
# 소스/빌드목록.txt 순서대로 이어 붙이기만 한다 — 검사는 하지 않음. 이어 붙이는 규칙은 tools/build.py 와 같다.
cd "$(dirname "$0")/.." || exit 1
LIST="소스/빌드목록.txt"; OUT="공문추출기.html"; TMP="$OUT.tmp"
[ -f "$LIST" ] || { echo "[오류] $LIST 가 없습니다."; exit 1; }
: > "$TMP"
first=1
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%$'\r'}"
  if [ $first = 1 ]; then line="${line#$'\xEF\xBB\xBF'}"; first=0; fi
  l="$(printf '%s' "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  case "$l" in ''|'#'*) continue;; esac
  case "$l" in '['*']') continue;; esac
  l="${l//\\//}"
  f="소스/$l"
  if [ ! -f "$f" ]; then echo "[오류] 목록에 있지만 파일이 없음: $f"; rm -f "$TMP"; exit 1; fi
  case "$l" in *.js|*.css) printf '/* ===== %s ===== */\n' "$l" >> "$TMP";; esac
  if [ "$(head -c3 "$f" | od -An -tx1 | tr -d ' \n')" = "efbbbf" ]; then tail -c +4 "$f" >> "$TMP"; else cat "$f" >> "$TMP"; fi
  if [ -s "$f" ] && [ -n "$(tail -c1 "$f")" ]; then printf '\n' >> "$TMP"; fi
done < "$LIST"
if [ -f "$OUT" ]; then mkdir -p "빌드결과/이전"; cp "$OUT" "빌드결과/이전/공문추출기_$(date +%Y%m%d-%H%M%S).html"; fi
mv "$TMP" "$OUT"
echo "[완료] $OUT ($(( $(wc -c < "$OUT") / 1024 )) KB) — 간단 빌드(검사 없음). 화면을 열어 오류가 없는지 확인하세요."
