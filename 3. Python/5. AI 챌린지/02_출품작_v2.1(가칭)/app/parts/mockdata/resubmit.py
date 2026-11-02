# -*- coding: utf-8 -*-
"""[가상자료 ⑩] 재제출본: 팀이 원본 엑셀을 고쳐 다시 보낸 상황을 만든다(재제출 비교 기능 시험용).

  같은 이름으로 다시 보냄    → 나중에_받은_자료/<원래 이름>
  이름을 바꿔 다시 보냄      → 나중에_받은_자료/<이름>(수정).xlsx
정답: 바뀐 칸(시트·칸·이전·이후)과, 그 칸을 쓰는 취합본 칸(표·행·열·이전 표시·이후 표시).
"""
import copy

from app.formats.xlsx import parse_ref
from app.parts.mockdata.model import fmtd


def _cell(rows, r, c):
    row = rows[r]
    return row[c] if c < len(row) else None


def _val(x):
    return x["v"] if isinstance(x, dict) else x


def make(rng, src, t, tables_order, k=None):
    """src: sources.build_source 결과, t: 그 원본의 DataTable → (수정한 시트, 정답 항목)"""
    sheets = copy.deepcopy(src["sheets"])
    by_name = {s["name"]: s for s in sheets}
    cells = [(rc, ref) for rc, ref in src["cellmap"].items() if rc[0] != t.TOTAL and not (t.ratio and rc[1] == t.ratio[0])]
    k = k or rng.randint(2, 4)
    picked = rng.sample(cells, min(k, len(cells)))
    changes, affected = [], []
    for (r, c), ref in picked:
        sheet, a1 = ref.split("!")
        rr, cc = parse_ref(a1)
        rows = by_name[sheet]["rows"]
        old = _val(_cell(rows, rr, cc))
        if isinstance(old, int):
            new = old + rng.choice([-1, 1]) * max(1, int(abs(old) * rng.uniform(0.03, 0.12)))
        else:
            new = round(old * rng.uniform(1.08, 1.25), 4)
        cell = rows[rr][cc]
        if isinstance(cell, dict):
            cell["v"] = new
        else:
            rows[rr][cc] = new
        changes.append({"시트": sheet, "칸": a1, "이전": old, "이후": new})
        sc = t.src_scale.get(c, 1)
        affected.append({"표": tables_order.index(t.key), "행": r, "열": c, "이전표시": t.cell_text(r, c),
                         "이후표시": fmtd(new / sc, t.dec(r, c))})
    return sheets, {"변경": changes, "영향": affected}
