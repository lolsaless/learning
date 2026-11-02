# -*- coding: utf-8 -*-
"""자동 평가(명령줄): 무작위 시나리오 여러 개를 만들어 검증 엔진을 채점하고 보고서를 저장한다.

  python tools/evaluate.py                         # 보통 크기 20개
  python tools/evaluate.py --n 100 --size 크게 --errors 12 --seed 40000
  python tools/evaluate.py --score 시연자료_무작위/가람도_777   # 이미 만든 시나리오 하나만 채점

보고서: <프로그램 폴더>/평가결과/평가_날짜_시각.md
"""
import os
import sys
import time
import shutil
import argparse
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import config, evaluation                     # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="자동 평가")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--size", default="보통", choices=["작게", "보통", "크게"])
    ap.add_argument("--errors", type=int, default=10)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--score", default=None, help="이미 만든 시나리오 폴더 하나만 채점")
    a = ap.parse_args(argv)
    if a.score:
        r = evaluation.score(a.score)
        print(f"{r['시나리오'].get('이름')}: 오류 {r['오류_맞음']}/{r['오류_전체']} · 정상 {r['정상_맞음']}/{r['정상_전체']} · "
              f"빨강 오탐 {len(r['빨강오탐'])} · 노랑 {len(r['노랑'])} · 칸 {r['칸수']}")
        for x in r["항목"]:
            if not x["ok"]:
                print(f"  ✗ {x['id']} {x['구분']} {x.get('위치')} → {x['판정']} (기대 {', '.join(x['기대'])})")
        return
    tmp = tempfile.mkdtemp(prefix="평가_")
    t = time.time()
    b = evaluation.batch(n=a.n, size=a.size, errors=a.errors, seed0=a.seed, out_root=tmp,
                         progress=lambda i, n, r: print(f"  {i}/{n} {r['시나리오']['이름']}: 오류 {r['오류_맞음']}/{r['오류_전체']}"
                                                        f" · 빨강 오탐 {len(r['빨강오탐'])}", flush=True))
    md = evaluation.report_md(b)
    out_dir = os.path.join(config.PROGRAM_ROOT, config.DIR_EVAL)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"평가_{time.strftime('%Y%m%d_%H%M%S')}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n검출 {b['검출']}/{b['심은오류']} ({b['검출률']}%) · 정상 {b['정상맞음']}/{b['정상전체']} · "
          f"빨강 오탐 {b['빨강오탐']} · 노랑 {b['노랑']} · {time.time() - t:.1f}초")
    print(f"보고서: {path}")


if __name__ == "__main__":
    main()
