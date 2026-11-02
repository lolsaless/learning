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
import re
import json
import time
import tempfile

from app.formats import registry
from app.formats.hwpx import table_grids
from app.parts.verify.engine import SourceIndex, Verifier
from app.parts.verify.part import apply_claims
from app.parts.ai.part import AiPart, item_spans

RED = ("mismatch", "unit", "calc", "conflict")
YELLOW = ("unknown", "multi", "claim")


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
                if f.startswith(("~$", ".")) or not registry.supported(p):
                    continue
                sid += 1
                s = f"S{sid}"
                names[s], roles[s] = f, role
                kind, obj = registry.read_source(p)
                if kind == "sheet":
                    idx.add_workbook(s, obj)
                else:
                    idx.add_grids(s, table_grids(obj))
    return idx, names, roles


def find_item(doc, a):
    if "표" in a:
        for it in doc.items:
            if it.kind == "cell" and it.table == a["표"] and it.rowlab == a["행"] and (it.collab or "").startswith(a["열"]):
                return it
    if "본문" in a and "앞글자" in a:                # 계산 문장: 결과 숫자 바로 앞 글자로 정확한 위치를 찾는다
        ns = lambda x: re.sub(r"\s+", "", x or "")
        head = ns(a["본문"])[:20]
        for it in doc.items:
            if it.kind == "para" and it.raw == a.get("문서값") and head in ns(it.context):
                b = doc.blocks[it.block]
                for s0, e0, k in item_spans(b):
                    if k == it.key and ns(b["text"][:s0]).endswith(a["앞글자"]):
                        return it
    if "본문" in a:
        for it in doc.items:
            if it.kind == "para" and a["본문"] in (it.context or "") and it.raw == a.get("문서값"):
                return it
    return None


def score(folder, stage=1, ai=None):
    """ai: None 이면 규칙 읽기만, AiPart 를 주면 그 AI 로 문장도 읽는다."""
    key = load_key(folder)
    target = os.path.join(folder, key["대상"])
    base = os.path.dirname(os.path.dirname(target))
    t0 = time.time()
    idx, names, roles = build_index(base)
    doc = registry.open_target(target)
    out = Verifier(idx, names, roles).verify(doc)
    reader = ai or AiPart(settings_path=os.devnull)
    claims = reader.read_doc(doc, use_ai=ai is not None)
    apply_claims(out["items"], claims["claims"])
    secs = time.time() - t0
    R = out["items"]
    rows, seen = [], set()
    src_hit = src_all = 0
    ai_skipped = 0
    for a in key["항목"]:
        exp = a.get("단계2기대") if stage == 2 and "단계2기대" in a else a["기대"]
        if a.get("AI필요") and ai is None:
            ai_skipped += 1                  # 자유 문형은 AI 읽기가 있을 때만 채점
            continue
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
            "출처일치": src_hit, "출처확인": src_all, "초": round(secs, 2), "AI제외": ai_skipped,
            "문장검산": claims["stat"]}


def batch(n=10, size="보통", errors=10, seed0=None, out_root=None, keep=False, progress=None,
          src_mix=False, target_fmt="hwpx", stmt_free=False, ai=None):
    from app.parts.mockdata.scenario import Scenario
    import random
    out_root = out_root or tempfile.mkdtemp(prefix="평가_")
    seed0 = int(seed0) if seed0 else random.randint(1000, 90000)
    results = []
    for i in range(int(n)):
        s = Scenario(out_root, seed=seed0 + i, size=size, errors=errors, gongmun=keep, guides=keep, form=keep,
                     resubmit=keep, src_mix=src_mix, target_fmt=target_fmt, stmt_free=stmt_free).run()
        r = score(s["folder"], ai=ai)
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


def score_resubmit(folder):
    """재제출 비교 채점: 정답표 '재제출'(바뀐 원본 칸·영향받는 취합본 칸)과 비교 결과를 맞춰 본다."""
    from app.parts.compare.part import ComparePart
    key = load_key(folder)
    if not key.get("재제출"):
        return None
    target = os.path.join(folder, key["대상"])
    base = os.path.dirname(os.path.dirname(target))
    idx, names, roles = build_index(base)
    doc = registry.open_target(target)
    out = Verifier(idx, names, roles).verify(doc)
    by_name = {v: k for k, v in names.items()}
    cmp = ComparePart.__new__(ComparePart)          # 보관 폴더 없이 비교 기능만 사용
    rows = []
    for rs in key["재제출"]:
        old, new = os.path.join(folder, rs["원본"]), os.path.join(folder, rs["수정본"])
        d = cmp.compare_paths(old, new)
        sid = by_name.get(os.path.basename(old))
        refs = {}
        for k, r in out["items"].items():
            it = doc.item(k)
            for o in (r.get("opinions") or (r.get("candidates") or [])[:1]):
                if o["sid"] == sid:
                    refs.setdefault(o["ref"], []).append({"key": k, "label": it.label, "raw": it.raw,
                                                          "scale": o.get("scale", 1.0), "dec": it.dec, "comma": it.comma})
        imp = {x["key"]: x for x in cmp.affected(d, refs)}
        got = {f"{c['sheet']}!{c['ref'].split('!')[-1]}" for c in d["changed"] if c["numeric"]}
        want = {f"{c['시트']}!{c['칸']}" for c in rs["변경"]}
        sheet_like = registry.ext_of(new) in (".xlsx", ".xlsm", ".xls", ".ods", ".csv", ".tsv")
        change_ok = (want <= got) if sheet_like and registry.ext_of(new) not in (".csv", ".tsv") else \
            d["numeric_changed"] >= len(want)
        hit = near = 0
        for a in rs["영향"]:
            it = find_item(doc, {"표": a["표"], "행": a["행"], "열": a["열"]})
            x = imp.get(it.key) if it else None
            if x and x["doc_new"] == a["이후표시"]:
                hit += 1
            elif x and x["doc_new"] and not sheet_like:
                # 인쇄 문서(pdf·docx) 원본은 표시 자릿수까지만 알 수 있어 두 번 반올림하면 끝자리 1 차이가 날 수 있음
                d_ = len(a["이후표시"].split(".")[1]) if "." in a["이후표시"] else 0
                f_ = lambda t: float(t.replace(",", ""))
                if abs(f_(x["doc_new"]) - f_(a["이후표시"])) <= 10 ** -d_ + 1e-9:
                    hit += 1
                    near += 1
        rows.append({"원본": os.path.basename(old), "수정본": os.path.basename(new), "형식": registry.ext_of(new),
                     "변경_정답": len(want), "변경_찾음": d["numeric_changed"], "변경_맞음": change_ok,
                     "영향_정답": len(rs["영향"]), "영향_맞음": hit, "끝자리차이": near, "같은이름": rs.get("같은이름")})
    return rows
