#!/bin/sh
cd "$(dirname "$0")"
python3 tools/make_mock.py --count 3 "$@"
echo
printf '끝났습니다. 창을 닫아도 됩니다.'
read x
