# -*- coding: utf-8 -*-
"""[재제출 비교 ①] 두 원본(이전·새로 받은 것)의 칸별 차이. 형식이 달라도(xlsx↔ods↔csv↔pdf) 같은 방식으로 비교한다.

flatten(원본)  → {시트이름: {(행, 열): (숫자 또는 None, 글자)}}
diff(이전, 이후) → 바뀐 칸 목록. 행이 끼워지거나 빠진 경우 행 이름(첫 글자 칸)으로 줄을 맞춘 뒤 비교한다.
"""
import difflib

from app.formats.xlsx import ref as a1ref


def flatten(book):
    out = {}
    if book["kind"] == "sheet":
        for sh in book["wb"].sheets:
            cells = {}
            for (r, c), cell in sh.cells.items():
                v = cell.v if cell.kind == "n" and not isinstance(cell.v, bool) else None
                cells[(r, c)] = (v, cell.text if cell.text is not None else str(cell.v))
            out[sh.name] = cells
    else:
        for g in book["grids"]:
            cells = {}
            for (r, c), t in (g.get("texts") or {}).items():
                vd = g["cells"].get((r, c))
                cells[(r, c)] = (vd[0] if vd else None, t)
            for (r, c), vd in g["cells"].items():
                cells.setdefault((r, c), (vd[0], ""))
            out[g["name"]] = cells
    return out


def ref_text(kind, sheet, r, c):
    return f"{sheet}!{a1ref(r, c)}" if kind == "sheet" else f"{sheet} {r + 1}행 {c + 1}열"


def _row_keys(cells):
    """행마다 '행 이름'(그 행의 첫 글자 칸) — 줄 맞추기용."""
    rows = {}
    for (r, c), (v, t) in sorted(cells.items()):
        if v is None and (t or "").strip() and r not in rows:
            rows[r] = t.strip()
    nr = max((r for r, _ in cells), default=-1) + 1
    return [rows.get(r, f"#{r}") for r in range(nr)]


def _align_rows(a, b):
    """이전 행 → 이후 행 대응. 행 수가 같으면 그대로, 다르면 행 이름 순서 맞추기."""
    ka, kb = _row_keys(a), _row_keys(b)
    if len(ka) == len(kb):
        return {r: r for r in range(len(ka))}, [], []
    sm = difflib.SequenceMatcher(None, ka, kb, autojunk=False)
    m, added, removed = {}, [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                m[i1 + k] = j1 + k
        else:
            removed += list(range(i1, i2))
            added += list(range(j1, j2))
    return m, added, removed


def _same(x, y):
    (va, ta), (vb, tb) = x, y
    if va is not None and vb is not None:
        return abs(va - vb) <= 1e-9 * max(1.0, abs(va))
    return (ta or "").strip() == (tb or "").strip()


def diff(old_book, new_book, limit=2000):
    A, B = flatten(old_book), flatten(new_book)
    kind = new_book["kind"]
    if len(A) == 1 and len(B) == 1 and set(A) != set(B):
        # 시트가 하나뿐인 자료(CSV 는 파일 이름이 시트 이름): 이름이 달라도 같은 시트로 본다
        (na, ca), (nb, cb) = next(iter(A.items())), next(iter(B.items()))
        B = {na: cb}
    out = {"changed": [], "added_rows": [], "removed_rows": [], "sheets_added": [], "sheets_removed": []}
    out["sheets_added"] = [s for s in B if s not in A]
    out["sheets_removed"] = [s for s in A if s not in B]
    for name in A:
        if name not in B:
            continue
        a, b = A[name], B[name]
        rmap, added, removed = _align_rows(a, b)
        out["added_rows"] += [{"sheet": name, "row": r + 1} for r in added]
        out["removed_rows"] += [{"sheet": name, "row": r + 1} for r in removed]
        cols = sorted({c for _, c in a} | {c for _, c in b})
        for r_old, r_new in sorted(rmap.items()):
            for c in cols:
                x, y = a.get((r_old, c), (None, "")), b.get((r_new, c), (None, ""))
                if _same(x, y):
                    continue
                if len(out["changed"]) >= limit:
                    out["truncated"] = True
                    return out
                out["changed"].append({"sheet": name, "r_old": r_old, "r": r_new, "c": c,
                                       "ref_old": ref_text(kind, name, r_old, c), "ref": ref_text(kind, name, r_new, c),
                                       "old": x[0], "new": y[0], "old_text": x[1], "new_text": y[1],
                                       "numeric": x[0] is not None or y[0] is not None})
    return out


def similarity(book_a, book_b):
    """두 원본이 '같은 자료의 다른 판'일 가능성(0~1): 시트 이름·글자 칸이 얼마나 겹치나."""
    A, B = flatten(book_a), flatten(book_b)
    names = len(set(A) & set(B)) / max(1, len(set(A) | set(B)))
    ta = {t.strip() for cells in A.values() for v, t in cells.values() if v is None and (t or "").strip()}
    tb = {t.strip() for cells in B.values() for v, t in cells.values() if v is None and (t or "").strip()}
    texts = len(ta & tb) / max(1, len(ta | tb))
    return round(0.3 * names + 0.7 * texts, 3)
