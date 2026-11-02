#!/bin/sh
cd "$(dirname "$0")"
python3 tools/evaluate.py --n 20 "$@"
echo
printf '끝났습니다. 창을 닫아도 됩니다.'
read x
