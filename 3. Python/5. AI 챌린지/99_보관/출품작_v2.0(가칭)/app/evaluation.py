# -*- coding: utf-8 -*-
"""평가 조립부: 정답표가 있는 시연자료를 검증 엔진으로 돌려 채점한다.

조립부(workspace.py)처럼 여러 파트를 함께 쓰는 곳이라 app/ 바로 아래에 둔다.
  - score(시나리오 폴더)            → 항목별 맞음/틀림, 오탐(빨강·노랑), 출처 위치 일치율
  - batch(n, 크기, 오류 수, 씨앗값) → 무작위 시나리오 n개를 만들어 채점하고 오류 종류별로 묶어 보고
  - report_md(결과)                 → 사람이 읽는 평가 보고서(마크다운)

판정 기준
  맞음   : 엔진 판정이 정답표 '기대' 목록 안에 있음(요일 오류는 본문 요일 검사에 걸렸는지)
  오탐   : 정답표에 없는 칸이 빨강(불일치·단위·계산·충돌) → '빨강 오탐', 노랑(출처 미확인·후보 여러 개) → '노랑'
  출처 일치: 정답표에 적힌 원본 칸(파일·시트·칸)이 엔진이 고른 첫 출처와 같은지
"""
import os
import json
import time
import tempfile

from app.formats.hwpx import HwpxDoc, table_grids
from app.formats.xlsx import read_xlsx
from app.parts.verify.engine import SourceIndex, Verifier

RED = ("mismatch", "unit", "calc", "conflict")
YELLOW = ("unknown", "multi")


def load_key(folder):
    with open(os.path.join(folder, "정답표.json"), encoding="utf-8") as f:
        return json.load(f)


def build_index(base):
    idx, names, roles = SourceIndex(), {}, {}
    sid = 0
    for sub, role in (("01_원본자료", "원본"), ("02_팀제출", "팀제출")):
        for dp, _, fs in sorted(os.walk(os.path.join(base, sub))):
            for f in sorted(fs):
                p = os.path.join(dp, f)
                if f.startswith(("~$", ".")):
                    continue
                sid += 1
                s = f"S{sid}"
                names[s], roles[s] = f, role
                if f.endswith((".xlsx", ".xlsm")):
                    idx.add_workbook(s, read_xlsx(p))
                elif f.endswith(".hwpx"):
                    idx.add_grids(s, table_grids(HwpxDoc(p)))
    return idx, names, roles


def find_item(doc, a):
    if "표" in a:
        for it in doc.items:
            if it.kind == "cell" and it.table == a["표"] and it.rowlab == a["행"] and (it.collab or "").startswith(a["열"]):
                return it
    if "본문" in a:
        for it in doc.items:
            if it.kind == "para" and a["본문"] in (it.context or "") and it.raw == a.get("문서값"):
                return it
    return None


def score(folder, stage=1):
    key = load_key(folder)
    target = os.path.join(folder, key["대상"])
    base = os.path.dirname(os.path.dirname(target))
    t0 = time.time()
    idx, names, roles = build_index(base)
    doc = HwpxDoc(target)
    out = Verifier(idx, names, roles).verify(doc)
    secs = time.time() - t0
    R = out["items"]
    rows, seen = [], set()
    src_hit = src_all = 0
    for a in key["항목"]:
        exp = a.get("단계2기대") if stage == 2 and "단계2기대" in a else a["기대"]
        row = {"id": a["id"], "구분": a["구분"], "종류": a.get("종류", ""), "기대": exp, "정상": bool(a.get("정상")),
               "연쇄": bool(a.get("연쇄")), "설명": a.get("설명", "")}
        if "요일" in a:
            hit = any(a["요일"] in t["raw"] for t in out["text_issues"] if t["kind"] == "weekday")
            row.update(ok=hit, 판정="weekday" if hit else "못 찾음", 위치=a["요일"])
            rows.append(row)
            continue
        it = find_item(doc, a)
        if not it:
            row.update(ok=False, 판정="칸 못 찾음", 위치=a.get("행") or a.get("본문"))
            rows.append(row)
            continue
        seen.add(it.key)
        st = R[it.key]["status"]
        row.update(ok=st in exp, 판정=st, 위치=it.label, 칸=it.key)
        if a.get("출처") and a.get("정상"):
            ops = R[it.key].get("opinions") or R[it.key].get("candidates") or []
            if ops:
                src_all += 1
                file_, ref = a["출처"].split(" ", 1)
                first = ops[0]
                if names.get(first["sid"]) == file_ and first["ref"] == ref:
                    src_hit += 1
                    row["출처일치"] = True
                else:
                    row["출처일치"] = False
                    row["엔진출처"] = f"{names.get(first['sid'])} {first['ref']}"
        rows.append(row)
    red = [(k, R[k]["status"], doc.item(k).label) for k in R if k not in seen and R[k]["status"] in RED]
    yellow = [(k, R[k]["status"], doc.item(k).label) for k in R if k not in seen and R[k]["status"] in YELLOW]
    dist = {}
    for r in R.values():
        dist[r["status"]] = dist.get(r["status"], 0) + 1
    errs = [r for r in rows if not r["정상"] and not r["연쇄"]]
    norms = [r for r in rows if r["정상"]]
    return {"시나리오": key.get("시나리오", {"이름": os.path.basename(folder)}), "folder": folder,
            "항목": rows, "오류_맞음": sum(r["ok"] for r in errs), "오류_전체": len(errs),
            "정상_맞음": sum(r["ok"] for r in norms), "정상_전체": len(norms),
            "연쇄_전체": sum(1 for r in rows if r["연쇄"]),
            "빨강오탐": red, "노랑": yellow, "칸수": len(R), "상태분포": dist,
            "출처일치": src_hit, "출처확인": src_all, "초": round(secs, 2)}


def batch(n=10, size="보통", errors=10, seed0=None, out_root=None, keep=False, progress=None):
    from app.parts.mockdata.scenario import Scenario
    import random
    out_root = out_root or tempfile.mkdtemp(prefix="평가_")
    seed0 = int(seed0) if seed0 else random.randint(1000, 90000)
    results = []
    for i in range(int(n)):
        s = Scenario(out_root, seed=seed0 + i, size=size, errors=errors, gongmun=keep, guides=keep, form=keep,
                     resubmit=keep).run()
        r = score(s["folder"])
        results.append(r)
        if progress:
            progress(i + 1, n, r)
    by = {}
    for r in results:
        for row in r["항목"]:
            if row["정상"] or row["연쇄"]:
                continue
            k = row["구분"]
            d = by.setdefault(k, [0, 0])
            d[1] += 1
            d[0] += 1 if row["ok"] else 0
    tot_e = sum(r["오류_전체"] for r in results)
    tot_ok = sum(r["오류_맞음"] for r in results)
    return {"시나리오수": len(results), "씨앗값": [seed0, seed0 + int(n) - 1], "크기": size, "오류수": errors,
            "검출": tot_ok, "심은오류": tot_e, "검출률": round(tot_ok / tot_e * 100, 1) if tot_e else None,
            "정상맞음": sum(r["정상_맞음"] for r in results), "정상전체": sum(r["정상_전체"] for r in results),
            "빨강오탐": sum(len(r["빨강오탐"]) for r in results), "노랑": sum(len(r["노랑"]) for r in results),
            "칸수": sum(r["칸수"] for r in results),
            "출처일치": sum(r["출처일치"] for r in results), "출처확인": sum(r["출처확인"] for r in results),
            "종류별": {k: {"검출": v[0], "전체": v[1], "검출률": round(v[0] / v[1] * 100, 1)} for k, v in sorted(by.items())},
            "평균초": round(sum(r["초"] for r in results) / max(1, len(results)), 2),
            "결과": results, "폴더": out_root}


def report_md(b):
    L = [f"# 자동 평가 보고 — 무작위 시나리오 {b['시나리오수']}개", "",
         f"- 씨앗값 {b['씨앗값'][0]}~{b['씨앗값'][1]} · 크기 {b['크기']} · 시나리오마다 오류 {b['오류수']}개 목표",
         f"- 검사한 칸 {b['칸수']:,}개, 시나리오당 검증 시간 평균 {b['평균초']}초", "",
         "| 지표 | 결과 |", "|---|---|",
         f"| 심은 오류 검출 | {b['검출']}/{b['심은오류']} ({b['검출률']}%) |",
         f"| 정상 사례를 정상으로 판정 | {b['정상맞음']}/{b['정상전체']} |",
         f"| 빨강 오탐(정답표에 없는 칸이 불일치·계산오류·충돌) | {b['빨강오탐']}칸 |",
         f"| 노랑(출처 미확인·후보 여러 개, 확인 필요) | {b['노랑']}칸 |",
         f"| 출처 위치 일치(정상 사례) | {b['출처일치']}/{b['출처확인']} |", "",
         "## 오류 종류별 검출", "", "| 종류 | 검출 | 전체 | 검출률 |", "|---|---|---|---|"]
    for k, v in b["종류별"].items():
        L.append(f"| {k} | {v['검출']} | {v['전체']} | {v['검출률']}% |")
    L += ["", "## 놓친 항목·오탐", ""]
    for r in b["결과"]:
        miss = [x for x in r["항목"] if not x["ok"] and not x["연쇄"]]
        if not miss and not r["빨강오탐"]:
            continue
        L.append(f"### {r['시나리오'].get('이름')}")
        for x in miss:
            L.append(f"- 놓침 {x['id']} {x['구분']} · {x.get('위치')} · 엔진 판정 {x['판정']} (기대 {', '.join(x['기대'])})")
        for k, st, lab in r["빨강오탐"]:
            L.append(f"- 빨강 오탐 {lab} → {st}")
    return "\n".join(L) + "\n"
