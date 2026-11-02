# -*- coding: utf-8 -*-
"""[검증 엔진 ①] 원본 색인: 모든 원본의 숫자 칸을 값 순서로 정렬해 두고, 값으로 후보 칸을 찾는다."""
import bisect

from app import config
from app.common import numbers as N
from app.formats.xlsx import ref as a1ref

AGREE = ("match", "round", "scale")
DISAGREE = ("mismatch", "unit")


class SourceIndex:
    def __init__(self):
        self.groups = {}       # gid -> dict(sid, sheet, kind, cells{(r,c):(v,dec)}, texts{(r,c):str})
        self._built = False
        self._arr = {}

    def add_workbook(self, sid, wb):
        for sh in wb.sheets:
            cells, texts = {}, {}
            for (r, c), cell in sh.cells.items():
                texts[(r, c)] = cell.text
                if cell.kind == "n":
                    cells[(r, c)] = (cell.v, None)
                elif cell.kind == "s":
                    tok = N.parse_cell(cell.text)
                    if tok and tok["unit"] not in ("년",):
                        cells[(r, c)] = (tok["value"], tok["dec"])
            gid = f"{sid}|{sh.name}"
            self.groups[gid] = {"sid": sid, "sheet": sh.name, "kind": "sheet", "cells": cells, "texts": texts,
                                "nrow": sh.maxr + 1, "ncol": sh.maxc + 1}
        self._built = False

    def add_grids(self, sid, grids):
        for g in grids:
            gid = f"{sid}|{g['name']}"
            self.groups[gid] = {"sid": sid, "sheet": g["name"], "kind": "doc", "cells": g["cells"],
                                "texts": g["texts"], "nrow": g["nrow"], "ncol": g["ncol"], "title": g.get("title", "")}
        self._built = False

    def remove_source(self, sid):
        for gid in [g for g, v in self.groups.items() if v["sid"] == sid]:
            del self.groups[gid]
        self._built = False

    def build(self):
        self._arr = {}
        for s, _ in config.UNIT_SCALES:
            rows = []
            for gid, g in self.groups.items():
                for (r, c), (v, d) in g["cells"].items():
                    rows.append((v * s, gid, r, c, v, d))
            rows.sort(key=lambda x: x[0])
            self._arr[s] = ([x[0] for x in rows], rows)
        self._built = True

    def candidates(self, v, dec, limit=4000):
        if not self._built:
            self.build()
        out = []
        t = N.tol(dec)
        for s, _ in config.UNIT_SCALES:
            keys, rows = self._arr[s]
            lo = bisect.bisect_left(keys, v - t - 1e-9 * max(1, abs(v)))
            hi = bisect.bisect_right(keys, v + t + 1e-9 * max(1, abs(v)))
            for x in rows[lo:hi][:limit]:
                sv, gid, r, c, raw, sdec = x
                # 원본도 반올림된 글자(한글 문서)라면 자릿수를 맞춰 비교
                if sdec is not None and sdec < dec:
                    if not N.close(v, sv, sdec):
                        continue
                ex = N.exact(sv, v)
                # 강한 근거: 정확히 같음 / 단위 환산 / 소수 자리 반올림(2.338→2.3)
                # 약한 근거: 소수 값(32.8)을 정수(33)로 반올림해야 맞는 경우 → 우연일 가능성이 큼
                if s < 1.0:
                    strong = abs(raw) >= 1000              # 원→천원 같은 큰 정수 환산
                elif s > 1.0:
                    strong = (s == 1000.0 and abs(raw) >= 1) or (s == 100.0 and abs(raw) <= 1.5 and dec >= 1)
                else:
                    strong = ex or dec > 0
                if not (ex or strong) and s != 1.0:
                    continue                                # 약한 배율 일치는 후보에서 제외

                out.append((gid, r, c, s, strong))
        return out

    def describe(self, gid, r, c):
        g = self.groups[gid]
        if g["kind"] == "sheet":
            return f"{g['sheet']}!{a1ref(r, c)}"
        if g["sheet"] == "본문":
            return f"본문 {r}번째 문단"
        return f"{g['sheet']} {r + 1}행 {c + 1}열"

    def value(self, gid, r, c):
        g = self.groups.get(gid)
        if not g:
            return None
        return g["cells"].get((r, c))

    def text(self, gid, r, c):
        g = self.groups.get(gid)
        return g["texts"].get((r, c), "") if g else ""

    def preview(self, gid, r, c, rad_r=3, rad_c=3):
        """원본 칸 주변 미리보기(격자)."""
        g = self.groups.get(gid)
        if not g:
            return None
        r0, r1 = max(0, r - rad_r), r + rad_r
        c0, c1 = max(0, c - rad_c), c + rad_c
        # 머리글을 보여 주기 위해 위쪽 첫 글자 행도 함께
        grid = []
        for rr in range(r0, r1 + 1):
            grid.append([g["texts"].get((rr, cc), "") for cc in range(c0, c1 + 1)])
        return {"r0": r0, "c0": c0, "grid": grid, "hit": [r - r0, c - c0], "kind": g["kind"], "sheet": g["sheet"],
                "cols": [a1ref(0, cc)[:-1] for cc in range(c0, c1 + 1)] if g["kind"] == "sheet" else [str(cc + 1) for cc in range(c0, c1 + 1)]}


def _relation(index, v, dec, sv, sdec, s):
    """원본 값 sv(배율 s 적용 전)과 문서 값 v의 관계."""
    x = sv * s
    if sdec is not None and sdec < dec:
        same = N.close(v, x, sdec)
    else:
        same = N.close(x, v, dec)
    if same:
        if s != 1.0:
            return "scale"
        return "match" if N.exact(x, v) or sdec is not None else "round"
    for s2, _ in config.UNIT_SCALES:
        # 0(또는 표시 자릿수로 0이 되는 값)은 어떤 값을 줄여도 나오므로 '단위 다름'의 근거가 되지 않는다
        if s2 != s and v != 0 and abs(sv * s2) >= 10 ** -dec and (
                N.close(sv * s2, v, dec)
                # 원본이 반올림된 단위(예: 천원 42,771)이고 문서가 원 단위(42,771,100)를 붙인 경우: 원본 자릿수 기준으로 비교
                or (sdec is not None and s2 > s and N.close(v / s2, sv, sdec))):
            return "unit"
    return "mismatch"


def scale_label(s):
    for s2, lab in config.UNIT_SCALES:
        if s2 == s:
            return lab
    return f"×{s}"

