# -*- coding: utf-8 -*-
"""[가상자료 ⑥] 문서 모형(blocks)을 한글(hwpx)·ODT 파일로 그린다.

block 종류
  {"kind": "title" | "center" | "head" | "body" | "note" | "text" | "blank", "text": 글자}
  {"kind": "p", "style": "body"|"head"|"note"|"text", "text": 글자}     ← 오류를 심을 수 있는 문단
  {"kind": "table", "rows": [[글자…]…], "widths": [비율…], "left": (왼쪽 정렬 열…)}
"""
from app.formats.hwpx_build import HwpxBuilder
from app.formats.odt import OdtBuilder


def _text_of(b):
    return b.get("text", "")


def to_hwpx(blocks, path, meta=""):
    h = HwpxBuilder(meta)
    for b in blocks:
        k = b["kind"]
        if k == "p":
            k = b.get("style", "body")
        if k == "title":
            h.title(_text_of(b))
        elif k == "head":
            h.heading(_text_of(b))
        elif k == "body":
            h.body(_text_of(b))
        elif k in ("text", "center"):
            h.text(_text_of(b))
        elif k == "note":
            h.note(_text_of(b))
        elif k == "blank":
            h.blank()
        elif k == "table":
            ncol = max(len(r) for r in b["rows"])
            h.table(b["rows"], widths=b.get("widths") or [3] + [2] * (ncol - 1), left_cols=tuple(b.get("left", ())))
    return h.save(path)


def to_odt(blocks, path, meta=""):
    o = OdtBuilder(meta)
    for b in blocks:
        k = b["kind"]
        if k == "p":
            k = b.get("style", "body")
        if k == "title":
            o.title(_text_of(b))
        elif k == "center":
            o.center(_text_of(b))
        elif k == "head":
            o.heading(_text_of(b))
        elif k in ("body", "text"):
            o.body(_text_of(b))
        elif k == "note":
            o.note(_text_of(b))
        elif k == "blank":
            o.blank()
        elif k == "table":
            o.table([[c.get("t", "") if isinstance(c, dict) else c for c in r] for r in b["rows"]])
    return o.save(path)


def save(blocks, path_no_ext, fmt, meta=""):
    """fmt: "hwpx" | "odt" | "both" → 만든 파일 경로 목록"""
    out = []
    if fmt in ("hwpx", "both"):
        out.append(to_hwpx(blocks, path_no_ext + ".hwpx", meta))
    if fmt in ("odt", "both"):
        out.append(to_odt(blocks, path_no_ext + ".odt", meta))
    return out
