# -*- coding: utf-8 -*-
"""시연 자료 정답표 대비 채점(엔진 단독)."""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.hwpx_io import HwpxDoc, table_grids
from app.core.xlsx_io import read_xlsx
from app.core.matcher import SourceIndex, Verifier

def build_index(root):
    idx = SourceIndex(); names = {}; roles = {}
    sid = 0
    for sub, role in (("01_원본자료", "원본"), ("02_팀제출", "팀제출")):
        for dp, _, fs in sorted(os.walk(os.path.join(root, sub))):
            for f in sorted(fs):
                p = os.path.join(dp, f); sid += 1; s = f"S{sid}"
                names[s] = f; roles[s] = role
                if f.endswith(".xlsx"): idx.add_workbook(s, read_xlsx(p))
                elif f.endswith(".hwpx"): idx.add_grids(s, table_grids(HwpxDoc(p)))
    return idx, names, roles

def find(doc, a):
    if "표" in a:
        for it in doc.items:
            if it.kind == "cell" and it.table == a["표"] and it.rowlab == a["행"] and it.collab.startswith(a["열"]):
                return it
    if "본문" in a:
        for it in doc.items:
            if it.kind == "para" and a["본문"] in (it.context or "") and it.raw == a["문서값"]:
                return it
    return None

def score(demo, stage=1, verbose=True):
    root = os.path.join(demo, "공유폴더(가상)", "2026 행정사무감사")
    with open(os.path.join(demo, "정답표.json"), encoding="utf-8") as f:
        ans = json.load(f)
    t0 = time.time()
    idx, names, roles = build_index(root)
    doc = HwpxDoc(os.path.join(root, "03_취합", "2026_행정사무감사_요구자료_취합본.hwpx"))
    V = Verifier(idx, names, roles)
    out = V.verify(doc)
    dt = time.time() - t0
    R = out["items"]; ok = 0; bad = []
    flagged_keys = set()
    for a in ans["항목"]:
        exp = a.get("단계2기대") if stage == 2 and "단계2기대" in a else a["기대"]
        if "요일" in a:
            hit = any(a["요일"] in t["raw"] for t in out["text_issues"] if t["kind"] == "weekday")
            ok += hit
            if not hit: bad.append((a["id"], "요일 못 찾음"))
            continue
        it = find(doc, a)
        if not it:
            bad.append((a["id"], "칸 못 찾음")); continue
        st = R[it.key]["status"]; flagged_keys.add(it.key)
        if st in exp: ok += 1
        else: bad.append((a["id"], it.key, st, exp, R[it.key].get("opinions"), R[it.key].get("calc")))
    # 정답표에 없는데 빨강·노랑인 칸(오탐)
    noise = [(k, r["status"]) for k, r in R.items() if k not in flagged_keys and r["status"] in ("mismatch", "unit", "calc", "conflict", "unknown", "multi")]
    cnt = {}
    for r in R.values(): cnt[r["status"]] = cnt.get(r["status"], 0) + 1
    if verbose:
        print(f"채점: {ok}/{len(ans['항목'])}  시간 {dt:.2f}s  칸 {len(R)}  상태분포 {cnt}")
        for b in bad: print("  ✗", b)
        print("  정답표 밖 표시:", noise)
        for ti, m in out["tables"].items(): print("  표", ti, [(names[x['sid']], x['sheet'], x['orient'], x['support']) for x in m])
    return ok, len(ans["항목"]), bad, noise, out

if __name__ == "__main__":
    demo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "시연자료")
    score(demo)
