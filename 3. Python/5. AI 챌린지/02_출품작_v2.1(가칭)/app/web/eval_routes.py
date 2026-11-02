# -*- coding: utf-8 -*-
"""[화면 연결] 자동 평가 주소: 시나리오 하나 채점, 무작위 시나리오 여러 개 일괄 평가, 시나리오로 시연 시작."""
import os
import time
import shutil
import tempfile

from app import config
from app import evaluation
from app.common.errors import WorkError
from app.web import demo


def _short(r):
    return {"이름": r["시나리오"].get("이름"), "오류": f"{r['오류_맞음']}/{r['오류_전체']}",
            "정상": f"{r['정상_맞음']}/{r['정상_전체']}", "빨강오탐": len(r["빨강오탐"]), "노랑": len(r["노랑"]),
            "칸수": r["칸수"], "초": r["초"],
            "놓침": [f"{x['id']} {x['구분']} · {x.get('위치')} → {x['판정']}" for x in r["항목"] if not x["ok"] and not x["연쇄"]],
            "오탐": [f"{lab} → {st}" for _, st, lab in r["빨강오탐"]]}


def routes(app):
    def score(b):
        r = evaluation.score(app.mock.folder(b["name"]))
        return dict(_short(r), 항목=r["항목"], 상태분포=r["상태분포"])

    def batch(b):
        n = int(b.get("n", 10))
        if not 1 <= n <= 200:
            raise WorkError("시나리오 수는 1~200 사이로 정해 주세요")
        tmp = tempfile.mkdtemp(prefix="평가_")
        res = evaluation.batch(n=n, size=b.get("size", "보통"), errors=int(b.get("errors", 10)),
                               seed0=b.get("seed") or None, out_root=tmp, src_mix=bool(b.get("src_mix")),
                               target_fmt=b.get("target_fmt") or "hwpx")
        md = evaluation.report_md(res)
        out_dir = os.path.join(config.PROGRAM_ROOT, config.DIR_EVAL)
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"평가_{time.strftime('%Y%m%d_%H%M%S')}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        shutil.rmtree(tmp, ignore_errors=True)
        out = {k: v for k, v in res.items() if k not in ("결과", "폴더")}
        out.update(시나리오=[_short(r) for r in res["결과"]], 보고서=path)
        return out

    return [
        ("POST", "/api/eval/score", score),
        ("POST", "/api/eval/batch", batch),
        ("POST", "/api/demo/scenario", lambda b: demo.setup_scenario(app, app.mock.folder(b["name"]), b.get("reset", False))),
    ]
