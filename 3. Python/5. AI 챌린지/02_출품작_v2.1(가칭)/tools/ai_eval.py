# -*- coding: utf-8 -*-
"""AI 모델 비교(모델 비종속 확인): 같은 무작위 시나리오로 여러 AI 를 돌려 문장 검산 성능을 비교한다.

  python tools/ai_eval.py --models mock mock-noise                       # 시험용 모의 AI(설치 없이)
  python tools/ai_eval.py --models ollama:exaone3.5:7.8b ollama:qwen2.5:7b --n 10
  python tools/ai_eval.py --models openai:local-model --url http://127.0.0.1:1234

지표: AI 에게 물은 문장 수 · 버린 답(형식 오류·지어낸 숫자) · 자유 문형 오류 검출 · 정상 판정 · 빨강 오탐 · 걸린 시간.
'빨강 오탐'은 AI 가 무엇을 답하든 0 이어야 한다(AI 읽기 결과는 노랑까지만 내기 때문).
보고서: <프로그램 폴더>/평가결과/AI모델비교_날짜_시각.md
"""
import os
import sys
import time
import shutil
import argparse
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import config, evaluation                    # noqa: E402
from app.parts.ai.part import AiPart                  # noqa: E402
from app.parts.ai.providers import Mock, make         # noqa: E402


def provider_of(spec, url=None):
    if spec == "mock":
        return Mock()
    if spec == "mock-noise":
        return Mock(model="모의AI(엉터리 답 50%)", noise=0.5)
    kind, model = spec.split(":", 1)
    return make({"provider": kind, "model": model, "url": url or config.AI_DEFAULT_URL.get(kind, "")})


def run(spec, n, seed, url=None):
    ai = AiPart(settings_path=os.devnull, provider=provider_of(spec, url))
    tmp = tempfile.mkdtemp(prefix="AI평가_")
    t0 = time.time()
    b = evaluation.batch(n=n, seed0=seed, out_root=tmp, stmt_free=True, ai=ai)
    shutil.rmtree(tmp, ignore_errors=True)
    st = {}
    for r in b["결과"]:
        for k, v in (r.get("문장검산") or {}).items():
            if isinstance(v, (int, float)):
                st[k] = st.get(k, 0) + v
    free = b["종류별"].get("문장 계산 오류 · 자유 문형", {"검출": 0, "전체": 0})
    return {"모델": spec, "AI 문장": int(st.get("ai_calls", 0)), "AI 검산식": int(st.get("ai", 0)),
            "버린 답": int(st.get("rejected", 0)), "자유 문형 오류 검출": f"{free['검출']}/{free['전체']}",
            "전체 오류 검출": f"{b['검출']}/{b['심은오류']}", "정상": f"{b['정상맞음']}/{b['정상전체']}",
            "빨강 오탐": b["빨강오탐"], "초": round(time.time() - t0, 1)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="AI 모델 비교")
    ap.add_argument("--models", nargs="+", default=["mock", "mock-noise"])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=80000)
    ap.add_argument("--url", default=None)
    a = ap.parse_args(argv)
    rows = []
    for m in a.models:
        print(f"· {m} …", flush=True)
        try:
            rows.append(run(m, a.n, a.seed, a.url))
        except Exception as e:
            rows.append({"모델": m, "오류": str(e)})
        print("  ", rows[-1], flush=True)
    cols = ["모델", "AI 문장", "AI 검산식", "버린 답", "자유 문형 오류 검출", "전체 오류 검출", "정상", "빨강 오탐", "초"]
    md = [f"# AI 모델 비교 — 시나리오 {a.n}개(씨앗값 {a.seed}~{a.seed + a.n - 1}, 자유 문형 계산 문장 포함)", "",
          "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        md.append("| " + " | ".join(str(r.get(c, r.get("오류", "") if c == "AI 문장" else "")) for c in cols) + " |")
    md += ["", "- 판정은 모두 프로그램 계산. AI 는 문장을 검산식으로 읽기만 한다.",
           "- 버린 답: JSON 형식 오류, 빠진 칸, 문장에 없는 숫자(지어낸 숫자) — 판정에 쓰지 않음.",
           "- 'mock'·'mock-noise' 는 실제 AI 가 아닌 시험용 모의 AI 다(파이프라인·안전장치 확인용)."]
    out = os.path.join(config.PROGRAM_ROOT, config.DIR_EVAL)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"AI모델비교_{time.strftime('%Y%m%d_%H%M%S')}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\n보고서: {path}")


if __name__ == "__main__":
    main()
