# -*- coding: utf-8 -*-
"""무작위 시연자료 만들기(명령줄).

  python tools/make_mock.py                      # 보통 크기 1개(씨앗값 무작위)
  python tools/make_mock.py --count 5 --size 크게 --errors 15
  python tools/make_mock.py --seed 777            # 같은 씨앗값 → 같은 자료
  python tools/make_mock.py --no-gongmun --no-guides --fmt hwpx

만든 자료는 <프로그램 폴더>/시연자료_무작위/ 에 쌓인다(--out 으로 바꿀 수 있음).
"""
import os
import sys
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import config                                  # noqa: E402
from app.parts.mockdata.part import MockDataPart        # noqa: E402
from app.parts.mockdata.errors import KINDS             # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="무작위 시연자료 만들기")
    ap.add_argument("--count", type=int, default=1, help="만들 개수(기본 1)")
    ap.add_argument("--seed", type=int, default=None, help="첫 씨앗값(없으면 무작위)")
    ap.add_argument("--size", default="보통", choices=["작게", "보통", "크게"])
    ap.add_argument("--errors", type=int, default=10, help="시나리오마다 심을 오류 수")
    ap.add_argument("--kinds", default=",".join(KINDS), help="오류 종류(쉼표로): " + ",".join(KINDS))
    ap.add_argument("--fmt", default="both", choices=["both", "hwpx", "odt"], help="공문·참고자료 형식")
    ap.add_argument("--no-gongmun", action="store_true")
    ap.add_argument("--no-guides", action="store_true")
    ap.add_argument("--no-form", action="store_true")
    ap.add_argument("--no-resubmit", action="store_true")
    ap.add_argument("--out", default=os.path.join(config.PROGRAM_ROOT, config.DIR_MOCK))
    a = ap.parse_args(argv)
    part = MockDataPart(a.out)
    for i in range(a.count):
        s = part.generate(seed=(a.seed + i) if a.seed is not None else None, size=a.size, errors=a.errors,
                          kinds=a.kinds.split(","), fmt=a.fmt, gongmun=not a.no_gongmun, guides=not a.no_guides,
                          form=not a.no_form, resubmit=not a.no_resubmit)
        print(f"[{i + 1}/{a.count}] {s['name']}  {s['org']} · 요구자료 {s['tables']}개 · 심은 오류 {s['errors']}개 · 파일 {s['files']}개")
        print(f"        {s['folder']}")


if __name__ == "__main__":
    main()
