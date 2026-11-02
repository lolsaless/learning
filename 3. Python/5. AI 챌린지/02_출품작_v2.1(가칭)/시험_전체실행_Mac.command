#!/bin/sh
cd "$(dirname "$0")"
python3 tests/run_all.py
echo
printf '끝났습니다. 창을 닫아도 됩니다.'
read x
