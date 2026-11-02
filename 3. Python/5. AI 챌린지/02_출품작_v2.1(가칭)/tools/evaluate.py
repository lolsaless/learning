# -*- coding: utf-8 -*-
"""자동 평가(명령줄): 무작위 시나리오 여러 개를 만들어 검증 엔진을 채점하고 보고서를 저장한다.

  python tools/evaluate.py                         # 보통 크기 20개
  python tools/evaluate.py --n 100 --size 크게 --errors 12 --seed 40000
  python tools/evaluate.py --score 시연자료_무작위/가람도_777   # 이미 만든 시나리오 하나만 채점
  python tools/evaluate.py --n 25 --src-mix --target-fmt pdf      # 원본 형식 섞기 + PDF 취합본
  python tools/evaluate.py --n 25 --stmt-free --ai mock           # 자유 문형 계산 문장 + 시험용 모의 AI
  python tools/evaluate.py --n 20 --resubmit                      # 재제출 비교 채점

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
    ap.add_argument("--src-mix", action="store_true", help="원본 형식 섞기(xlsx·ods·csv·pdf·docx)")
    ap.add_argument("--target-fmt", default="hwpx", help="취합본 형식: hwpx·docx·pdf·odt·md·mix")
    ap.add_argument("--stmt-free", action="store_true", help="자유 문형 계산 문장 섞기(AI 읽기가 있어야 채점)")
    ap.add_argument("--ai", default=None, help="mock(시험용 모의 AI) 또는 settings(AI설정.json 의 AI)")
    ap.add_argument("--resubmit", action="store_true", help="재제출 비교 채점")
    a = ap.parse_args(argv)
    if a.resubmit:
        return resubmit_eval(a)
    ai = None
    if a.ai:
        from app.parts.ai.part import AiPart
        from app.parts.ai.providers import Mock
        ai = AiPart(settings_path=os.devnull, provider=Mock()) if a.ai == "mock" else AiPart()
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
    b = evaluation.batch(n=a.n, size=a.size, errors=a.errors, seed0=a.seed, out_root=tmp, src_mix=a.src_mix,
                         target_fmt=a.target_fmt, stmt_free=a.stmt_free, ai=ai,
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


def resubmit_eval(a):
    from app.parts.mockdata.scenario import Scenario
    import random
    tmp = tempfile.mkdtemp(prefix="재제출평가_")
    seed0 = a.seed or random.randint(1000, 90000)
    files = ok = imp = imp_all = near = 0
    for i in range(a.n):
        s = Scenario(tmp, seed=seed0 + i, size=a.size, errors=a.errors, gongmun=False, guides=False, form=False,
                     resubmit=True, src_mix=a.src_mix).run()
        for r in evaluation.score_resubmit(s["folder"]) or []:
            files += 1
            ok += r["변경_맞음"]
            imp += r["영향_맞음"]
            imp_all += r["영향_정답"]
            near += r["끝자리차이"]
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"재제출본 {files}개: 바뀐 칸 찾기 {ok}/{files} · 영향받는 취합본 칸과 새 값 {imp}/{imp_all}"
          f"(인쇄 문서 원본 끝자리 1 차이 {near}) · 씨앗값 {seed0}~{seed0 + a.n - 1}")


if __name__ == "__main__":
    main()
